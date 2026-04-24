"""One-shot: rename legacy attribute names / coerce legacy shapes in
DynamoDB to match the current model field names.

Renames (apply once per stage):

    Drive:     output_power          → rated_power
               ambient_temp          → operating_temp
    Gearhead:  max_continuous_torque → rated_torque
               max_peak_torque       → peak_torque

Coercions:

    ip_rating: str "IP54" → int 54  (applies across all product types).
               Also handles bare-digit strings "54" and legacy
               {"value": 54} dicts.

Dry-run by default. Pass ``--apply`` to actually rewrite items.

Usage:
    DYNAMODB_TABLE_NAME=... AWS_REGION=... \\
        uv run python scripts/rename_legacy_fields.py [--apply]
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
load_dotenv(REPO / ".env")

import boto3  # noqa: E402

from datasheetminer.models.common import _coerce_ip_rating  # noqa: E402


@dataclass(frozen=True)
class Rename:
    product_type: str
    old_name: str
    new_name: str


RENAMES: List[Rename] = [
    Rename("drive", "output_power", "rated_power"),
    Rename("drive", "ambient_temp", "operating_temp"),
    Rename("gearhead", "max_continuous_torque", "rated_torque"),
    Rename("gearhead", "max_peak_torque", "peak_torque"),
]


def scan_all(table) -> list[dict]:
    items: list[dict] = []
    kwargs: dict = {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply", action="store_true", help="Perform writes (default: dry-run)"
    )
    args = ap.parse_args()

    table_name = os.environ.get("DYNAMODB_TABLE_NAME")
    region = os.environ.get("AWS_REGION", "us-east-1")
    if not table_name:
        print("DYNAMODB_TABLE_NAME not set", file=sys.stderr)
        return 1

    print(
        f"{'APPLY' if args.apply else 'DRY-RUN'} — table={table_name} region={region}"
    )

    ddb = boto3.resource("dynamodb", region_name=region)
    table = ddb.Table(table_name)

    items = scan_all(table)
    print(f"Scanned {len(items)} items")

    per_rename: Dict[str, int] = {f"{r.product_type}.{r.old_name}": 0 for r in RENAMES}
    ip_coerced = 0
    ip_dropped = 0
    rewrites = 0

    for item in items:
        ptype = item.get("product_type")
        pk = item.get("PK")
        sk = item.get("SK")
        if not ptype or not pk or not sk:
            continue

        applicable = [
            r for r in RENAMES if r.product_type == ptype and r.old_name in item
        ]
        raw_ip = item.get("ip_rating")
        needs_ip_coercion = raw_ip is not None and not isinstance(raw_ip, int)
        if needs_ip_coercion:
            coerced = _coerce_ip_rating(raw_ip)
            # `_coerce_ip_rating` passes unknown types through unchanged;
            # for the migration we want only ints or absence.
            new_ip_value = coerced if isinstance(coerced, int) else None
        else:
            new_ip_value = None

        if not applicable and not needs_ip_coercion:
            continue

        set_expr_parts: list[str] = []
        remove_expr_parts: list[str] = []
        attr_values: dict = {}
        attr_names: dict = {}

        for idx, r in enumerate(applicable):
            placeholder = f":v{idx}"
            old_alias = f"#o{idx}"
            new_alias = f"#n{idx}"
            set_expr_parts.append(f"{new_alias} = {placeholder}")
            remove_expr_parts.append(old_alias)
            attr_values[placeholder] = item[r.old_name]
            attr_names[old_alias] = r.old_name
            attr_names[new_alias] = r.new_name
            per_rename[f"{r.product_type}.{r.old_name}"] += 1

        if needs_ip_coercion:
            attr_names["#ip"] = "ip_rating"
            if new_ip_value is not None:
                attr_values[":ip"] = new_ip_value
                set_expr_parts.append("#ip = :ip")
                ip_coerced += 1
            else:
                # Un-parseable string — drop the attribute so the model
                # defaults to None rather than 500-ing on deserialize.
                remove_expr_parts.append("#ip")
                ip_dropped += 1

        update_expr_segments = []
        if set_expr_parts:
            update_expr_segments.append("SET " + ", ".join(set_expr_parts))
        if remove_expr_parts:
            update_expr_segments.append("REMOVE " + ", ".join(remove_expr_parts))
        update_expr = " ".join(update_expr_segments)

        if args.apply:
            kwargs = {
                "Key": {"PK": pk, "SK": sk},
                "UpdateExpression": update_expr,
                "ExpressionAttributeNames": attr_names,
            }
            if attr_values:
                kwargs["ExpressionAttributeValues"] = attr_values
            table.update_item(**kwargs)
        rewrites += 1

    print()
    print("Per-field rename count:")
    for key, n in per_rename.items():
        print(f"  {key:<40} {n}")
    print(f"ip_rating coerced (str → int): {ip_coerced}")
    print(f"ip_rating dropped (unparseable): {ip_dropped}")
    print(f"Total items touched: {rewrites}")
    if not args.apply:
        print("\n(Dry run — re-run with --apply to commit.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
