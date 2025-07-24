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

# Never convert this to .gemini it will break the cloud service and throw an import error
from gemini import analyze_document

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context) -> dict:
    """
    Handles incoming API requests.

    Args:
        event (dict): The event object from API Gateway.
        context: The context object from API Gateway.

    Returns:
        dict: A dictionary containing the status code, body, and headers.
    """
    logger.info(f"Received event: {json.dumps(event)}")
    logger.info(f"Context: {context}")

    try:
        # Extract API key from headers
        headers = event.get("headers", {})

        # Body can be a string or dict, so we handle both
        body_raw = event.get("body", "{}")
        if isinstance(body_raw, str):
            body = json.loads(body_raw)
        else:
            body = body_raw

        prompt = body.get("prompt", "")
        url = body.get("url", "")
        # API Gateway header keys are lowercased, so we look for 'x-api-key'.
        # This avoids conflicts with the standard 'Authorization' header used by AWS.
        api_key = headers.get("x-api-key")

        if not api_key:
            logger.warning("API key missing in 'x-api-key' header.")
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "error": {
                            "message": "API key is missing or invalid.",
                            "type": "authentication_error",
                        }
                    }
                ),
                "headers": {"Content-Type": "application/json"},
            }

        user_api_key = api_key.strip()

        if not user_api_key:
            logger.warning("API key is empty after stripping.")
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "error": {
                            "message": "API key is missing or invalid.",
                            "type": "authentication_error",
                        }
                    }
                ),
                "headers": {"Content-Type": "application/json"},
            }

    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }

    try:
        response = analyze_document(prompt, url, user_api_key)
    except Exception as e:
        logger.error(f"Error during document analysis: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }

    if not hasattr(response, "text"):
        logger.error(
            "Response object from analyze_document is missing 'text' attribute."
        )
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "Invalid or malformed response from document analysis service."
                }
            ),
            "headers": {"Content-Type": "application/json"},
        }

    return {
        "statusCode": 200,
        "body": json.dumps({"message": response.text}),
        "headers": {"Content-Type": "application/json"},
    }
