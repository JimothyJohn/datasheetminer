"""DynamoDB interface for datasheet models.

This module provides CRUD operations for Product models in DynamoDB.
AWS credentials are expected to be configured via environment variables:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_DEFAULT_REGION (optional, defaults to us-east-1)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Type, TypeVar, Union

from uuid import UUID

import boto3  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

from datasheetminer.config import REGION
from datasheetminer.models.drive import Drive
from datasheetminer.models.motor import Motor
from datasheetminer.models.product import ProductBase


# Type variable for Pydantic models
T = TypeVar("T", bound=ProductBase)


class DynamoDBClient:
    """DynamoDB client with CRUD operations for datasheet models."""

    table_name: str
    dynamodb: Any  # boto3 DynamoDB resource
    table: Any  # boto3 DynamoDB table

    def __init__(self, table_name: str = "products") -> None:
        """Initialize DynamoDB client.
        Args:
            table_name: Name of the DynamoDB table (default: "products")
        """
        self.table_name = table_name

        # Initialize DynamoDB resource
        # Credentials are automatically loaded from environment variables:
        # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN (optional)
        self.dynamodb = boto3.resource("dynamodb", region_name=REGION)
        self.table = self.dynamodb.Table(table_name)

    def _convert_floats_to_decimal(self, obj: Any) -> Any:
        """Recursively convert float values to Decimal for DynamoDB compatibility.

        Args:
            obj: Object to convert (dict, list, or primitive)

        Returns:
            Converted object with floats replaced by Decimals
        """
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(item) for item in obj]
        else:
            return obj

    def _serialize_item(self, model: ProductBase) -> Dict[str, Any]:
        """Convert Pydantic model to DynamoDB item format.

        Args:
            model: Product instance

        Returns:
            Dictionary ready for DynamoDB insertion
        """
        # Use model_dump without by_alias to get field names as defined (id, not _id)
        data = model.model_dump(by_alias=False, exclude_none=True)

        # Convert UUID to string for DynamoDB
        if "product_id" in data and isinstance(data["product_id"], UUID):
            data["product_id"] = str(data["product_id"])

        # Add product type for querying
        data["product_type"] = model.product_type

        # Add PK and SK for single-table design
        model_type: str = model.product_type.upper()
        product_id_str: str = str(data.get("product_id", ""))
        data["PK"] = f"PRODUCT#{model_type}"
        data["SK"] = f"PRODUCT#{product_id_str}"

        # Convert all float values to Decimal for DynamoDB compatibility
        data = self._convert_floats_to_decimal(data)

        return data

    def _deserialize_item(
        self, item: Dict[str, Any], model_class: Type[T]
    ) -> Optional[T]:
        """Convert DynamoDB item to Pydantic model.

        Args:
            item: DynamoDB item dictionary
            model_class: Pydantic model class to deserialize into

        Returns:
            Model instance or None if deserialization fails
        """
        try:
            return model_class.model_validate(item, strict=False)
        except Exception as e:
            print(f"Error deserializing item: {e}")
            return None

    def create(self, model: ProductBase) -> bool:
        """Create a new item in DynamoDB.

        Args:
            model: Product instance

        Returns:
            True if successful, False otherwise
        """
        try:
            item = self._serialize_item(model)
            self.table.put_item(Item=item)
            return True
        except ClientError as e:
            print(f"Error creating item: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            print(f"Unexpected error creating item: {e}")
            return False

    def read(self, product_id: Union[str, UUID], model_class: Type[T]) -> Optional[T]:
        """Read an item from DynamoDB by ID.
        Args:
            product_id: UUID or string ID of the item
            model_class: Product class
        Returns:
            Model instance or None if not found
        """
        try:
            # Convert UUID to string if necessary
            id_str = str(product_id) if isinstance(product_id, UUID) else product_id

            # Determine PK and SK based on the new schema
            model_type = model_class.product_type.upper()
            pk = f"PRODUCT#{model_type}"
            sk = f"PRODUCT#{id_str}"

            response = self.table.get_item(Key={"PK": pk, "SK": sk})

            if "Item" not in response:
                return None

            return self._deserialize_item(response["Item"], model_class)
        except ClientError as e:
            print(f"Error reading item: {e.response['Error']['Message']}")
            return None
        except Exception as e:
            print(f"Unexpected error reading item: {e}")
            return None

    def product_exists(
        self,
        product_type: str,
        manufacturer: str,
        product_name: str,
        model_class: Type[T],
    ) -> bool:
        """Check if a product with the given type, manufacturer, and name already exists.

        AI-generated comment: This method checks for duplicate products by querying the
        table partition for the specific product_type and filtering by both manufacturer
        and product_name. This provides enhanced precision to handle cases where multiple
        manufacturers might have products with identical names.
        It returns True if at least one matching product exists, False otherwise.
        This is used to avoid redundant scraping of products already in the database.

        Args:
            product_type: The type of the product (e.g., "motor", "drive", "robot_arm").
            manufacturer: The manufacturer of the product.
            product_name: The name of the product.
            model_class: The Pydantic model class to use for validation.

        Returns:
            True if product exists, False otherwise.
        """
        try:
            # AI-generated comment: Use the PK to query only items of the specific product type,
            # then filter by both manufacturer and product_name for enhanced precision.
            model_type: str = product_type.upper()
            pk_value: str = f"PRODUCT#{model_type}"

            response = self.table.query(
                KeyConditionExpression="PK = :pk",
                FilterExpression="manufacturer = :manufacturer AND product_name = :product_name",
                ExpressionAttributeValues={
                    ":pk": pk_value,
                    ":manufacturer": manufacturer,
                    ":product_name": product_name,
                },
                Limit=1,  # We only need to know if at least one exists
            )

            # Return True if we found at least one matching item
            return bool(response.get("Items"))

        except ClientError as e:
            print(f"Error checking if product exists: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            print(f"Unexpected error checking if product exists: {e}")
            return False

    def update(self, model: ProductBase) -> bool:
        """Update an existing item in DynamoDB.

        Args:
            model: Product instance with updated data

        Returns:
            True if successful, False otherwise
        """
        try:
            item = self._serialize_item(model)

            # Extract PK and SK for the update key
            pk = item.pop("PK")
            sk = item.pop("SK")

            # Build update expression
            update_expr_parts = []
            expr_attr_names = {}
            expr_attr_values = {}

            for key, value in item.items():
                # Use attribute name placeholders to handle reserved words
                placeholder = f"#{key}"
                value_placeholder = f":{key}"

                update_expr_parts.append(f"{placeholder} = {value_placeholder}")
                expr_attr_names[placeholder] = key
                expr_attr_values[value_placeholder] = value

            update_expression = "SET " + ", ".join(update_expr_parts)

            self.table.update_item(
                Key={"PK": pk, "SK": sk},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values,
            )
            return True
        except ClientError as e:
            print(f"Error updating item: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            print(f"Unexpected error updating item: {e}")
            return False

    def delete(
        self, product_id: Union[str, UUID], model_class: Type[ProductBase]
    ) -> bool:
        """Delete an item from DynamoDB.
        Args:
            product_id: UUID or string ID of the item to delete
            model_class: The class of the product to delete.
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert UUID to string if necessary
            id_str: str = (
                str(product_id) if isinstance(product_id, UUID) else product_id
            )

            # Determine PK and SK for deletion
            model_type: str = model_class.product_type.upper()
            pk: str = f"PRODUCT#{model_type}"
            sk: str = f"PRODUCT#{id_str}"

            self.table.delete_item(Key={"PK": pk, "SK": sk})
            return True
        except ClientError as e:
            print(f"Error deleting item: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            print(f"Unexpected error deleting item: {e}")
            return False

    def list(
        self,
        model_class: Type[T],
        limit: Optional[int] = None,
        filter_expr: Optional[str] = None,
        filter_values: Optional[Dict[str, Any]] = None,
    ) -> List[T]:
        """List items from DynamoDB with optional filtering.
        Args:
            model_class: Product class
            limit: Maximum number of items to return (optional)
            filter_expr: DynamoDB filter expression (optional)
            filter_values: Values for filter expression (optional)
        Returns:
            List of model instances
        """
        try:
            # Build query parameters
            query_kwargs: Dict[str, Any] = {}

            # Filter by model type using the model's default value for product_type
            model_type: str = model_class.model_fields["product_type"].default.upper()
            pk_value: str = f"PRODUCT#{model_type}"

            query_kwargs["KeyConditionExpression"] = "PK = :pk"
            query_kwargs["ExpressionAttributeValues"] = {":pk": pk_value}

            # Add additional filter if provided
            if filter_expr and filter_values:
                query_kwargs["FilterExpression"] = filter_expr
                query_kwargs["ExpressionAttributeValues"].update(filter_values)

            # Add limit if provided
            if limit:
                query_kwargs["Limit"] = limit

            # Perform query
            response: Dict[str, Any] = self.table.query(**query_kwargs)
            items: List[Dict[str, Any]] = response.get("Items", [])

            # Handle pagination if needed (when no limit is specified)
            while "LastEvaluatedKey" in response and not limit:
                query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = self.table.query(**query_kwargs)
                items.extend(response.get("Items", []))

            # Deserialize items
            results: List[T] = []
            for item in items:
                deserialized: Optional[T] = self._deserialize_item(item, model_class)
                if deserialized:
                    results.append(deserialized)

            return results
        except ClientError as e:
            print(f"Error listing items: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            print(f"Unexpected error listing items: {e}")
            return []

    def list_all(self, limit: Optional[int] = None) -> List[ProductBase]:
        """List all items from DynamoDB with optional limit, using scan.

        Args:
            limit: Maximum number of items to return (optional)

        Returns:
            List of model instances
        """
        try:
            scan_kwargs: Dict[str, Any] = {}
            if limit:
                scan_kwargs["Limit"] = limit

            response = self.table.scan(**scan_kwargs)
            items = response.get("Items", [])

            while "LastEvaluatedKey" in response and not limit:
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = self.table.scan(**scan_kwargs)
                items.extend(response.get("Items", []))

            results: List[ProductBase] = []
            model_map: Dict[str, Type[ProductBase]] = {
                "motor": Motor,
                "drive": Drive,
            }

            for item in items:
                product_type = item.get("product_type")
                if not product_type:
                    continue

                model_class = model_map.get(product_type.lower())
                if model_class:
                    deserialized = self._deserialize_item(item, model_class)
                    if deserialized:
                        results.append(deserialized)
            return results
        except ClientError as e:
            print(f"Error listing all items: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            print(f"Unexpected error listing all items: {e}")
            return []

    def batch_create(self, models: Sequence[ProductBase]) -> int:
        """Create multiple items in DynamoDB using batch write.

        Args:
            models: List of Product instances

        Returns:
            Number of successfully created items
        """
        if not models:
            return 0

        try:
            success_count: int = 0

            # DynamoDB batch_write_item has a limit of 25 items per request
            batch_size: int = 25

            for i in range(0, len(models), batch_size):
                batch: Sequence[ProductBase] = models[i : i + batch_size]

                with self.table.batch_writer() as writer:
                    for model in batch:
                        try:
                            item: Dict[str, Any] = self._serialize_item(model)
                            writer.put_item(Item=item)
                            success_count += 1
                        except Exception as e:
                            print(f"Error in batch item: {e}")
                            continue

            return success_count
        except ClientError as e:
            print(f"Error in batch create: {e.response['Error']['Message']}")
            return success_count
        except Exception as e:
            print(f"Unexpected error in batch create: {e}")
            return success_count

    def delete_all(self, confirm: bool = False, dry_run: bool = False) -> int:
        """Delete ALL items from the DynamoDB table.

        WARNING: This is an extremely destructive operation that cannot be undone!
        All data in the table will be permanently deleted.

        Safety measures:
        - Requires confirm=True parameter
        - Prompts for typed confirmation ("DELETE ALL")
        - Shows item count before deletion
        - Supports dry-run mode for testing

        Args:
            confirm: Must be True to proceed with deletion (safety check)
            dry_run: If True, only count items without deleting them

        Returns:
            Number of items deleted (or counted if dry_run=True)

        Example:
            # Dry run to see how many items would be deleted
            count = client.delete_all(dry_run=True)
            print(f"Would delete {count} items")

            # Actually delete all items (requires confirmation)
            deleted = client.delete_all(confirm=True)
        """
        if not confirm and not dry_run:
            print("ERROR: delete_all() requires confirm=True parameter")
            print("This operation will delete ALL items from the table!")
            print("Use dry_run=True to see item count without deleting")
            return 0

        try:
            # Scan the entire table to get all items
            print(f"Scanning table '{self.table_name}'...")
            items: List[Dict[str, Any]] = []
            scan_kwargs: Dict[str, Any] = {
                "ProjectionExpression": "PK, SK"  # Only fetch keys for efficiency
            }

            while True:
                response = self.table.scan(**scan_kwargs)
                items.extend(response.get("Items", []))

                if "LastEvaluatedKey" not in response:
                    break
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

            item_count: int = len(items)
            print(f"Found {item_count} items in table '{self.table_name}'")

            # Dry run - just return the count
            if dry_run:
                print("DRY RUN - No items were deleted")
                return item_count

            # No items to delete
            if item_count == 0:
                print("Table is already empty")
                return 0

            # Prompt for user confirmation
            print("\n" + "=" * 80)
            print("⚠️  WARNING: YOU ARE ABOUT TO DELETE ALL DATA FROM THE TABLE!")
            print("=" * 80)
            print(f"Table name: {self.table_name}")
            print(f"Items to delete: {item_count}")
            print("\nThis operation CANNOT be undone!")
            print("\nType 'DELETE ALL' (without quotes) to confirm:")

            user_input: str = input("> ").strip()

            if user_input != "DELETE ALL":
                print("\nDeletion cancelled - confirmation text did not match")
                return 0

            # Perform deletion in batches
            print(f"\nDeleting {item_count} items...")
            deleted_count: int = 0
            batch_size: int = 25  # DynamoDB batch write limit

            for i in range(0, len(items), batch_size):
                batch = items[i : i + batch_size]

                with self.table.batch_writer() as writer:
                    for item in batch:
                        try:
                            writer.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
                            deleted_count += 1
                        except Exception as e:
                            print(f"Error deleting item: {e}")
                            continue

                # Progress indicator
                if deleted_count % 100 == 0:
                    print(f"  Deleted {deleted_count}/{item_count} items...")

            print(f"\n✓ Successfully deleted {deleted_count} items")
            return deleted_count

        except ClientError as e:
            print(f"Error during delete_all: {e.response['Error']['Message']}")
            return 0
        except Exception as e:
            print(f"Unexpected error during delete_all: {e}")
            return 0

    def delete_duplicates(
        self, confirm: bool = False, dry_run: bool = False, keep: str = "first"
    ) -> Dict[str, int]:
        """Delete duplicate items based on part_number, keeping one copy.

        WARNING: This is a destructive operation that cannot be undone!
        Duplicate items will be permanently deleted based on part_number.

        Strategy:
        - Groups items by part_number
        - For each group with duplicates, keeps one item and deletes the rest
        - "keep" parameter determines which item to keep:
          - "first": Keep first item scanned (default)
          - "last": Keep last item scanned
          - "newest": Keep item with most recent product_id (UUID timestamp)

        Safety measures:
        - Requires confirm=True parameter
        - Prompts for typed confirmation ("DELETE DUPLICATES")
        - Shows duplicate count before deletion
        - Supports dry-run mode for testing

        Args:
            confirm: Must be True to proceed with deletion (safety check)
            dry_run: If True, only identify duplicates without deleting
            keep: Which item to keep - "first", "last", or "newest" (default: "first")

        Returns:
            Dictionary with counts:
            {
                "total_items": Total items scanned,
                "unique_part_numbers": Number of unique part numbers,
                "duplicate_groups": Number of part numbers with duplicates,
                "duplicates_found": Total duplicate items found,
                "duplicates_deleted": Number of items actually deleted
            }

        Example:
            # Dry run to see duplicate count
            stats = client.delete_duplicates(dry_run=True)
            print(f"Found {stats['duplicates_found']} duplicates")

            # Delete duplicates, keeping the first occurrence
            stats = client.delete_duplicates(confirm=True, keep="first")

            # Delete duplicates, keeping the newest by UUID
            stats = client.delete_duplicates(confirm=True, keep="newest")
        """
        if not confirm and not dry_run:
            print("ERROR: delete_duplicates() requires confirm=True parameter")
            print("This operation will delete duplicate items from the table!")
            print("Use dry_run=True to see duplicate count without deleting")
            return {
                "total_items": 0,
                "unique_part_numbers": 0,
                "duplicate_groups": 0,
                "duplicates_found": 0,
                "duplicates_deleted": 0,
            }

        if keep not in ["first", "last", "newest"]:
            print(f"ERROR: Invalid keep parameter '{keep}'")
            print("Must be 'first', 'last', or 'newest'")
            return {
                "total_items": 0,
                "unique_part_numbers": 0,
                "duplicate_groups": 0,
                "duplicates_found": 0,
                "duplicates_deleted": 0,
            }

        try:
            # Scan the entire table
            print(f"Scanning table '{self.table_name}' for duplicates...")
            items: List[Dict[str, Any]] = []
            scan_kwargs: Dict[str, Any] = {}

            while True:
                response = self.table.scan(**scan_kwargs)
                items.extend(response.get("Items", []))

                if "LastEvaluatedKey" not in response:
                    break
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

            total_items: int = len(items)
            print(f"Found {total_items} total items")

            # Group items by part_number
            from collections import defaultdict

            groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

            for item in items:
                part_number = item.get("part_number")
                if part_number:  # Only group items that have a part_number
                    groups[part_number].append(item)

            # Find duplicates
            duplicate_groups: List[tuple[str, List[Dict[str, Any]]]] = []
            duplicates_found: int = 0

            for part_number, group_items in groups.items():
                if len(group_items) > 1:
                    duplicate_groups.append((part_number, group_items))
                    duplicates_found += len(group_items) - 1  # All but one

            unique_part_numbers: int = len(groups)
            duplicate_group_count: int = len(duplicate_groups)

            print(f"Found {unique_part_numbers} unique part numbers")
            print(f"Found {duplicate_group_count} part numbers with duplicates")
            print(f"Total duplicate items to delete: {duplicates_found}")

            # Show detailed breakdown
            if duplicate_groups:
                print("\nDuplicate breakdown:")
                for part_number, group_items in sorted(
                    duplicate_groups, key=lambda x: len(x[1]), reverse=True
                )[:10]:
                    print(f"  - '{part_number}': {len(group_items)} copies")
                if len(duplicate_groups) > 10:
                    print(f"  ... and {len(duplicate_groups) - 10} more")

            # Dry run - just return the stats
            if dry_run:
                print("\nDRY RUN - No items were deleted")
                return {
                    "total_items": total_items,
                    "unique_part_numbers": unique_part_numbers,
                    "duplicate_groups": duplicate_group_count,
                    "duplicates_found": duplicates_found,
                    "duplicates_deleted": 0,
                }

            # No duplicates to delete
            if duplicates_found == 0:
                print("\nNo duplicates found - nothing to delete")
                return {
                    "total_items": total_items,
                    "unique_part_numbers": unique_part_numbers,
                    "duplicate_groups": 0,
                    "duplicates_found": 0,
                    "duplicates_deleted": 0,
                }

            # Prompt for user confirmation
            print("\n" + "=" * 80)
            print("⚠️  WARNING: YOU ARE ABOUT TO DELETE DUPLICATE ITEMS!")
            print("=" * 80)
            print(f"Table name: {self.table_name}")
            print(f"Duplicate items to delete: {duplicates_found}")
            print(f"Keep strategy: {keep}")
            print("\nThis operation CANNOT be undone!")
            print("\nType 'DELETE DUPLICATES' (without quotes) to confirm:")

            user_input: str = input("> ").strip()

            if user_input != "DELETE DUPLICATES":
                print("\nDeletion cancelled - confirmation text did not match")
                return {
                    "total_items": total_items,
                    "unique_part_numbers": unique_part_numbers,
                    "duplicate_groups": duplicate_group_count,
                    "duplicates_found": duplicates_found,
                    "duplicates_deleted": 0,
                }

            # Determine which items to delete
            items_to_delete: List[Dict[str, Any]] = []

            for part_number, group_items in duplicate_groups:
                # Sort items based on keep strategy
                if keep == "last":
                    # Keep last item
                    items_to_delete.extend(group_items[:-1])
                elif keep == "newest":
                    # Keep item with newest product_id (UUID v4 has timestamp component)
                    sorted_items = sorted(
                        group_items,
                        key=lambda x: str(x.get("product_id", "")),
                        reverse=True,
                    )
                    items_to_delete.extend(sorted_items[1:])
                else:  # first (default)
                    # Keep first item
                    items_to_delete.extend(group_items[1:])

            # Perform deletion in batches
            print(f"\nDeleting {len(items_to_delete)} duplicate items...")
            deleted_count: int = 0
            batch_size: int = 25  # DynamoDB batch write limit

            for i in range(0, len(items_to_delete), batch_size):
                batch = items_to_delete[i : i + batch_size]

                with self.table.batch_writer() as writer:
                    for item in batch:
                        try:
                            writer.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
                            deleted_count += 1
                        except Exception as e:
                            print(f"Error deleting item: {e}")
                            continue

                # Progress indicator
                if deleted_count % 100 == 0:
                    print(f"  Deleted {deleted_count}/{len(items_to_delete)} items...")

            print(f"\n✓ Successfully deleted {deleted_count} duplicate items")

            return {
                "total_items": total_items,
                "unique_part_numbers": unique_part_numbers,
                "duplicate_groups": duplicate_group_count,
                "duplicates_found": duplicates_found,
                "duplicates_deleted": deleted_count,
            }

        except ClientError as e:
            print(f"Error during delete_duplicates: {e.response['Error']['Message']}")
            return {
                "total_items": 0,
                "unique_part_numbers": 0,
                "duplicate_groups": 0,
                "duplicates_found": 0,
                "duplicates_deleted": 0,
            }
        except Exception as e:
            print(f"Unexpected error during delete_duplicates: {e}")
            return {
                "total_items": 0,
                "unique_part_numbers": 0,
                "duplicate_groups": 0,
                "duplicates_found": 0,
                "duplicates_deleted": 0,
            }
