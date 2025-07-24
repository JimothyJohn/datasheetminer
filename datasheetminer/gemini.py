from google import genai
from google.genai import types
import httpx


def analyze_document(prompt: str, url: str, api_key: str):
    """
    Asynchronously generate AI response for document analysis.

    Args:
        prompt: The analysis prompt
        url: URL of the PDF document to analyze
        api_key: Gemini API key for authentication

    Returns:
        Generated content response from Gemini AI
    """
    # DO NOT MODIFY
    client = genai.Client(api_key=api_key)

    with httpx.Client() as http_client:
        response = http_client.get(url)
        response.raise_for_status()
        doc_data = response.content

    return client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(
                data=doc_data,
                mime_type="application/pdf",
            ),
            prompt,
        ],
    )
