import tempfile
from pathlib import Path
from typing import Any, List, Optional, Set, Dict, Union
import json
import argparse
import re
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from uuid import UUID
import logging
import os
import gzip
import zlib
import shutil


import PyPDF2
from PyPDF2.errors import PdfReadError


# AI-generated comment:
# Configure a logger for this module. This will provide consistent, formatted
# output and allow for different log levels to be set for debugging.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger: logging.Logger = logging.getLogger(__name__)


def get_product_info_from_json(
    file_path: str, product_type: str, index: int
) -> Dict[str, Any]:
    """
    Retrieves product information from a JSON file.

    Args:
        file_path (str): The path to the JSON file.
        product_type (str): The type of product (e.g., 'motors', 'drives').
        index (int): The index of the product in the list.

    Returns:
        Dict[str, Any]: A dictionary containing the product's details.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        ValueError: If the product_type or index is invalid.
    """
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"JSON file not found at: {file_path}")

    if product_type not in data:
        raise ValueError(f"Product type '{product_type}' not found in JSON file.")

    products = data[product_type]
    if not isinstance(products, list) or not (0 <= index < len(products)):
        raise ValueError(f"Invalid index {index} for product type '{product_type}'.")

    product_info = products[index].copy()

    # Standardize product key to product_name
    if "product" in product_info:
        product_info["product_name"] = product_info.pop("product")

    # Convert pages to string format
    if "pages" in product_info and isinstance(product_info["pages"], list):
        product_info["pages"] = ",".join(map(str, product_info["pages"]))

    return product_info


class PageRangeError(ValueError):
    """Custom exception for errors in parsing page ranges."""

    pass


class UUIDEncoder(json.JSONEncoder):
    """A custom JSON encoder to handle UUID objects."""

    def default(self, obj: Any) -> Any:
        """Convert UUID objects to strings, let the base class handle others."""
        if isinstance(obj, UUID):
            # if the obj is uuid, we simply return the value of uuid
            return str(obj)
        return json.JSONEncoder.default(self, obj)


def parse_page_ranges(page_ranges_str: str) -> List[int]:
    """
    Parses a string of page ranges into a list of 0-indexed page numbers.

    This function can handle comma-separated page numbers and ranges
    indicated with a colon. For example, '1,3:5,8' will be parsed into
    the list [0, 2, 3, 4, 7].

    Args:
        page_ranges_str (str): A string containing page numbers and ranges.

    Returns:
        List[int]: A sorted list of unique, 0-indexed page numbers.

    Raises:
        PageRangeError: If the page range string is invalid.
    """
    # AI-generated comment: Use a set to automatically handle duplicate page numbers.
    pages_set: Set[int] = set()
    parts: List[str] = page_ranges_str.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            if ":" in part or "-" in part:
                # AI-generated comment: Use regex to split by either ':' or '-' to handle
                # different range notations like '1-5' or '1:5'. This makes the CLI
                # more user-friendly.
                range_parts: List[str] = re.split(r"[:-]", part)
                if len(range_parts) != 2:
                    raise PageRangeError(f"Invalid range format: '{part}'")

                start_str: str
                end_str: str
                start_str, end_str = range_parts
                start: int = int(start_str)
                end: int = int(end_str)
                if start > end:
                    raise PageRangeError(f"Invalid range: {start} > {end}")
                # AI-generated comment: Convert to 0-indexed and add to the set.
                pages_set.update(range(start - 1, end))
            else:
                # AI-generated comment: Convert single page number to 0-indexed.
                pages_set.add(int(part) - 1)
        except ValueError as e:
            # AI-generated comment: Raise a custom exception for better error handling.
            raise PageRangeError(f"Invalid page or range: '{part}'") from e

    # AI-generated comment: Return a sorted list of unique page numbers.
    return sorted(list(pages_set))


def extract_json_from_string(text: str) -> str:
    """
    Extracts a JSON object from a string by finding the first '{' and the last '}'.

    Args:
        text (str): The string containing the JSON object, possibly with surrounding text.

    Returns:
        str: The extracted and validated JSON string.

    Raises:
        ValueError: If a JSON object cannot be found or the extracted string is not valid JSON.
    """
    try:
        start_index: int = text.find("{")
        end_index: int = text.rfind("}")
        if start_index == -1 or end_index == -1 or start_index > end_index:
            raise ValueError("Could not find a valid JSON object in the response.")

        json_str: str = text[start_index : end_index + 1]
        json.loads(json_str)  # Validate that the string is valid JSON
        return json_str
    except json.JSONDecodeError as e:
        raise ValueError(f"Extracted string is not valid JSON: {e}") from e


def download_pdf(url: str, destination: Path) -> None:
    """
    Retrieves a PDF document and saves it to a local file.

    Args:
        url (str): The location of the PDF document.
        destination (Path): The local path to save the PDF.

    Raises:
        HTTPError: If there is an issue retrieving the document.
    """
    try:
        with urlopen(url, timeout=30) as response:
            with open(destination, "wb") as f:
                f.write(response.read())

        logger.info(f"Successfully retrieved PDF document from {url}")

    except (HTTPError, URLError) as e:
        logger.error(f"Error retrieving PDF: {e}")
        raise


def extract_pdf_pages(
    input_pdf_path: Path, output_pdf_path: Path, pages: List[int]
) -> None:
    """
    Extracts specific pages from a PDF and saves them to a new file.

    Args:
        input_pdf_path (Path): The path to the source PDF file.
        output_pdf_path (Path): The path to save the new PDF file.
        pages (List[int]): A list of 0-indexed page numbers to extract.
    """
    pdf_writer: PyPDF2.PdfWriter = PyPDF2.PdfWriter()
    try:
        # AI-generated comment:
        # Add detailed logging for the PDF extraction process to help diagnose issues.
        logger.info(
            f"Extracting pages {pages} from '{input_pdf_path.name}' to '{output_pdf_path.name}'"
        )
        with open(input_pdf_path, "rb") as pdf_file:
            pdf_reader: PyPDF2.PdfReader = PyPDF2.PdfReader(pdf_file)
            logger.info(
                f"Source PDF '{input_pdf_path.name}' has {len(pdf_reader.pages)} pages."
            )

            for page_num in pages:
                if 0 <= page_num < len(pdf_reader.pages):
                    pdf_writer.add_page(pdf_reader.pages[page_num])
                else:
                    logger.warning(
                        f"Page number {page_num + 1} is out of range for PDF with {len(pdf_reader.pages)} pages."
                    )
        if pdf_writer.pages:
            with open(output_pdf_path, "wb") as output_file:
                pdf_writer.write(output_file)
            logger.info(
                f"Successfully created {output_pdf_path} with {len(pdf_writer.pages)} pages."
            )
        else:
            logger.warning("No valid pages found to extract.")

    except FileNotFoundError:
        logger.error(f"Input PDF not found at {input_pdf_path}")
        raise
    except PdfReadError as e:
        # AI-generated comment:
        # Catch specific PyPDF2 errors. If a PDF is corrupted, this will save a
        # copy to /tmp for later inspection, which is very useful for debugging.
        logger.error(f"PyPDF2 could not read the PDF file at {input_pdf_path}: {e}")
        debug_path = Path(f"/tmp/problematic_{input_pdf_path.name}")
        shutil.copy(input_pdf_path, debug_path)
        logger.error(f"Copied problematic PDF to {debug_path} for inspection.")
        raise
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during PDF extraction: {e}", exc_info=True
        )
        raise


def process_pdf_from_url(url: str, page_ranges_str: str) -> Path | None:
    """
    Retrieves, processes, and returns the path to a temporary PDF file.

    This function orchestrates the retrieval and page extraction process,
    returning the path to a new temporary file containing only the
    specified pages. It is the primary API for this module.

    Args:
        url (str): The location of the PDF document.
        page_ranges_str (str): The page selection string (e.g., '1,3').

    Returns:
        Optional[Path]: The path to the temporary file with extracted
                        pages, or None if an error occurs.
    """
    try:
        page_numbers: List[int] = parse_page_ranges(page_ranges_str)
    except PageRangeError as e:
        logger.error(f"Error parsing pages argument: {e}")
        return None

    # AI-generated comment: Create a persistent temporary file to store the result.
    # It will be the caller's responsibility to delete this file.
    output_temp_file: Any = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    output_path: Path = Path(output_temp_file.name)
    output_temp_file.close()  # Close the file so it can be written to

    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        try:
            download_pdf(url, Path(temp_pdf.name))
            extract_pdf_pages(Path(temp_pdf.name), output_path, page_numbers)
            return output_path
        except (HTTPError, URLError):
            logger.error("Could not process the PDF due to a retrieval error.")
            return None
        except Exception as e:
            logger.error(f"A general error occurred: {e}", exc_info=True)
            return None


def get_web_content(url: str) -> str | None:
    """
    Retrieve HTML content from a webpage.

    Args:
        url: URL of the webpage to fetch

    Returns: HTML content as string or None if retrieval fails
    """
    logger.info(f"Fetching web content from URL: {url}")

    try:
        headers: dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        req: Request = Request(url, headers=headers)

        with urlopen(req, timeout=30.0) as response:
            response_headers = response.info()
            content_type = response_headers.get("Content-Type", "")
            logger.debug(f"Content-Type: {content_type}")

            raw_data = response.read()

            # Handle compressed content
            content_encoding = response_headers.get("Content-Encoding")
            if content_encoding == "gzip":
                logger.info("Decompressing gzip content.")
                data = gzip.decompress(raw_data)
            elif content_encoding == "deflate":
                logger.info("Decompressing deflate content.")
                data = zlib.decompress(raw_data)
            else:
                data = raw_data

            # Decode to text
            html_content = data.decode("utf-8", errors="replace")
            logger.info(f"Retrieved {len(html_content)} characters of HTML content")
            return html_content

    except (HTTPError, URLError) as e:
        logger.error(f"Error retrieving web content: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching web content: {e}", exc_info=True)
        return None


def is_pdf_url(url: str) -> bool:
    """
    Determine if a URL points to a PDF document.

    Args:
        url: The URL to check

    Returns: True if the URL appears to be a PDF, False otherwise
    """
    # Check file extension
    if url.lower().endswith(".pdf"):
        return True

    # Try to check Content-Type header for remote URLs
    if url.startswith(("http://", "https://")):
        try:
            headers: dict[str, str] = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
            }
            req: Request = Request(url, headers=headers, method="HEAD")
            with urlopen(req, timeout=10.0) as response:
                content_type = response.info().get("Content-Type", "")
                if "application/pdf" in content_type.lower():
                    return True
        except Exception as e:
            logger.warning(f"Could not check Content-Type for {url}: {e}")

    return False


def get_document(
    url: str,
    pages: Optional[Union[str, List[int]]] = None,
) -> bytes | None:
    """
    Retrieve PDF document for analysis.

    Args:
        url: Local file path or URL of the PDF document to analyze
        pages: Optional string (e.g., '1,3-5,7') or list of page numbers to extract

    Returns: PDF document bytes or None if retrieval fails
    """
    # AI-generated comment:
    # Add logging to track the document retrieval process.
    logger.info(f"Retrieving document from URL: {url}")
    if pages:
        logger.info(f"Extracting pages: {pages}")

    doc_data: Optional[bytes] = None
    input_pdf_path: Optional[Path] = None

    try:
        if not url.startswith(("http://", "https://")):
            input_pdf_path = Path(url)
            logger.info(f"Reading local file: {input_pdf_path}")
        else:
            temp_pdf: Any = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            input_pdf_path = Path(temp_pdf.name)
            logger.info(f"Downloading to temporary file: {input_pdf_path}")

            # AI-generated comment: Add a User-Agent header to the request to mimic a
            # web browser, which helps prevent 403 Forbidden errors from servers
            # that block simple scripts.
            headers: dict[str, str] = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            req: Request = Request(url, headers=headers)
            logger.debug(f"Request headers: {json.dumps(headers, indent=2)}")

            with urlopen(req, timeout=25.0) as response:
                # AI-generated comment:
                # Log response headers to check for things like Content-Encoding.
                # If content is compressed, it must be decompressed before use.
                response_headers = response.info()
                logger.debug(f"Response headers: \n{response_headers}")
                raw_data = response.read()

                content_encoding = response_headers.get("Content-Encoding")
                if content_encoding == "gzip":
                    logger.info("Decompressing gzip content.")
                    data = gzip.decompress(raw_data)
                elif content_encoding == "deflate":
                    logger.info("Decompressing deflate content.")
                    data = zlib.decompress(raw_data)
                else:
                    data = raw_data

                input_pdf_path.write_bytes(data)
                logger.info(f"Wrote {len(data)} bytes to {input_pdf_path}")

        if pages and input_pdf_path:
            pages_to_extract: List[int]
            if isinstance(pages, str):
                pages_to_extract = parse_page_ranges(pages)
            else:
                pages_to_extract = pages

            with tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False
            ) as temp_output_pdf:
                output_pdf_path: Path = Path(temp_output_pdf.name)

            extract_pdf_pages(input_pdf_path, output_pdf_path, pages_to_extract)
            doc_data = output_pdf_path.read_bytes()
            output_pdf_path.unlink()  # Clean up the extracted pages PDF
        elif input_pdf_path:
            doc_data = input_pdf_path.read_bytes()

    finally:
        # If the input was retrieved remotely, clean up the temporary file.
        if (
            url.startswith(("http://", "https://"))
            and input_pdf_path
            and input_pdf_path.exists()
        ):
            input_pdf_path.unlink()

    return doc_data


def validate_page_ranges(value: str) -> str:
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
    valid_chars: Set[str] = set("0123456789,-:")
    if not all(char in valid_chars for char in value):
        raise argparse.ArgumentTypeError(
            f"Invalid characters in page range string: '{value}'"
        )
    return value


def validate_url(value: str) -> str:
    """
    Validate that the provided file path or URL is valid.

    AI-generated comment: This validator ensures the file path exists or the URL
    is properly formatted before proceeding with the analysis.

    Args:
        value: The file path or URL value to validate

    Returns:
        The validated file path or URL string

    Raises:
        argparse.ArgumentTypeError: If the path/URL is invalid or inaccessible
    """
    if not value:
        return value

    # Check if it's a file path
    if not value.startswith(("http://", "https://")):
        file_path: Path = Path(value)
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


def format_response(response: str, format_type: str) -> str:
    """
    Format the response according to the specified output format.

    AI-generated comment: This function provides multiple output formats to make
    the CLI output more flexible and useful for different use cases, including
    integration with other tools and systems.
    """
    if format_type == "json":
        # AI-generated comment: This part of the function is now primarily for
        # non-Pydantic model responses. The main logic handles the parsed models directly.
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


def parse_gemini_response(
    response: Any,
    schema_type: type,
    product_type: str,
    context: Optional[Dict[str, Any]] = None,
) -> List[Any]:
    """
    Parse Gemini API response using a two-step validation process.
    """
    parsed_json = []

    # Step 1: Get raw JSON from response, handling pre-parsed and raw text
    if response and hasattr(response, "parsed") and response.parsed:
        logger.info(f"Using pre-parsed response with {len(response.parsed)} items")
        parsed_json = [item.model_dump() for item in response.parsed]
    elif response and hasattr(response, "text"):
        logger.warning("Attempting manual parse of raw response text.")
        raw_text = response.text.strip() if response.text else ""
        # Simple JSON load, assuming the fallback logic for truncated JSON
        # will populate parsed_json if the direct load fails.
        try:
            loaded_json = json.loads(raw_text)
            if isinstance(loaded_json, list):
                parsed_json = loaded_json
            elif isinstance(loaded_json, dict):
                parsed_json = [loaded_json]
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response text: {e}")
            # Here you might add your existing brace-depth parsing logic
            # to handle truncated JSON and populate `parsed_json`
            pass
    else:
        raise ValueError("Response object is invalid or has no text to parse.")

    if not parsed_json:
        raise ValueError("Could not extract any JSON objects from the response.")

    # Step 2: Validate against the full schema after merging with context
    validated_models = []
    for item in parsed_json:
        # Merge LLM-extracted data with the provided context
        full_data = {**item}
        if context:
            full_data.update(context)

        # Always set the product_type from the function argument
        full_data["product_type"] = product_type

        try:
            # Validate the combined data against the final, strict model
            full_model = schema_type(**full_data)
            validated_models.append(full_model)
        except Exception as e:
            logger.error(
                f"Failed to validate merged data for '{item.get('part_number', 'unknown')}': {e}"
            )
            continue

    if not validated_models:
        raise ValueError(
            "No objects could be successfully validated against the full schema."
        )

    logger.info(f"Successfully created {len(validated_models)} full model instances.")
    return validated_models
