import tempfile
from pathlib import Path
from typing import List, Set, Optional
import json
import argparse

import PyPDF2

import httpx


class PageRangeError(ValueError):
    """Custom exception for errors in parsing page ranges."""

    pass


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
    parts = page_ranges_str.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            if ":" in part:
                start_str, end_str = part.split(":")
                start = int(start_str)
                end = int(end_str)
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
        start_index = text.find("{")
        end_index = text.rfind("}")
        if start_index == -1 or end_index == -1 or start_index > end_index:
            raise ValueError("Could not find a valid JSON object in the response.")

        json_str = text[start_index : end_index + 1]
        json.loads(json_str)  # Validate that the string is valid JSON
        return json_str
    except json.JSONDecodeError as e:
        raise ValueError(f"Extracted string is not valid JSON: {e}") from e


def download_pdf(url: str, destination: Path) -> None:
    """
    Synchronously downloads a PDF from a URL and saves it to a local file.

    Args:
        url (str): The URL of the PDF to download.
        destination (Path): The local path to save the downloaded PDF.

    Raises:
        HTTPError: If there is an issue with the download.
    """
    # AI-generated comment: Use a standard httpx call for synchronous download.
    try:
        response = httpx.get(url, timeout=30)
        response.raise_for_status()  # Raises an exception for bad status codes
        with open(destination, "wb") as f:
            f.write(response.content)

        print(f"Successfully downloaded PDF from {url}")

    except httpx.HTTPError as e:
        print(f"Error downloading PDF: {e}")
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
    pdf_writer = PyPDF2.PdfWriter()
    try:
        with open(input_pdf_path, "rb") as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            for page_num in pages:
                if 0 <= page_num < len(pdf_reader.pages):
                    pdf_writer.add_page(pdf_reader.pages[page_num])
                else:
                    print(f"Warning: Page number {page_num + 1} is out of range.")
        if pdf_writer.pages:
            with open(output_pdf_path, "wb") as output_file:
                pdf_writer.write(output_file)
            print(f"Successfully created {output_pdf_path}")
        else:
            print("No valid pages found to extract.")

    except FileNotFoundError:
        print(f"Error: Input PDF not found at {input_pdf_path}")
    except Exception as e:
        print(f"An error occurred: {e}")


def process_pdf_from_url(url: str, page_ranges_str: str) -> Path | None:
    """
    Downloads, processes, and returns the path to a temporary PDF file.

    This function orchestrates the download and page extraction process,
    returning the path to a new temporary file containing only the
    specified pages. It is the primary API for this module.

    Args:
        url (str): The URL of the PDF to download.
        page_ranges_str (str): The page selection string (e.g., '1,3:5').

    Returns:
        Optional[Path]: The path to the temporary file with extracted
                        pages, or None if an error occurs.
    """
    try:
        page_numbers = parse_page_ranges(page_ranges_str)
    except PageRangeError as e:
        print(f"Error parsing pages argument: {e}")
        return None

    # AI-generated comment: Create a persistent temporary file to store the result.
    # It will be the caller's responsibility to delete this file.
    output_temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    output_path = Path(output_temp_file.name)
    output_temp_file.close()  # Close the file so it can be written to

    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        try:
            download_pdf(url, Path(temp_pdf.name))
            extract_pdf_pages(Path(temp_pdf.name), output_path, page_numbers)
            return output_path
        except httpx.HTTPError:
            print("Could not process the PDF due to a download error.")
            return None
        except Exception as e:
            print(f"A general error occurred: {e}")
            return None


def get_document(
    url: str,
    pages_str: Optional[str] = None,
) -> bytes | None:
    """
    Generate AI response for document analysis.

    Args:
        url: URL or local file path of the PDF document to analyze
        pages_str: Optional string specifying pages to extract (e.g., '1,3-5,7')

    Returns: None
    """
    doc_data = None
    input_pdf_path = None

    try:
        if not url.startswith(("http://", "https://")):
            input_pdf_path = Path(url)
        else:
            temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            input_pdf_path = Path(temp_pdf.name)
            with httpx.Client(timeout=httpx.Timeout(25.0)) as http_client:
                response = http_client.get(url)
                response.raise_for_status()
                input_pdf_path.write_bytes(response.content)

        if pages_str and input_pdf_path:
            pages = parse_page_ranges(pages_str.replace("-", ":"))
            with tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False
            ) as temp_output_pdf:
                output_pdf_path = Path(temp_output_pdf.name)

            extract_pdf_pages(input_pdf_path, output_pdf_path, pages)
            doc_data = output_pdf_path.read_bytes()
            output_pdf_path.unlink()  # Clean up the extracted pages PDF
        elif input_pdf_path:
            doc_data = input_pdf_path.read_bytes()

    finally:
        # If the input was a URL, a temporary file was created for it.
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
    properly formatted before making httpx to the Gemini API.

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
