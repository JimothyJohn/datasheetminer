"""DynamoDB interface for datasheet models.

This module provides CRUD operations for Product models in DynamoDB.
AWS credentials are expected to be configured via environment variables:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_DEFAULT_REGION (optional, defaults to us-east-1)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from uuid import UUID

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel

from datasheetminer.models.product import ProductBase
from datasheetminer.config import REGION

# Type variable for Pydantic models
T = TypeVar("T", bound=BaseModel)


class DynamoDBClient:
    """DynamoDB client with CRUD operations for datasheet models."""

    def __init__(self, table_name: str = "products"):
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

    def _serialize_item(self, model: Union[ProductBase]) -> Dict[str, Any]:
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

    def create(self, model: Union[ProductBase]) -> bool:
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
            id_str = str(product_id) if isinstance(product_id, UUID) else product_id

            # Determine PK and SK for deletion
            model_type = model_class.product_type.upper()
            pk = f"PRODUCT#{model_type}"
            sk = f"PRODUCT#{id_str}"

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
            model_type = model_class.model_fields["product_type"].default.upper()
            pk_value = f"PRODUCT#{model_type}"

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
            response = self.table.query(**query_kwargs)
            items = response.get("Items", [])

            # Handle pagination if needed (when no limit is specified)
            while "LastEvaluatedKey" in response and not limit:
                query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = self.table.query(**query_kwargs)
                items.extend(response.get("Items", []))

            # Deserialize items
            results = []
            for item in items:
                deserialized = self._deserialize_item(item, model_class)
                if deserialized:
                    results.append(deserialized)

            return results
        except ClientError as e:
            print(f"Error listing items: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            print(f"Unexpected error listing items: {e}")
            return []

    def batch_create(self, models: List[Union[ProductBase]]) -> int:
        """Create multiple items in DynamoDB using batch write.

        Args:
            models: List of Product instances

        Returns:
            Number of successfully created items
        """
        if not models:
            return 0

        try:
            success_count = 0

            # DynamoDB batch_write_item has a limit of 25 items per request
            batch_size = 25

            for i in range(0, len(models), batch_size):
                batch = models[i : i + batch_size]

                with self.table.batch_writer() as writer:
                    for model in batch:
                        try:
                            item = self._serialize_item(model)
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
