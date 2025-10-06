from typing import Type
import httpx

from google import genai
from google.genai import types
from pydantic import BaseModel

from datasheetminer.config import GUARDRAILS, SCHEMA_GUIDANCE
from datasheetminer.models.drive import Drive
from datasheetminer.models.motor import Motor

MODEL = "gemini-2.5-flash"  # Explicitly define model for clarity
SCHEMA_CHOICES: dict[str, Type[BaseModel]] = {
    "motor": Motor,
    "drive": Drive,
}


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

    # Uses httpx to pull file from oneline S3 bucket, e.g. https://datasheetminer.s3.us-east-1.amazonaws.com/motor.json
    with httpx.Client() as http_client:
        response = http_client.get(
            f"https://datasheetminer.s3.us-east-1.amazonaws.com/{schema}.json"
        )
        schema_str = response.text

    prompt = f"Identify the individual components along with their key specifications. Use this guidance {SCHEMA_GUIDANCE} and this schema: {schema_str} to capture the important characteristics based on the information provided. Outline the schema as a JSON object. Create a list of JSON objects with each product found.\n\n{GUARDRAILS}"

    # Use faster model and add generation config for speed
    # AI-generated comment: Set stream=False to disable streaming responses.
    # This changes the function to return a single response.
    return client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(
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
