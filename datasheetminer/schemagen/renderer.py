"""Deterministic Python-source rendering from a ``ProposedModel``.

Two pure functions:

- ``render_model_file(pm)`` — returns the full contents of a new
  ``datasheetminer/models/<type>.py`` file.
- ``render_product_type_patch(old_common_py_source, pm)`` — returns
  a new ``common.py`` source string with the new ``product_type`` appended
  to the ``ProductType = Literal[...]`` line. Idempotent: patching twice
  yields the same result as patching once.

The output of ``render_model_file`` is passed through ``ast.parse`` before
any caller writes it to disk — if we emit something that doesn't parse,
we want to fail before touching the repo.
"""

from __future__ import annotations

import ast
import re
from typing import List

from datasheetminer.schemagen.meta_schema import ProposedField, ProposedModel


# Map ``ProposedField.kind`` → Python type annotation string. ``literal``
# is handled specially because it needs ``literal_values``.
_KIND_TO_ANNOTATION: dict[str, str] = {
    "int": "Optional[int]",
    "float": "Optional[float]",
    "str": "Optional[str]",
    "bool": "Optional[bool]",
    "list_str": "Optional[List[str]]",
    "value_unit": "Optional[ValueUnit]",
    "min_max_unit": "Optional[MinMaxUnit]",
}

# Kinds that need importing from ``datasheetminer.models.common``.
_COMMON_KINDS: frozenset[str] = frozenset({"value_unit", "min_max_unit"})

# Kinds that need ``List`` from typing.
_LIST_KINDS: frozenset[str] = frozenset({"list_str"})


def _annotation_for(field: ProposedField) -> str:
    if field.kind == "literal":
        # ``literal_values`` guaranteed non-empty by ProposedField validator.
        values = ", ".join(repr(v) for v in field.literal_values or [])
        return f"Optional[Literal[{values}]]"
    return _KIND_TO_ANNOTATION[field.kind]


def _field_line(field: ProposedField) -> str:
    annotation = _annotation_for(field)
    return (
        f"    {field.name}: {annotation} = "
        f"Field(None, description={field.description!r})"
    )


def _build_imports(pm: ProposedModel) -> List[str]:
    """Compute the set of imports needed for the rendered class."""
    kinds = {f.kind for f in pm.fields}
    has_literal_field = "literal" in kinds or bool(pm.subtype_values)
    has_list = bool(_LIST_KINDS & kinds)
    has_common = bool(_COMMON_KINDS & kinds)

    typing_imports: List[str] = ["Optional"]
    if has_list:
        typing_imports.append("List")
    if has_literal_field:
        typing_imports.append("Literal")
    typing_imports.sort()

    lines: List[str] = [
        "from __future__ import annotations",
        "",
        f"from typing import {', '.join(typing_imports)}",
        "",
        "from pydantic import Field",
        "",
    ]
    if has_common:
        common_imports = sorted(
            {
                "ValueUnit" if "value_unit" in kinds else None,
                "MinMaxUnit" if "min_max_unit" in kinds else None,
            }
            - {None}
        )
        # type: ignore[arg-type]  (the None filter keeps mypy happy at runtime)
        lines.append(
            "from datasheetminer.models.common import "
            + ", ".join(str(name) for name in common_imports)
        )
    lines.append("from datasheetminer.models.product import ProductBase")
    return lines


def _build_class_body(pm: ProposedModel) -> List[str]:
    lines: List[str] = [
        f"class {pm.class_name}(ProductBase):",
        f'    """{pm.docstring}"""',
        "",
        f"    product_type: Literal[{pm.product_type!r}] = {pm.product_type!r}",
    ]
    if pm.subtype_values:
        values = ", ".join(repr(v) for v in pm.subtype_values)
        lines.append(f"    type: Optional[Literal[{values}]] = None")
    # Auto-render a default `series` line only if the LLM didn't already
    # propose one — otherwise we'd emit the field twice.
    llm_proposed_series = any(f.name == "series" for f in pm.fields)
    if not llm_proposed_series:
        lines.append("    series: Optional[str] = None")

    current_section: str | None = None
    for field in pm.fields:
        if field.section and field.section != current_section:
            lines.append("")
            lines.append(f"    # --- {field.section} ---")
            current_section = field.section
        lines.append(_field_line(field))
    return lines


def render_model_file(pm: ProposedModel) -> str:
    """Render the full source of a new ``datasheetminer/models/<type>.py``.

    Raises ``SyntaxError`` if the generated source fails to parse — this is
    a last-line-of-defense check against a renderer bug; under normal
    operation the output always parses because only validated tokens
    (names, repr'd strings, dispatch-table annotations) reach the output.
    """
    import_lines = _build_imports(pm)
    class_lines = _build_class_body(pm)
    source = "\n".join(import_lines + ["", ""] + class_lines) + "\n"
    # Smoke-test parseability. Raises SyntaxError on failure.
    ast.parse(source)
    return source


# ---------------------------------------------------------------------
# ``common.py`` ProductType Literal patcher
# ---------------------------------------------------------------------

# Matches:   ProductType = Literal["motor", "drive", ...]
# Tolerates single- or double-quoted entries, multi-line declarations, and
# trailing commas. We capture the inside of the brackets so we can parse
# the existing values via ast and re-render them deterministically.
_PRODUCT_TYPE_RE = re.compile(
    r"^(?P<prefix>ProductType\s*=\s*Literal\[)(?P<body>.*?)(?P<suffix>\])\s*$",
    re.MULTILINE | re.DOTALL,
)


def render_product_type_patch(old_source: str, pm: ProposedModel) -> str:
    """Return ``old_source`` with ``pm.product_type`` added to ``ProductType``.

    Idempotent: if ``pm.product_type`` is already present, returns
    ``old_source`` unchanged. Raises ``ValueError`` if the ``ProductType =
    Literal[...]`` declaration can't be located.
    """
    match = _PRODUCT_TYPE_RE.search(old_source)
    if not match:
        raise ValueError(
            "Could not find 'ProductType = Literal[...]' declaration in "
            "common.py source. Refusing to patch."
        )

    body = match.group("body")
    # Parse the existing values via ast to avoid fragile string parsing.
    try:
        parsed = ast.literal_eval(f"[{body}]")
    except (SyntaxError, ValueError) as e:
        raise ValueError(
            f"Failed to parse existing ProductType values: {e!r}. "
            "Refusing to patch common.py."
        ) from e

    if not isinstance(parsed, list) or not all(isinstance(v, str) for v in parsed):
        raise ValueError(
            "ProductType declaration doesn't parse as a list of strings; "
            "refusing to patch."
        )

    if pm.product_type in parsed:
        return old_source  # idempotent

    new_values = parsed + [pm.product_type]
    new_body = ", ".join(repr(v) for v in new_values)
    start, end = match.span("body")
    return old_source[:start] + new_body + old_source[end:]
