"""Prompt + field-reuse-registry builder for the schemagen Gemini call.

Everything here is read-only over ``SCHEMA_CHOICES`` — we reflect over
the existing product models to generate examples and the canonical-field
registry the LLM uses to stay consistent with existing naming.
"""

from __future__ import annotations

import typing
from typing import Any, Dict, List, Optional, Type, get_args, get_origin

from pydantic import BaseModel

from datasheetminer.models.common import MinMaxUnit, ValueUnit
from datasheetminer.models.product import ProductBase
from datasheetminer.schemagen.meta_schema import RESERVED_FIELD_NAMES


# Canonical units, pulled from the csv_schema.py legacy reference. Kept
# here so the system prompt can list them without depending on that file
# (which is on its way out — see the plan).
CANONICAL_UNITS: List[str] = [
    "V",
    "A",
    "W",
    "Nm",
    "mNm",
    "rpm",
    "kg",
    "g",
    "mm",
    "N",
    "mH",
    "ohm",
    "kgcm²",
    "°C",
    "Hz",
    "dB",
    "arcmin",
    "h",
    "mm/s",
    "mm/rev",
    "USD",
    "years",
    "V/krpm",
    "Nm/A",
    "Nm/arcmin",
]


def _annotation_str(annotation: Any) -> str:
    """Best-effort stringification of a Pydantic field annotation."""
    # Strip Optional[...] wrapping for readability.
    origin = get_origin(annotation)
    if origin is typing.Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            inner = _annotation_str(args[0])
            return f"Optional[{inner}]"
    # ValueUnit / MinMaxUnit are Annotated[...] aliases — their repr is
    # long and unhelpful. Special-case by identity.
    if annotation is ValueUnit:
        return "ValueUnit"
    if annotation is MinMaxUnit:
        return "MinMaxUnit"
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation)


def _classify_kind(annotation: Any) -> str:
    """Coarse classification of a field's annotation → ProposedField.kind.

    Returns one of the kind literals, or ``"other"`` for annotations that
    don't map cleanly (nested BaseModels, tuples, etc.). Used only for
    building the registry summary — the actual rendering is driven by
    the LLM's response, not this function.
    """
    origin = get_origin(annotation)
    if origin is typing.Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _classify_kind(args[0])
        return "other"
    if annotation is ValueUnit:
        return "value_unit"
    if annotation is MinMaxUnit:
        return "min_max_unit"
    if annotation is int:
        return "int"
    if annotation is float:
        return "float"
    if annotation is str:
        return "str"
    if annotation is bool:
        return "bool"
    if origin is list:
        args = get_args(annotation)
        if args and args[0] is str:
            return "list_str"
        return "other"
    if origin is typing.Literal:
        return "literal"
    return "other"


def build_field_registry(
    schema_choices: Dict[str, Type[ProductBase]],
) -> Dict[str, Dict[str, Any]]:
    """Reflect over existing models to build the canonical-field registry.

    Keys are field names. Values are ``{"kind", "annotation", "seen_in"}``,
    where ``seen_in`` is the list of class names that define the field.
    Only fields NOT in ``RESERVED_FIELD_NAMES`` are included — base-class
    fields are uninteresting for reuse.
    """
    registry: Dict[str, Dict[str, Any]] = {}
    for class_obj in schema_choices.values():
        if not issubclass(class_obj, BaseModel):
            continue
        for field_name, field_info in class_obj.model_fields.items():
            if field_name in RESERVED_FIELD_NAMES:
                continue
            kind = _classify_kind(field_info.annotation)
            entry = registry.setdefault(
                field_name,
                {
                    "kind": kind,
                    "annotation": _annotation_str(field_info.annotation),
                    "seen_in": [],
                },
            )
            if class_obj.__name__ not in entry["seen_in"]:
                entry["seen_in"].append(class_obj.__name__)
    return registry


def format_registry_for_prompt(registry: Dict[str, Dict[str, Any]]) -> str:
    """Format the registry as a compact text block for the system prompt."""
    lines: List[str] = []
    for name in sorted(registry):
        entry = registry[name]
        seen = ", ".join(entry["seen_in"])
        lines.append(
            f"- {name}: {entry['kind']} ({entry['annotation']})  — seen in: {seen}"
        )
    return "\n".join(lines)


def _example_for_class(class_obj: Type[ProductBase]) -> Dict[str, Any]:
    """Render an existing class as a compact ProposedModel-shaped dict.

    Used as an in-prompt example. We only surface the top-level shape —
    fields whose annotation doesn't classify cleanly are skipped.
    """
    fields_example: List[Dict[str, Any]] = []
    subtype_values: Optional[List[str]] = None
    for field_name, field_info in class_obj.model_fields.items():
        if field_name in RESERVED_FIELD_NAMES:
            continue
        if field_name == "series":
            # Rendered automatically — not a proposed field.
            continue
        kind = _classify_kind(field_info.annotation)
        if kind == "other":
            continue
        entry: Dict[str, Any] = {
            "name": field_name,
            "kind": kind,
            "description": field_info.description or f"{field_name} of the product",
        }
        if kind == "literal":
            # Extract the enum values.
            origin_args = get_args(field_info.annotation)
            literal_args: List[str] = []
            for arg in origin_args:
                if get_origin(arg) is typing.Literal:
                    literal_args = [v for v in get_args(arg) if isinstance(v, str)]
                    break
                if arg is type(None):
                    continue
            if literal_args:
                entry["literal_values"] = literal_args
            else:
                continue  # skip fields we can't reconstruct
        fields_example.append(entry)

    # Pull subtype_values from the ``type`` field if it's a Literal.
    type_field = class_obj.model_fields.get("type")
    if type_field is not None:
        origin_args = get_args(type_field.annotation)
        for arg in origin_args:
            if get_origin(arg) is typing.Literal:
                vals = [v for v in get_args(arg) if isinstance(v, str)]
                if vals:
                    subtype_values = vals
                break

    return {
        "class_name": class_obj.__name__,
        "product_type": class_obj.model_fields["product_type"].default,
        "docstring": (class_obj.__doc__ or "").strip().splitlines()[0]
        if class_obj.__doc__
        else "",
        "subtype_values": subtype_values,
        "fields": fields_example[:12],  # cap to keep the prompt short
    }


def build_examples(
    schema_choices: Dict[str, Type[ProductBase]],
) -> List[Dict[str, Any]]:
    """Build 2–3 in-prompt examples reflected from existing models.

    Prefers Motor (has subtype_values), Drive, and ElectricCylinder for
    variety. Falls back to whatever is available.
    """
    preferred = ["motor", "drive", "electric_cylinder"]
    out: List[Dict[str, Any]] = []
    for key in preferred:
        if key in schema_choices:
            out.append(_example_for_class(schema_choices[key]))
    if not out:
        # Fallback: first three available.
        for class_obj in list(schema_choices.values())[:3]:
            out.append(_example_for_class(class_obj))
    return out


def build_system_prompt(
    schema_choices: Dict[str, Type[ProductBase]],
) -> str:
    """Assemble the full system prompt."""
    import json as _json

    registry = build_field_registry(schema_choices)
    registry_block = format_registry_for_prompt(registry)
    examples = build_examples(schema_choices)
    examples_block = _json.dumps(examples, indent=2)
    units_block = ", ".join(CANONICAL_UNITS)
    reserved_block = ", ".join(sorted(RESERVED_FIELD_NAMES))

    return (
        "You are a senior industrial-automation engineer helping maintain a "
        "Pydantic model catalog for an industrial-product datasheet extractor. "
        "When given a PDF datasheet for a product type the repo doesn't yet "
        "support, propose a new Pydantic model by returning a ProposedModel "
        "object.\n\n"
        "NAMING CONVENTIONS (strict):\n"
        "- Field names are snake_case.\n"
        "- Numeric-with-unit specs use kind='value_unit' (single value) or "
        "'min_max_unit' (range). Pick the canonical unit from this list: "
        f"{units_block}.\n"
        "- Prefer prefixes: rated_*, max_*, peak_*, continuous_*, nominal_*.\n"
        "- Closed enumerations (under 12 values) use kind='literal' with "
        "literal_values.\n"
        "- Open-ended tag lists (certifications, approvals, modes) use "
        "kind='list_str'.\n"
        "- Never propose any of these reserved names (they are inherited "
        f"from ProductBase): {reserved_block}.\n"
        "- The conventional subtype discriminator field is 'type' — DO NOT "
        "propose it as a regular field. Instead, populate "
        "ProposedModel.subtype_values when the datasheet covers multiple "
        "sub-variants of the same supertype (e.g. magnetic vs solid-state "
        "contactors). Leave subtype_values null when there is only one "
        "variant.\n\n"
        "CANONICAL FIELD REGISTRY — reuse these exact names (with the same "
        "kind and unit) when the same concept appears in your datasheet. "
        "Populate ProposedField.reused_from with the classes you're reusing "
        "from:\n"
        f"{registry_block}\n\n"
        "THREE EXAMPLES of the ProposedModel shape — match this structure "
        "exactly:\n"
        f"{examples_block}\n\n"
        "QUALITY RULES:\n"
        "- Only propose fields you can actually find in the datasheet. Do "
        "NOT invent specs that aren't documented.\n"
        "- Every field needs a one-line description.\n"
        "- Group fields semantically and set 'section' on the first field "
        "of each group (e.g. 'Electrical', 'Mechanical', 'Environmental').\n"
        "- Target 15–30 fields total. Bias toward completeness within the "
        "datasheet, not toward breadth of speculation."
    )


def build_user_prompt(product_type: str, max_fields: int) -> str:
    """Per-call user instruction. The PDF itself is attached separately."""
    return (
        f"Propose a Pydantic model named after the product_type='{product_type}'. "
        "Extract every distinct specification documented in the attached "
        "datasheet. When the datasheet covers multiple sub-variants of the "
        "same supertype, populate subtype_values — do not model them as "
        "separate classes.\n\n"
        f"Soft cap: {max_fields} fields. Prefer reusing canonical field "
        "names from the registry when the same concept appears.\n\n"
        "Return exactly one ProposedModel via the propose_model tool."
    )
