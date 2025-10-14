"""Utility to query and inspect DynamoDB table contents.

This module provides functionality to list, count, and inspect items
in DynamoDB tables to verify data has been correctly inserted.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from datasheetminer.db.dynamo import DynamoDBClient
from datasheetminer.models.drive import Drive
from datasheetminer.models.motor import Motor


class TableInspector:
    """Utility class to inspect DynamoDB table contents."""

    def __init__(self, table_name: str = "products"):
        """Initialize TableInspector with DynamoDB client.
        Args:
            table_name: Name of the DynamoDB table (default: "products")
        """
        self.db_client = DynamoDBClient(table_name=table_name)
        self.table_name = table_name

    def count_items(self) -> Dict[str, int]:
        """Count items in the table by type.

        Returns:
            Dictionary with counts by type
        """
        print(f"Counting items in table '{self.table_name}'...")

        # Get all items
        all_items = self.db_client.list_all()

        # Count by type
        motor_count = sum(1 for item in all_items if isinstance(item, Motor))
        drive_count = sum(1 for item in all_items if isinstance(item, Drive))

        return {
            "total": len(all_items),
            "motors": motor_count,
            "products": drive_count,
        }

    def list_items(
        self, item_type: str = "all", limit: int = 10, show_details: bool = False
    ) -> List[Dict[str, Any]]:
        """List items from the table.

        Args:
            item_type: Type of items to list ("all", "motor", "drive")
            limit: Maximum number of items to return
            show_details: Show full item details (default: False)

        Returns:
            List of item dictionaries
        """
        print(
            f"Listing {item_type} items from table '{self.table_name}' (limit: {limit})..."
        )

        if item_type == "all":
            items = self.db_client.list_all(limit=limit)
        elif item_type == "motor":
            items = self.db_client.list(Motor, limit=limit)
        elif item_type == "drive":
            items = self.db_client.list(Drive, limit=limit)
        else:
            raise ValueError(f"Invalid item type: {item_type}")

        # Convert to dictionaries
        results = []
        for item in items:
            if show_details:
                # Full model dump with JSON serialization
                item_dict = item.model_dump(by_alias=True, mode="json")
            else:
                # Summary only
                item_dict = {
                    "product_id": str(item.product_id),
                    "type": item.__class__.__name__,
                    "manufacturer": getattr(item, "manufacturer", "N/A"),
                    "part_number": getattr(item, "part_number", "N/A"),
                }

            results.append(item_dict)

        return results

    def get_item_by_id(self, item_id: str, item_type: str = "drive") -> Dict[str, Any]:
        """Get a specific item by ID.

        Args:
            item_id: ID of the item to retrieve
            item_type: Type of item ("motor" or "drive")

        Returns:
            Item dictionary or empty dict if not found
        """
        print(f"Retrieving {item_type} with ID: {item_id}...")

        model_class = Motor if item_type == "motor" else Drive
        item = self.db_client.read(item_id, model_class)

        if item:
            return item.model_dump(by_alias=True, mode="json")
        else:
            return {}

    def print_summary(self) -> None:
        """Print a summary of table contents."""
        print("\n" + "=" * 60)
        print(f"TABLE SUMMARY: {self.table_name}")
        print("=" * 60)

        counts = self.count_items()
        print(f"Total items:  {counts['total']}")
        print(f"Motors:       {counts['motors']}")
        print(f"products:       {counts['products']}")
        print()


def main() -> int:
    """CLI entry point for the query utility."""
    parser = argparse.ArgumentParser(
        description="Query and inspect DynamoDB table contents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show table summary
  uv run datasheetminer/query.py --table products --summary

  # List all items (summary view)
  uv run datasheetminer/query.py --table products --list

  # List products with full details
  uv run datasheetminer/query.py --table products --list --type drive --details

  # List first 5 motors
  uv run datasheetminer/query.py --table products --list --type motor --limit 5

  # Get specific item by ID
  uv run datasheetminer/query.py --table products --get <item-id> --type drive

Environment Variables:
  AWS_ACCESS_KEY_ID        AWS access key
  AWS_SECRET_ACCESS_KEY    AWS secret key
  AWS_DEFAULT_REGION       AWS region (default: us-east-1)
        """,
    )

    parser.add_argument(
        "--table",
        type=str,
        default="products",
        help="DynamoDB table name (default: products)",
    )

    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show table summary with counts",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List items from the table",
    )

    parser.add_argument(
        "--get",
        type=str,
        help="Get specific item by ID",
    )

    parser.add_argument(
        "--type",
        type=str,
        choices=["all", "motor", "drive"],
        default="all",
        help="Type of items to query (default: all)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of items to list (default: 10)",
    )

    parser.add_argument(
        "--details",
        action="store_true",
        help="Show full item details (default: summary only)",
    )

    args = parser.parse_args()

    # Initialize inspector
    inspector = TableInspector(table_name=args.table)

    try:
        if args.summary:
            # Show summary
            inspector.print_summary()

        elif args.list:
            # List items
            items = inspector.list_items(
                item_type=args.type, limit=args.limit, show_details=args.details
            )

            print(f"\nFound {len(items)} item(s):\n")

            if items:
                # Pretty print JSON
                print(json.dumps(items, indent=2))
            else:
                print("No items found in table")

        elif args.get:
            # Get specific item
            item = inspector.get_item_by_id(args.get, args.type)

            if item:
                print("\nItem found:\n")
                print(json.dumps(item, indent=2))
            else:
                print(f"\nItem not found: {args.get}")
                return 1

        else:
            # Default: show summary
            inspector.print_summary()

        return 0

    except Exception as e:
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
