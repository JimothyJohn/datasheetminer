#!/usr/bin/env python3
"""Backfill DynamoDB rows where ValueUnit / MinMaxUnit fields leaked as
compact ``"value;unit"`` / ``"min-max;unit"`` strings instead of structured
dicts.

The compact string format was the in-memory Pydantic representation prior
to UNITS Phases 1-4. Most fields round-tripped through the regex layer
cleanly and were stored on DynamoDB as dicts already, but exotic forms
(scientific notation, qualifier-prefixed values, ranges with negatives)
silently fell through and persisted as raw strings — visible in the
Product Detail UI as ``"5.5e-5;kg·cm²"``.

This script scans every product row, finds string values that look like
compact units, parses them through the new ``ValueUnit`` / ``MinMaxUnit``
coercers (which handle scientific notation and friends), writes the dict
form back, and emits a manual-review markdown for anything unparseable.

Usage:

    source .env && uv run python cli/migrate_units_to_dict.py --stage dev --dry-run
    source .env && uv run python cli/migrate_units_to_dict.py --stage dev
    source .env && uv run python cli/migrate_units_to_dict.py --stage staging
    source .env && uv run python cli/migrate_units_to_dict.py --stage prod

Same ``--stage``-gated safety pattern as ``cli/admin.py``: dev first,
eyeball the review file, fix any genuinely broken records by hand, then
promote.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import boto3

from specodex.models.common import MinMaxUnit, ValueUnit

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / ".logs"
LOG_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR = REPO_ROOT / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(LOG_DIR / "migrate_units_to_dict.log"),
    ],
)
log = logging.getLogger("migrate_units")


STAGE_TABLE = {
    "dev": "products-dev",
    "staging": "products-staging",
    "prod": "products-prod",
}


def _looks_like_compact_unit(s: str) -> bool:
    """Cheap pre-filter — only call the full coercer on plausible candidates.

    Compact units are tight: ``"5.5e-5;kg·cm²"``, ``"-40-85;°C"``, ``"100+;A"``.
    Neither side has internal whitespace and neither is empty. Free-text
    ``"Power: 100W; Speed: 3000rpm"`` fails the no-internal-space check and
    is rejected before reaching the parser, keeping the manual-review file
    free of obvious description-field noise.
    """
    if not isinstance(s, str) or ";" not in s:
        return False
    parts = s.split(";")
    if len(parts) != 2:
        return False
    left, right = parts[0].strip(), parts[1].strip()
    if not left or not right:
        return False
    return not any(c.isspace() for c in left) and not any(c.isspace() for c in right)


def _try_parse_compact(s: str) -> dict | None:
    """Try ValueUnit then MinMaxUnit. Returns the dict form or None."""
    try:
        return ValueUnit.model_validate(s).model_dump()
    except Exception:
        pass
    try:
        return MinMaxUnit.model_validate(s).model_dump()
    except Exception:
        pass
    return None


def _walk_and_fix(
    obj: Any,
    path: tuple[str, ...] = (),
    fixes: list[tuple[tuple[str, ...], str, dict]] | None = None,
    unparseable: list[tuple[tuple[str, ...], str]] | None = None,
) -> Any:
    """Recursively walk obj, replacing compact-unit strings with dicts.

    Mutates ``obj`` in place. Records each replacement in ``fixes`` and
    each failed-to-parse candidate in ``unparseable`` for the review log.
    """
    if fixes is None:
        fixes = []
    if unparseable is None:
        unparseable = []

    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if isinstance(value, str) and _looks_like_compact_unit(value):
                parsed = _try_parse_compact(value)
                if parsed is not None:
                    obj[key] = parsed
                    fixes.append((path + (key,), value, parsed))
                else:
                    unparseable.append((path + (key,), value))
            else:
                _walk_and_fix(value, path + (key,), fixes, unparseable)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            if isinstance(value, str) and _looks_like_compact_unit(value):
                parsed = _try_parse_compact(value)
                if parsed is not None:
                    obj[idx] = parsed
                    fixes.append((path + (f"[{idx}]",), value, parsed))
                else:
                    unparseable.append((path + (f"[{idx}]",), value))
            else:
                _walk_and_fix(value, path + (f"[{idx}]",), fixes, unparseable)

    return obj


def _decimalize(obj: Any) -> Any:
    """Convert floats to Decimal for DynamoDB write compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _decimalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimalize(v) for v in obj]
    return obj


def _scan_all_products(table: Any) -> Iterable[dict]:
    """Paginate through every PRODUCT#* row in the table."""
    kwargs: dict[str, Any] = {
        "FilterExpression": "begins_with(PK, :prefix)",
        "ExpressionAttributeValues": {":prefix": "PRODUCT#"},
    }
    while True:
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            yield item
        if "LastEvaluatedKey" not in resp:
            return
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def _format_path(path: tuple[str, ...]) -> str:
    return ".".join(path) if path else "<root>"


def _write_review(
    review_path: Path,
    stage: str,
    table_name: str,
    review_entries: list[dict],
) -> None:
    """Write the manual-review markdown for unparseable strings."""
    lines = [
        f"# Units migration review — {stage} ({table_name})",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}_",
        "",
        f"{len(review_entries)} row(s) had string values resembling compact units that the new ValueUnit/MinMaxUnit coercer could not parse. Inspect each, fix by hand if it's a legitimate spec, or delete the row if the string is junk.",
        "",
    ]
    for entry in review_entries:
        lines.append(f"## `{entry['PK']}` / `{entry['SK']}`")
        lines.append("")
        lines.append(f"- **product_name:** {entry.get('product_name', '?')}")
        lines.append(f"- **manufacturer:** {entry.get('manufacturer', '?')}")
        lines.append("")
        lines.append("| Field path | Raw string |")
        lines.append("|---|---|")
        for path, value in entry["unparseable"]:
            lines.append(f"| `{_format_path(path)}` | `{value}` |")
        lines.append("")
    review_path.write_text("\n".join(lines))


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--stage",
        required=True,
        choices=list(STAGE_TABLE),
        help="Which DynamoDB table to operate on",
    )
    parser.add_argument(
        "--table",
        help="Override the table name (defaults to STAGE_TABLE[stage])",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to DynamoDB",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
    )
    args = parser.parse_args()

    table_name = args.table or STAGE_TABLE[args.stage]
    db = boto3.resource("dynamodb", region_name=args.region)
    table = db.Table(table_name)

    log.info(
        "Scanning %s (stage=%s) for compact-unit string leaks", table_name, args.stage
    )

    scanned = 0
    fixed_rows = 0
    fixed_fields = 0
    unparseable_rows = 0
    review_entries: list[dict] = []

    for item in _scan_all_products(table):
        scanned += 1
        pk = item.get("PK")
        sk = item.get("SK")
        if not pk or not sk:
            log.warning("Row missing PK/SK, skipping: keys=%s", list(item.keys()))
            continue

        working = deepcopy(item)
        fixes: list[tuple[tuple[str, ...], str, dict]] = []
        unparseable: list[tuple[tuple[str, ...], str]] = []

        _walk_and_fix(working, fixes=fixes, unparseable=unparseable)

        if unparseable:
            unparseable_rows += 1
            review_entries.append(
                {
                    "PK": pk,
                    "SK": sk,
                    "product_name": item.get("product_name"),
                    "manufacturer": item.get("manufacturer"),
                    "unparseable": unparseable,
                }
            )

        if not fixes:
            continue

        fixed_rows += 1
        fixed_fields += len(fixes)
        for path, before, after in fixes:
            log.info(
                "  %s / %s · %s: %r → %s",
                pk,
                sk,
                _format_path(path),
                before,
                after,
            )

        if args.dry_run:
            continue

        try:
            table.put_item(Item=_decimalize(working))
        except Exception as e:
            log.error("Failed to write %s/%s: %s", pk, sk, e)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    review_path = OUTPUTS_DIR / f"units_migration_review_{args.stage}_{timestamp}.md"
    if review_entries:
        _write_review(review_path, args.stage, table_name, review_entries)
        log.info("Manual-review file: %s", review_path)

    summary = {
        "stage": args.stage,
        "table": table_name,
        "dry_run": args.dry_run,
        "scanned": scanned,
        "fixed_rows": fixed_rows if not args.dry_run else 0,
        "would_fix_rows": fixed_rows,
        "fixed_fields": fixed_fields if not args.dry_run else 0,
        "would_fix_fields": fixed_fields,
        "unparseable_rows": unparseable_rows,
        "review_file": str(review_path) if review_entries else None,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
