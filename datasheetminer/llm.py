from google import genai
from google.genai import types
from config import GUARDRAILS


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
