"""Utility to push JSON data from files into DynamoDB.

This module provides functionality to load JSON data from files and insert
them into DynamoDB using the DynamoDBClient class. It supports both Motor
and Drive models with automatic type detection and validation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Union

from pydantic import ValidationError

from datasheetminer.db.dynamo import DynamoDBClient
from datasheetminer.models.drive import Drive
from datasheetminer.models.motor import Motor


class DataPusher:
    """Utility class to push JSON data into DynamoDB."""

    def __init__(self, table_name: str = "products"):
        """Initialize DataPusher with DynamoDB client.

        Args:
            table_name: Name of the DynamoDB table (default: "products")
        """
        self.db_client = DynamoDBClient(table_name=table_name)

    def _normalize_json_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize JSON item to match Pydantic model expectations.

        Args:
            item: Raw JSON item dictionary

        Returns:
            Normalized item dictionary
        """
        # Create a copy to avoid modifying the original
        normalized = item.copy()

        # Handle nested datasheet_url structure
        if "datasheet_url" in normalized and isinstance(
            normalized["datasheet_url"], dict
        ):
            # Extract the URL string from the nested structure
            if "url" in normalized["datasheet_url"]:
                normalized["datasheet_url"] = normalized["datasheet_url"]["url"]

        return normalized

    def _detect_model_type(self, item: Dict[str, Any]) -> str:
        """Detect whether an item is a Motor or Drive based on fields.

        Args:
            item: JSON item dictionary

        Returns:
            "motor" or "drive" based on detected type, "unknown" if cannot determine
        """
        # Drive-specific fields
        drive_fields = {
            "input_voltage",
            "output_power",
            "fieldbus",
            "control_modes",
            "switching_frequency",
        }

        # Motor-specific fields
        motor_fields = {
            "rated_speed",
            "rated_torque",
            "peak_torque",
            "encoder_feedback_support",
            "poles",
        }

        # Check for drive-specific fields
        drive_score = sum(1 for field in drive_fields if field in item)

        # Check for motor-specific fields
        motor_score = sum(1 for field in motor_fields if field in item)

        # Use type field if present
        if "type" in item:
            item_type = item["type"]
            if item_type in ["servo", "variable frequency"]:
                return "drive"
            elif item_type in [
                "brushless dc",
                "brushed dc",
                "ac induction",
                "ac synchronous",
                "ac servo",
                "permanent magnet",
                "hybrid",
            ]:
                return "motor"

        # Fall back to field-based detection
        if drive_score > motor_score:
            return "drive"
        elif motor_score > drive_score:
            return "motor"

        return "unknown"

    def load_json_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load JSON data from a file.

        Args:
            file_path: Path to JSON file

        Returns:
            List of JSON objects

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file contains invalid JSON
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "r") as f:
            data = json.load(f)

        # Handle both single objects and arrays
        if isinstance(data, dict):
            return [data]
        elif isinstance(data, list):
            return data
        else:
            raise ValueError(f"Expected JSON object or array, got {type(data)}")

    def validate_and_convert(
        self, items: List[Dict[str, Any]]
    ) -> tuple[List[Union[Motor, Drive]], List[Dict[str, Any]]]:
        """Validate JSON items and convert to Pydantic models.

        Args:
            items: List of JSON item dictionaries

        Returns:
            Tuple of (valid_models, failed_items)
        """
        valid_models: List[Union[Motor, Drive]] = []
        failed_items: List[Dict[str, Any]] = []

        for idx, item in enumerate(items):
            try:
                # Normalize the item
                normalized = self._normalize_json_item(item)

                # Detect model type
                model_type = self._detect_model_type(normalized)

                if model_type == "drive":
                    model = Drive.model_validate(normalized)
                    valid_models.append(model)
                elif model_type == "motor":
                    model = Motor.model_validate(normalized)
                    valid_models.append(model)
                else:
                    print(f"Warning: Could not detect type for item {idx}")
                    failed_items.append(
                        {"item": item, "error": "Could not detect model type"}
                    )

            except ValidationError as e:
                print(f"Validation error for item {idx}: {e}")
                failed_items.append({"item": item, "error": str(e)})
            except Exception as e:
                print(f"Unexpected error for item {idx}: {e}")
                failed_items.append({"item": item, "error": str(e)})

        return valid_models, failed_items

    def push_to_db(
        self, models: List[Union[Motor, Drive]], use_batch: bool = True
    ) -> tuple[int, int]:
        """Push validated models to DynamoDB.

        Args:
            models: List of Motor or Drive model instances
            use_batch: Use batch write for better performance (default: True)

        Returns:
            Tuple of (success_count, failure_count)
        """
        if not models:
            return 0, 0

        if use_batch:
            # Use batch write
            success_count = self.db_client.batch_create(models)
            failure_count = len(models) - success_count
        else:
            # Use individual writes
            success_count = 0
            failure_count = 0

            for model in models:
                if self.db_client.create(model):
                    success_count += 1
                else:
                    failure_count += 1

        return success_count, failure_count

    def process_file(self, file_path: Path, use_batch: bool = True) -> Dict[str, Any]:
        """Process a JSON file end-to-end: load, validate, and push to DB.

        Args:
            file_path: Path to JSON file
            use_batch: Use batch write for better performance (default: True)

        Returns:
            Dictionary with processing results
        """
        print(f"Loading data from {file_path}...")

        # Load JSON data
        try:
            items = self.load_json_file(file_path)
            print(f"Loaded {len(items)} items from file")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "items_loaded": 0,
                "items_validated": 0,
                "items_pushed": 0,
                "items_failed": 0,
            }

        # Validate and convert
        print("Validating items...")
        valid_models, failed_items = self.validate_and_convert(items)
        print(
            f"Validated {len(valid_models)} items, {len(failed_items)} items failed validation"
        )

        # Push to database
        if valid_models:
            print(f"Pushing {len(valid_models)} items to DynamoDB...")
            success_count, failure_count = self.push_to_db(valid_models, use_batch)
            print(
                f"Successfully pushed {success_count} items, {failure_count} items failed"
            )
        else:
            success_count = 0
            failure_count = 0
            print("No valid items to push to database")

        return {
            "success": True,
            "items_loaded": len(items),
            "items_validated": len(valid_models),
            "items_pushed": success_count,
            "items_failed": len(failed_items) + failure_count,
            "validation_errors": len(failed_items),
        }


def main() -> int:
    """CLI entry point for the pusher utility."""
    parser = argparse.ArgumentParser(
        description="Push JSON data from files into DynamoDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Push data from powersmart.json to default table
  uv run datasheetminer/pusher.py --file powersmart.json

  # Push to custom table
  uv run datasheetminer/pusher.py --file powersmart.json --table my-table

  # Use individual writes instead of batch
  uv run datasheetminer/pusher.py --file powersmart.json --no-batch

Environment Variables:
  AWS_ACCESS_KEY_ID        AWS access key
  AWS_SECRET_ACCESS_KEY    AWS secret key
  AWS_DEFAULT_REGION       AWS region (default: us-east-1)
        """,
    )

    parser.add_argument(
        "--file",
        type=Path,
        default=Path("powersmart.json"),
        help="Path to JSON file (default: powersmart.json)",
    )

    parser.add_argument(
        "--table",
        type=str,
        default="products",
        help="DynamoDB table name (default: products)",
    )

    parser.add_argument(
        "--no-batch",
        action="store_true",
        help="Use individual writes instead of batch writes",
    )

    args = parser.parse_args()

    # Initialize pusher
    pusher = DataPusher(table_name=args.table)

    # Process file
    result = pusher.process_file(args.file, use_batch=not args.no_batch)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if result["success"]:
        print(f"Items loaded:     {result['items_loaded']}")
        print(f"Items validated:  {result['items_validated']}")
        print(f"Items pushed:     {result['items_pushed']}")
        print(f"Items failed:     {result['items_failed']}")
        print(f"Validation errors: {result.get('validation_errors', 0)}")

        if result["items_pushed"] == result["items_loaded"]:
            print("\nStatus: All items successfully pushed!")
            return 0
        elif result["items_pushed"] > 0:
            print("\nStatus: Partial success")
            return 1
        else:
            print("\nStatus: Failed to push any items")
            return 1
    else:
        print(f"Error: {result['error']}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
