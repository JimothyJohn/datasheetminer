"""
Lambda handler for the datasheetminer API.

This module contains the lambda_handler function, which is the entry point for the API.
It extracts the API key from the event headers, validates it, and uses it to generate a response from the Gemini API.

The lambda_handler function takes two arguments:
    - event: The event object from the API Gateway
    - context: The context object from the API Gateway
"""

import json
import logging
from gemini import analyze_document

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context) -> None:
    """
    Handles incoming API requests and streams the response.

    AI-generated comment: This function is decorated with `@awslambdaric.stream_response`
    to enable streaming responses from AWS Lambda. The response is written
    chunk by chunk to the output stream provided by the `context` object.

    Args:
        event (dict): The event object from API Gateway.
        context: The context object from API Gateway, which includes the output stream.
    """
    logger.info(f"Received event: {json.dumps(event)}")
    logger.info(f"Context: {context}")

    try:
        # Extract API key from headers
        headers = event.get("headers", {})
        body_raw = event.get("body", "{}")
        body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
        prompt = body.get("prompt", "")
        url = body.get("url", "")
        api_key = headers.get("x-api-key")

        if not api_key:
            logger.warning("API key missing in 'x-api-key' header.")
            context.fail("API key is missing or invalid.")
            return

        user_api_key = api_key.strip()
        if not user_api_key:
            logger.warning("API key is empty after stripping.")
            context.fail("API key is missing or invalid.")
            return

    except Exception as e:
        logger.error(f"Error processing request: {e}")
        context.fail(f"Error processing request: {e}")
        return

    try:
        response_stream = analyze_document(prompt, url, user_api_key)
        for chunk in response_stream:
            if hasattr(chunk, "text"):
                context.write(chunk.text.encode("utf-8"))

    except Exception as e:
        logger.error(f"Error during document analysis: {e}")
        # AI-generated comment: If an error occurs during streaming, log it and
        # attempt to inform the client. Note that headers may have already been sent.
        context.write(f"Error during analysis: {e}".encode("utf-8"))
        return
