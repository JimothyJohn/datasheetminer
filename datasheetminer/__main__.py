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
from pathlib import Path

from dotenv import load_dotenv

from datasheetminer.utils import (
    get_document,
    validate_api_key,
    validate_page_ranges,
    validate_url,
)
from datasheetminer.llm import generate_content

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging for CLI
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """
    Datasheetminer CLI - Analyze PDF documents using Gemini AI.

    AI-generated comment: This is the main CLI function that orchestrates the document
    analysis process. It handles argument parsing, validation, and coordinates the
    analysis workflow while providing user-friendly output and error handling.

    Examples:
        # Basic usage with environment variable
        export GEMINI_API_KEY="your-api-key"
        uv run datasheetminer --url "https://example.com/doc.pdf"

        # Save output to file
        uv run datasheetminer -u "https://example.com/spec.pdf" -o analysis.txt

        # Use markdown output format
        uv run datasheetminer -u "https://example.com/tech.pdf"
    """
    parser = argparse.ArgumentParser(
        description="Datasheetminer CLI - Analyze PDF documents using Gemini AI.",
        epilog="""
    Examples:
        # Basic usage with environment variable
        export GEMINI_API_KEY="your-api-key"
        datasheetminer --url "https://example.com/doc.pdf"

        # Save output to file
        datasheetminer -u "https://example.com/spec.pdf" -o analysis.txt

        # Use markdown output format
        datasheetminer -u "https://example.com/tech.pdf"
    """,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-t",
        "--type",
        choices=["motor", "drive"],
        required=True,
        help="The type of schema to use for analysis (motor or drive)",
    )
    parser.add_argument(
        "-u",
        "--url",
        required=True,
        type=validate_url,
        help="URL of the PDF document to analyze",
    )
    parser.add_argument(
        "-p",
        "--pages",
        required=True,
        type=validate_page_ranges,
        help="Specific pages of the PDF to analyze. e.g., '1,3-5,7'. This is a required argument.",
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

    args = parser.parse_args()

    # Manually handle API key validation
    api_key = args.x_api_key or os.environ.get("GEMINI_API_KEY")
    try:
        validated_api_key = validate_api_key(api_key)
    except argparse.ArgumentTypeError as e:
        parser.error(str(e))

    logger.info(f"Starting document analysis for URL: {args.url}")
    logger.info(f"Pages: {args.pages}")

    try:
        # AI-generated comment: Process the document analysis and handle the single response.
        # The response is now a single object, not a stream.
        doc_data = get_document(args.url, args.pages)
        if doc_data is None:
            print("Could not retrieve document.", file=sys.stderr)
            sys.exit(1)

        response = generate_content(doc_data, validated_api_key, args.type)

        if not response or not hasattr(response, "parsed") or not response.parsed:
            print("No response received from Gemini AI", file=sys.stderr)
            sys.exit(1)

        # AI-generated comment: The response.parsed attribute now contains a list of Pydantic
        # model instances. We can iterate through them and convert them to dictionaries
        # for JSON serialization.
        parsed_data = [item.model_dump() for item in response.parsed]

        # Output the response
        if args.output:
            try:
                # AI-generated comment: Serialize the parsed data to a formatted JSON string.
                formatted_response = json.dumps(parsed_data, indent=2)

                # Save to file
                args.output.write_text(formatted_response, encoding="utf-8")
                print(f"Response saved to: {args.output}", file=sys.stderr)
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
            formatted_response = json.dumps(parsed_data, indent=2)
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
