#!/usr/bin/env python3
"""
Script to delete all items from the DynamoDB table.

WARNING: This is a destructive operation that cannot be undone!

Usage:
    # Dry run to see how many items would be deleted
    uv run python scripts/delete_all_items.py --dry-run

    # Actually delete all items (requires confirmation)
    uv run python scripts/delete_all_items.py --table-name products
"""

import argparse
import sys

from datasheetminer.db.dynamo import DynamoDBClient


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Delete all items from DynamoDB table",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
    # Dry run to see item count (safe - no deletion)
    uv run python scripts/delete_all_items.py --dry-run

    # Delete all items (requires typing "DELETE ALL" to confirm)
    uv run python scripts/delete_all_items.py --table-name products
        """,
    )
    parser.add_argument(
        "--table-name",
        default="products",
        help="DynamoDB table name (default: products)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count items without deleting (safe mode)",
    )

    args = parser.parse_args()

    # Create DynamoDB client
    client = DynamoDBClient(table_name=args.table_name)

    if args.dry_run:
        # Dry run mode - safe
        print("Running in DRY RUN mode - no items will be deleted")
        count = client.delete_all(dry_run=True)
        print(f"\nSummary: {count} items would be deleted")
        sys.exit(0)

    # Normal mode - will prompt for "DELETE ALL" confirmation
    deleted = client.delete_all(confirm=True)
    if deleted > 0:
        print(f"\n✓ Deletion complete: {deleted} items deleted")
    else:
        print("\nNo items were deleted")


if __name__ == "__main__":
    main()
