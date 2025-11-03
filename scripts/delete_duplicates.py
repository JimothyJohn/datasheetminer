#!/usr/bin/env python3
"""
Script to delete duplicate items based on part_number.

WARNING: This is a destructive operation that cannot be undone!

Usage:
    # Dry run to see duplicate count
    uv run python scripts/delete_duplicates.py --dry-run

    # Delete duplicates, keeping the first occurrence
    uv run python scripts/delete_duplicates.py --table-name products

    # Delete duplicates, keeping the newest by UUID
    uv run python scripts/delete_duplicates.py --table-name products --keep newest
"""

import argparse
import sys

from datasheetminer.db.dynamo import DynamoDBClient


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Delete duplicate items based on part_number",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
    # Dry run to see duplicate count (safe - no deletion)
    uv run python scripts/delete_duplicates.py --dry-run

    # Delete duplicates, keep first occurrence (requires confirmation)
    uv run python scripts/delete_duplicates.py --table-name products

    # Delete duplicates, keep newest by UUID
    uv run python scripts/delete_duplicates.py --table-name products --keep newest

    # Delete duplicates, keep last occurrence scanned
    uv run python scripts/delete_duplicates.py --table-name products --keep last

Keep strategies:
    first   - Keep the first item found during scan (default)
    last    - Keep the last item found during scan
    newest  - Keep item with newest product_id (UUID timestamp)
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
        help="Identify duplicates without deleting (safe mode)",
    )
    parser.add_argument(
        "--keep",
        choices=["first", "last", "newest"],
        default="first",
        help="Which item to keep when duplicates found (default: first)",
    )

    args = parser.parse_args()

    # Create DynamoDB client
    client = DynamoDBClient(table_name=args.table_name)

    if args.dry_run:
        # Dry run mode - safe
        print("Running in DRY RUN mode - no items will be deleted\n")
        stats = client.delete_duplicates(dry_run=True)

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total items:          {stats['total_items']}")
        print(f"Unique part numbers:  {stats['unique_part_numbers']}")
        print(f"Duplicate groups:     {stats['duplicate_groups']}")
        print(f"Duplicates found:     {stats['duplicates_found']}")
        print(f"Would be deleted:     {stats['duplicates_found']}")
        sys.exit(0)

    # Normal mode - will prompt for "DELETE DUPLICATES" confirmation
    print(f"Keep strategy: {args.keep}\n")
    stats = client.delete_duplicates(confirm=True, keep=args.keep)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total items:          {stats['total_items']}")
    print(f"Unique part numbers:  {stats['unique_part_numbers']}")
    print(f"Duplicate groups:     {stats['duplicate_groups']}")
    print(f"Duplicates found:     {stats['duplicates_found']}")
    print(f"Duplicates deleted:   {stats['duplicates_deleted']}")

    if stats["duplicates_deleted"] > 0:
        print(f"\n✓ Successfully deleted {stats['duplicates_deleted']} duplicate items")
    else:
        print("\nNo duplicates were deleted")


if __name__ == "__main__":
    main()
