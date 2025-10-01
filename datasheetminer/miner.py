from .llm import generate_content
import httpx
from pathlib import Path


def analyze_document(prompt: str, url: str, api_key: str):
    """
    Generate AI response for document analysis.

    Args:
        prompt: The analysis prompt
        url: URL or local file path of the PDF document to analyze
        api_key: Gemini API key for authentication

    Returns:
        Generated content response from the LLM
    """
    # Check if it's a local file path
    if not url.startswith(('http://', 'https://')):
        file_path = Path(url)
        doc_data = file_path.read_bytes()
    else:
        # Add timeout for HTTP requests to prevent hanging
        with httpx.Client(timeout=httpx.Timeout(25.0)) as http_client:
            response = http_client.get(url)
            response.raise_for_status()
            doc_data = response.content

    return generate_content(prompt, doc_data, api_key)
