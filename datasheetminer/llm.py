import logging
from typing import Any, Type

from google import genai
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from datasheetminer.config import GUARDRAILS, MODEL, SCHEMA_CHOICES


logger: logging.Logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
)
def generate_content(doc_data: bytes, api_key: str, schema: str) -> Any:
    """
    Generate AI response for document analysis.

    Args:
        doc_data: The document data in bytes
        api_key: Gemini API key for authentication
        schema: The Pydantic model to use for the response schema
    """
    client: genai.Client = genai.Client(api_key=api_key)

    schema_type: Type[BaseModel] = SCHEMA_CHOICES[schema]

    prompt: str = (
        f"You are being presented with a catalog for an industrial product. Identify the individual versions along with their key specifications.\n\n{GUARDRAILS}"
    )

    # Use faster model and add generation config for speed
    # AI-generated comment: Set stream=False to disable streaming responses.
    # This changes the function to return a single response.
    # This step can take as long as 3 minutes to complete.
    response: Any = client.models.generate_content(
        model=MODEL,
        # https://ai.google.dev/gemini-api/docs/document-processing
        contents=[
            genai.types.Part.from_bytes(
                data=doc_data,
                mime_type="application/pdf",
            ),
            prompt,
        ],
        # https://ai.google.dev/gemini-api/docs/structured-output
        config={
            "response_mime_type": "application/json",
            # https://cloud.google.com/vertex-ai/docs/model-reference/inference#generationconfig
            # AI-generated comment: Removed explicit max_output_tokens to use model's default limit.
            # Gemini 2.5 Flash has 8192 max output tokens by default, which is sufficient
            # for most datasheet extraction tasks. Setting artificially high limits may
            # cause the API to truncate responses unexpectedly.
            "response_schema": list[schema_type],  # type: ignore[valid-type]
        },
    )

    logger.debug(f"Full Gemini response: {response!r}")

    return response
