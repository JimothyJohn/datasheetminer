#!/usr/bin/env python3
"""Inspect a single datasheet end-to-end without touching the database.

Runs the standard pipeline (download → page_finder → Gemini → Pydantic
parse) and dumps every artifact to ``outputs/inspect/<slug>/`` so you
can manually compare the source PDF, what page_finder picked, what
Gemini returned, and what survived validation.

Use this when an ingest run reports a quality_fail or extract_fail and
you want to decide whether the catalog is broken or our pipeline is.

Usage:
    source .env && ./Quickstart inspect <url> --type <product_type> [options]

Options:
    --type TYPE                Required. Pydantic product type (motor, drive,
                               electric_cylinder, linear_actuator, ...).
    --manufacturer NAME        Optional context for the LLM.
    --product-name NAME        Optional context for the LLM.
    --product-family NAME      Optional context for the LLM.
    --pages 3,4,5              Comma-separated 1-indexed page list. Skips
                               page_finder when set.
    --out DIR                  Override output directory.
                               Default: outputs/inspect/<sha16-of-url>/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

from specodex.config import SCHEMA_CHOICES
from specodex.llm import generate_content
from specodex.page_finder import find_spec_pages_by_text
from specodex.utils import (
    UUIDEncoder,
    get_document,
    get_web_content,
    is_pdf_url,
    parse_gemini_response,
    validate_api_key,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("inspect")


def _slug_for_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _token_counts(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return 0, 0

    def _i(v: Any) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    return (
        _i(getattr(usage, "prompt_token_count", 0)),
        _i(getattr(usage, "candidates_token_count", 0)),
    )


def _raw_text(response: Any) -> str:
    if response and hasattr(response, "text") and response.text:
        return response.text  # type: ignore[no-any-return]
    return ""


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Datasheet URL (PDF or HTML).")
    parser.add_argument(
        "--type",
        required=True,
        choices=sorted(SCHEMA_CHOICES.keys()),
        help="Pydantic product type to validate against.",
    )
    parser.add_argument("--manufacturer", default="UNKNOWN")
    parser.add_argument("--product-name", default="UNKNOWN")
    parser.add_argument("--product-family", default=None)
    parser.add_argument(
        "--pages",
        default=None,
        help="Comma-separated 1-indexed page list (skips page_finder).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Override output directory. Default: outputs/inspect/<sha16>/",
    )
    args = parser.parse_args(argv)

    api_key = validate_api_key(os.environ.get("GEMINI_API_KEY"))
    out_dir = args.out or (Path("outputs/inspect") / _slug_for_url(args.url))
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("Inspection output → %s", out_dir)

    is_pdf = is_pdf_url(args.url)
    content_type = "pdf" if is_pdf else "html"

    # 1. Download
    if is_pdf:
        source = get_document(args.url)
        if source is None:
            (out_dir / "error.txt").write_text("pdf_download_failed", encoding="utf-8")
            log.error("PDF download failed.")
            return 2
        (out_dir / "datasheet.pdf").write_bytes(source)
    else:
        source = get_web_content(args.url)
        if source is None:
            (out_dir / "error.txt").write_text("html_download_failed", encoding="utf-8")
            log.error("HTML download failed.")
            return 2
        (out_dir / "datasheet.html").write_text(source, encoding="utf-8")

    # 2. Page finder
    pages_0idx: List[int] = []
    page_finder_method = "explicit" if args.pages else "text_keyword"
    if args.pages:
        pages_0idx = [int(p) - 1 for p in args.pages.split(",") if p.strip()]
    elif is_pdf:
        pages_0idx = find_spec_pages_by_text(source) or []
    (out_dir / "page_finder.json").write_text(
        json.dumps(
            {
                "method": page_finder_method,
                "pages_1idx": [p + 1 for p in pages_0idx],
                "pages_0idx": pages_0idx,
                "total_pages_input": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info(
        "page_finder: %d page(s) -> %s", len(pages_0idx), [p + 1 for p in pages_0idx]
    )

    # 3. Gemini call
    # Use bundled extraction (single LLM call) for transparency — easier to
    # diff one response than N per-page responses. Limited to the pages we
    # picked; if no pages found and it's a PDF, just send the whole thing.
    if is_pdf and pages_0idx:
        from specodex.scraper import _extract_bundled_pdf

        doc_data: Any = _extract_bundled_pdf(source, pages_0idx)
    else:
        doc_data = source

    context = {
        "manufacturer": args.manufacturer,
        "product_name": args.product_name,
        "product_family": args.product_family or args.product_name,
        "datasheet_url": args.url,
        "pages": [p + 1 for p in pages_0idx] if pages_0idx else None,
    }

    log.info("Calling Gemini (product_type=%s)...", args.type)
    response = generate_content(doc_data, api_key, args.type, context, content_type)

    raw = _raw_text(response)
    (out_dir / "gemini_response.json").write_text(raw, encoding="utf-8")
    inp_tokens, out_tokens = _token_counts(response)
    log.info("Gemini tokens: input=%d output=%d", inp_tokens, out_tokens)

    # 4. Pydantic parse
    validation_errors: List[str] = []
    parsed_models: List[Any] = []
    try:
        parsed_models = parse_gemini_response(
            response, SCHEMA_CHOICES[args.type], args.type, context
        )
    except Exception as exc:
        validation_errors.append(f"parse_gemini_response raised: {exc}")
        log.error("parse_gemini_response failed: %s", exc)

    parsed_payload = [m.model_dump(mode="json") for m in parsed_models]
    (out_dir / "parsed.json").write_text(
        json.dumps(parsed_payload, indent=2, cls=UUIDEncoder), encoding="utf-8"
    )

    # parse_gemini_response logs per-row failures via logger.error but doesn't
    # surface them — re-validate row-by-row to capture error text for the dump.
    try:
        raw_payload = json.loads(raw) if raw else []
        if isinstance(raw_payload, dict):
            raw_items = [raw_payload]
        elif isinstance(raw_payload, list):
            raw_items = raw_payload
        else:
            raw_items = []
        model_class = SCHEMA_CHOICES[args.type]
        for idx, item in enumerate(raw_items):
            if not isinstance(item, dict):
                validation_errors.append(
                    f"row {idx}: not an object ({type(item).__name__})"
                )
                continue
            full = dict(item)
            full.setdefault("manufacturer", context["manufacturer"])
            full.setdefault("product_name", context["product_name"])
            full.setdefault("product_type", args.type)
            try:
                model_class.model_validate(full)
            except Exception as exc:
                pn = item.get("part_number") or item.get("product_name") or f"row{idx}"
                validation_errors.append(f"{pn}: {exc}")
    except Exception as exc:
        validation_errors.append(f"could not re-validate raw payload: {exc}")

    (out_dir / "validation_errors.txt").write_text(
        "\n\n".join(validation_errors) if validation_errors else "(none)\n",
        encoding="utf-8",
    )

    # 5. Summary
    summary = {
        "url": args.url,
        "product_type": args.type,
        "manufacturer": args.manufacturer,
        "product_name": args.product_name,
        "content_type": content_type,
        "pages_used_1idx": [p + 1 for p in pages_0idx],
        "page_finder_method": page_finder_method,
        "gemini_input_tokens": inp_tokens,
        "gemini_output_tokens": out_tokens,
        "rows_in_response": len(json.loads(raw))
        if raw and raw.strip().startswith("[")
        else None,
        "rows_validated": len(parsed_models),
        "rows_with_errors": len(validation_errors),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print(json.dumps(summary, indent=2))
    print(f"\nArtifacts: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
