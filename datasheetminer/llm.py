from google import genai
from google.genai import types
from config import GUARDRAILS
import utils


def generate_content(prompt: str, doc_data: bytes, api_key: str):
    """
    Generate AI response for document analysis.

    Args:
        prompt: The analysis prompt
        doc_data: The document data in bytes
        api_key: Gemini API key for authentication

    Returns:
        Generated content response from Gemini AI
    """
    client = genai.Client(api_key=api_key)
    model = "gemini-2.5-flash"  # Explicitly define model for clarity
    prompt = f"{prompt}\n\n{GUARDRAILS}"

    # Use faster model and add generation config for speed
    # AI-generated comment: Set stream=False to disable streaming responses.
    # This changes the function to return a single response.
    return client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(
                data=doc_data,
                mime_type="application/pdf",
            ),
            prompt,
        ],
    )


def analyze_document(prompt: str, url: str, api_key: str, pages: str):
    """
    Generate AI response for document analysis.

    Args:
        prompt: The analysis prompt
        url: URL of the PDF document to analyze
        api_key: Gemini API key for authentication
        pages: The page selection string (e.g., '1,3:5')

    Returns:
        Generated content response from the LLM
    """
    # AI-generated comment: Call the synchronous utility function directly.
    processed_pdf_path = utils.process_pdf_from_url(url, pages)

    if not processed_pdf_path:
        # AI-generated comment: If PDF processing fails, return an error.
        # In a real application, you might raise an exception here.
        return "Error: Could not process the PDF."

    try:
        # AI-generated comment: Read the content of the processed, temporary PDF.
        with open(processed_pdf_path, "rb") as f:
            doc_data = f.read()
    finally:
        # AI-generated comment: Ensure the temporary file is deleted after use.
        processed_pdf_path.unlink()

    return generate_content(prompt, doc_data, api_key)
