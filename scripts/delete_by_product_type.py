#!/usr/bin/env python3
"""
Script to delete all products of a specific type from DynamoDB.

AI-generated comment: This script provides a generic way to delete all products
of a given type (motor, drive, gearhead, robot_arm, etc.) from the DynamoDB table.
It uses the partition key to efficiently query all items of that type, then deletes
them using batch operations. Safety checks include dry-run mode and confirmation prompts.

Usage:
    # Dry run to see what would be deleted
    python scripts/delete_by_product_type.py motor

    # Actually delete with confirmation
    python scripts/delete_by_product_type.py motor --confirm

    # Delete drives
    python scripts/delete_by_product_type.py drive --confirm
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

from datasheetminer.config import REGION


def delete_by_product_type(
    product_type: str,
    table_name: str = "products",
    dry_run: bool = True,
) -> int:
    """Delete all products of a specific type from DynamoDB.

    AI-generated comment: This function queries the DynamoDB table using the
    partition key pattern (PRODUCT#<TYPE>) to retrieve all items of the specified
    product type, then deletes them in batches of 25 (DynamoDB's batch write limit).
    The function includes safety measures like confirmation prompts and dry-run mode.

    Args:
        product_type: The type of product to delete (e.g., 'motor', 'drive', 'gearhead')
        table_name: Name of the DynamoDB table (default: 'products')
        dry_run: If True, only count items without deleting them

    Returns:
        Number of items deleted (or counted if dry_run=True)

    Raises:
        ClientError: If there's an error communicating with DynamoDB
    """
    # AI-generated comment: Initialize DynamoDB client using boto3 resource API
    # for easier batch operations
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(table_name)

    # AI-generated comment: Construct the partition key based on the product type
    # All products of the same type share this PK in our single-table design
    pk_value = f"PRODUCT#{product_type.upper()}"

    print(f"Querying table '{table_name}' for product_type='{product_type}'...")
    print(f"Partition key: {pk_value}")

    # AI-generated comment: Query all items with this partition key
    # We only need PK and SK for deletion, so use ProjectionExpression for efficiency
    try:
        items: List[Dict[str, Any]] = []
        query_kwargs: Dict[str, Any] = {
            "KeyConditionExpression": "PK = :pk",
            "ExpressionAttributeValues": {":pk": pk_value},
            "ProjectionExpression": "PK, SK, manufacturer, product_name, part_number",
        }

        # AI-generated comment: Handle pagination to get all items
        while True:
            response = table.query(**query_kwargs)
            items.extend(response.get("Items", []))

            if "LastEvaluatedKey" not in response:
                break
            query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        item_count = len(items)
        print(f"Found {item_count} items with product_type='{product_type}'")

        if item_count == 0:
            print(f"No {product_type} products found - nothing to delete")
            return 0

        # AI-generated comment: Show sample of items that will be deleted
        print("\nSample of items to be deleted:")
        for item in items[:10]:
            manufacturer = item.get("manufacturer", "N/A")
            product_name = item.get("product_name", "N/A")
            part_number = item.get("part_number", "N/A")
            print(f"  - {manufacturer} {product_name} ({part_number})")
        if item_count > 10:
            print(f"  ... and {item_count - 10} more")

        # AI-generated comment: Dry run mode - just return the count
        if dry_run:
            print("\nDRY RUN - No items were deleted")
            print("Use --confirm flag to actually delete items")
            return item_count

        # AI-generated comment: Prompt for user confirmation with explicit text match
        print("\n" + "=" * 80)
        print(
            f"⚠️  WARNING: YOU ARE ABOUT TO DELETE ALL {product_type.upper()} PRODUCTS!"
        )
        print("=" * 80)
        print(f"Table name: {table_name}")
        print(f"Product type: {product_type}")
        print(f"Items to delete: {item_count}")
        print("\nThis operation CANNOT be undone!")
        print(f"\nType 'DELETE {product_type.upper()}' (without quotes) to confirm:")

        user_input = input("> ").strip()

        if user_input != f"DELETE {product_type.upper()}":
            print("\nDeletion cancelled - confirmation text did not match")
            return 0

        # AI-generated comment: Perform deletion in batches of 25 (DynamoDB limit)
        # Using batch_writer context manager for automatic batching and retries
        print(f"\nDeleting {item_count} items...")
        deleted_count = 0
        batch_size = 25

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]

            with table.batch_writer() as writer:
                for item in batch:
                    try:
                        writer.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
                        deleted_count += 1
                    except Exception as e:
                        print(f"Error deleting item {item.get('SK', 'unknown')}: {e}")
                        continue

            # AI-generated comment: Progress indicator every 50 items
            if deleted_count % 50 == 0:
                print(f"  Deleted {deleted_count}/{item_count} items...")

        print(f"\n✓ Successfully deleted {deleted_count} items")
        return deleted_count

    except ClientError as e:
        print(f"Error querying/deleting items: {e.response['Error']['Message']}")
        return 0
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 0


def main() -> None:
    """Main entry point for the script.

    AI-generated comment: Parse command-line arguments and execute the deletion.
    Requires at least one argument (product_type). The --confirm flag controls
    whether to actually delete items or just perform a dry run.
    """
    if len(sys.argv) < 2:
        print("Usage: python delete_by_product_type.py <product_type> [--confirm]")
        print("\nExamples:")
        print("  python delete_by_product_type.py motor         # Dry run")
        print("  python delete_by_product_type.py motor --confirm  # Actually delete")
        print("  python delete_by_product_type.py drive --confirm")
        print("  python delete_by_product_type.py gearhead --confirm")
        print("  python delete_by_product_type.py robot_arm --confirm")
        sys.exit(1)

    product_type = sys.argv[1].lower()
    confirm = "--confirm" in sys.argv

    if not confirm:
        print("=" * 80)
        print("Running in DRY RUN mode (no deletions will occur)")
        print("Use --confirm flag to actually delete items")
        print("=" * 80)
        print()

    delete_by_product_type(product_type, dry_run=not confirm)


if __name__ == "__main__":
    main()
