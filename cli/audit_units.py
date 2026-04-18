"""Audit DynamoDB for value-unit strings with more than one semicolon.

Related: todo/fundamental-flaws.md (flaw #1).

`_parse_compact_units` in datasheetminer/db/dynamo.py uses a greedy `(.*)`
capture for the unit portion of a "value;unit" string, so any stored value
like "1;2;V" reads back as {value=1, unit="2;V"} instead of falling through
to the passthrough path. A writer-side invariant has now been added
(models/common.py) so new writes cannot produce this, but existing rows need
to be audited.

Usage:
    ./Quickstart admin audit-units                 # scan the configured table
    ./Quickstart admin audit-units -o out.jsonl    # write findings to a file
    ./Quickstart admin audit-units --table foo     # override table name

Read-only. Exits 0 when nothing dirty is found, non-zero otherwise.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Iterator

import boto3  # type: ignore

from datasheetminer.config import REGION, TABLE_NAME


logger: logging.Logger = logging.getLogger("dsm.audit-units")


def _iter_all_items(table: Any) -> Iterator[dict[str, Any]]:
    """Yield every item from a DynamoDB table via paginated scan."""
    scan_kwargs: dict[str, Any] = {}
    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            yield item
        lek = response.get("LastEvaluatedKey")
        if not lek:
            return
        scan_kwargs["ExclusiveStartKey"] = lek


def _find_dirty_strings(
    item: dict[str, Any], prefix: str = ""
) -> list[tuple[str, str]]:
    """Walk the item recursively and return (path, value) for any string
    that contains more than one ';'. That's the pattern the greedy regex
    misparses."""
    found: list[tuple[str, str]] = []
    if isinstance(item, dict):
        for k, v in item.items():
            path = f"{prefix}.{k}" if prefix else k
            found.extend(_find_dirty_strings(v, path))
    elif isinstance(item, list):
        for i, v in enumerate(item):
            found.extend(_find_dirty_strings(v, f"{prefix}[{i}]"))
    elif isinstance(item, str) and item.count(";") >= 2:
        found.append((prefix, item))
    return found


def audit(table_name: str, region: str, out_path: str | None) -> int:
    """Scan the table and report any fields whose value has more than one ';'.

    Returns the process exit code: 0 if clean, 1 if dirty rows were found.
    """
    ddb = boto3.resource("dynamodb", region_name=region)
    table = ddb.Table(table_name)

    dirty_count = 0
    scanned = 0
    writer = open(out_path, "w") if out_path else None

    try:
        for item in _iter_all_items(table):
            scanned += 1
            findings = _find_dirty_strings(item)
            if not findings:
                continue
            dirty_count += 1
            pk = item.get("PK", "<no PK>")
            sk = item.get("SK", "<no SK>")
            report = {
                "PK": pk,
                "SK": sk,
                "fields": [{"path": p, "value": v} for p, v in findings],
            }
            line = json.dumps(report, default=str)
            if writer:
                writer.write(line + "\n")
            else:
                print(line)
    finally:
        if writer:
            writer.close()

    print(
        f"audit-units: scanned {scanned} items, found {dirty_count} with "
        f"multi-semicolon fields",
        file=sys.stderr,
    )
    return 0 if dirty_count == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit-units",
        description=(
            "Scan DynamoDB for 'value;unit' strings with more than one ';' — "
            "the shape that _parse_compact_units misparses."
        ),
    )
    parser.add_argument(
        "--table",
        default=os.environ.get("DYNAMODB_TABLE_NAME", TABLE_NAME),
        help="DynamoDB table to scan (default: $DYNAMODB_TABLE_NAME or config)",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", REGION),
        help="AWS region (default: $AWS_REGION or config)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Write findings as JSONL to this path (default: stdout)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    return audit(args.table, args.region, args.output)


if __name__ == "__main__":
    sys.exit(main())
