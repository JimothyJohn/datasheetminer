"""Anthropic Claude provider for datasheet extraction.

Mirrors ``datasheetminer.llm`` (Gemini) but sends the document to Claude
via the Messages API with ``output_config.format`` enforcing a strict
JSON Schema generated from the Pydantic model. Defaults to
``claude-opus-4-6`` with adaptive thinking and the system prompt is
cache-controlled so repeated calls in a batch share the prefix.

Streaming is on by default — the skill recommends it whenever a request
involves long input (a multi-page PDF) or a large ``max_tokens`` budget,
since it dodges per-chunk HTTP timeouts. We use ``messages.stream`` and
return the result of ``stream.get_final_message()``, so callers get the
same kind of object ``messages.create`` would return.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, Optional

import anthropic
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from datasheetminer.config import GUARDRAILS, SCHEMA_CHOICES
from datasheetminer.models.llm_schema import to_anthropic_schema


logger: logging.Logger = logging.getLogger(__name__)

# Default model — explicit per the claude-api skill, which mandates
# claude-opus-4-6 unless the caller asks for something else.
ANTHROPIC_MODEL: str = "claude-opus-4-6"

# Output token budget. Catalogs may have 20+ variants × ~400 tokens each
# plus thinking; 32K leaves headroom without exceeding the model cap.
ANTHROPIC_MAX_TOKENS: int = 32000


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    # Don't retry validation/auth/permission errors — only transient ones.
    retry=retry_if_not_exception_type(
        (
            anthropic.BadRequestError,
            anthropic.AuthenticationError,
            anthropic.PermissionDeniedError,
            anthropic.NotFoundError,
        )
    ),
)
def generate_content_anthropic(
    doc_data: bytes | str,
    api_key: str,
    schema: str,
    context: Optional[Dict[str, Any]] = None,
    content_type: str = "pdf",
    model: Optional[str] = None,
) -> Any:
    """Send a datasheet to Claude and get a strict-JSON extraction back.

    Returns the final ``anthropic.types.Message`` object (whatever
    ``stream.get_final_message()`` produces). Callers parse the JSON via
    ``datasheetminer.utils.parse_anthropic_response``.

    Args:
        doc_data: PDF bytes or HTML string.
        api_key: Anthropic API key. Falls through to the SDK's default
            (``ANTHROPIC_API_KEY`` env var) if empty/None.
        schema: Product type key into ``SCHEMA_CHOICES`` (e.g. ``"drive"``).
        context: Caller-known fields (manufacturer, product_name, ...) that
            are excluded from the schema. Mentioned in the prompt so the
            model knows it doesn't need to re-emit them.
        content_type: ``"pdf"`` or ``"html"``.
        model: Override the Anthropic model identifier. Defaults to
            ``ANTHROPIC_MODEL``.
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    full_schema_type = SCHEMA_CHOICES[schema]
    response_schema = to_anthropic_schema(full_schema_type)

    user_content: list[Any] = []
    if content_type == "pdf":
        if not isinstance(doc_data, bytes):
            raise ValueError("PDF content must be bytes")
        user_content.append(
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(doc_data).decode("ascii"),
                },
            }
        )
        logger.info(f"Analyzing PDF document ({len(doc_data)} bytes)")
    elif content_type == "html":
        if not isinstance(doc_data, str):
            raise ValueError("HTML content must be string")
        user_content.append(
            {
                "type": "text",
                "text": f"HTML Content:\n\n{doc_data}",
            }
        )
        logger.info(f"Analyzing HTML content ({len(doc_data)} characters)")
    else:
        raise ValueError(f"Unsupported content_type: {content_type}")

    context_block = ""
    if context:
        context_block = (
            "The following fields are ALREADY KNOWN and will be filled in "
            "by the caller — DO NOT emit them in your output (they're not "
            "in the response schema):\n"
            f"- product_name: {context.get('product_name')!r}\n"
            f"- manufacturer: {context.get('manufacturer')!r}\n"
            f"- product_family: {context.get('product_family')!r}\n"
            f"- datasheet_url: {context.get('datasheet_url')!r}\n\n"
        )

    single_page_nudge = ""
    if context and context.get("single_page_mode"):
        single_page_nudge = (
            "You are analyzing a SINGLE PAGE of a larger datasheet. "
            "Extract only products whose specifications visibly appear on "
            "THIS page. If no product specs are visible, return an empty "
            "products array.\n\n"
        )

    user_content.append(
        {
            "type": "text",
            "text": (
                f"{single_page_nudge}"
                "Extract one entry per distinct product VARIANT found in the "
                "document — a distinct part number, voltage class, or form "
                "factor is a separate entry. Leave optional fields null when "
                "the spec is genuinely absent; do NOT fabricate values.\n\n"
                f"{context_block}"
                f"{GUARDRAILS}"
            ),
        }
    )

    # System prompt is cache-controlled. The schema (passed via output_config)
    # plus this system text are the only invariant parts across a batch run,
    # so we mark this as ephemeral to get cache hits on every catalog after
    # the first.
    system = [
        {
            "type": "text",
            "text": (
                "You are an expert at extracting product specifications from "
                "industrial product catalogs. Your output must strictly conform "
                "to the JSON schema provided in output_config. Numeric specs "
                "with units are emitted as nested objects with explicit "
                "value/unit (or min/max/unit) keys — never as strings."
            ),
            "cache_control": {"type": "ephemeral"},
        }
    ]

    with client.messages.stream(
        model=model or ANTHROPIC_MODEL,
        max_tokens=ANTHROPIC_MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user_content}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": response_schema,
            }
        },
    ) as stream:
        response = stream.get_final_message()

    logger.debug("Anthropic response: %r", response)

    usage = getattr(response, "usage", None)
    if usage is not None:
        logger.info(
            "Anthropic usage: input=%s cache_read=%s cache_create=%s output=%s",
            getattr(usage, "input_tokens", None),
            getattr(usage, "cache_read_input_tokens", None),
            getattr(usage, "cache_creation_input_tokens", None),
            getattr(usage, "output_tokens", None),
        )

    return response
