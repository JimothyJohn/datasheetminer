from typing import Type

from google import genai
from pydantic import BaseModel

from datasheetminer.config import GUARDRAILS, MODEL, SCHEMA_CHOICES


def generate_content(doc_data: bytes, api_key: str, schema: str):
    """
    Generate AI response for document analysis.

    Args:
        doc_data: The document data in bytes
        api_key: Gemini API key for authentication
        schema: The Pydantic model to use for the response schema
    """
    client = genai.Client(api_key=api_key)

    schema_type: Type[BaseModel] = SCHEMA_CHOICES[schema]

    prompt = f"You are being presented with a catalog for an indsutrial product. Identify the individual versions along with their key specifications.\n\n{GUARDRAILS}"

    # Use faster model and add generation config for speed
    # AI-generated comment: Set stream=False to disable streaming responses.
    # This changes the function to return a single response.
    return client.models.generate_content(
        model=MODEL,
        contents=[
            genai.types.Part.from_bytes(
                data=doc_data,
                mime_type="application/pdf",
            ),
            prompt,
        ],
        config={
            "response_mime_type": "application/json",
            "response_schema": list[schema_type],
        },
    )
