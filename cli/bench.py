"""
Benchmark runner for the datasheet ingress pipeline.

Measures speed, cost, redundancy, and data quality for a set of
control datasheets against known ground-truth outputs.

Usage:
    ./Quickstart bench                      Page-finding only (no API calls)
    ./Quickstart bench --live               Full pipeline (calls Gemini)
    ./Quickstart bench --filter j5-filtered Run a single fixture
    ./Quickstart bench --update-cache       Run live + save responses to cache
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("bench")

ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = ROOT / "tests" / "benchmark"
FIXTURE_DIR = BENCHMARK_DIR / "datasheets"
EXPECTED_DIR = BENCHMARK_DIR / "expected"
CACHE_DIR = BENCHMARK_DIR / "cache"
OUTPUT_DIR = ROOT / "outputs" / "benchmarks"

# Gemini token pricing (USD per 1M tokens). Update when models change.
# Numbers from ai.google.dev/gemini-api/docs/pricing.
TOKEN_PRICES: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
}


def _load_fixtures(filter_slug: str | None = None) -> list[dict[str, Any]]:
    manifest = BENCHMARK_DIR / "fixtures.json"
    with open(manifest) as f:
        fixtures = json.load(f)
    if filter_slug:
        fixtures = [fx for fx in fixtures if fx["slug"] == filter_slug]
        if not fixtures:
            log.error(f"No fixture matching --filter '{filter_slug}'")
            sys.exit(1)
    return fixtures


def _load_expected(filename: str) -> list[dict[str, Any]]:
    path = EXPECTED_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _load_cached_response(slug: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"{slug}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _save_cached_response(slug: str, data: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{slug}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _benchmark_page_finding(pdf_bytes: bytes) -> dict[str, Any]:
    """Run both old (binary) and new (scored) page detection and return metrics."""
    from datasheetminer.page_finder import (
        find_spec_pages_by_text,
        find_spec_pages_scored,
    )

    try:
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        doc.close()
    except ImportError:
        total_pages = -1

    t0 = time.perf_counter()
    old_pages = find_spec_pages_by_text(pdf_bytes)
    old_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    scored_pages, page_details = find_spec_pages_scored(pdf_bytes)
    scored_ms = (time.perf_counter() - t1) * 1000

    return {
        "total_pages": total_pages,
        "text_heuristic_pages": old_pages,
        "text_heuristic_count": len(old_pages),
        "scored_pages": scored_pages,
        "scored_count": len(scored_pages),
        "page_find_ms": round(old_ms, 1),
        "scored_find_ms": round(scored_ms, 1),
    }


def _filter_pdf_pages(pdf_bytes: bytes, pages: list[int]) -> bytes:
    """Extract specific pages from a PDF and return as new PDF bytes."""
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


def _run_extraction(
    pdf_bytes: bytes,
    fixture: dict[str, Any],
    pages: list[int] | None,
) -> dict[str, Any]:
    """Run Gemini extraction and return metrics + raw response data."""
    from datasheetminer.config import MODEL, SCHEMA_CHOICES
    from datasheetminer.llm import generate_content
    from datasheetminer.utils import parse_gemini_response, validate_api_key

    api_key = validate_api_key(os.environ.get("GEMINI_API_KEY"))
    product_type = fixture["product_type"]
    context = {
        "product_name": fixture.get("product_name"),
        "manufacturer": fixture.get("manufacturer"),
        "product_family": fixture.get("product_family"),
    }

    if pages:
        sent_bytes = _filter_pdf_pages(pdf_bytes, pages)
    else:
        sent_bytes = pdf_bytes

    t0 = time.perf_counter()
    response = generate_content(sent_bytes, api_key, product_type, context, "pdf")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
    output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

    prices = TOKEN_PRICES.get(MODEL, {"input": 0.0, "output": 0.0})
    cost_usd = (
        input_tokens * prices["input"] / 1_000_000
        + output_tokens * prices["output"] / 1_000_000
    )

    raw_text = response.text if hasattr(response, "text") else ""

    parsed = parse_gemini_response(
        response, SCHEMA_CHOICES[product_type], product_type, context
    )
    extracted = [m.model_dump(mode="json") for m in parsed]

    return {
        "model": MODEL,
        "extraction_ms": round(elapsed_ms, 1),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_usd, 6),
        "pdf_bytes_sent": len(sent_bytes),
        "variants_extracted": len(extracted),
        "extracted": extracted,
        "raw_response": raw_text,
    }


def _normalize_value(v: Any) -> Any:
    """Normalize a field value for comparison — handles the ;-separated format."""
    if v is None:
        return None
    if isinstance(v, str) and ";" in v:
        parts = v.split(";", 1)
        try:
            return (float(parts[0]), parts[1].strip().lower())
        except ValueError:
            return v.lower().strip()
    if isinstance(v, dict):
        if "value" in v and "unit" in v:
            return (float(v["value"]), v["unit"].lower())
        if "min" in v and "max" in v and "unit" in v:
            return (float(v["min"]), float(v["max"]), v["unit"].lower())
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return v.lower().strip()
    return v


def _compare_products(
    extracted: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    meta_fields: set[str] | None = None,
) -> dict[str, Any]:
    """Compare extracted vs expected products, returning quality metrics."""
    if meta_fields is None:
        meta_fields = {
            "product_id",
            "product_type",
            "product_name",
            "product_family",
            "manufacturer",
            "PK",
            "SK",
            "datasheet_url",
            "pages",
        }

    if not expected:
        return {
            "status": "no_ground_truth",
            "expected_variants": 0,
            "extracted_variants": len(extracted),
            "fields_checked": 0,
            "fields_match": 0,
            "fields_missing": 0,
            "fields_wrong": 0,
            "fields_extra": 0,
            "precision": None,
            "recall": None,
            "details": [],
        }

    # Match extracted to expected by part_number when possible
    exp_by_pn: dict[str, dict] = {}
    exp_unmatched: list[dict] = []
    for e in expected:
        pn = (e.get("part_number") or "").strip()
        if pn:
            exp_by_pn[pn.lower()] = e
        else:
            exp_unmatched.append(e)

    details: list[dict[str, Any]] = []
    total_checked = 0
    total_match = 0
    total_missing = 0
    total_wrong = 0

    for ext in extracted:
        ext_pn = (ext.get("part_number") or "").strip().lower()
        matched_exp = exp_by_pn.pop(ext_pn, None) if ext_pn else None
        if matched_exp is None and exp_unmatched:
            matched_exp = exp_unmatched.pop(0)

        if matched_exp is None:
            details.append(
                {
                    "part_number": ext.get("part_number"),
                    "status": "extra_variant",
                }
            )
            continue

        field_results: dict[str, str] = {}
        spec_fields = [f for f in matched_exp.keys() if f not in meta_fields]

        for field in spec_fields:
            exp_val = matched_exp.get(field)
            ext_val = ext.get(field)

            if exp_val is None:
                continue

            total_checked += 1
            norm_exp = _normalize_value(exp_val)
            norm_ext = _normalize_value(ext_val)

            if ext_val is None:
                field_results[field] = "missing"
                total_missing += 1
            elif norm_exp == norm_ext:
                field_results[field] = "match"
                total_match += 1
            elif isinstance(norm_exp, tuple) and isinstance(norm_ext, tuple):
                # Numeric with unit — check value within 5% tolerance
                if len(norm_exp) == len(norm_ext) and len(norm_exp) >= 2:
                    vals_close = all(
                        abs(a - b) <= 0.05 * max(abs(a), 1e-9)
                        for a, b in zip(norm_exp[:-1], norm_ext[:-1])
                        if isinstance(a, (int, float)) and isinstance(b, (int, float))
                    )
                    if vals_close:
                        field_results[field] = "match"
                        total_match += 1
                    else:
                        field_results[field] = (
                            f"wrong (got={ext_val}, expected={exp_val})"
                        )
                        total_wrong += 1
                else:
                    field_results[field] = f"wrong (got={ext_val}, expected={exp_val})"
                    total_wrong += 1
            else:
                field_results[field] = f"wrong (got={ext_val}, expected={exp_val})"
                total_wrong += 1

        details.append(
            {
                "part_number": ext.get("part_number"),
                "fields": field_results,
            }
        )

    unmatched_expected = len(exp_by_pn) + len(exp_unmatched)

    precision = (
        total_match / (total_match + total_wrong)
        if (total_match + total_wrong) > 0
        else None
    )
    recall = total_match / total_checked if total_checked > 0 else None

    return {
        "status": "compared",
        "expected_variants": len(expected),
        "extracted_variants": len(extracted),
        "matched_variants": len(extracted)
        - sum(1 for d in details if d.get("status") == "extra_variant"),
        "unmatched_expected": unmatched_expected,
        "fields_checked": total_checked,
        "fields_match": total_match,
        "fields_missing": total_missing,
        "fields_wrong": total_wrong,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "details": details,
    }


def _print_table(results: list[dict[str, Any]]) -> None:
    """Print a compact results table to stderr."""
    header = (
        f"{'Fixture':<28} {'Pages':>6} {'Old':>5} {'New':>5} "
        f"{'Sent KB':>8} {'LLM ms':>8} {'Tokens':>10} {'Cost':>8} {'P/R':>12}"
    )
    print(header, file=sys.stderr)
    print("-" * len(header), file=sys.stderr)

    for r in results:
        slug = r["slug"][:27]
        pf = r.get("page_finding", {})
        total_pages = pf.get("total_pages", "?")
        old_count = pf.get("text_heuristic_count", "?")
        new_count = pf.get("scored_count", "?")

        ext = r.get("extraction", {})
        sent_kb = (
            f"{ext.get('pdf_bytes_sent', 0) / 1024:.0f}"
            if ext.get("pdf_bytes_sent")
            else "-"
        )
        llm_ms = (
            f"{ext.get('extraction_ms', 0):.0f}" if ext.get("extraction_ms") else "-"
        )
        tokens = ext.get("input_tokens", 0) + ext.get("output_tokens", 0)
        tokens_str = f"{tokens:,}" if tokens else "-"
        cost = f"${ext.get('cost_usd', 0):.4f}" if ext.get("cost_usd") else "-"

        q = r.get("quality", {})
        prec = q.get("precision")
        rec = q.get("recall")
        pr_str = (
            f"{prec:.0%}/{rec:.0%}" if prec is not None and rec is not None else "-"
        )

        print(
            f"{slug:<28} {str(total_pages):>6} {str(old_count):>5} {str(new_count):>5} "
            f"{sent_kb:>8} {llm_ms:>8} {tokens_str:>10} {cost:>8} {pr_str:>12}",
            file=sys.stderr,
        )


def run(
    *,
    live: bool = False,
    filter_slug: str | None = None,
    update_cache: bool = False,
) -> list[dict[str, Any]]:
    """Run benchmarks and return results list."""
    fixtures = _load_fixtures(filter_slug)
    results: list[dict[str, Any]] = []

    for fixture in fixtures:
        slug = fixture["slug"]
        pdf_path = FIXTURE_DIR / fixture["pdf"]
        if not pdf_path.exists():
            log.warning(f"Skipping {slug}: {pdf_path} not found")
            continue

        log.info(f"Benchmarking: {slug}")
        pdf_bytes = pdf_path.read_bytes()
        result: dict[str, Any] = {
            "slug": slug,
            "pdf": fixture["pdf"],
            "product_type": fixture["product_type"],
            "pdf_bytes_total": len(pdf_bytes),
        }

        # Phase 1: page finding (always runs, no API call)
        pf = _benchmark_page_finding(pdf_bytes)
        result["page_finding"] = pf
        spec_pages = (
            pf["scored_pages"] if pf.get("scored_pages") else pf["text_heuristic_pages"]
        )
        redundancy = (
            1.0 - (len(spec_pages) / pf["total_pages"])
            if pf["total_pages"] > 0
            else 0.0
        )
        result["redundancy_ratio"] = round(redundancy, 4)

        # Phase 2: LLM extraction
        extraction: dict[str, Any] = {}
        if live:
            try:
                extraction = _run_extraction(pdf_bytes, fixture, spec_pages or None)
                if update_cache:
                    _save_cached_response(
                        slug,
                        {
                            "extracted": extraction["extracted"],
                            "raw_response": extraction.get("raw_response", ""),
                            "input_tokens": extraction["input_tokens"],
                            "output_tokens": extraction["output_tokens"],
                            "model": extraction["model"],
                        },
                    )
            except Exception as e:
                log.error(f"Extraction failed for {slug}: {e}")
                extraction = {"error": str(e)}
        else:
            cached = _load_cached_response(slug)
            if cached:
                extraction = {
                    "from_cache": True,
                    "variants_extracted": len(cached.get("extracted", [])),
                    "extracted": cached.get("extracted", []),
                    "input_tokens": cached.get("input_tokens", 0),
                    "output_tokens": cached.get("output_tokens", 0),
                    "model": cached.get("model", "unknown"),
                }

        result["extraction"] = extraction

        # Phase 3: quality comparison
        expected = _load_expected(fixture.get("expected", f"{slug}.json"))
        extracted = extraction.get("extracted", [])
        if extracted:
            result["quality"] = _compare_products(extracted, expected)
        elif expected:
            result["quality"] = {
                "status": "no_extraction",
                "expected_variants": len(expected),
                "extracted_variants": 0,
            }
        else:
            result["quality"] = {"status": "no_ground_truth"}

        results.append(result)

    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="bench",
        description="Benchmark the datasheet ingress pipeline.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live Gemini extraction (requires GEMINI_API_KEY)",
    )
    parser.add_argument(
        "--filter",
        dest="filter_slug",
        default=None,
        help="Run only the fixture matching this slug",
    )
    parser.add_argument(
        "--update-cache",
        action="store_true",
        help="Save live extraction responses to cache for future offline runs",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Write results to a specific JSON file",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    results = run(
        live=args.live,
        filter_slug=args.filter_slug,
        update_cache=args.update_cache,
    )

    _print_table(results)

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = args.output or OUTPUT_DIR / f"{ts}.json"
    latest_path = OUTPUT_DIR / "latest.json"

    report = {
        "timestamp": ts,
        "live": args.live,
        "fixtures": results,
    }
    output_path.write_text(json.dumps(report, indent=2, default=str))
    latest_path.write_text(json.dumps(report, indent=2, default=str))

    log.info(f"Results written to {output_path}")
    log.info(f"Latest symlink: {latest_path}")

    # Exit non-zero if any extraction errored
    if any(r.get("extraction", {}).get("error") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
