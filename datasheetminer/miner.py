from llm import generate_content
import httpx
from pathlib import Path
from typing import Optional
import tempfile
from utils import extract_pdf_pages, parse_page_ranges


def analyze_document(
    prompt: str, url: str, api_key: str, pages_str: Optional[str] = None
):
    """
    Generate AI response for document analysis.

    Args:
        prompt: The analysis prompt
        url: URL or local file path of the PDF document to analyze
        api_key: Gemini API key for authentication
        pages_str: Optional string specifying pages to extract (e.g., '1,3-5,7')

    Returns:
        Generated content response from the LLM
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

    if doc_data:
        return generate_content(prompt, doc_data, api_key)
    else:
        # Handle case where doc_data could not be created
        raise Exception("Could not process PDF to generate document data.")
