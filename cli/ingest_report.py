"""Produce vendor-outreach reports from the ingest log.

Reads ``INGEST#`` records written by ``scraper.process_datasheet`` and
groups quality-fail entries by manufacturer so the user can paste the
output into an email to the vendor asking for the missing specs.

Usage (via Quickstart):
    ./Quickstart ingest-report
    ./Quickstart ingest-report --manufacturer Tolomatic
    ./Quickstart ingest-report --format json
    ./Quickstart ingest-report --email-template --manufacturer Tolomatic

Flags:
    --manufacturer  Exact-match filter on the ``manufacturer`` attr.
    --status        Filter by log status (default: quality_fail).
                    Use ``all`` to include success/extract_fail too.
    --since         ISO-8601 timestamp; only attempts at/after this time.
    --format        markdown | json | csv (default: markdown).
    --email-template Emit a ready-to-send vendor email body per
                    manufacturer instead of the diagnostic report.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import sys
from collections import defaultdict
from typing import Any, Dict, Iterable, List

from specodex.db.dynamo import DynamoDBClient
from specodex.ingest_log import STATUS_QUALITY_FAIL

logger: logging.Logger = logging.getLogger("ingest-report")


# ---------------------------------------------------------------------------
# Grouping / dedup
# ---------------------------------------------------------------------------


def _latest_per_url(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse attempt history to one row per URL (the newest attempt).

    The log is append-only: every retry writes a new SK, so a URL that was
    a ``quality_fail`` in March and a ``success`` in April will appear
    twice in a raw scan. The report should reflect *current* state —
    keep only the row with the largest SK per URL.
    """
    latest: Dict[str, Dict[str, Any]] = {}
    for r in records:
        url = r.get("url", "")
        sk = r.get("SK", "")
        prior = latest.get(url)
        if prior is None or sk > prior.get("SK", ""):
            latest[url] = r
    return list(latest.values())


def _group_by_manufacturer(
    records: Iterable[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        grouped[r.get("manufacturer", "Unknown")].append(r)
    # Deterministic order — stable both for diffs and for test assertions.
    for mfg in grouped:
        grouped[mfg].sort(
            key=lambda r: (r.get("product_name_hint") or "", r.get("url") or "")
        )
    return dict(sorted(grouped.items()))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _extract_date(record: Dict[str, Any]) -> str:
    """Return the 10-char ISO date from an SK like INGEST#2026-04-24T03:12:55Z."""
    sk = record.get("SK", "")
    iso = sk.split("#", 1)[-1]
    return iso[:10] if iso else "?"


def render_markdown(grouped: Dict[str, List[Dict[str, Any]]]) -> str:
    """Diagnostic markdown report — one section per manufacturer."""
    if not grouped:
        return "No ingest-log records matched the filter.\n"

    out: List[str] = []
    for mfg, rows in grouped.items():
        out.append(f"# {mfg} — {len(rows)} datasheet(s) with incomplete extractions\n")
        for r in rows:
            name = r.get("product_name_hint") or "(unnamed)"
            ptype = r.get("product_type", "?")
            parts = r.get("extracted_part_numbers") or []
            filled = r.get("fields_filled_avg", 0)
            total = r.get("fields_total", 0)
            missing = r.get("fields_missing") or []

            out.append(f"## {name} ({ptype})")
            out.append(f"- URL: {r.get('url', '?')}")
            out.append(f"- Last attempt: {_extract_date(r)}")
            if parts:
                preview = ", ".join(parts[:8])
                suffix = f" (+{len(parts) - 8} more)" if len(parts) > 8 else ""
                out.append(f"- Variants extracted: {len(parts)} ({preview}{suffix})")
            out.append(f"- Fields found: {filled}/{total} average")
            if missing:
                out.append("- Fields missing across all variants:")
                # Chunk 4 per bullet for readability.
                chunks = [missing[i : i + 4] for i in range(0, len(missing), 4)]
                for chunk in chunks:
                    out.append(f"  - {', '.join(chunk)}")
            out.append("")
    return "\n".join(out) + "\n"


def render_json(grouped: Dict[str, List[Dict[str, Any]]]) -> str:
    # DynamoDB Decimals aren't JSON-serializable; render them as numbers.
    from decimal import Decimal

    def _default(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj) if obj % 1 else int(obj)
        raise TypeError(f"{type(obj).__name__} is not JSON serializable")

    return json.dumps(grouped, indent=2, default=_default, sort_keys=True) + "\n"


def render_csv(grouped: Dict[str, List[Dict[str, Any]]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "manufacturer",
            "product_name",
            "product_type",
            "url",
            "last_attempt",
            "status",
            "products_extracted",
            "products_written",
            "fields_filled_avg",
            "fields_total",
            "part_numbers",
            "missing_fields",
        ]
    )
    for mfg, rows in grouped.items():
        for r in rows:
            writer.writerow(
                [
                    mfg,
                    r.get("product_name_hint") or "",
                    r.get("product_type", ""),
                    r.get("url", ""),
                    _extract_date(r),
                    r.get("status", ""),
                    r.get("products_extracted", 0),
                    r.get("products_written", 0),
                    r.get("fields_filled_avg", 0),
                    r.get("fields_total", 0),
                    "|".join(r.get("extracted_part_numbers") or []),
                    "|".join(r.get("fields_missing") or []),
                ]
            )
    return buf.getvalue()


def render_email_template(grouped: Dict[str, List[Dict[str, Any]]]) -> str:
    """Emit one plain-text email body per manufacturer.

    The user pastes into Gmail (or pipes to `mail`) and reviews before
    sending. No auto-send — keeps a human in the loop for vendor
    relationships.
    """
    if not grouped:
        return "No manufacturers with incomplete extractions.\n"

    out: List[str] = []
    for mfg, rows in grouped.items():
        # Union missing fields across all rows for the manufacturer so
        # one email covers everything they could fill in.
        all_missing: set[str] = set()
        part_numbers: set[str] = set()
        families: set[str] = set()
        for r in rows:
            all_missing.update(r.get("fields_missing") or [])
            part_numbers.update(r.get("extracted_part_numbers") or [])
            if r.get("product_family_hint"):
                families.add(r["product_family_hint"])

        out.append(f"=== Email to {mfg} ===")
        out.append(f"Subject: Request for complete specifications — {mfg} products")
        out.append("")
        out.append(f"Hello {mfg} team,")
        out.append("")
        out.append(
            "We catalog industrial product specifications for engineers "
            "specifying new builds. We pulled what we could from your public "
            "datasheets for the following products:"
        )
        out.append("")
        if families:
            out.append("Families:")
            for fam in sorted(families):
                out.append(f"  - {fam}")
            out.append("")
        if part_numbers:
            sorted_pns = sorted(part_numbers)
            preview = ", ".join(sorted_pns[:20])
            suffix = f" (+{len(sorted_pns) - 20} more)" if len(sorted_pns) > 20 else ""
            out.append(f"Part numbers: {preview}{suffix}")
            out.append("")
        if all_missing:
            out.append(
                "To complete the listings we're missing values for these "
                "specifications across at least one variant. Could you send "
                "us a datasheet or spec table covering them?"
            )
            out.append("")
            for field in sorted(all_missing):
                out.append(f"  - {field}")
            out.append("")
        out.append(
            "If some specs genuinely don't apply to the family, just let "
            "us know and we'll mark them N/A on our end."
        )
        out.append("")
        out.append("Thanks,")
        out.append("The DatasheetMiner team")
        out.append("")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ingest-report",
        description="Group ingest-log quality-fails by manufacturer for vendor outreach.",
    )
    parser.add_argument(
        "--manufacturer",
        default=None,
        help="Exact-match filter on manufacturer (default: all).",
    )
    parser.add_argument(
        "--status",
        default=STATUS_QUALITY_FAIL,
        help="Ingest status to report on; pass 'all' for no filter.",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="ISO-8601 timestamp (e.g. 2026-04-01). Only attempts at/after this date.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "csv"],
        default="markdown",
        help="Output format (default: markdown).",
    )
    parser.add_argument(
        "--email-template",
        action="store_true",
        help="Emit vendor outreach email bodies instead of a diagnostic report.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write output to a file instead of stdout.",
    )

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    args = parser.parse_args(argv)

    status_filter = None if args.status == "all" else args.status
    client = DynamoDBClient()

    records = client.list_ingest(
        manufacturer=args.manufacturer,
        status=status_filter,
        since=args.since,
    )
    records = _latest_per_url(records)

    # A URL whose newest attempt is a success shouldn't show up in the
    # quality-fail report even if earlier attempts failed.
    if status_filter:
        records = [r for r in records if r.get("status") == status_filter]

    grouped = _group_by_manufacturer(records)

    if args.email_template:
        out_text = render_email_template(grouped)
    elif args.format == "json":
        out_text = render_json(grouped)
    elif args.format == "csv":
        out_text = render_csv(grouped)
    else:
        out_text = render_markdown(grouped)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out_text)
        logger.warning("wrote %s", args.output)
    else:
        sys.stdout.write(out_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
