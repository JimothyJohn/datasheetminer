import logging
from typing import Any, Type, Optional, Dict

from google import genai
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from datasheetminer.config import GUARDRAILS, MODEL, SCHEMA_CHOICES
from datasheetminer.models.factory import create_llm_schema


logger: logging.Logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
)
def generate_content(
    doc_data: bytes | str,
    api_key: str,
    schema: str,
    context: Optional[Dict[str, Any]] = None,
    content_type: str = "pdf",
) -> Any:
    """
    Generate AI response for document analysis.

    Args:
        doc_data: The document data (bytes for PDF, string for HTML)
        api_key: Gemini API key for authentication
        schema: The Pydantic model to use for the response schema
        context: Optional context with pre-defined specs for the LLM
        content_type: Type of content - "pdf" or "html" (default: "pdf")
    """
    client: genai.Client = genai.Client(api_key=api_key)

    full_schema_type: Type[BaseModel] = SCHEMA_CHOICES[schema]
    llm_schema = create_llm_schema(full_schema_type)

    prompt: str
    if context:
        prompt = f"""You are being presented with a catalog for an industrial product.
The following information is already known:
- Product Name: {context.get("product_name")}
- Manufacturer: {context.get("manufacturer")}
- Product Family: {context.get("product_family")}
- Datasheet URL: {context.get("datasheet_url")}

Your task is to identify the individual product versions from the document and extract their key technical specifications.
Do NOT include the product_name, manufacturer, product_family, or datasheet_url in your response.

For any field that requires a value and a unit (e.g., weight, torque, voltage), format it as a single string: "value;unit".
For fields representing a range, use the format: "min-max;unit".
Example: "rated_current": "2.5;A", "rated_voltage": "100-200;V"

Focus only on the fields defined in the response schema.

{GUARDRAILS}
"""
    else:
        prompt = f"""You are being presented with a catalog for an industrial product. Identify the individual versions along with their key specifications.

For any field that requires a value and a unit (e.g., weight, torque, voltage), format it as a single string: "value;unit".
For fields representing a range, use the format: "min-max;unit".
Example: "rated_current": "2.5;A", "rated_voltage": "100-200;V"

{GUARDRAILS}
"""

    # Prepare content parts based on content type
    contents: list[Any] = []

    if content_type == "pdf":
        # PDF content - send as bytes with appropriate MIME type
        if not isinstance(doc_data, bytes):
            raise ValueError("PDF content must be bytes")

        contents = [
            genai.types.Part.from_bytes(
                data=doc_data,
                mime_type="application/pdf",
            ),
            prompt,
        ]
        logger.info(f"Analyzing PDF document ({len(doc_data)} bytes)")

    elif content_type == "html":
        # HTML content - send as text
        if not isinstance(doc_data, str):
            raise ValueError("HTML content must be string")

        contents = [
            f"HTML Content:\n\n{doc_data}\n\n{prompt}",
        ]
        logger.info(f"Analyzing HTML content ({len(doc_data)} characters)")

    else:
        raise ValueError(f"Unsupported content_type: {content_type}")

    # Use faster model and add generation config for speed
    # AI-generated comment: Set stream=False to disable streaming responses.
    # This changes the function to return a single response.
    # This step can take as long as 3 minutes to complete.
    response: Any = client.models.generate_content(
        model=MODEL,
        contents=contents,
        # https://ai.google.dev/gemini-api/docs/structured-output
        config={
            "response_mime_type": "application/json",
            # https://cloud.google.com/vertex-ai/docs/model-reference/inference#generationconfig
            # AI-generated comment: Removed explicit max_output_tokens to use model's default limit.
            # Gemini 2.5 Flash has 8192 max output tokens by default, which is sufficient
            # for most datasheet extraction tasks. Setting artificially high limits may
            # cause the API to truncate responses unexpectedly.
            "max_output_tokens": 65536,
            "response_schema": list[llm_schema],  # type: ignore[valid-type]
        },
    )

    logger.debug(f"Full Gemini response: {response!r}")

    return response
