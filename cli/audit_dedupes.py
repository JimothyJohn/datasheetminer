"""DEDUPE Phase 1 — scan dev DB for prefix-drift duplicates.

Read-only on DynamoDB. Groups rows by (manufacturer, family-aware normalized
core) using the same strip rule as `compute_product_id` (so the audit's
notion of "same product" matches what `compute_product_id` would now write).

Emits two artifacts per run:

- ``outputs/dedupe_audit_<stage>_<ts>.json`` — every group with >= 2 rows.
  For each group, classifies every populated field as identical /
  complementary / conflicting and suggests an action (``merge``,
  ``review``, ``delete-junk``).
- ``outputs/dedupe_review_<stage>_<ts>.md`` — human-review queue: one
  section per ``review`` group with a 3-column table of the disagreeing
  fields, one row per source.

Phase 1 only — no DB writes, no Phase 2 ``--apply``. Per todo/DEDUPE.md.

Usage:
    uv run python -m cli.audit_dedupes --stage dev
    uv run python -m cli.audit_dedupes --stage dev --output /tmp/audit.json
    uv run python -m cli.audit_dedupes --rows tests/fixtures/sample.json  # offline
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from specodex.ids import _strip_family_prefix, normalize_string

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "outputs"

log = logging.getLogger("audit_dedupes")

# Fields that are bookkeeping or identity, not part of the product's spec —
# diffs on these don't drive the merge classification. Three buckets:
#   - storage metadata: PK, SK, product_id, id, type, created_at, updated_at
#   - provenance: pages, datasheet_url, source_url, extraction_id
#   - identity (we GROUP on family-aware core, so prefix-drifted
#     part_number/product_name/product_family are *expected* to differ —
#     that's the whole point of the audit)
NON_SPEC_FIELDS = frozenset(
    {
        "PK",
        "SK",
        "product_id",
        "id",
        "_id",
        "type",
        "created_at",
        "updated_at",
        "ingested_at",
        "pages",
        "datasheet_url",
        "source_url",
        "extraction_id",
        "manufacturer",
        "part_number",
        "product_name",
        "product_family",
        "product_type",
    }
)

# Placeholder/junk part-number patterns — rows that look like extraction
# noise and are candidates for `delete-junk` rather than merge. Kept short
# and conservative; the operator decides per group.
JUNK_PART_NUMBER_PATTERNS = (
    "unknown",
    "n/a",
    "tbd",
    "placeholder",
    "see spec",
)


# ── Pure functions (testable without DynamoDB) ─────────────────────────


def family_aware_core(part_number: str | None, product_family: str | None) -> str:
    """Return the normalized core of a part number after stripping the family.

    Uses the same `_strip_family_prefix` rule that `compute_product_id`
    applies on write — so the audit groups rows the same way the new ID
    function would have collapsed them.
    """
    norm_pn = normalize_string(part_number)
    norm_family = normalize_string(product_family)
    if norm_pn and norm_family:
        return _strip_family_prefix(norm_pn, norm_family)
    return norm_pn


def is_junk_part_number(pn: str | None) -> bool:
    """Match the conservative placeholder patterns — operator-confirmable."""
    if not pn:
        return True
    pn_l = pn.lower().strip()
    return any(token in pn_l for token in JUNK_PART_NUMBER_PATTERNS)


def group_rows(rows: Iterable[dict]) -> dict[tuple[str, str], list[dict]]:
    """Group rows by (manufacturer_norm, family_aware_core).

    Rows missing both manufacturer and a usable part_number are skipped —
    they wouldn't have collapsed under the new ID rule either.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        mfg = normalize_string(row.get("manufacturer"))
        core = family_aware_core(row.get("part_number"), row.get("product_family"))
        if not mfg or not core:
            continue
        groups.setdefault((mfg, core), []).append(row)
    return groups


def _spec_keys(rows: list[dict]) -> set[str]:
    """Union of populated spec-field keys across the group."""
    keys: set[str] = set()
    for row in rows:
        for k, v in row.items():
            if k in NON_SPEC_FIELDS or k.startswith("_"):
                continue
            if v is None or v == "" or v == [] or v == {}:
                continue
            keys.add(k)
    return keys


def _values_for(rows: list[dict], field: str) -> list[Any]:
    """Field values across rows; None for absent/null/empty."""
    out: list[Any] = []
    for row in rows:
        v = row.get(field)
        if v is None or v == "" or v == [] or v == {}:
            out.append(None)
        else:
            out.append(v)
    return out


def classify_field(values: list[Any]) -> str:
    """Return ``identical`` / ``complementary`` / ``conflicting`` for a field.

    - All non-null and equal → ``identical``.
    - Some null, the rest equal (or just one non-null) → ``complementary``.
    - Two or more distinct non-null values → ``conflicting``.
    """
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "identical"  # vacuously safe
    distinct = {json.dumps(v, sort_keys=True, default=str) for v in non_null}
    if len(distinct) > 1:
        return "conflicting"
    if len(non_null) == len(values):
        return "identical"
    return "complementary"


def suggest_action(classifications: dict[str, str], rows: list[dict]) -> str:
    """Pick `merge`, `review`, or `delete-junk` for a group.

    - ``delete-junk`` if every part_number in the group is a placeholder
      pattern AND there's at least one neighbor with a real part number
      under the same core (rare — the placeholder rows are extraction noise).
    - ``review`` if any classification is ``conflicting``.
    - ``merge`` otherwise.
    """
    pns = [r.get("part_number") for r in rows]
    junky = [is_junk_part_number(p) for p in pns]
    if any(junky) and not all(junky):
        return "delete-junk"
    if any(c == "conflicting" for c in classifications.values()):
        return "review"
    return "merge"


def diff_group(rows: list[dict]) -> dict[str, str]:
    """Per-field classification dict for a group of >= 2 rows."""
    return {
        field: classify_field(_values_for(rows, field)) for field in _spec_keys(rows)
    }


def audit(rows: Iterable[dict]) -> list[dict[str, Any]]:
    """Return a list of group reports with diffs + suggested action.

    Only groups with >= 2 rows are included — the singletons are exactly
    what we want (one canonical row per product).
    """
    groups = group_rows(rows)
    reports: list[dict[str, Any]] = []
    for (mfg, core), group_rows_list in sorted(groups.items()):
        if len(group_rows_list) < 2:
            continue
        classifications = diff_group(group_rows_list)
        action = suggest_action(classifications, group_rows_list)

        # Family mismatch is a special signal — same normalized core, two
        # different `product_family` values. The new ID rule would still
        # collapse these (`product_family` only feeds the strip), but the
        # operator needs to know before merging.
        families = sorted(
            {
                str(r.get("product_family") or "")
                for r in group_rows_list
                if r.get("product_family")
            }
        )
        family_mismatch = len(families) > 1
        if family_mismatch and action == "merge":
            action = "review"  # demote to manual

        reports.append(
            {
                "manufacturer": mfg,
                "normalized_core": core,
                "row_count": len(group_rows_list),
                "rows": [
                    {
                        "PK": r.get("PK"),
                        "SK": r.get("SK"),
                        "product_id": r.get("product_id") or r.get("id"),
                        "part_number": r.get("part_number"),
                        "product_family": r.get("product_family"),
                        "datasheet_url": r.get("datasheet_url") or r.get("source_url"),
                    }
                    for r in group_rows_list
                ],
                "field_classifications": classifications,
                "family_mismatch": family_mismatch,
                "suggested_action": action,
            }
        )
    return reports


# ── Rendering ──────────────────────────────────────────────────────────


def render_review_md(reports: list[dict[str, Any]]) -> str:
    """Markdown review queue for the `review` and `delete-junk` groups.

    Reviewer reads top-down, picks per disagreeing field, runs Phase 3
    `--from-review` (not in this PR).
    """
    review = [r for r in reports if r["suggested_action"] != "merge"]
    lines: list[str] = [
        "# DEDUPE review queue",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        f"Total groups needing review: **{len(review)}** "
        f"(out of {len(reports)} groups with >= 2 rows)",
        "",
    ]
    if not review:
        lines.append("✅ Nothing to review. All duplicate groups can auto-merge.")
        return "\n".join(lines) + "\n"
    for i, r in enumerate(review, 1):
        lines.extend(
            [
                f"## {i}. `{r['manufacturer']}` / `{r['normalized_core']}` "
                f"— {r['suggested_action']}",
                "",
                f"- {r['row_count']} rows in this group"
                + (" · ⚠ family mismatch" if r["family_mismatch"] else ""),
                "",
                "### Source rows",
                "",
                "| # | part_number | product_family | datasheet_url |",
                "|---|---|---|---|",
            ]
        )
        for j, row in enumerate(r["rows"], 1):
            url = row.get("datasheet_url") or ""
            url_md = f"[link]({url})" if url else "—"
            lines.append(
                f"| {j} | `{row.get('part_number') or ''}` | "
                f"`{row.get('product_family') or ''}` | {url_md} |"
            )
        conflicting = [
            f for f, c in r["field_classifications"].items() if c == "conflicting"
        ]
        if conflicting:
            lines.extend(
                [
                    "",
                    "### Conflicting fields",
                    "",
                    "| field | "
                    + " | ".join(f"row {i + 1}" for i in range(r["row_count"]))
                    + " |",
                    "|---|" + "|".join(["---"] * r["row_count"]) + "|",
                ]
            )
        lines.append("")
    return "\n".join(lines) + "\n"


# ── DB scan (not unit-tested — boto-bound) ─────────────────────────────


def fetch_rows_from_dynamo(table_name: str) -> list[dict]:
    """Scan the products table and return raw items (dicts).

    Kept as a thin shim around `boto3.resource('dynamodb').Table(...).scan()`
    so the audit logic stays unit-testable on plain dicts. Returns the raw
    DynamoDB items (Decimal-typed numerics) — the audit's classification
    treats them as opaque values.
    """
    import boto3  # type: ignore

    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )
    table = boto3.resource("dynamodb", region_name=region).Table(table_name)
    items: list[dict] = []
    kwargs: dict[str, Any] = {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    log.info("Scanned %s items from %s", len(items), table_name)
    return items


def _decimal_to_native(obj: Any) -> Any:
    """Recursively convert Decimal → int/float so json.dumps works."""
    from decimal import Decimal

    if isinstance(obj, Decimal):
        as_int = int(obj)
        return as_int if as_int == obj else float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_native(v) for v in obj]
    return obj


# ── CLI entry ──────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="audit_dedupes", description=__doc__)
    parser.add_argument(
        "--stage",
        choices=["dev"],
        default="dev",
        help="Stage to scan. Phase 1 is dev-only; staging/prod refused on purpose.",
    )
    parser.add_argument(
        "--table",
        help="Override DynamoDB table name (default: products-<stage>)",
    )
    parser.add_argument(
        "--rows",
        type=Path,
        help="Read rows from a JSON file (list of dicts) instead of DynamoDB. "
        "Used by tests and dry-runs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the audit JSON here (default: outputs/dedupe_audit_<stage>_<ts>.json)",
    )
    parser.add_argument(
        "--review-output",
        type=Path,
        help="Write the review queue MD here (default: outputs/dedupe_review_<stage>_<ts>.md)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress INFO logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    if args.rows:
        raw = json.loads(args.rows.read_text())
        if not isinstance(raw, list):
            print(
                f"--rows must point to a JSON list of dicts, got {type(raw).__name__}",
                file=sys.stderr,
            )
            return 2
        rows = raw
    else:
        table = args.table or f"products-{args.stage}"
        rows = [_decimal_to_native(r) for r in fetch_rows_from_dynamo(table)]

    reports = audit(rows)
    log.info(
        "Found %s groups with >= 2 rows (%s merge-safe, %s for review, %s delete-junk)",
        len(reports),
        sum(1 for r in reports if r["suggested_action"] == "merge"),
        sum(1 for r in reports if r["suggested_action"] == "review"),
        sum(1 for r in reports if r["suggested_action"] == "delete-junk"),
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = args.output or OUTPUT_DIR / f"dedupe_audit_{args.stage}_{ts}.json"
    md_path = args.review_output or OUTPUT_DIR / f"dedupe_review_{args.stage}_{ts}.md"

    json_path.write_text(
        json.dumps(
            {
                "stage": args.stage,
                "timestamp": ts,
                "total_groups": len(reports),
                "groups": reports,
            },
            indent=2,
            default=str,
        )
    )
    md_path.write_text(render_review_md(reports))

    log.info("Wrote audit JSON: %s", json_path)
    log.info("Wrote review queue: %s", md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
