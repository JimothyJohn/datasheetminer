import tempfile
from pathlib import Path
from typing import Any, List, Optional, Set, Dict
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


def get_document(
    url: str,
    pages_str: Optional[str] = None,
) -> bytes | None:
    """
    Retrieve PDF document for analysis.

    Args:
        url: Local file path or URL of the PDF document to analyze
        pages_str: Optional string specifying pages to extract (e.g., '1,3-5,7')

    Returns: PDF document bytes or None if retrieval fails
    """
    # AI-generated comment:
    # Add logging to track the document retrieval process.
    logger.info(f"Retrieving document from URL: {url}")
    if pages_str:
        logger.info(f"Extracting pages: {pages_str}")

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

        if pages_str and input_pdf_path:
            pages: List[int] = parse_page_ranges(pages_str)
            with tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False
            ) as temp_output_pdf:
                output_pdf_path: Path = Path(temp_output_pdf.name)

            extract_pdf_pages(input_pdf_path, output_pdf_path, pages)
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
    response: Any, schema_type: type, product_type: str
) -> List[Any]:
    """
    Parse Gemini API response with fallback strategies for incomplete/malformed responses.

    AI-generated comment: This function implements a robust two-tier parsing strategy:
    1. Try to parse the entire response as valid JSON (most reliable)
    2. Fall back to extracting complete objects using brace-depth tracking

    It also strips out any product_id fields the LLM might generate, as the program
    generates proper UUIDs automatically via Pydantic's default_factory.

    Args:
        response: The response object from Gemini API
        schema_type: The Pydantic model class to validate against
        product_type: The product type string (for logging)

    Returns:
        List of validated Pydantic model instances with auto-generated UUIDs

    Raises:
        ValueError: If no valid objects can be parsed from the response
    """
    from datasheetminer.config import SCHEMA_CHOICES

    parsed_models: List[Any] = []

    # AI-generated comment: Check the finish reason to detect truncation or errors
    if response and hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, "finish_reason"):
            finish_reason = str(candidate.finish_reason)
            logger.info(f"Response finish reason: {finish_reason}")

            # AI-generated comment: Common finish reasons:
            # - STOP: Normal completion
            # - MAX_TOKENS: Hit output token limit (response truncated)
            # - SAFETY: Blocked by safety filters
            # - RECITATION: Blocked due to recitation
            if "MAX_TOKENS" in finish_reason.upper():
                logger.error(
                    "Response was truncated due to MAX_TOKENS limit! "
                    "The model hit its output token limit. Consider:"
                    "\n  1. Reducing the number of pages analyzed"
                    "\n  2. Using a model with higher output limits"
                    "\n  3. Processing the document in smaller chunks"
                )

    # AI-generated comment: First, check if the response has already been parsed by the SDK
    if response and hasattr(response, "parsed") and response.parsed:
        logger.info(f"Using pre-parsed response with {len(response.parsed)} items")
        return response.parsed

    # AI-generated comment: If not pre-parsed, attempt manual parsing from response.text
    if not (response and hasattr(response, "text")):
        raise ValueError("Response has no text attribute to parse")

    logger.warning(
        "Failed to parse Gemini response automatically. Attempting manual parse of response text."
    )

    raw_text = response.text.strip()

    # AI-generated comment: Check for signs of truncation before attempting to parse.
    # Truncated responses typically end mid-JSON with incomplete structures.
    if raw_text and not raw_text.endswith("]"):
        logger.warning(
            f"Response appears truncated (ends with '{raw_text[-20:]}' instead of ']'). "
            "This may indicate the model hit its max_output_tokens limit or experienced an API error. "
            "Will attempt to extract complete objects only."
        )

    response_size_kb = len(raw_text) / 1024
    logger.info(f"Response size: {response_size_kb:.2f} KB ({len(raw_text)} chars)")

    parsed_json = []

    # AI-generated comment: Strategy 1 - Try to parse the entire response as valid JSON.
    # This is the most reliable approach and handles nested objects correctly.
    try:
        parsed_json_list = json.loads(raw_text)
        if isinstance(parsed_json_list, list):
            parsed_json = parsed_json_list
            logger.info(
                f"Successfully parsed complete JSON response with {len(parsed_json)} items."
            )
        elif isinstance(parsed_json_list, dict):
            # Single object response, wrap in list
            parsed_json = [parsed_json_list]
            logger.info("Successfully parsed single JSON object response.")
        else:
            raise ValueError("JSON response is neither a list nor a dict.")

    except json.JSONDecodeError as e:
        # AI-generated comment: Strategy 2 - If direct parsing fails, the response may be truncated.
        # Use brace-depth tracking to extract complete objects from the response.
        logger.warning(
            f"Full JSON parse failed ({e}). Attempting to extract complete objects from potentially truncated response."
        )

        # AI-generated comment: Log helpful debugging info about the response
        logger.debug(f"Response length: {len(raw_text)} chars")
        logger.debug(f"Response starts with: {raw_text[:100]}")
        logger.debug(f"Response ends with: {raw_text[-100:]}")

        # Find the start of the array
        list_start = raw_text.find("[")
        if list_start == -1:
            logger.error(
                "No JSON array found in response. Response might not be JSON at all."
            )
            logger.debug(f"First 500 chars: {raw_text[:500]}")
            raise ValueError("No JSON array found in response.")

        logger.debug(f"Found array start at position {list_start}")

        # Extract content after the opening bracket
        content = raw_text[list_start + 1 :]
        logger.debug(f"Extracted content length: {len(content)} chars")

        # AI-generated comment: Parse objects by tracking brace depth to handle nested structures.
        # This is more robust than splitting on `},` which breaks nested objects.
        current_obj = ""
        brace_depth = 0
        in_string = False
        escape_next = False

        for char in content:
            if escape_next:
                current_obj += char
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                current_obj += char
                continue

            if char == '"' and not escape_next:
                in_string = not in_string

            current_obj += char

            if not in_string:
                if char == "{":
                    brace_depth += 1
                elif char == "}":
                    brace_depth -= 1

                    # AI-generated comment: When brace_depth returns to 0, we have a complete object
                    if brace_depth == 0:
                        obj_str = current_obj.strip().rstrip(",")
                        # AI-generated comment: Skip empty strings - these cause "Expecting value" errors
                        if obj_str and obj_str != "{}":
                            try:
                                obj = json.loads(obj_str)
                                parsed_json.append(obj)
                                logger.debug(
                                    f"Extracted complete object: {obj.get('product_name', 'unknown')}"
                                )
                            except json.JSONDecodeError as obj_error:
                                logger.warning(
                                    f"Failed to parse object (length {len(obj_str)}): {obj_error}"
                                )
                                # Log first 200 chars of problematic object for debugging
                                logger.debug(
                                    f"Problematic object preview: {obj_str[:200]}..."
                                )
                        current_obj = ""

        if not parsed_json:
            raise ValueError(
                "No complete JSON objects could be extracted from response."
            )

        logger.info(
            f"Successfully extracted {len(parsed_json)} complete objects from response."
        )

    # AI-generated comment: Remove any product_id fields that the LLM might have generated.
    # The program generates UUIDs automatically via default_factory=uuid4 in the model.
    # LLMs generate malformed UUIDs, so we strip them out and let Pydantic create proper ones.
    for obj in parsed_json:
        if "product_id" in obj:
            removed_id = obj.pop("product_id")
            logger.debug(
                f"Removed LLM-generated product_id '{removed_id}' for {obj.get('product_name', 'unknown')}. "
                "Program will generate a proper UUID."
            )

    # AI-generated comment: Validate extracted JSON objects against the expected schema
    model_class = SCHEMA_CHOICES[product_type]
    validated_models = []
    for i, item in enumerate(parsed_json):
        try:
            validated_model = model_class.model_validate(item)
            validated_models.append(validated_model)
        except Exception as e:
            logger.error(
                f"Failed to validate item {i} ({item.get('product_name', 'unknown')}): {e}"
            )
            # Continue processing other items even if one fails
            continue

    if not validated_models:
        raise ValueError("No valid objects could be validated against the schema.")

    logger.info(
        f"Successfully validated {len(validated_models)}/{len(parsed_json)} items against {product_type} schema."
    )

    return validated_models
