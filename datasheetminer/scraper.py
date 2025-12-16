#!/usr/bin/env python3
"""
CLI entry point for datasheetminer.

AI-generated comment: This module provides a command-line interface for the datasheetminer
application, allowing users to run document analysis locally without needing to deploy
to AWS Lambda. It serves as a wrapper around the core analysis functionality and can
be easily extended for MCP (Model Context Protocol) integration.

Usage:
    uv run datasheetminer --url "https://example.com/doc.pdf" --x-api-key $KEYVAR
    uv run datasheetminer --help
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, List, Optional, Type


from datasheetminer.config import SCHEMA_CHOICES
from datasheetminer.db.dynamo import DynamoDBClient
from datasheetminer.models.product import ProductBase
from datasheetminer.utils import (
    get_document,
    get_web_content,
    is_pdf_url,
    validate_api_key,
    UUIDEncoder,
    get_product_info_from_json,
    parse_gemini_response,
)
from datasheetminer.llm import generate_content


class ElapsedTimeFormatter(logging.Formatter):
    """
    AI-generated comment: This custom logging formatter converts log timestamps into
    an elapsed time format (M:SS), making it easier to track the duration of
    different stages of the program execution. It's initialized once and calculates
    all subsequent log times relative to its creation.
    """

    def __init__(self, fmt=None, datefmt=None, style="%"):
        super().__init__(fmt, datefmt, style)
        self.start_time = time.time()

    def formatTime(self, record, datefmt=None):
        """
        AI-generated comment: This method is overridden from the base Formatter class.
        It calculates the time elapsed since the program started and formats it
        as M:SS.
        """
        elapsed_seconds = record.created - self.start_time
        minutes, seconds = divmod(elapsed_seconds, 60)
        return f"{int(minutes)}:{int(seconds):02}"


# Configure logging for CLI
# AI-generated comment: A handler is created and equipped with the custom
# ElapsedTimeFormatter. This handler is then passed to logging.basicConfig to ensure
# all log messages will be formatted with elapsed time.
handler = logging.StreamHandler()
handler.setFormatter(
    ElapsedTimeFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    handlers=[handler],
)
logger: logging.Logger = logging.getLogger(__name__)


def main() -> None:
    """
    Datasheetminer CLI - Analyze PDF documents and web pages using Gemini AI.

    AI-generated comment: This is the main CLI function that orchestrates the document
    analysis process. It handles argument parsing, validation, and coordinates the
    analysis workflow while providing user-friendly output and error handling.
    The scraper now intelligently detects whether the URL is a PDF or webpage and
    handles each appropriately.

    Examples:
        # Analyze a PDF datasheet
        export GEMINI_API_KEY="your-api-key"
        uv run datasheetminer --url "https://example.com/motor.pdf"

        # Analyze a product webpage
        uv run datasheetminer --url "https://example.com/product-specs"

        # Save output to file
        uv run datasheetminer -u "https://example.com/spec.pdf" -o analysis.json
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Datasheetminer CLI - Analyze PDF documents and web pages using Gemini AI.",
        epilog="""
    Examples:
        # Analyze a PDF datasheet
        export GEMINI_API_KEY="your-api-key"
        datasheetminer --url "https://example.com/motor.pdf"

        # Analyze a product webpage (automatically detected)
        datasheetminer --url "https://example.com/product-specs"

        # Save output to file
        datasheetminer -u "https://example.com/spec.pdf" -o analysis.json

        Note: The tool automatically detects whether the URL is a PDF or webpage.
        For PDFs, you can specify page ranges. For webpages, the entire page is analyzed.
    """,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-t",
        "--type",
        required=False,
        help="The type of schema to use for analysis (motor, drive, gearhead, robot_arm, etc)",
    )

    parser.add_argument(
        "--x-api-key",
        help="Gemini API key (can also be set via GEMINI_API_KEY environment variable)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output.json"),
        help="Output file path for saving the response (optional)",
    )
    parser.add_argument(
        "--from-json",
        type=str,
        help="Path to a JSON file with product info.",
    )
    parser.add_argument(
        "--json-index",
        type=int,
        default=0,
        help="Index of the item in the JSON file to process (default: 0)",
    )

    parser.add_argument(
        "--scrape-from-db",
        action="store_true",
        help="Fetch datasheet info from DynamoDB using product name and family.",
    )
    parser.add_argument(
        "--scrape-all",
        action="store_true",
        help="Iterate through ALL datasheets in the DB and scrape them if not already processed.",
    )
    parser.add_argument("--url", help="Datasheet URL (required if not using --from-json, --scrape-from-db, or --scrape-all)")
    parser.add_argument("--pages", help="Comma-separated list of pages (e.g. '1,2,3')")
    parser.add_argument("--product-name", help="Product name")
    parser.add_argument("--manufacturer", help="Manufacturer")
    parser.add_argument("--product-family", help="Product family")

    args: argparse.Namespace = parser.parse_args()
    client: DynamoDBClient = DynamoDBClient()

    # Manually handle API key validation
    api_key: Optional[str] = args.x_api_key or os.environ.get("GEMINI_API_KEY")
    try:
        validated_api_key: str = validate_api_key(api_key)
    except argparse.ArgumentTypeError as e:
        parser.error(str(e))



    # Handle Scrape All Mode
    if args.scrape_all:
        logger.info("Starting bulk scrape of all datasheets...")
        all_datasheets = client.get_all_datasheets()
        logger.info(f"Found {len(all_datasheets)} datasheets in DB.")
        
        success_count = 0
        skip_count = 0
        fail_count = 0
        
        for ds in all_datasheets:
            logger.info(f"Processing datasheet: {ds.product_name} ({ds.datasheet_id})")
            try:
                result = process_datasheet(
                    client=client,
                    api_key=validated_api_key,
                    product_type=ds.product_type,
                    manufacturer=ds.manufacturer or "Unknown", # Should not happen if schema enforced
                    product_name=ds.product_name,
                    product_family=ds.product_family or "",
                    url=ds.url,
                    pages=ds.pages,
                    output_path=None # Don't write individual files for bulk scrape
                )
                if result == "skipped":
                    skip_count += 1
                elif result == "success":
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"Error processing datasheet {ds.datasheet_id}: {e}")
                fail_count += 1
                
        logger.info(f"Bulk scrape completed. Success: {success_count}, Skipped: {skip_count}, Failed: {fail_count}")
        sys.exit(0)

    # Determine source of information for single scrape
    url_raw: Optional[str] = None
    pages: Optional[List[int]] = None
    manufacturer_raw: Optional[str] = None
    product_name_raw: Optional[str] = None
    product_family_raw: Optional[str] = None
    product_type_raw: Optional[str] = args.type

    if args.from_json:
        try:
            info = get_product_info_from_json(
                args.from_json, f"{args.type}", args.json_index
            )
            url_raw = info.get("url")
            pages = info.get("pages")
            manufacturer_raw = info.get("manufacturer")
            product_name_raw = info.get("product_name")
            product_family_raw = info.get("product_family")
            if not product_type_raw:
                product_type_raw = info.get("product_type")
        except (FileNotFoundError, ValueError) as e:
            parser.error(str(e))

    elif args.scrape_from_db:
        # Query DB for datasheet
        datasheets = []
        
        if args.product_name:
            # Try finding by product name first
            datasheets = client.get_datasheets_by_product_name(args.product_name)
        elif args.product_family:
            # Try finding by family
            datasheets = client.get_datasheets_by_family(args.product_family)
        elif args.manufacturer:
            # Fallback to getting all and filtering
            all_ds = client.get_all_datasheets()
            datasheets = [ds for ds in all_ds if ds.manufacturer == args.manufacturer]
        else:
            # If only type is provided (or nothing else specific), fetch all
            datasheets = client.get_all_datasheets()

        # Filter results based on other provided criteria
        filtered_datasheets = []
        for ds in datasheets:
            match = True
            # Filter by type (required arg)
            if args.type and ds.product_type != args.type:
                match = False
                
            if args.product_name and ds.product_name != args.product_name:
                match = False
            if args.product_family and ds.product_family != args.product_family:
                match = False
            if args.manufacturer and ds.manufacturer != args.manufacturer:
                match = False
            
            if match:
                filtered_datasheets.append(ds)
        
        if not filtered_datasheets:
            criteria = []
            if args.type: criteria.append(f"type='{args.type}'")
            if args.product_name: criteria.append(f"name='{args.product_name}'")
            if args.product_family: criteria.append(f"family='{args.product_family}'")
            if args.manufacturer: criteria.append(f"manufacturer='{args.manufacturer}'")
            
            logger.error(f"No datasheet found in DB matching criteria: {', '.join(criteria)}")
            sys.exit(1)
            
        # Process all matching datasheets
        logger.info(f"Found {len(filtered_datasheets)} matching datasheets in DB.")
        
        success_count = 0
        skip_count = 0
        fail_count = 0
        
        for ds in filtered_datasheets:
            logger.info(f"Processing datasheet: {ds.product_name} ({ds.datasheet_id})")
            try:
                result = process_datasheet(
                    client=client,
                    api_key=validated_api_key,
                    product_type=ds.product_type,
                    manufacturer=ds.manufacturer or "Unknown",
                    product_name=ds.product_name,
                    product_family=ds.product_family or "",
                    url=ds.url,
                    pages=ds.pages,
                    output_path=None # Don't write individual files for bulk scrape
                )
                if result == "skipped":
                    skip_count += 1
                elif result == "success":
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"Error processing datasheet {ds.datasheet_id}: {e}")
                fail_count += 1
                
        logger.info(f"Scrape from DB completed. Success: {success_count}, Skipped: {skip_count}, Failed: {fail_count}")
        sys.exit(0)

    else:
        # Manual CLI args
        url_raw = args.url
        if args.pages:
            try:
                pages = [int(p.strip()) for p in args.pages.split(",")]
            except ValueError:
                parser.error("Pages must be a comma-separated list of integers")
        
        manufacturer_raw = args.manufacturer
        product_name_raw = args.product_name
        product_family_raw = args.product_family

    # Validation
    if not url_raw:
        parser.error("URL is required (via --url, --from-json, or --scrape-from-db)")
    
    # If not scraping from DB, type is required
    if not args.scrape_from_db and not args.scrape_all and not product_type_raw:
         parser.error("Product type is required (via -t/--type) when not scraping from DB.")

    if not manufacturer_raw:
        parser.error("Manufacturer is required")
    if not product_name_raw:
        parser.error("Product name is required")
    if not product_type_raw:
        # If we are here, it means we are scraping from DB but the datasheet entry didn't have a type?
        # Or we are iterating and some entries might be missing type.
        # But wait, if we are scraping from DB, we get type from the DB entry.
        # If we are doing manual URL, we enforced it above.
        # So this check is mostly for safety.
        parser.error("Product type is required")

    # Type narrowing
    manufacturer_str: str = manufacturer_raw
    product_name_str: str = product_name_raw
    product_family_str: str = product_family_raw or ""
    url_str: str = url_raw
    product_type_str: str = product_type_raw

    try:
        process_datasheet(
            client=client,
            api_key=validated_api_key,
            product_type=product_type_str,
            manufacturer=manufacturer_str,
            product_name=product_name_str,
            product_family=product_family_str,
            url=url_str,
            pages=pages,
            output_path=args.output
        )
    except Exception as e:
        logger.error(f"Error during document analysis: {e}")
        sys.exit(1)


def process_datasheet(
    client: DynamoDBClient,
    api_key: str,
    product_type: str,
    manufacturer: str,
    product_name: str,
    product_family: str,
    url: str,
    pages: Optional[List[int]],
    output_path: Optional[Path] = None
) -> str:
    """
    Process a single datasheet: check existence, scrape, parse, and save to DB.
    Returns: "success", "skipped", or "failed"
    """
    
    # Check if product already exists
    model_class: Type[ProductBase] = SCHEMA_CHOICES[product_type]
    from datasheetminer.models.datasheet import Datasheet

    # Ensure Datasheet entry exists (for management UI)
    # DISABLED: User requested to prevent scraper from adding datasheets
    # if not client.datasheet_exists(url):
    #     logger.info(f"Creating missing Datasheet entry for: {url}")
    #     ds = Datasheet(
    #         url=url,
    #         pages=pages,
    #         product_type=product_type,
    #         product_name=product_name,
    #         product_family=product_family,
    #         manufacturer=manufacturer,
    #     )
    #     client.create(ds)

    if client.product_exists(product_type, manufacturer, product_name, model_class):
        logger.warning(
            f"⚠️  Product '{product_name}' by manufacturer '{manufacturer}' with product_type '{product_type}' "
            f"already exists in the database. Skipping scraping to avoid duplicates."
        )
        return "skipped"

    # Context for LLM
    context = {
        "product_name": product_name,
        "manufacturer": manufacturer,
        "product_family": product_family,
        "datasheet_url": url,
        "pages": pages,
    }

    # Detect content type
    is_pdf: bool = is_pdf_url(url)
    content_type: str = "pdf" if is_pdf else "html"

    logger.info(f"Starting document analysis for: {url}")
    logger.info(f"Content type detected: {content_type}")
    if is_pdf and pages:
        logger.info(f"Pages: {pages}")

    try:
        doc_data: Optional[bytes | str] = None

        if is_pdf:
            doc_data = get_document(url, pages)
            if doc_data is None:
                logger.error("Could not retrieve PDF document.")
                return "failed"
        else:
            if pages:
                logger.warning("Pages parameter is ignored for web content")
            doc_data = get_web_content(url)
            if doc_data is None:
                logger.error("Could not retrieve web content.")
                return "failed"

        # Generate content
        response: Any = generate_content(
            doc_data, api_key, product_type, context, content_type
        )

        # Debug output
        if response and hasattr(response, "text"):
            debug_output_path = Path("gemini_response_debug.txt")
            try:
                debug_output_path.write_text(response.text, encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not save debug response: {e}")

        # Parse response
        try:
            parsed_models: List[Any] = parse_gemini_response(
                response, SCHEMA_CHOICES[product_type], product_type, context
            )
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            return "failed"

        if not parsed_models:
            logger.error("No valid response received from Gemini AI.")
            return "failed"

        # Inject source metadata and deterministic IDs
        import uuid
        import re
        
        # Use a fixed namespace for product IDs to ensure reproducibility across runs
        PRODUCT_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')

        def normalize_string(s: Optional[str]) -> str:
            """Normalize string for ID generation: lowercase, alphanumeric only."""
            if not s:
                return ""
            # Remove non-alphanumeric characters (keep alphanumeric)
            # This handles "Nidec Corp." vs "Nidec-Corp" vs "Nidec"
            # We keep spaces for readability in the source string but strip them for ID
            # Actually, removing ALL special chars including spaces makes it most robust against formatting 
            # e.g. "Model A" vs "Model-A"
            s = s.lower().strip()
            return re.sub(r'[^a-z0-9]', '', s)

        valid_models = []
        
        for model in parsed_models:
            model.datasheet_url = url
            model.pages = pages
            
            # Robust Deterministic ID Generation
            norm_manufacturer = normalize_string(model.manufacturer) or normalize_string(manufacturer)
            norm_part_number = normalize_string(model.part_number)
            norm_name = normalize_string(model.product_name)
            
            id_string = ""
            
            if norm_manufacturer and norm_part_number:
                # Primary Strategy: Manufacturer + Part Number
                id_string = f"{norm_manufacturer}:{norm_part_number}"
                logger.debug(f"ID Strategy: Manuf+PartNum ({id_string})")
            elif norm_manufacturer and norm_name:
                # Fallback Strategy: Manufacturer + Product Name
                # Used when part number is missing but we have a distinct product name
                id_string = f"{norm_manufacturer}:{norm_name}"
                logger.warning(f"⚠️  Missing part number for '{model.product_name}'. Using Manuf+Name for ID.")
            else:
                # Last resort: Hash the URL + Index (if multiple items from one URL)
                # This prevents "random" IDs but ties identity to the source URL
                # which is better than random but not ideal for deduplication across different URLs.
                # However, for now, we'll skip to be safe as per user request to avoid duplicates.
                logger.error(
                    f"❌ Could not generate robust ID for product '{model.product_name}'. "
                    "Missing Manufacturer AND (Part Number OR distinct Product Name). Skipping to avoid duplicates."
                )
                continue
                
            model.product_id = uuid.uuid5(PRODUCT_NAMESPACE, id_string)
            logger.info(f"Generated ID {model.product_id} from key '{id_string}'")
            
            # Check if this specific ID already exists in DB
            from datasheetminer.models.product import ProductBase
            existing_item = client.read(model.product_id, ProductBase)
            if existing_item:
                logger.info(f"ℹ️  Product with ID {model.product_id} already exists. Skipping.")
                continue
            
            valid_models.append(model)

        parsed_data: List[Any] = [item.model_dump() for item in valid_models]

        # Output to file if requested
        if output_path:
            try:
                formatted_response: str = json.dumps(
                    parsed_data, indent=2, cls=UUIDEncoder
                )
                output_path.write_text(formatted_response, encoding="utf-8")
                print(f"Response saved to: {output_path}", file=sys.stderr)
            except Exception as e:
                print(f"Error saving response: {e}", file=sys.stderr)

        # Save to DB
        success_count: int = client.batch_create(parsed_models)
        failure_count: int = len(parsed_data) - success_count
        logger.info(
            f"Successfully pushed {success_count} items to DynamoDB, {failure_count} items failed"
        )
        
        if success_count > 0:
            return "success"
        else:
            return "failed"

    except Exception as e:
        logger.error(f"Error during document analysis: {e}")
        return "failed"


if __name__ == "__main__":
    # AI-generated comment: This allows the module to be run directly as a script
    # in addition to being imported as a module, providing flexibility for
    # different execution methods.
    main()
