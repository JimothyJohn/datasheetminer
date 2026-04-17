"""Gemini call that proposes a ProposedModel from a PDF.

Uses Gemini's structured-output mode with ``response_schema=ProposedModel``
— the ``google.genai`` SDK converts the Pydantic class to Gemini's
OpenAPI-subset schema internally, so the response text is JSON matching
``ProposedModel``'s shape.

Large PDFs (>20 MB) route through the Files API to stay under the inline
upload cap; the file is deleted after the call so storage doesn't
accumulate across runs.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any, Dict, Optional, Type

from google import genai
from google.genai import types as genai_types
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from datasheetminer.config import MODEL, SCHEMA_CHOICES
from datasheetminer.models.product import ProductBase
from datasheetminer.schemagen.meta_schema import ProposedModel
from datasheetminer.schemagen.prompt import build_system_prompt, build_user_prompt
from datasheetminer.utils import _strip_json_fences

logger: logging.Logger = logging.getLogger(__name__)

GEMINI_MAX_TOKENS: int = 16000

# Route binary PDFs at or above this size through the Files API. Gemini's
# inline document cap is around 20 MB; bigger catalogs need the upload path.
FILES_API_SIZE_THRESHOLD_BYTES: int = 20 * 1024 * 1024


def _should_retry(exc: BaseException) -> bool:
    """Retry transient transport errors; bail on 4xx client errors."""
    from google.genai import errors as genai_errors

    if isinstance(exc, genai_errors.ClientError):
        return False
    return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    retry=retry_if_exception(_should_retry),
)
def propose_model(
    pdf_bytes: bytes,
    product_type: str,
    api_key: str,
    schema_choices: Optional[Dict[str, Type[ProductBase]]] = None,
    model: str = MODEL,
    max_fields: int = 30,
) -> ProposedModel:
    """Send ``pdf_bytes`` to Gemini and return a validated ``ProposedModel``.

    Large PDFs auto-upload via the Files API and are deleted afterwards.

    Args:
        pdf_bytes: Raw datasheet bytes.
        product_type: snake_case product type key (e.g. ``"contactor"``).
        api_key: Gemini API key. Falls through to ``GEMINI_API_KEY`` env
            var when empty.
        schema_choices: Registry of existing product types to reflect over
            for examples and the reuse-registry. Defaults to the live
            ``SCHEMA_CHOICES`` — override in tests.
        model: Gemini model id.
        max_fields: Soft cap surfaced in the user prompt.

    Raises:
        google.genai.errors.ClientError: transport/auth errors (not retried
            for auth, file-size, or other non-transient conditions).
        ValueError: the LLM returned output that fails ``ProposedModel``
            validation or isn't valid JSON.
    """
    if schema_choices is None:
        schema_choices = SCHEMA_CHOICES

    client = genai.Client(api_key=api_key) if api_key else genai.Client()

    system_prompt = build_system_prompt(schema_choices)
    user_prompt = build_user_prompt(product_type, max_fields)

    use_files_api = len(pdf_bytes) >= FILES_API_SIZE_THRESHOLD_BYTES
    uploaded_file: Any = None

    try:
        if use_files_api:
            logger.info(
                "schemagen: PDF is %.1f MB; uploading via Files API",
                len(pdf_bytes) / (1024 * 1024),
            )
            uploaded_file = client.files.upload(
                file=io.BytesIO(pdf_bytes),
                config={"mime_type": "application/pdf"},
            )
            pdf_part: Any = uploaded_file
        else:
            pdf_part = genai_types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf",
            )

        logger.info(
            "schemagen: calling %s with %d-byte PDF for product_type=%r (transport=%s)",
            model,
            len(pdf_bytes),
            product_type,
            "files_api" if use_files_api else "inline",
        )

        response = client.models.generate_content(
            model=model,
            contents=[pdf_part, user_prompt],
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=ProposedModel,
                max_output_tokens=GEMINI_MAX_TOKENS,
            ),
        )
    finally:
        # Files persist until deleted; clean up regardless of success so we
        # don't leak storage on retry loops or validation errors.
        if uploaded_file is not None:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception as e:
                logger.warning(
                    "Failed to delete uploaded file %s: %s — clean up manually",
                    uploaded_file.name,
                    e,
                )

    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        logger.info(
            "schemagen usage: input=%s output=%s cache_read=%s",
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
            getattr(usage, "cached_content_token_count", None),
        )

    raw_text = getattr(response, "text", None) or ""
    if not raw_text:
        raise ValueError("Gemini response has no text content.")
    raw_text = _strip_json_fences(raw_text)
    if not raw_text:
        raise ValueError("Empty Gemini response text; cannot parse JSON.")

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini response was not valid JSON: {e}") from e

    return ProposedModel.model_validate(payload)
