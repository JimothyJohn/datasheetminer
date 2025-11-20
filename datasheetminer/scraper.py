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
        required=True,
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
        required=True,
        help="Path to a JSON file with product info.",
    )
    parser.add_argument(
        "--json-index",
        type=int,
        required=True,
        help="Index of the product in the JSON file.",
    )

    args: argparse.Namespace = parser.parse_args()

    try:
        info = get_product_info_from_json(
            args.from_json, f"{args.type}", args.json_index
        )
        url_raw = info.get("url")
        pages = info.get("pages")
        manufacturer_raw = info.get("manufacturer")
        product_name_raw = info.get("product_name")
        product_family_raw = info.get("product_family")
        product_type_raw = args.type or info.get("product_type")
    except (FileNotFoundError, ValueError) as e:
        parser.error(str(e))

    # After potentially loading from JSON, check for required args
    required_info = ["url", "manufacturer", "product_name"]
    missing_info = [
        arg for arg in required_info if info is None or info.get(arg) is None
    ]
    if missing_info:
        parser.error(f"Missing required info in JSON: {', '.join(missing_info)}")

    # AI-generated comment: Validate product_type is provided (required via argparse)
    if not product_type_raw:
        parser.error("Product type is required")

    # AI-generated comment: Type narrowing - after validation we know these are not None
    manufacturer: str = manufacturer_raw  # type: ignore[assignment]
    product_name: str = product_name_raw  # type: ignore[assignment]
    product_family: str = product_family_raw  # type: ignore[assignment]
    url: str = url_raw  # type: ignore[assignment]
    product_type: str = product_type_raw  # type: ignore[assignment]

    # Manually handle API key validation
    api_key: Optional[str] = args.x_api_key or os.environ.get("GEMINI_API_KEY")
    try:
        validated_api_key: str = validate_api_key(api_key)
    except argparse.ArgumentTypeError as e:
        parser.error(str(e))

    # AI-generated comment:
    # Before proceeding with the analysis, check if a product with the same
    # product_type, manufacturer, and product_name already exists in the database
    # to avoid redundant scraping. Including manufacturer provides enhanced precision
    # to handle cases where different manufacturers might have identically named products.
    # This is an important optimization that saves both time and resources (API calls, compute time, etc.).
    client: DynamoDBClient = DynamoDBClient()
    model_class: Type[ProductBase] = SCHEMA_CHOICES[args.type]

    if client.product_exists(product_type, manufacturer, product_name, model_class):
        logger.warning(
            f"⚠️  Product '{product_name}' by manufacturer '{manufacturer}' with product_type '{product_type}' "
            f"already exists in the database. Skipping scraping to avoid duplicates."
        )
        sys.exit(0)

    # AI-generated comment: Create a context dictionary to provide known info to the LLM
    context = {
        "product_name": product_name,
        "manufacturer": manufacturer,
        "product_family": product_family,
        "datasheet_url": url,
    }

    # AI-generated comment: Detect if URL points to a PDF or a webpage
    # This allows the scraper to handle both types of content intelligently
    is_pdf: bool = is_pdf_url(url)
    content_type: str = "pdf" if is_pdf else "html"

    logger.info(f"Starting document analysis for: {url}")
    logger.info(f"Content type detected: {content_type}")
    if is_pdf and pages:
        logger.info(f"Pages: {pages}")

    try:
        # AI-generated comment: Fetch content based on detected type
        # For PDFs: use get_document() to get bytes and optionally extract pages
        # For webpages: use get_web_content() to get HTML as string
        doc_data: Optional[bytes | str] = None

        if is_pdf:
            # PDF content - get as bytes
            doc_data = get_document(url, pages)
            if doc_data is None:
                print("Could not retrieve PDF document.", file=sys.stderr)
                sys.exit(1)
        else:
            # Webpage content - get as HTML string
            if pages:
                logger.warning(
                    "Pages parameter is ignored for web content (only applies to PDFs)"
                )

            doc_data = get_web_content(url)
            if doc_data is None:
                print("Could not retrieve web content.", file=sys.stderr)
                sys.exit(1)

        # AI-generated comment: Generate content with appropriate content type and context
        response: Any = generate_content(
            doc_data, validated_api_key, args.type, context, content_type
        )

        # AI-generated comment: Save the raw Gemini response to a file for debugging.
        # This helps diagnose parsing issues when the response is truncated or malformed.
        if response and hasattr(response, "text"):
            debug_output_path = Path("gemini_response_debug.txt")
            try:
                debug_output_path.write_text(response.text, encoding="utf-8")
                logger.info(f"Raw Gemini response saved to: {debug_output_path}")
            except Exception as e:
                logger.warning(f"Could not save debug response: {e}")

        # AI-generated comment: Use the centralized parsing utility from utils.py
        # This handles both automatic and manual parsing with fallback strategies
        try:
            parsed_models: List[Any] = parse_gemini_response(
                response, SCHEMA_CHOICES[args.type], args.type, context
            )
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            parsed_models = []

        if not parsed_models:
            logger.error("No valid response received from Gemini AI.")
            logger.debug(f"Raw Gemini response: {response}")
            if response and hasattr(response, "text"):
                logger.error(f"Gemini response text: {response.text}")
            print("No response received from Gemini AI", file=sys.stderr)
            sys.exit(1)

        # AI-generated comment: The response.parsed attribute now contains a list of Pydantic
        # model instances. We can iterate through them and convert them to dictionaries
        # for JSON serialization.
        # AI-generated comment:
        # The context is now merged inside parse_gemini_response.
        # This loop is no longer needed.
        # for model in parsed_models:
        #     model.manufacturer = manufacturer
        #     # AI-generated comment: product_name is now extracted by the LLM.
        #     # We no longer overwrite it with the generic name from urls.json.
        #     # model.product_name = product_name
        #     model.product_family = product_family
        #     model.product_type = product_type
        #     model.datasheet_url = url

        parsed_data: List[Any] = [item.model_dump() for item in parsed_models]

        # Output the response
        if args.output:
            try:
                # AI-generated comment: Serialize the parsed data to a formatted JSON string.
                formatted_response: str = json.dumps(
                    parsed_data, indent=2, cls=UUIDEncoder
                )

                # Save to file
                args.output.write_text(formatted_response, encoding="utf-8")
                print(f"Response saved to: {args.output}", file=sys.stderr)
                success_count: int = client.batch_create(parsed_models)
                print(
                    f"Successfully pushed {success_count} items to DynamoDB",
                    file=sys.stderr,
                )
                failure_count: int = len(parsed_data) - success_count
                logger.info(
                    f"Successfully pushed {success_count} items to DynamoDB, {failure_count} items failed"
                )

            except Exception as e:
                # AI-generated comment: Handle cases where serialization fails.
                print(f"Error saving response: {e}", file=sys.stderr)
                # Fallback to saving the raw text if available
                if hasattr(response, "text"):
                    args.output.write_text(response.text, encoding="utf-8")
                    print("Saved raw response instead.", file=sys.stderr)
        else:
            # Print to stdout
            # AI-generated comment: For stdout, we'll also print the formatted JSON.
            # The format_response function is no longer needed for JSON output.
            formatted_response = json.dumps(parsed_data, indent=2, cls=UUIDEncoder)
            print(formatted_response)

        logger.info("Document analysis completed successfully")

    except Exception as e:
        logger.error(f"Error during document analysis: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # AI-generated comment: This allows the module to be run directly as a script
    # in addition to being imported as a module, providing flexibility for
    # different execution methods.
    main()
