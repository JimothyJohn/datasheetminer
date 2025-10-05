import argparse
import tempfile
from pathlib import Path
from typing import List, Set
import json

import requests
import PyPDF2
from requests import HTTPError


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
    # AI-generated comment: Use a standard requests call for synchronous download.
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raises an exception for bad status codes
        with open(destination, "wb") as f:
            f.write(response.content)

        print(f"Successfully downloaded PDF from {url}")

    except HTTPError as e:
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
        except HTTPError:
            print("Could not process the PDF due to a download error.")
            return None
        except Exception as e:
            print(f"A general error occurred: {e}")
            return None


def main() -> None:
    """
    Main function to handle command-line arguments and orchestrate the PDF extraction.
    """
    parser = argparse.ArgumentParser(
        description="Download a PDF and extract specific pages."
    )
    parser.add_argument("url", help="The URL of the PDF to download.")
    parser.add_argument(
        "pages",
        help="The pages to extract, e.g., '1,3:5,8' for pages 1, 3, 4, 5, and 8.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="extracted_pages.pdf",
        help="The name of the output PDF file.",
    )

    args = parser.parse_args()

    # AI-generated comment: Use the new process_pdf_from_url function for the CLI.
    processed_pdf_path = process_pdf_from_url(args.url, args.pages)

    if processed_pdf_path:
        # AI-generated comment: Move the temporary file to the desired output location.
        final_output_path = Path(args.output)
        try:
            processed_pdf_path.rename(final_output_path)
            print(f"Final output saved to {final_output_path}")
        except OSError as e:
            print(f"Error moving file: {e}")
            # AI-generated comment: Clean up the temporary file if the move fails.
            processed_pdf_path.unlink()


if __name__ == "__main__":
    # AI-generated comment: Run the main synchronous function.
    main()
