#!/usr/bin/env python3
"""
Migration script to fix product_type values in DynamoDB.

This script fixes items where product_type contains full descriptions like
"Variable Frequency Drive" instead of just "drive".

Usage:
    uv run python scripts/migrate_product_types.py --table-name products [--dry-run]
"""

import argparse
import sys
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

from datasheetminer.config import REGION


def normalize_product_type(product_type: str) -> str:
    """Normalize product type to 'motor' or 'drive'.

    Args:
        product_type: The product type string from the database

    Returns:
        Normalized product type ('motor' or 'drive')

    Raises:
        ValueError: If product type cannot be normalized
    """
    product_type_lower = product_type.lower().strip()

    # Check for drive types
    if any(
        keyword in product_type_lower
        for keyword in ["drive", "vfd", "inverter", "servo drive"]
    ):
        return "drive"

    # Check for motor types
    if any(
        keyword in product_type_lower
        for keyword in ["motor", "servo motor", "induction"]
    ):
        return "motor"

    raise ValueError(f"Cannot determine product type from: {product_type}")


def migrate_items(table_name: str, dry_run: bool = False) -> None:
    """Migrate all items in the DynamoDB table.

    Args:
        table_name: Name of the DynamoDB table
        dry_run: If True, don't actually update items (just print what would be done)
    """
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(table_name)

    print(f"Scanning table '{table_name}'...")

    # Scan all items
    items_to_migrate: List[Dict[str, Any]] = []
    scan_kwargs: Dict[str, Any] = {}

    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])

        for item in items:
            old_product_type = item.get("product_type", "")
            old_pk = item.get("PK", "")

            # Skip if already correct
            if old_product_type in ["motor", "drive"]:
                continue

            try:
                new_product_type = normalize_product_type(old_product_type)
                new_pk = f"PRODUCT#{new_product_type.upper()}"

                items_to_migrate.append(
                    {
                        "old_pk": old_pk,
                        "old_sk": item.get("SK", ""),
                        "old_product_type": old_product_type,
                        "new_product_type": new_product_type,
                        "new_pk": new_pk,
                        "item": item,
                    }
                )
            except ValueError as e:
                print(f"⚠️  Warning: {e}")
                continue

        # Check if there are more items to scan
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    print(f"\nFound {len(items_to_migrate)} items to migrate:")
    print("=" * 80)

    for item_info in items_to_migrate:
        print(f"\nPK: {item_info['old_pk']} → {item_info['new_pk']}")
        print(f"SK: {item_info['old_sk']}")
        print(
            f"product_type: '{item_info['old_product_type']}' → '{item_info['new_product_type']}'"
        )

    if dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN - No items were actually modified")
        print("Run without --dry-run to perform the migration")
        return

    # Confirm migration
    print("\n" + "=" * 80)
    response = input(f"\nMigrate {len(items_to_migrate)} items? (yes/no): ")
    if response.lower() not in ["yes", "y"]:
        print("Migration cancelled")
        return

    # Perform migration
    print("\nMigrating items...")
    success_count = 0
    error_count = 0

    for item_info in items_to_migrate:
        try:
            # Delete old item
            table.delete_item(
                Key={"PK": item_info["old_pk"], "SK": item_info["old_sk"]}
            )

            # Update item fields
            new_item = item_info["item"].copy()
            new_item["product_type"] = item_info["new_product_type"]
            new_item["PK"] = item_info["new_pk"]

            # Put new item
            table.put_item(Item=new_item)

            print(f"✓ Migrated: {item_info['old_pk']} → {item_info['new_pk']}")
            success_count += 1

        except ClientError as e:
            print(
                f"✗ Error migrating {item_info['old_pk']}: {e.response['Error']['Message']}"
            )
            error_count += 1
            continue

    print("\n" + "=" * 80)
    print("Migration complete!")
    print(f"  Success: {success_count}")
    print(f"  Errors:  {error_count}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate product_type values in DynamoDB table"
    )
    parser.add_argument(
        "--table-name",
        default="products",
        help="DynamoDB table name (default: products)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually modifying data",
    )

    args = parser.parse_args()

    try:
        migrate_items(args.table_name, args.dry_run)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
