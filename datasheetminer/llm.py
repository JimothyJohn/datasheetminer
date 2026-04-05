import logging
from typing import Any, Optional, Dict

from google import genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from datasheetminer.config import GUARDRAILS, MODEL, SCHEMA_CHOICES
from datasheetminer.models.csv_schema import build_columns, header_row


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
        schema: The name of the product type (key into SCHEMA_CHOICES)
        context: Optional context with pre-defined specs for the LLM
        content_type: Type of content - "pdf" or "html" (default: "pdf")
    """
    client: genai.Client = genai.Client(api_key=api_key)

    full_schema_type = SCHEMA_CHOICES[schema]
    columns = build_columns(full_schema_type)
    csv_header = header_row(columns)

    # Build a terse per-column hint so the LLM understands list/numeric
    # semantics without us having to repeat instructions in prose.
    hint_lines = []
    for col in columns:
        if col.kind == "list":
            hint_lines.append(f"- {col.header}: pipe-separated list (e.g. A|B|C)")
        elif col.kind in ("value", "min", "max"):
            hint_lines.append(f"- {col.header}: plain number, unit is {col.unit}")
    hints = "\n".join(hint_lines)

    context_block = ""
    if context:
        context_block = f"""The following information is already known (do NOT repeat it in your output):
- Product Name: {context.get("product_name")}
- Manufacturer: {context.get("manufacturer")}
- Product Family: {context.get("product_family")}
- Datasheet URL: {context.get("datasheet_url")}

"""

    prompt = f"""You are extracting product specifications from an industrial catalog.

{context_block}Return the data as CSV. The FIRST row MUST be exactly this header:
{csv_header}

Then one row per product variant found in the document.

Formatting rules:
- Leave a cell EMPTY when the specification is absent. Do not write "null" or "N/A".
- Numeric columns contain plain numbers only — no units, no "+", no "~". The unit is already in the column header.
- For range columns (*_min / *_max), fill both sides when the spec is a range; fill only one when it's a single value.
- List columns (marked below) use "|" as the separator.
- Wrap any cell containing a comma in double quotes.

Column details:
{hints}

{GUARDRAILS}
"""

    contents: list[Any] = []

    if content_type == "pdf":
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
        if not isinstance(doc_data, str):
            raise ValueError("HTML content must be string")
        contents = [f"HTML Content:\n\n{doc_data}\n\n{prompt}"]
        logger.info(f"Analyzing HTML content ({len(doc_data)} characters)")
    else:
        raise ValueError(f"Unsupported content_type: {content_type}")

    # Plain-text response; CSV is enforced by the prompt and parsed locally.
    response: Any = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config={
            "response_mime_type": "text/plain",
            "max_output_tokens": 65536,
        },
    )

    logger.debug(f"Full Gemini response: {response!r}")

    return response
