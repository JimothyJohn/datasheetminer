"""Utility to delete items from DynamoDB with flexible filtering.

This module provides functionality to delete items from DynamoDB based on
complex combinations of filters including manufacturer, product_type,
product_name, and product_family. Supports both dry-run and confirmed deletion.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError  # type: ignore

from datasheetminer.db.dynamo import DynamoDBClient


class DataDeleter:
    """Utility class to delete items from DynamoDB with flexible filtering."""

    db_client: DynamoDBClient
    table_name: str

    def __init__(self, table_name: str = "products") -> None:
        """Initialize DataDeleter with DynamoDB client.

        Args:
            table_name: Name of the DynamoDB table (default: "products")
        """
        self.db_client = DynamoDBClient(table_name=table_name)
        self.table_name = table_name

    def _build_filter_expression(
        self,
        manufacturer: Optional[str] = None,
        product_type: Optional[str] = None,
        product_name: Optional[str] = None,
        product_family: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Build DynamoDB filter expression from provided filters.

        Args:
            manufacturer: Filter by manufacturer name
            product_type: Filter by product type (motor, drive, etc.)
            product_name: Filter by product name
            product_family: Filter by product family

        Returns:
            Tuple of (filter_expression, expression_attribute_values)
            Returns (None, None) if no filters provided
        """
        filter_parts: List[str] = []
        attr_values: Dict[str, Any] = {}

        if manufacturer:
            filter_parts.append("manufacturer = :manufacturer")
            attr_values[":manufacturer"] = manufacturer

        if product_type:
            filter_parts.append("product_type = :product_type")
            attr_values[":product_type"] = product_type.lower()

        if product_name:
            filter_parts.append("product_name = :product_name")
            attr_values[":product_name"] = product_name

        if product_family:
            filter_parts.append("product_family = :product_family")
            attr_values[":product_family"] = product_family

        if not filter_parts:
            return None, None

        filter_expression: str = " AND ".join(filter_parts)
        return filter_expression, attr_values

    def query_items_to_delete(
        self,
        manufacturer: Optional[str] = None,
        product_type: Optional[str] = None,
        product_name: Optional[str] = None,
        product_family: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query items that match the specified filters.

        Args:
            manufacturer: Filter by manufacturer name
            product_type: Filter by product type (motor, drive, etc.)
            product_name: Filter by product name
            product_family: Filter by product family

        Returns:
            List of items matching the filters
        """
        filter_expr, filter_values = self._build_filter_expression(
            manufacturer, product_type, product_name, product_family
        )

        if not filter_expr:
            print("ERROR: At least one filter must be specified")
            return []

        try:
            # If product_type is specified, we can use query for efficiency
            if product_type:
                model_type: str = product_type.upper()
                pk_value: str = f"PRODUCT#{model_type}"

                query_kwargs: Dict[str, Any] = {
                    "KeyConditionExpression": "PK = :pk",
                    "ExpressionAttributeValues": {":pk": pk_value},
                }

                # Add additional filters if provided
                if manufacturer or product_name or product_family:
                    # Rebuild filter expression without product_type
                    additional_filter_parts: List[str] = []
                    additional_attr_values: Dict[str, Any] = {}

                    if manufacturer:
                        additional_filter_parts.append("manufacturer = :manufacturer")
                        additional_attr_values[":manufacturer"] = manufacturer

                    if product_name:
                        additional_filter_parts.append("product_name = :product_name")
                        additional_attr_values[":product_name"] = product_name

                    if product_family:
                        additional_filter_parts.append(
                            "product_family = :product_family"
                        )
                        additional_attr_values[":product_family"] = product_family

                    if additional_filter_parts:
                        query_kwargs["FilterExpression"] = " AND ".join(
                            additional_filter_parts
                        )
                        query_kwargs["ExpressionAttributeValues"].update(
                            additional_attr_values
                        )

                # Execute query
                response = self.db_client.table.query(**query_kwargs)
                items: List[Dict[str, Any]] = response.get("Items", [])

                # Handle pagination
                while "LastEvaluatedKey" in response:
                    query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                    response = self.db_client.table.query(**query_kwargs)
                    items.extend(response.get("Items", []))

            else:
                # No product_type - must use scan (less efficient)
                scan_kwargs: Dict[str, Any] = {
                    "FilterExpression": filter_expr,
                    "ExpressionAttributeValues": filter_values,
                }

                response = self.db_client.table.scan(**scan_kwargs)
                items = response.get("Items", [])

                # Handle pagination
                while "LastEvaluatedKey" in response:
                    scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                    response = self.db_client.table.scan(**scan_kwargs)
                    items.extend(response.get("Items", []))

            return items

        except ClientError as e:
            print(f"Error querying items: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            print(f"Unexpected error querying items: {e}")
            return []

    def delete_items(
        self,
        manufacturer: Optional[str] = None,
        product_type: Optional[str] = None,
        product_name: Optional[str] = None,
        product_family: Optional[str] = None,
        confirm: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Delete items matching the specified filters.

        WARNING: This is a destructive operation that cannot be undone!

        Safety measures:
        - Requires confirm=True parameter
        - Prompts for typed confirmation ("DELETE")
        - Shows item count and samples before deletion
        - Supports dry-run mode for testing

        Args:
            manufacturer: Filter by manufacturer name
            product_type: Filter by product type (motor, drive, etc.)
            product_name: Filter by product name
            product_family: Filter by product family
            confirm: Must be True to proceed with deletion (safety check)
            dry_run: If True, only show what would be deleted without deleting

        Returns:
            Dictionary with deletion results:
            {
                "items_found": Total items matching filters,
                "items_deleted": Number of items actually deleted,
                "filters_used": Dictionary of filters applied
            }

        Examples:
            # Dry run - see what would be deleted
            result = deleter.delete_items(manufacturer="ABB", dry_run=True)

            # Delete all products from a specific manufacturer
            result = deleter.delete_items(manufacturer="ABB", confirm=True)

            # Delete specific product type from manufacturer
            result = deleter.delete_items(
                manufacturer="Siemens",
                product_type="motor",
                confirm=True
            )

            # Delete specific product
            result = deleter.delete_items(
                manufacturer="Baldor",
                product_name="M3615T",
                confirm=True
            )
        """
        if not confirm and not dry_run:
            print("ERROR: delete_items() requires confirm=True parameter")
            print("This operation will delete items from the table!")
            print("Use dry_run=True to see what would be deleted")
            return {
                "items_found": 0,
                "items_deleted": 0,
                "filters_used": {},
            }

        # Build filter summary
        filters_used: Dict[str, Optional[str]] = {
            "manufacturer": manufacturer,
            "product_type": product_type,
            "product_name": product_name,
            "product_family": product_family,
        }

        # Remove None values
        filters_used = {k: v for k, v in filters_used.items() if v is not None}

        if not filters_used:
            print("ERROR: At least one filter must be specified")
            return {
                "items_found": 0,
                "items_deleted": 0,
                "filters_used": {},
            }

        # Query items to delete
        print("Querying items matching filters...")
        print(f"Filters: {filters_used}")
        print()

        items: List[Dict[str, Any]] = self.query_items_to_delete(
            manufacturer, product_type, product_name, product_family
        )

        item_count: int = len(items)
        print(f"Found {item_count} items matching filters")

        if item_count == 0:
            print("No items found - nothing to delete")
            return {
                "items_found": 0,
                "items_deleted": 0,
                "filters_used": filters_used,
            }

        # Show sample of items that will be deleted
        print("\nSample of items to be deleted:")
        for item in items[:5]:
            product_id: str = item.get("product_id", "N/A")
            manufacturer_name: str = item.get("manufacturer", "N/A")
            product_name_str: str = item.get("product_name", "N/A")
            product_type_str: str = item.get("product_type", "N/A")
            print(
                f"  - {product_id}: {manufacturer_name} {product_name_str} ({product_type_str})"
            )

        if item_count > 5:
            print(f"  ... and {item_count - 5} more items")
        print()

        # Dry run - just return the count
        if dry_run:
            print("DRY RUN - No items were deleted")
            return {
                "items_found": item_count,
                "items_deleted": 0,
                "filters_used": filters_used,
            }

        # Prompt for user confirmation
        print("=" * 80)
        print("⚠️  WARNING: YOU ARE ABOUT TO DELETE ITEMS FROM THE TABLE!")
        print("=" * 80)
        print(f"Table name: {self.table_name}")
        print(f"Items to delete: {item_count}")
        print(f"Filters: {filters_used}")
        print("\nThis operation CANNOT be undone!")
        print("\nType 'DELETE' (without quotes) to confirm:")

        user_input: str = input("> ").strip()

        if user_input != "DELETE":
            print("\nDeletion cancelled - confirmation text did not match")
            return {
                "items_found": item_count,
                "items_deleted": 0,
                "filters_used": filters_used,
            }

        # Perform deletion in batches
        print(f"\nDeleting {item_count} items...")
        deleted_count: int = 0
        batch_size: int = 25  # DynamoDB batch write limit

        try:
            for i in range(0, len(items), batch_size):
                batch = items[i : i + batch_size]

                with self.db_client.table.batch_writer() as writer:
                    for item in batch:
                        try:
                            writer.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
                            deleted_count += 1
                        except Exception as e:
                            print(f"Error deleting item: {e}")
                            continue

                # Progress indicator
                if deleted_count % 100 == 0 or deleted_count == item_count:
                    print(f"  Deleted {deleted_count}/{item_count} items...")

            print(f"\n✓ Successfully deleted {deleted_count} items")

            return {
                "items_found": item_count,
                "items_deleted": deleted_count,
                "filters_used": filters_used,
            }

        except ClientError as e:
            print(f"Error during deletion: {e.response['Error']['Message']}")
            return {
                "items_found": item_count,
                "items_deleted": deleted_count,
                "filters_used": filters_used,
            }
        except Exception as e:
            print(f"Unexpected error during deletion: {e}")
            return {
                "items_found": item_count,
                "items_deleted": deleted_count,
                "filters_used": filters_used,
            }


def main() -> int:
    """CLI entry point for the deleter utility."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Delete items from DynamoDB with flexible filtering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run - see what would be deleted by manufacturer
  uv run datasheetminer/db/deleter.py --manufacturer "ABB" --dry-run

  # Delete all products from a manufacturer
  uv run datasheetminer/db/deleter.py --manufacturer "ABB" --confirm

  # Delete specific product type from manufacturer
  uv run datasheetminer/db/deleter.py --manufacturer "Siemens" --product-type motor --confirm

  # Delete specific product by name
  uv run datasheetminer/db/deleter.py --manufacturer "Baldor" --product-name "M3615T" --confirm

  # Delete by product family
  uv run datasheetminer/db/deleter.py --manufacturer "ABB" --product-family "ACS880" --confirm

  # Complex query - manufacturer + type + family
  uv run datasheetminer/db/deleter.py \\
    --manufacturer "Siemens" \\
    --product-type drive \\
    --product-family "SINAMICS" \\
    --confirm

Environment Variables:
  AWS_ACCESS_KEY_ID        AWS access key
  AWS_SECRET_ACCESS_KEY    AWS secret key
  AWS_DEFAULT_REGION       AWS region (default: us-east-1)

Safety Features:
  - Requires --confirm flag to actually delete
  - Shows preview of items to be deleted
  - Requires typed confirmation ("DELETE")
  - Supports --dry-run for testing
  - At least one filter must be specified
        """,
    )

    parser.add_argument(
        "--table",
        type=str,
        default="products",
        help="DynamoDB table name (default: products)",
    )

    parser.add_argument(
        "--manufacturer",
        type=str,
        help="Filter by manufacturer name",
    )

    parser.add_argument(
        "--product-type",
        type=str,
        choices=["motor", "drive", "gearhead", "robot_arm"],
        help="Filter by product type",
    )

    parser.add_argument(
        "--product-name",
        type=str,
        help="Filter by product name",
    )

    parser.add_argument(
        "--product-family",
        type=str,
        help="Filter by product family",
    )

    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm deletion (required to actually delete)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting",
    )

    args: argparse.Namespace = parser.parse_args()

    # Check that at least one filter is specified
    if not any(
        [
            args.manufacturer,
            args.product_type,
            args.product_name,
            args.product_family,
        ]
    ):
        print("ERROR: At least one filter must be specified")
        print("Use --help for usage information")
        return 1

    # Initialize deleter
    deleter: DataDeleter = DataDeleter(table_name=args.table)

    try:
        # Delete items
        result: Dict[str, Any] = deleter.delete_items(
            manufacturer=args.manufacturer,
            product_type=args.product_type,
            product_name=args.product_name,
            product_family=args.product_family,
            confirm=args.confirm,
            dry_run=args.dry_run,
        )

        # Print summary
        print("\n" + "=" * 60)
        print("DELETION SUMMARY")
        print("=" * 60)
        print(f"Filters used:     {result['filters_used']}")
        print(f"Items found:      {result['items_found']}")
        print(f"Items deleted:    {result['items_deleted']}")

        if (
            result["items_deleted"] == result["items_found"]
            and result["items_found"] > 0
        ):
            print("\nStatus: All matching items deleted successfully!")
            return 0
        elif result["items_deleted"] > 0:
            print("\nStatus: Partial deletion")
            return 1
        elif result["items_found"] == 0:
            print("\nStatus: No items found matching filters")
            return 0
        else:
            print("\nStatus: No items deleted")
            return 1

    except Exception as e:
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
