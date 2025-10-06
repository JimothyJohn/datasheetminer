"""
Generic CRUD framework for AWS DynamoDB tables.

This module provides a DynamoDBHandler class to simplify Create, Read, Update, and Delete
operations for a DynamoDB table. It uses the Boto3 resource API for a higher-level,
object-oriented interface to DynamoDB.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# AI-generated comment: Initialize logger for the module. This will inherit the configuration
# from the root logger, which should be configured at the application's entry point.
logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")


class DynamoDBHandler:
    """
    A handler for CRUD operations on a single DynamoDB table.

    AI-generated comment: This class abstracts the Boto3 DynamoDB resource API
    to provide simple methods for common database operations. It automatically
    fetches the table's key schema on initialization.
    """

    def __init__(self, table_name: str, region_name: str = AWS_REGION):
        """
        Initializes the DynamoDBHandler for a specific table.

        Args:
            table_name (str): The name of the DynamoDB table.
            region_name (str): The AWS region of the DynamoDB table.
        """
        try:
            self.table_name = table_name
            # AI-generated comment: Use the Boto3 resource API for easier item handling.
            self.dynamodb_resource = boto3.resource("dynamodb", region_name=region_name)
            self.table = self.dynamodb_resource.Table(table_name)
            self.key_schema = self.table.key_schema
            self.hash_key = self.key_schema[0]["AttributeName"]
            self.range_key = (
                self.key_schema[1]["AttributeName"]
                if len(self.key_schema) > 1
                else None
            )
            logger.info(
                f"DynamoDBHandler initialized for table '{table_name}' in region '{region_name}'"
            )
            logger.info(f"Table keys: Hash={self.hash_key}, Range={self.range_key}")
        except ClientError as e:
            logger.error(
                f"Failed to initialize DynamoDBHandler for table {table_name}: {e}"
            )
            raise

    def create_item(
        self, item: Dict[str, Any], overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new item in the DynamoDB table.

        Args:
            item (Dict[str, Any]): The item to create, as a Python dictionary.
            overwrite (bool): If True, it will overwrite an existing item with the same key.
                              If False, it will fail if an item with the same key exists.

        Returns:
            Dict[str, Any]: The response from DynamoDB's put_item call.

        Raises:
            ClientError: If the item already exists and overwrite is False, or for other
                         DynamoDB service errors.
        """
        try:
            put_args = {"Item": item}
            if not overwrite:
                # AI-generated comment: Use a condition expression to prevent overwriting existing items.
                put_args["ConditionExpression"] = (
                    f"attribute_not_exists({self.hash_key})"
                )

            response = self.table.put_item(**put_args)
            logger.info(f"Successfully created item in {self.table_name}.")
            return response
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    f"Item with primary key already exists in {self.table_name}."
                )
            else:
                logger.error(f"Failed to create item in {self.table_name}: {e}")
            raise

    def get_item(self, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single item by its key from the DynamoDB table.

        Args:
            key (Dict[str, Any]): A dictionary representing the primary key of the item.

        Returns:
            Optional[Dict[str, Any]]: The retrieved item as a dictionary, or None if not found.

        Raises:
            ClientError: For DynamoDB service errors.
        """
        try:
            response = self.table.get_item(Key=key)
            item = response.get("Item")
            if item:
                logger.info(
                    f"Successfully retrieved item with key {key} from {self.table_name}."
                )
            else:
                logger.info(f"Item with key {key} not found in {self.table_name}.")
            return item
        except ClientError as e:
            logger.error(
                f"Failed to get item with key {key} from {self.table_name}: {e}"
            )
            raise

    def update_item(
        self, key: Dict[str, Any], updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing item in the DynamoDB table.

        Args:
            key (Dict[str, Any]): The primary key of the item to update.
            updates (Dict[str, Any]): A dictionary of attribute names and their new values.

        Returns:
            Dict[str, Any]: The response from DynamoDB's update_item call.

        Raises:
            ClientError: If the item does not exist, or for other DynamoDB service errors.
        """
        # AI-generated comment: Dynamically build the UpdateExpression to apply specified changes.
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}

        key_names = [k["AttributeName"] for k in self.key_schema]

        for field, value in updates.items():
            if field in key_names:
                logger.warning(f"Skipping update of key attribute '{field}'")
                continue

            name_placeholder = f"#{field}"
            value_placeholder = f":{field}"
            update_expression_parts.append(f"{name_placeholder} = {value_placeholder}")
            expression_attribute_names[name_placeholder] = field
            expression_attribute_values[value_placeholder] = value

        if not update_expression_parts:
            logger.warning("No valid fields to update provided.")
            return {"error": "No valid fields provided for update."}

        update_expression = "SET " + ", ".join(update_expression_parts)

        try:
            response = self.table.update_item(
                Key=key,
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ConditionExpression=f"attribute_exists({self.hash_key})",
                ReturnValues="UPDATED_NEW",
            )
            logger.info(
                f"Successfully updated item with key {key} in {self.table_name}."
            )
            return response
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    f"Item with key {key} not found for update in {self.table_name}."
                )
            else:
                logger.error(
                    f"Failed to update item with key {key} in {self.table_name}: {e}"
                )
            raise

    def delete_item(self, key: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete an item from the DynamoDB table.

        Args:
            key (Dict[str, Any]): The primary key of the item to delete.

        Returns:
            Dict[str, Any]: The response from DynamoDB's delete_item call.

        Raises:
            ClientError: If the item does not exist, or for other DynamoDB service errors.
        """
        try:
            response = self.table.delete_item(
                Key=key, ConditionExpression=f"attribute_exists({self.hash_key})"
            )
            logger.info(
                f"Successfully deleted item with key {key} from {self.table_name}."
            )
            return response
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    f"Item with key {key} not found for deletion in {self.table_name}."
                )
            else:
                logger.error(
                    f"Failed to delete item with key {key} from {self.table_name}: {e}"
                )
            raise

    def scan_all(self) -> List[Dict[str, Any]]:
        """
        Scan the entire table and return all items. Handles pagination automatically.

        Returns:
            List[Dict[str, Any]]: A list of all items in the table.

        Raises:
            ClientError: For DynamoDB service errors.
        """
        try:
            items = []
            scan_kwargs = {}
            # AI-generated comment: Loop to handle pagination for large tables.
            while True:
                response = self.table.scan(**scan_kwargs)
                items.extend(response.get("Items", []))
                if "LastEvaluatedKey" not in response:
                    break
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            logger.info(
                f"Scan complete. Found {len(items)} items in {self.table_name}."
            )
            return items
        except ClientError as e:
            logger.error(f"Failed to scan table {self.table_name}: {e}")
            raise

    def query(self, key_condition_expression: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Query the table using a key condition expression.

        Args:
            key_condition_expression: A Key object from boto3.dynamodb.conditions.
                                      Example: Key('my_hash_key').eq('some_value')
            **kwargs: Additional arguments for the query operation (e.g., FilterExpression).

        Returns:
            List[Dict[str, Any]]: A list of items matching the query.

        Raises:
            ClientError: For DynamoDB service errors.
        """
        try:
            # AI-generated comment: Handle pagination for query results.
            items = []
            query_kwargs = {
                "KeyConditionExpression": key_condition_expression,
                **kwargs,
            }
            while True:
                response = self.table.query(**query_kwargs)
                items.extend(response.get("Items", []))
                if "LastEvaluatedKey" not in response:
                    break
                query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

            logger.info(f"Query returned {len(items)} items from {self.table_name}.")
            return items
        except ClientError as e:
            logger.error(f"Failed to query table {self.table_name}: {e}")
            raise
