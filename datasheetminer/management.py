"""Management utility for datasheetminer administrative tasks.

This module contains functions for managing the database, such as
finding and deleting duplicate products.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from botocore.exceptions import ClientError  # type: ignore

from datasheetminer.db.dynamo import DynamoDBClient
from datasheetminer.models.product import ProductBase


class Deduplicator:
    """Class to handle finding and deleting duplicate products."""

    db_client: DynamoDBClient
    table_name: str

    def __init__(self, table_name: str = "products") -> None:
        """Initialize Deduplicator with DynamoDB client.

        Args:
            table_name: Name of the DynamoDB table (default: "products")
        """
        self.db_client = DynamoDBClient(table_name=table_name)
        self.table_name = table_name

    def find_duplicates(self) -> Dict[Tuple[str, str, str], List[Dict[str, Any]]]:
        """Find duplicate products based on part_number, product_name, and manufacturer.

        Returns:
            Dictionary where key is (part_number, product_name, manufacturer)
            and value is a list of product items that share these attributes.
            Only groups with > 1 item are returned.
        """
        print("Scanning table for duplicates...")
        
        # Scan all items
        # Note: For large tables, this might need to be optimized or paginated carefully,
        # but for this task we'll scan everything into memory to group them.
        all_items = self.db_client.list_all()
        
        print(f"Scanned {len(all_items)} items. Grouping by attributes...")

        grouped_items: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)

        for item in all_items:
            # We need to access attributes safely. 
            # The items returned by list_all are Pydantic models (ProductBase subclasses)
            
            part_number = (getattr(item, "part_number", "") or "").strip()
            product_name = (getattr(item, "product_name", "") or "").strip()
            manufacturer = (getattr(item, "manufacturer", "") or "").strip()
            
            # Create a unique key for grouping
            # Using lower case for case-insensitive comparison if desired, 
            # but strict requirement said "share the same...", implying exact match.
            # However, usually deduplication implies some normalization. 
            # I'll stick to exact match for now but strip whitespace.
            key = (part_number, product_name, manufacturer)
            
            # Convert model to dict for easier handling later
            item_dict = item.model_dump(by_alias=True, mode="json")
            grouped_items[key].append(item_dict)

        # Filter out unique items (lists with length 1)
        duplicates = {k: v for k, v in grouped_items.items() if len(v) > 1}
        
        return duplicates

    def delete_duplicates(self, confirm: bool = False, dry_run: bool = False) -> Dict[str, int]:
        """Delete duplicate products, keeping one per group.

        Args:
            confirm: Must be True to proceed with deletion.
            dry_run: If True, only show what would be deleted.

        Returns:
            Summary of actions taken.
        """
        if not confirm and not dry_run:
            print("ERROR: delete_duplicates() requires confirm=True parameter")
            print("Use dry_run=True to see what would be deleted")
            return {"found": 0, "deleted": 0}

        duplicates = self.find_duplicates()
        
        total_duplicates_found = sum(len(items) - 1 for items in duplicates.values())
        groups_count = len(duplicates)
        
        print(f"\nFound {groups_count} groups with duplicates (total {total_duplicates_found} items to delete).")

        if total_duplicates_found == 0:
            print("No duplicates found.")
            return {"found": 0, "deleted": 0}

        items_to_delete: List[Dict[str, Any]] = []

        print("\nDuplicate groups found:")
        for key, items in duplicates.items():
            part_num, prod_name, mfg = key
            print(f"  Group: '{mfg}' - '{prod_name}' - '{part_num}' ({len(items)} items)")
            
            # Sort items to be deterministic about which one we keep.
            # For example, keep the one with the oldest creation date? 
            # We don't have creation date in ProductBase.
            # Let's sort by product_id (UUID) just to be deterministic.
            items.sort(key=lambda x: x.get("product_id", ""))
            
            # Keep the first one, delete the rest
            keep = items[0]
            delete_list = items[1:]
            
            print(f"    Keeping: ID {keep.get('product_id')}")
            for item in delete_list:
                print(f"    Deleting: ID {item.get('product_id')}")
                items_to_delete.append(item)

        if dry_run:
            print(f"\nDRY RUN: Would delete {len(items_to_delete)} items.")
            return {"found": total_duplicates_found, "deleted": 0}

        # Confirmation
        print("=" * 80)
        print(f"⚠️  WARNING: YOU ARE ABOUT TO DELETE {len(items_to_delete)} ITEMS!")
        print("=" * 80)
        print("Type 'DELETE' (without quotes) to confirm:")
        
        user_input = input("> ").strip()
        if user_input != "DELETE":
            print("Deletion cancelled.")
            return {"found": total_duplicates_found, "deleted": 0}

        # Execute deletion
        print(f"\nDeleting {len(items_to_delete)} items...")
        deleted_count = 0
        batch_size = 25
        
        try:
            for i in range(0, len(items_to_delete), batch_size):
                batch = items_to_delete[i : i + batch_size]
                
                with self.db_client.table.batch_writer() as writer:
                    for item in batch:
                        try:
                            writer.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
                            deleted_count += 1
                        except Exception as e:
                            print(f"Error deleting item {item.get('product_id')}: {e}")
                
                print(f"  Deleted {deleted_count}/{len(items_to_delete)} items...")

            print(f"\n✓ Successfully deleted {deleted_count} items.")
            return {"found": total_duplicates_found, "deleted": deleted_count}

        except Exception as e:
            print(f"Error during deletion: {e}")
            return {"found": total_duplicates_found, "deleted": deleted_count}


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Datasheet Miner Management Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Deduplicate command
    dedup_parser = subparsers.add_parser("deduplicate", help="Find and delete duplicate products")
    dedup_parser.add_argument("--table", default="products", help="DynamoDB table name")
    dedup_parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    dedup_parser.add_argument("--confirm", action="store_true", help="Confirm deletion")
    dedup_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    if args.command == "deduplicate":
        deduplicator = Deduplicator(table_name=args.table)
        
        # Capture stdout if json mode is enabled to prevent pollution
        if args.json:
            import io
            import json
            
            # Redirect stdout to suppress logs
            original_stdout = sys.stdout
            sys.stdout = io.StringIO()
            
            try:
                result = deduplicator.delete_duplicates(confirm=args.confirm, dry_run=args.dry_run)
                
                # Restore stdout and print JSON
                sys.stdout = original_stdout
                print(json.dumps(result))
            except Exception as e:
                sys.stdout = original_stdout
                print(json.dumps({"error": str(e)}))
                return 1
        else:
            deduplicator.delete_duplicates(confirm=args.confirm, dry_run=args.dry_run)
        
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
