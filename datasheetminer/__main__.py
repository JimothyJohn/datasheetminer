#!/usr/bin/env python3
"""
CLI entry point for datasheetminer.

AI-generated comment: This module provides a command-line interface for the datasheetminer
application, allowing users to run document analysis locally without needing to deploy
to AWS Lambda. It serves as a wrapper around the core analysis functionality and can
be easily extended for MCP (Model Context Protocol) integration.

Usage:
    uv run datasheetminer --prompt "Analyze this document" --url "https://example.com/doc.pdf" --x-api-key $KEYVAR
    uv run datasheetminer --help
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Handle imports for both module and direct execution
try:
    from .miner import analyze_document
    from .utils import extract_json_from_string
except ImportError:
    # Fallback for direct execution
    from miner import analyze_document
    from utils import extract_json_from_string

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging for CLI
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_page_ranges(value: str) -> str:
    """
    Validates the page range string format. It doesn't parse it into a list,
    as the processing function will handle that. This is just for basic validation.
    e.g., "1,3-5,7"

    Args:
        value: The string containing page ranges.

    Returns:
        The original string if valid.

    Raises:
        argparse.ArgumentTypeError: If the format is invalid.
    """
    if not value:
        raise argparse.ArgumentTypeError("Pages argument cannot be empty.")

    # A simple regex could be used here for stricter validation,
    # but for now we'll just check for invalid characters.
    valid_chars = set("0123456789,-")
    if not all(char in valid_chars for char in value):
        raise argparse.ArgumentTypeError(
            f"Invalid characters in page range string: '{value}'"
        )
    return value


def validate_url(value: str) -> str:
    """
    Validate that the provided URL or file path is valid.

    AI-generated comment: This validator ensures the URL is properly formatted or
    the file path exists before proceeding with the analysis.

    Args:
        value: The URL or file path value to validate

    Returns:
        The validated URL or file path string

    Raises:
        argparse.ArgumentTypeError: If the URL/path is invalid or inaccessible
    """
    if not value:
        return value

    # Check if it's a file path
    if not value.startswith(("http://", "https://")):
        file_path = Path(value)
        if not file_path.exists():
            raise argparse.ArgumentTypeError(f"File not found: {value}")
        if not file_path.is_file():
            raise argparse.ArgumentTypeError(f"Not a file: {value}")
        return str(file_path.absolute())

    return value


def validate_api_key(value: Optional[str]) -> str:
    """
    Validate that the API key is provided and not empty.

    AI-generated comment: This validator ensures the API key is present and
    properly formatted before making requests to the Gemini API.

    Args:
        value: The API key value to validate

    Returns:
        The validated API key string

    Raises:
        argparse.ArgumentTypeError: If the API key is missing or invalid
    """
    if not value:
        raise argparse.ArgumentTypeError(
            "API key is required. Use --x-api-key or set GEMINI_API_KEY environment variable"
        )

    if len(value.strip()) < 10:  # Basic length validation
        raise argparse.ArgumentTypeError("API key appears to be too short")

    return value.strip()


def main() -> None:
    """
    Datasheetminer CLI - Analyze PDF documents using Gemini AI.

    AI-generated comment: This is the main CLI function that orchestrates the document
    analysis process. It handles argument parsing, validation, and coordinates the
    analysis workflow while providing user-friendly output and error handling.

    Examples:
        # Basic usage with environment variable
        export GEMINI_API_KEY="your-api-key"
        uv run datasheetminer --prompt "Summarize this document" --url "https://example.com/doc.pdf"

        # Save output to file
        uv run datasheetminer -p "Extract key specifications" -u "https://example.com/spec.pdf" -o analysis.txt

        # Use markdown output format
        uv run datasheetminer -p "Create a technical summary" -u "https://example.com/tech.pdf" -f markdown
    """
    parser = argparse.ArgumentParser(
        description="Datasheetminer CLI - Analyze PDF documents using Gemini AI.",
        epilog="""
    Examples:
        # Basic usage with environment variable
        export GEMINI_API_KEY="your-api-key"
        datasheetminer --prompt "Summarize this document" --url "https://example.com/doc.pdf"

        # Save output to file
        datasheetminer -p "Extract key specifications" -u "https://example.com/spec.pdf" -o analysis.txt

        # Use markdown output format
        datasheetminer -p "Create a technical summary" -u "https://example.com/tech.pdf" -f markdown
    """,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-p",
        "--prompt",
        required=True,
        help="The analysis prompt to send to Gemini AI",
    )
    parser.add_argument(
        "-u",
        "--url",
        required=True,
        type=validate_url,
        help="URL of the PDF document to analyze",
    )
    parser.add_argument(
        "--pages",
        required=True,
        type=parse_page_ranges,
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
        help="Output file path for saving the response (optional)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format for the response",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    args = parser.parse_args()

    # Manually handle API key validation
    api_key = args.x_api_key or os.environ.get("GEMINI_API_KEY")
    try:
        validated_api_key = validate_api_key(api_key)
    except argparse.ArgumentTypeError as e:
        parser.error(str(e))

    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"Starting document analysis for URL: {args.url}")
    logger.info(f"Prompt: {args.prompt}")
    logger.info(f"Pages: {args.pages}")

    try:
        # AI-generated comment: Process the document analysis and handle the single response.
        # The response is now a single object, not a stream.
        response = analyze_document(
            args.prompt, args.url, validated_api_key, args.pages
        )

        if not response or not hasattr(response, "text") or not response.text.strip():
            print("No response received from Gemini AI", file=sys.stderr)
            sys.exit(1)

        full_response = response.text

        # Output the response
        if args.output:
            try:
                # AI-generated comment: Extract, validate, and format the JSON response.
                json_str = extract_json_from_string(full_response)
                parsed_json = json.loads(json_str)
                formatted_response = json.dumps(parsed_json, indent=2)

                # Save to file
                args.output.write_text(formatted_response, encoding="utf-8")
                print(f"Response saved to: {args.output}", file=sys.stderr)
            except ValueError as e:
                # AI-generated comment: Handle cases where the response is not valid JSON.
                print(
                    f"Warning: Could not parse JSON from response: {e}",
                    file=sys.stderr,
                )
                print("Saving raw response instead.", file=sys.stderr)
                args.output.write_text(full_response, encoding="utf-8")
        else:
            # Print to stdout
            formatted_response = format_response(full_response, args.format)
            print(formatted_response)

        logger.info("Document analysis completed successfully")

    except Exception as e:
        logger.error(f"Error during document analysis: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def format_response(response: str, format_type: str) -> str:
    """
    Format the response according to the specified output format.

    AI-generated comment: This function provides multiple output formats to make
    the CLI output more flexible and useful for different use cases, including
    integration with other tools and systems.

    Args:
        response: The raw response text from Gemini AI
        format_type: The desired output format ('text', 'json', or 'markdown')

    Returns:
        The formatted response string
    """
    if format_type == "json":
        return json.dumps(
            {"response": response, "status": "success", "timestamp": str(Path().cwd())},
            indent=2,
        )

    elif format_type == "markdown":
        # AI-generated comment: Convert the response to markdown format for
        # better readability and integration with markdown processors.
        return f"# Document Analysis Response\n\n{response}\n\n---\n*Generated by Datasheetminer CLI*"

    else:  # text format (default)
        return response


if __name__ == "__main__":
    # AI-generated comment: This allows the module to be run directly as a script
    # in addition to being imported as a module, providing flexibility for
    # different execution methods.
    main()
