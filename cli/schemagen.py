"""``./Quickstart schemagen`` — propose a new Pydantic product model from a PDF.

Dry-run by default: prints unified diffs of the new ``models/<type>.py``
file and the ``common.py`` ``ProductType`` literal patch. Pass ``--write``
to commit both edits to disk, then (unless ``--skip-verify``) re-extract
the same PDF through the newly-registered schema to verify end-to-end.

Usage:
    ./Quickstart schemagen <pdf-path> --type <snake_case>
        [--class-name PascalCase]
        [--write]
        [--json-only]
        [--skip-verify]
        [--max-fields N]
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("schemagen")


ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "datasheetminer" / "models"
COMMON_PY = MODELS_DIR / "common.py"


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="schemagen",
        description=(
            "Propose a new Pydantic product model from a PDF datasheet. "
            "Dry-run by default; pass --write to commit."
        ),
    )
    parser.add_argument("pdf_path", help="Path to the datasheet PDF.")
    parser.add_argument(
        "--type",
        dest="product_type",
        required=True,
        help="snake_case product_type identifier (e.g. 'contactor').",
    )
    parser.add_argument(
        "--class-name",
        default=None,
        help="PascalCase class name. Default: derived from --type.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Commit the proposed model + common.py patch to disk.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print the raw ProposedModel JSON and exit (skip rendering).",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="After --write, skip the second Gemini call that re-extracts the PDF.",
    )
    parser.add_argument(
        "--max-fields",
        type=int,
        default=30,
        help="Soft cap on proposed field count (default: 30).",
    )
    return parser.parse_args(argv)


def _derive_class_name(product_type: str) -> str:
    return "".join(part.capitalize() for part in product_type.split("_"))


def _filter_pdf_pages(pdf_bytes: bytes, pages: List[int]) -> bytes:
    """Extract specific 0-indexed pages into a new PDF. Mirrors ``cli/bench.py``."""
    try:
        import fitz
    except ImportError:
        return pdf_bytes

    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    dst = fitz.open()
    for p in sorted(pages):
        if p < len(src):
            dst.insert_pdf(src, from_page=p, to_page=p)
    result = dst.tobytes()
    dst.close()
    src.close()
    return result


def _validate_product_type(product_type: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", product_type):
        sys.exit(
            f"ERROR: --type must be snake_case (lowercase letters, digits, "
            f"underscores; starting with a letter). Got: {product_type!r}"
        )


def _check_registry_warnings(
    pm: Any,
    registry: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Compare proposed fields against the reuse registry, return warnings."""
    warnings: List[str] = []
    for field in pm.fields:
        entry = registry.get(field.name)
        if entry is None:
            continue
        # Same name exists elsewhere. Check kind + unit agree.
        if entry["kind"] != field.kind:
            warnings.append(
                f"Field {field.name!r} proposed with kind={field.kind!r} but "
                f"repo already uses kind={entry['kind']!r} in "
                f"{', '.join(entry['seen_in'])}. Consider matching the "
                f"existing type."
            )
    return warnings


def _print_diff(label: str, old: str, new: str, path: Path) -> None:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    rel = path.relative_to(ROOT) if path.is_absolute() else path
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{rel}",
        tofile=f"b/{rel}",
        n=3,
    )
    diff_text = "".join(diff)
    if not diff_text:
        print(f"(no changes to {rel})")
        return
    print(f"=== {label}: {rel} ===")
    print(diff_text, end="" if diff_text.endswith("\n") else "\n")


def _run_verification(pdf_bytes: bytes, product_type: str, api_key: str) -> None:
    """Call the real extraction path against the newly-registered schema."""
    # Re-import to pick up the newly-added SCHEMA_CHOICES entry.
    import importlib

    import datasheetminer.config as cfg
    import datasheetminer.models as models_pkg

    importlib.reload(models_pkg)  # best-effort; submodules already imported
    importlib.reload(cfg)

    if product_type not in cfg.SCHEMA_CHOICES:
        print(
            f"WARNING: verification skipped — {product_type!r} not in "
            "SCHEMA_CHOICES after reload. Run the CLI in a fresh process to "
            "verify.",
            file=sys.stderr,
        )
        return

    from datasheetminer.llm import generate_content
    from datasheetminer.utils import parse_gemini_response

    print(f"\n=== Verification pass: extracting with new {product_type!r} schema ===")
    try:
        response = generate_content(
            doc_data=pdf_bytes,
            api_key=api_key,
            schema=product_type,
            context=None,
            content_type="pdf",
        )
    except Exception as e:
        print(f"ERROR: verification extraction call failed: {e}", file=sys.stderr)
        return

    schema_type = cfg.SCHEMA_CHOICES[product_type]
    try:
        products = parse_gemini_response(
            response,
            schema_type=schema_type,
            product_type=product_type,
            context={"manufacturer": "UNKNOWN", "product_name": "UNKNOWN"},
        )
    except Exception as e:
        print(f"ERROR: parsing verification response failed: {e}", file=sys.stderr)
        return

    if not products:
        print(
            "WARNING: extraction returned zero products — Gemini may not "
            "have found data matching the proposed schema."
        )
        return

    first = products[0]
    dumped = first.model_dump(mode="json", exclude_none=True)
    print(f"First extracted variant ({len(products)} total):")
    print(json.dumps(dumped, indent=2, default=str))


def main(argv: List[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    _validate_product_type(args.product_type)
    pdf_path = Path(args.pdf_path).resolve()
    if not pdf_path.is_file():
        sys.exit(f"ERROR: PDF not found: {pdf_path}")

    pdf_bytes = pdf_path.read_bytes()
    class_name = args.class_name or _derive_class_name(args.product_type)

    # Import late so argparse --help doesn't require the dependencies.
    from datasheetminer.config import SCHEMA_CHOICES
    from datasheetminer.page_finder import find_spec_pages_by_text
    from datasheetminer.schemagen.llm import propose_model
    from datasheetminer.schemagen.prompt import build_field_registry
    from datasheetminer.schemagen.renderer import (
        render_model_file,
        render_product_type_patch,
    )

    if args.product_type in SCHEMA_CHOICES:
        sys.exit(
            f"ERROR: product_type {args.product_type!r} is already registered "
            "(found in datasheetminer/models/). Pick a different name, or "
            "extend the existing model by hand."
        )

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        sys.exit("ERROR: GEMINI_API_KEY not set. Export it or add it to .env.")

    # Run the standard pre-filter: page_finder narrows the PDF to spec-table
    # pages before anything hits the LLM. Matches cli/bench.py:_run_extraction.
    spec_pages = find_spec_pages_by_text(pdf_bytes)
    if spec_pages:
        filtered_bytes = _filter_pdf_pages(pdf_bytes, spec_pages)
        log.info(
            "page_finder selected %d of %d-byte PDF → %d pages, %d bytes",
            len(spec_pages),
            len(pdf_bytes),
            len(spec_pages),
            len(filtered_bytes),
        )
        pdf_for_llm = filtered_bytes
    else:
        log.warning(
            "page_finder found no spec pages — keyword heuristic may not fit "
            "this product type. Sending full PDF (%d bytes); expect size/token "
            "limits to bite on large catalogs.",
            len(pdf_bytes),
        )
        pdf_for_llm = pdf_bytes

    log.info("Calling Gemini to propose schema for %r...", args.product_type)
    pm = propose_model(
        pdf_bytes=pdf_for_llm,
        product_type=args.product_type,
        api_key=api_key,
        schema_choices=SCHEMA_CHOICES,
        max_fields=args.max_fields,
    )

    # Force consistency: the LLM's product_type MUST match the CLI argument,
    # but we tolerate class_name divergence (CLI override wins).
    if pm.product_type != args.product_type:
        log.warning(
            "Gemini returned product_type=%r, overriding to match --type=%r",
            pm.product_type,
            args.product_type,
        )
        pm = pm.model_copy(update={"product_type": args.product_type})
    if args.class_name and pm.class_name != class_name:
        pm = pm.model_copy(update={"class_name": class_name})

    if args.json_only:
        print(pm.model_dump_json(indent=2))
        return 0

    registry = build_field_registry(SCHEMA_CHOICES)
    warnings = _check_registry_warnings(pm, registry)

    new_model_path = MODELS_DIR / f"{args.product_type}.py"
    new_model_source = render_model_file(pm)

    old_common_source = COMMON_PY.read_text()
    new_common_source = render_product_type_patch(old_common_source, pm)

    _print_diff(
        "New model file",
        "" if not new_model_path.exists() else new_model_path.read_text(),
        new_model_source,
        new_model_path,
    )
    _print_diff("common.py patch", old_common_source, new_common_source, COMMON_PY)

    if warnings:
        print("\n=== Registry reuse warnings ===")
        for w in warnings:
            print(f"- {w}")

    if not args.write:
        print("\n(dry-run — pass --write to commit these edits)")
        return 0

    if new_model_path.exists():
        sys.exit(
            f"ERROR: {new_model_path.relative_to(ROOT)} already exists. "
            "Refusing to overwrite. Delete it first if you want to regenerate."
        )

    # Write common.py first, then the model file last — see plan.
    COMMON_PY.write_text(new_common_source)
    new_model_path.write_text(new_model_source)
    print(f"\nWrote {new_model_path.relative_to(ROOT)}")
    print(f"Patched {COMMON_PY.relative_to(ROOT)}")

    # Auto-discovery smoke test in a fresh subprocess so module caching
    # can't mask a broken registration.
    smoke = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-c",
            (
                "from datasheetminer.config import SCHEMA_CHOICES; "
                f"assert {args.product_type!r} in SCHEMA_CHOICES, "
                f"'{args.product_type} missing from SCHEMA_CHOICES'"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if smoke.returncode != 0:
        print(
            f"\nWARNING: auto-discovery smoke test failed:\n{smoke.stderr}",
            file=sys.stderr,
        )
    else:
        print(f"Auto-discovery confirmed: {args.product_type!r} in SCHEMA_CHOICES")

    if args.skip_verify:
        return 0

    # Verification uses the same pre-filtered bytes so it exercises the
    # same input the proposal saw, not the full catalog.
    _run_verification(pdf_for_llm, args.product_type, api_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
