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

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

# Handle imports for both module and direct execution
try:
    from .miner import analyze_document
except ImportError:
    # Fallback for direct execution
    from miner import analyze_document

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging for CLI
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def validate_url(ctx: click.Context, param: click.Parameter, value: str) -> str:
    """
    Validate that the provided URL or file path is valid.

    AI-generated comment: This validator ensures the URL is properly formatted or
    the file path exists before proceeding with the analysis.

    Args:
        ctx: Click context object
        param: Click parameter object
        value: The URL or file path value to validate

    Returns:
        The validated URL or file path string

    Raises:
        click.BadParameter: If the URL/path is invalid or inaccessible
    """
    if not value:
        return value

    # Check if it's a file path
    if not value.startswith(('http://', 'https://')):
        file_path = Path(value)
        if not file_path.exists():
            raise click.BadParameter(f"File not found: {value}")
        if not file_path.is_file():
            raise click.BadParameter(f"Not a file: {value}")
        return str(file_path.absolute())

    return value


def validate_api_key(ctx: click.Context, param: click.Parameter, value: str) -> str:
    """
    Validate that the API key is provided and not empty.
    
    AI-generated comment: This validator ensures the API key is present and
    properly formatted before making requests to the Gemini API.
    
    Args:
        ctx: Click context object
        param: Click parameter object
        value: The API key value to validate
        
    Returns:
        The validated API key string
        
    Raises:
        click.BadParameter: If the API key is missing or invalid
    """
    if not value:
        raise click.BadParameter("API key is required. Use --x-api-key or set GEMINI_API_KEY environment variable")
    
    if len(value.strip()) < 10:  # Basic length validation
        raise click.BadParameter("API key appears to be too short")
    
    return value.strip()


@click.command()
@click.option(
    "--prompt",
    "-p",
    required=True,
    help="The analysis prompt to send to Gemini AI"
)
@click.option(
    "--url",
    "-u",
    required=True,
    callback=validate_url,
    help="URL of the PDF document to analyze"
)
@click.option(
    "--x-api-key",
    callback=validate_api_key,
    envvar="GEMINI_API_KEY",
    help="Gemini API key (can also be set via GEMINI_API_KEY environment variable)"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path for saving the response (optional)"
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format for the response"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging"
)
@click.version_option(version="0.1.0", prog_name="datasheetminer")
def main(
    prompt: str,
    url: str,
    x_api_key: str,
    output: Optional[Path],
    format: str,
    verbose: bool
) -> None:
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
    # Set logging level based on verbose flag
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info(f"Starting document analysis for URL: {url}")
    logger.info(f"Prompt: {prompt}")
    
    try:
        # AI-generated comment: Process the document analysis and handle the single response.
        # The response is now a single object, not a stream.
        response = analyze_document(prompt, url, x_api_key)
        
        if not response or not hasattr(response, 'text') or not response.text.strip():
            click.echo("No response received from Gemini AI", err=True)
            sys.exit(1)
        
        full_response = response.text
        
        # Format the response based on user preference
        formatted_response = format_response(full_response, format)
        
        # Output the response
        if output:
            # Save to file
            output.write_text(formatted_response, encoding='utf-8')
            click.echo(f"Response saved to: {output}", err=True)
        else:
            # Print to stdout
            click.echo(formatted_response)
        
        logger.info("Document analysis completed successfully")
        
    except Exception as e:
        logger.error(f"Error during document analysis: {e}")
        click.echo(f"Error: {e}", err=True)
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
        return json.dumps({
            "response": response,
            "status": "success",
            "timestamp": str(Path().cwd())
        }, indent=2)
    
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
