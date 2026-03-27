#!/usr/bin/env python3
"""Migrate Faulhaber linear actuators from PRODUCT#MOTOR to PRODUCT#ELECTRIC_CYLINDER.

Identifies motors where rated_torque is in N (force) instead of Nm (torque),
remaps fields to the electric_cylinder schema, writes new items, and deletes
the old motor items.

Usage:
    source .env && uv run python cli/migrate_electric_cylinders.py --dry-run
    source .env && uv run python cli/migrate_electric_cylinders.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import boto3

LOG_DIR = Path(__file__).resolve().parent.parent / ".logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(LOG_DIR / "migrate_electric_cylinders.log"),
    ],
)
log = logging.getLogger("migrate")


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


# Motor fields that map directly to electric_cylinder fields
FIELD_REMAP = {
    "rated_torque": "continuous_force",
    "peak_torque": "max_push_force",
    "rated_speed": "max_linear_speed",
    "max_speed": "max_linear_speed",  # fallback if rated_speed absent
}

# Motor fields that carry over unchanged
CARRY_FIELDS = {
    "product_id",
    "product_name",
    "product_family",
    "part_number",
    "manufacturer",
    "series",
    "rated_voltage",
    "rated_current",
    "peak_current",
    "rated_power",
    "weight",
    "dimensions",
    "ip_rating",
    "datasheet_url",
    "pages",
    "release_year",
    "radial_load_force_rating",
    "axial_load_force_rating",
    "rotor_inertia",
    "encoder_feedback_support",
}

# Fields specific to motor schema that don't belong on electric_cylinder
SKIP_FIELDS = {"PK", "SK", "product_type", "type"}


def is_force_unit(field_val: dict | None) -> bool:
    """Check if a value+unit dict has a force unit (N) rather than torque (Nm)."""
    if not isinstance(field_val, dict):
        return False
    unit = field_val.get("unit", "")
    return unit == "N" or unit == "mN" or unit == "kN"


def is_linear_speed(field_val: dict | None) -> bool:
    """Check if a value+unit dict has a linear speed unit (mm/s) rather than rpm."""
    if not isinstance(field_val, dict):
        return False
    unit = field_val.get("unit", "")
    return "mm/s" in unit or "m/s" in unit or "in/s" in unit


def should_migrate(item: dict) -> bool:
    """Determine if a motor item is actually an electric cylinder."""
    rated_torque = item.get("rated_torque")
    rated_speed = item.get("rated_speed")

    # Primary signal: torque in N (force)
    if is_force_unit(rated_torque):
        return True

    # Secondary signal: speed in mm/s (linear) with no torque
    if rated_torque is None and is_linear_speed(rated_speed):
        return True

    return False


def remap_item(item: dict) -> dict:
    """Convert a motor item dict to an electric_cylinder item dict."""
    new = {}
    new["PK"] = "PRODUCT#ELECTRIC_CYLINDER"
    new["product_type"] = "electric_cylinder"

    pid = item["product_id"]
    new["SK"] = f"PRODUCT#{pid}"

    # Carry over unchanged fields
    for field in CARRY_FIELDS:
        if field in item and item[field] is not None and item[field] != "":
            new[field] = deepcopy(item[field])

    # Remap force fields
    if "rated_torque" in item and item["rated_torque"] is not None:
        new["continuous_force"] = deepcopy(item["rated_torque"])
    if "peak_torque" in item and item["peak_torque"] is not None:
        new["max_push_force"] = deepcopy(item["peak_torque"])

    # Remap speed: motor rated_speed (mm/s) → electric_cylinder max_linear_speed
    if "rated_speed" in item and item["rated_speed"] is not None:
        new["max_linear_speed"] = deepcopy(item["rated_speed"])

    # Remap load ratings to electric_cylinder field names
    if "radial_load_force_rating" in new:
        new["max_radial_load"] = new.pop("radial_load_force_rating")
    if "axial_load_force_rating" in new:
        new["max_axial_load"] = new.pop("axial_load_force_rating")

    return new


def fetch_faulhaber_motors(table) -> list[dict]:
    """Query all Faulhaber motors from PRODUCT#MOTOR partition."""
    items = []
    resp = table.query(
        KeyConditionExpression="PK = :pk",
        FilterExpression="manufacturer = :mfg",
        ExpressionAttributeValues={":pk": "PRODUCT#MOTOR", ":mfg": "Faulhaber"},
    )
    items.extend(resp.get("Items", []))

    while "LastEvaluatedKey" in resp:
        resp = table.query(
            KeyConditionExpression="PK = :pk",
            FilterExpression="manufacturer = :mfg",
            ExpressionAttributeValues={":pk": "PRODUCT#MOTOR", ":mfg": "Faulhaber"},
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))

    return items


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Migrate electric cylinders")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to DynamoDB",
    )
    args = parser.parse_args()

    table_name = os.environ.get("DYNAMODB_TABLE_NAME", "products-dev")
    db = boto3.resource("dynamodb", region_name="us-east-1")
    table = db.Table(table_name)

    log.info("Scanning %s for Faulhaber motors to migrate", table_name)
    motors = fetch_faulhaber_motors(table)
    log.info("Found %d Faulhaber motors total", len(motors))

    to_migrate = [m for m in motors if should_migrate(m)]
    to_skip = [m for m in motors if not should_migrate(m)]

    log.info(
        "Migrating %d items, skipping %d (legitimate motors)",
        len(to_migrate),
        len(to_skip),
    )

    for item in to_skip:
        name = item.get("product_name", "?")
        torque = item.get("rated_torque", {})
        log.info("  SKIP: %s (torque=%s)", name, torque)

    migrated = 0
    errors = 0

    for item in to_migrate:
        old_pk = item["PK"]
        old_sk = item["SK"]
        name = item.get("product_name", "?")
        part = item.get("part_number", "?")

        new_item = remap_item(item)

        if args.dry_run:
            log.info(
                "  DRY-RUN: %s (%s) → ELECTRIC_CYLINDER",
                name,
                part,
            )
            continue

        try:
            # Write new electric_cylinder item
            table.put_item(Item=new_item)

            # Delete old motor item
            table.delete_item(Key={"PK": old_pk, "SK": old_sk})

            migrated += 1
            log.info("  MIGRATED: %s (%s)", name, part)

        except Exception as e:
            errors += 1
            log.error("  ERROR migrating %s (%s): %s", name, part, e)

    if args.dry_run:
        log.info("Dry run complete. %d items would be migrated.", len(to_migrate))
    else:
        log.info(
            "Migration complete. migrated=%d, errors=%d, skipped=%d",
            migrated,
            errors,
            len(to_skip),
        )

    # Write summary
    summary = {
        "table": table_name,
        "total_faulhaber": len(motors),
        "migrated": migrated if not args.dry_run else 0,
        "would_migrate": len(to_migrate),
        "skipped": len(to_skip),
        "errors": errors,
        "dry_run": args.dry_run,
    }
    print(json.dumps(summary, indent=2, cls=DecimalEncoder))


if __name__ == "__main__":
    main()
