"""
Unit tests for the lambda handler.

This module contains tests for the lambda_handler function.
It uses pytest and unittest.mock.
"""

from unittest.mock import patch, MagicMock
import pytest
import json

# AI-generated comment:
# Mock the 'awslambdaric.stream_response' decorator before importing the 'app' module.
# The local 'awslambdaric' library does not include this decorator, which is only
# available in the AWS Lambda execution environment. This mock is an identity
# function that allows the tests to run without raising an AttributeError.
patch('awslambdaric.stream_response', lambda func: func).start()

# AI-generated comment:
# Mock 'awslambdaric.bootstrap' to prevent errors when 'set_header' is called.
# This function is part of the response streaming functionality and is not
# needed for unit testing the handler's logic.
patch('awslambdaric.bootstrap', MagicMock()).start()

from datasheetminer import app


@pytest.fixture()
def apigw_event():
    """
    Generates API GW Event.

    AI-generated comment:
    This fixture provides a sample API Gateway event. The 'body' is a JSON string,
    which simulates a typical request from API Gateway.
    """
    return {
        "body": '{"prompt": "test prompt", "url": "https://example.com/test.pdf"}',
        "headers": {
            "x-api-key": "test-api-key",
        },
        # AI-generated comment:
        # Including a minimal requestContext to ensure the handler can execute
        # without errors related to missing keys.
        "requestContext": {},
    }


@pytest.fixture
def mock_context():
    """
    Creates a mock context object for the Lambda handler.

    AI-generated comment:
    This fixture creates a mock context object for the Lambda handler.
    It includes mock 'write' and 'fail' methods to allow tests to verify
    that the handler interacts with the context object as expected for both
    successful streaming responses and error conditions.
    """
    return MagicMock()


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler(mock_analyze_document, apigw_event, mock_context):
    """
    Tests the lambda_handler's happy path for a streaming response.
    """
    # AI-generated comment:
    # Mock the 'analyze_document' function to return an iterable of chunks,
    # simulating a streaming response. Each chunk has a 'text' attribute,
    # which the handler will write to the response stream.
    mock_chunk = MagicMock()
    mock_chunk.text = "This is a test response."
    mock_analyze_document.return_value = [mock_chunk]

    app.lambda_handler(apigw_event, mock_context)

    # AI-generated comment:
    # Verify that the handler wrote the expected content to the stream.
    # The content should be UTF-8 encoded.
    mock_context.write.assert_called_once_with("This is a test response.".encode("utf-8"))
    mock_context.fail.assert_not_called()


def test_lambda_handler_missing_api_key(apigw_event, mock_context):
    """
    Tests the lambda_handler with a missing API key.
    """
    # AI-generated comment:
    # This test simulates a request where the 'x-api-key' header is missing.
    # The handler is expected to call 'context.fail' with an appropriate error message.
    del apigw_event["headers"]["x-api-key"]
    app.lambda_handler(apigw_event, mock_context)
    mock_context.fail.assert_called_once_with("API key is missing or invalid.")


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_invalid_api_key_format(mock_analyze_document, apigw_event, mock_context):
    """
    Tests the lambda_handler with an invalid API key format (empty string).
    """
    # AI-generated comment:
    # This test simulates a request with an empty 'x-api-key' header.
    # The handler should call 'context.fail' and not proceed to call 'analyze_document'.
    apigw_event["headers"]["x-api-key"] = ""
    app.lambda_handler(apigw_event, mock_context)
    mock_context.fail.assert_called_once_with("API key is missing or invalid.")
    mock_analyze_document.assert_not_called()


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_missing_url(mock_analyze_document, apigw_event, mock_context):
    """
    Tests the lambda_handler with a missing URL in the request body.
    """
    # AI-generated comment:
    # This test ensures that the handler correctly processes requests with a missing URL.
    # 'analyze_document' should be called with an empty string for the URL.
    body = json.loads(apigw_event["body"])
    del body["url"]
    apigw_event["body"] = json.dumps(body)

    mock_analyze_document.return_value = []

    app.lambda_handler(apigw_event, mock_context)

    prompt = body.get("prompt", "")
    api_key = apigw_event["headers"]["x-api-key"]

    mock_analyze_document.assert_called_once_with(prompt, "", api_key)
    mock_context.fail.assert_not_called()


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_missing_prompt(mock_analyze_document, apigw_event, mock_context):
    """
    Tests the lambda_handler with a missing prompt in the request body.
    """
    # AI-generated comment:
    # This test verifies that the handler correctly handles requests with a missing prompt.
    # 'analyze_document' should be called with an empty string for the prompt.
    body = json.loads(apigw_event["body"])
    del body["prompt"]
    apigw_event["body"] = json.dumps(body)

    mock_analyze_document.return_value = []

    app.lambda_handler(apigw_event, mock_context)

    url = body.get("url", "")
    api_key = apigw_event["headers"]["x-api-key"]

    mock_analyze_document.assert_called_once_with("", url, api_key)
    mock_context.fail.assert_not_called()


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_analyze_document_exception(mock_analyze_document, apigw_event, mock_context):
    """
    Tests the lambda_handler when analyze_document raises an exception.
    """
    # AI-generated comment:
    # This test simulates an exception occurring within 'analyze_document'. The handler
    # should catch the exception and write an error message to the response stream.
    test_exception = Exception("Test exception")
    mock_analyze_document.side_effect = test_exception
    app.lambda_handler(apigw_event, mock_context)
    mock_context.write.assert_called_once_with(f"Error during analysis: {test_exception}".encode("utf-8"))
    mock_context.fail.assert_not_called()


def test_lambda_handler_malformed_json(apigw_event, mock_context):
    """
    Tests the lambda_handler with malformed JSON in the request body.
    """
    # AI-generated comment:
    # This test provides a malformed JSON string in the body. The handler
    # should fail gracefully by calling 'context.fail'.
    apigw_event["body"] = "{ invalid json"
    app.lambda_handler(apigw_event, mock_context)
    mock_context.fail.assert_called()


def test_lambda_handler_none_body(apigw_event, mock_context):
    """
    Tests the lambda_handler with None as the request body.
    """
    # AI-generated comment:
    # This test simulates a request with a 'None' body. The handler should
    # treat this as an error and call 'context.fail'.
    apigw_event["body"] = None
    app.lambda_handler(apigw_event, mock_context)
    mock_context.fail.assert_called()


def test_lambda_handler_missing_headers(apigw_event, mock_context):
    """
    Tests the lambda_handler with missing headers entirely.
    """
    # AI-generated comment:
    # Simulates a request where the 'headers' object is missing. The handler should
    # fail because it cannot find the required API key.
    del apigw_event["headers"]
    app.lambda_handler(apigw_event, mock_context)
    mock_context.fail.assert_called_once_with("API key is missing or invalid.")


def test_lambda_handler_whitespace_api_key(apigw_event, mock_context):
    """
    Tests the lambda_handler with whitespace-only API key.
    """
    # AI-generated comment:
    # This test provides an API key that contains only whitespace. The handler should
    # correctly identify this as an invalid key and call 'context.fail'.
    apigw_event["headers"]["x-api-key"] = "   \n\t   "
    app.lambda_handler(apigw_event, mock_context)
    mock_context.fail.assert_called_once_with("API key is missing or invalid.")


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_dict_body(mock_analyze_document, apigw_event, mock_context):
    """
    Tests the lambda_handler when body is already a dict (not string).
    """
    # AI-generated comment:
    # This test provides the body as a dictionary instead of a JSON string. The handler
    # should be able to process this without trying to parse it as JSON.
    test_body = {"prompt": "test prompt", "url": "https://example.com/test.pdf"}
    apigw_event["body"] = test_body

    mock_chunk = MagicMock()
    mock_chunk.text = "Dict body response"
    mock_analyze_document.return_value = [mock_chunk]

    app.lambda_handler(apigw_event, mock_context)

    mock_context.write.assert_called_once_with("Dict body response".encode("utf-8"))
    mock_context.fail.assert_not_called()

@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_minimal_event(mock_analyze_document, mock_context):
    """
    Tests the lambda_handler with minimal required event structure.
    """
    minimal_event = {
        "body": '{"prompt": "test", "url": "https://example.com/test.pdf"}',
        "headers": {"x-api-key": "test-key"},
    }
    mock_chunk = MagicMock()
    mock_chunk.text = "Minimal event response"
    mock_analyze_document.return_value = [mock_chunk]

    app.lambda_handler(minimal_event, mock_context)
    
    mock_context.write.assert_called_once_with("Minimal event response".encode("utf-8"))
    mock_context.fail.assert_not_called()

@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_case_insensitive_headers(mock_analyze_document, apigw_event, mock_context):
    """
    Tests that API key lookup fails with different case variations if not handled.
    """
    # Remove the lowercase version and add uppercase
    del apigw_event["headers"]["x-api-key"]
    apigw_event["headers"]["X-API-KEY"] = "test-api-key"

    app.lambda_handler(apigw_event, mock_context)

    # API Gateway automatically lowercases headers, but a direct invocation might not.
    # The current implementation `headers.get("x-api-key")` is case-sensitive.
    mock_context.fail.assert_called_once_with("API key is missing or invalid.")
    mock_analyze_document.assert_not_called()

def test_lambda_handler_empty_string_body(apigw_event, mock_context):
    """
    Tests the lambda_handler with empty string body.
    """
    # AI-generated comment:
    # An empty string body should be treated as invalid input since it cannot
    # be parsed as JSON to extract 'prompt' and 'url'.
    apigw_event["body"] = ""
    app.lambda_handler(apigw_event, mock_context)
    mock_context.fail.assert_called()
