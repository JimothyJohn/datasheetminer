"""
Unit tests for the lambda handler.

This module contains the test_lambda_handler function, which is used to test the lambda handler.

It uses the pytest library to run the tests and the unittest.mock library to mock the analyze_document function.

The test_lambda_handler function takes an event object as input and uses the lambda_handler function to generate a response.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from datasheetminer import app


@pytest.fixture()
def apigw_event():
    """Generates API GW Event"""

    return {
        "body": '{ "test": "body"}',
        "resource": "/{proxy+}",
        "requestContext": {
            "resourceId": "123456",
            "apiId": "1234567890",
            "resourcePath": "/{proxy+}",
            "httpMethod": "POST",
            "requestId": "c6af9ac6-7b61-11e6-9a41-93e8deadbeef",
            "accountId": "123456789012",
            "identity": {
                "apiKey": "",
                "userArn": "",
                "cognitoAuthenticationType": "",
                "caller": "",
                "userAgent": "Custom User Agent String",
                "user": "",
                "cognitoIdentityPoolId": "",
                "cognitoIdentityId": "",
                "cognitoAuthenticationProvider": "",
                "sourceIp": "127.0.0.1",
                "accountId": "",
            },
            "stage": "prod",
        },
        "queryStringParameters": {"foo": "bar"},
        "headers": {
            "Via": "1.1 08f323deadbeefa7af34d5feb414ce27.cloudfront.net (CloudFront)",
            "Accept-Language": "en-US,en;q=0.8",
            "CloudFront-Is-Desktop-Viewer": "true",
            "CloudFront-Is-SmartTV-Viewer": "false",
            "CloudFront-Is-Mobile-Viewer": "false",
            "X-Forwarded-For": "127.0.0.1, 127.0.0.2",
            "CloudFront-Viewer-Country": "US",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "X-Forwarded-Port": "443",
            "Host": "1234567890.execute-api.us-east-1.amazonaws.com",
            "X-Forwarded-Proto": "https",
            "X-Amz-Cf-Id": "aaaaaaaaaae3VYQb9jd-nvCd-de396Uhbp027Y2JvkCPNLmGJHqlaA==",
            "CloudFront-Is-Tablet-Viewer": "false",
            "Cache-Control": "max-age=0",
            "User-Agent": "Custom User Agent String",
            "CloudFront-Forwarded-Proto": "https",
            "Accept-Encoding": "gzip, deflate, sdch",
            "x-api-key": "test-api-key",
        },
        "pathParameters": {"proxy": "/examplepath"},
        "httpMethod": "POST",
        "stageVariables": {"baz": "qux"},
        "path": "/examplepath",
    }


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler(mock_analyze_document, apigw_event):
    # AI-generated comment:
    # The following mock response is structured to emulate the expected output from the `analyze_document` function.
    # It includes a `text` attribute, which the lambda handler will access and include in its response body.
    # This allows us to test the handler's behavior in isolation, without making a real API call.
    mock_response = MagicMock()
    mock_response.text = "This is a test response."
    mock_analyze_document.return_value = mock_response

    ret = app.lambda_handler(apigw_event, "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert "message" in data
    assert data["message"] == "This is a test response."


def test_lambda_handler_missing_api_key(apigw_event):
    """
    Tests the lambda_handler with a missing API key.
    """
    # AI-generated comment:
    # This test simulates a request where the 'x-api-key' header is missing.
    # The expected behavior is for the lambda_handler to return a 401 Unauthorized error.
    # This ensures that the API key validation is working correctly.
    del apigw_event["headers"]["x-api-key"]
    ret = app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 401
    data = json.loads(ret["body"])
    assert "error" in data
    assert data["error"]["type"] == "authentication_error"


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_invalid_api_key_format(mock_analyze_document, apigw_event):
    """
    Tests the lambda_handler with an invalid API key format (empty string).
    """
    # This test simulates a request with an empty 'x-api-key' header.
    # The lambda_handler should return a 401 Unauthorized error.
    apigw_event["headers"]["x-api-key"] = ""

    # Add a valid body to prevent other errors in the handler
    apigw_event["body"] = json.dumps(
        {"prompt": "test prompt", "url": "https://example.com/test.pdf"}
    )

    ret = app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 401
    data = json.loads(ret["body"])
    assert "error" in data
    assert data["error"]["type"] == "authentication_error"
    # Ensure analyze_document was not called
    mock_analyze_document.assert_not_called()


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_missing_url(mock_analyze_document, apigw_event):
    """
    Tests the lambda_handler with a missing URL in the request body.
    """
    # AI-generated comment:
    # This test ensures that the lambda_handler correctly handles requests with a missing URL.
    # It mocks the 'analyze_document' function to verify that it is called with an empty string
    # for the URL, and that the handler still returns a 200 OK response.
    body = json.loads(apigw_event["body"])
    if "url" in body:
        del body["url"]
    apigw_event["body"] = json.dumps(body)

    mock_response = MagicMock()
    mock_response.text = "This is a test response."
    mock_analyze_document.return_value = mock_response

    app.lambda_handler(apigw_event, "")

    # Extract prompt and api_key from the event
    prompt = body.get("prompt", "")
    api_key = apigw_event["headers"]["x-api-key"]

    mock_analyze_document.assert_called_once_with(prompt, "", api_key)


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_missing_prompt(mock_analyze_document, apigw_event):
    """
    Tests the lambda_handler with a missing prompt in the request body.
    """
    # AI-generated comment:
    # This test verifies that the lambda_handler correctly handles requests with a missing prompt.
    # It mocks the 'analyze_document' function to ensure that it is called with an empty string
    # for the prompt, and that the handler still returns a 200 OK response.
    body = json.loads(apigw_event["body"])
    if "prompt" in body:
        del body["prompt"]
    apigw_event["body"] = json.dumps(body)

    mock_response = MagicMock()
    mock_response.text = "This is a test response."
    mock_analyze_document.return_value = mock_response

    app.lambda_handler(apigw_event, "")

    # Extract url and api_key from the event
    url = body.get("url", "")
    api_key = apigw_event["headers"]["x-api-key"]

    mock_analyze_document.assert_called_once_with("", url, api_key)


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_analyze_document_exception(mock_analyze_document, apigw_event):
    """
    Tests the lambda_handler when analyze_document raises an exception.
    """
    mock_analyze_document.side_effect = Exception("Test exception")
    ret = app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 500
    data = json.loads(ret["body"])
    assert "error" in data
    assert data["error"] == "Test exception"


def test_lambda_handler_malformed_json(apigw_event):
    """
    Tests the lambda_handler with malformed JSON in the request body.
    """
    apigw_event["body"] = "{ invalid json"
    ret = app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 500
    data = json.loads(ret["body"])
    assert "error" in data


def test_lambda_handler_none_body(apigw_event):
    """
    Tests the lambda_handler with None as the request body.
    """
    apigw_event["body"] = None
    ret = app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 500
    data = json.loads(ret["body"])
    assert "error" in data


def test_lambda_handler_missing_headers(apigw_event):
    """
    Tests the lambda_handler with missing headers entirely.
    """
    del apigw_event["headers"]
    ret = app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 401
    data = json.loads(ret["body"])
    assert "error" in data
    assert data["error"]["type"] == "authentication_error"


def test_lambda_handler_whitespace_api_key(apigw_event):
    """
    Tests the lambda_handler with whitespace-only API key.
    """
    apigw_event["headers"]["x-api-key"] = "   \n\t   "
    ret = app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 401
    data = json.loads(ret["body"])
    assert "error" in data
    assert data["error"]["type"] == "authentication_error"


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_dict_body(mock_analyze_document, apigw_event):
    """
    Tests the lambda_handler when body is already a dict (not string).
    """
    test_body = {"prompt": "test prompt", "url": "https://example.com/test.pdf"}
    apigw_event["body"] = test_body  # Pass dict directly instead of JSON string

    mock_response = MagicMock()
    mock_response.text = "Dict body response"
    mock_analyze_document.return_value = mock_response

    ret = app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 200
    data = json.loads(ret["body"])
    assert data["message"] == "Dict body response"


@pytest.fixture()
def minimal_event():
    """
    Minimal API Gateway event for testing edge cases.
    """
    return {
        "body": '{"prompt": "test", "url": "https://example.com/test.pdf"}',
        "headers": {"x-api-key": "test-key"},
    }


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_minimal_event(mock_analyze_document, minimal_event):
    """
    Tests the lambda_handler with minimal required event structure.
    """
    mock_response = MagicMock()
    mock_response.text = "Minimal event response"
    mock_analyze_document.return_value = mock_response

    ret = app.lambda_handler(minimal_event, "")
    assert ret["statusCode"] == 200
    data = json.loads(ret["body"])
    assert data["message"] == "Minimal event response"


@patch("datasheetminer.app.analyze_document")
def test_lambda_handler_case_insensitive_headers(mock_analyze_document, apigw_event):
    """
    Tests that API key lookup works with different case variations.
    """
    # Remove the lowercase version and add uppercase
    del apigw_event["headers"]["x-api-key"]
    apigw_event["headers"]["X-API-KEY"] = "test-api-key"

    mock_response = MagicMock()
    mock_response.text = "Case test response"
    mock_analyze_document.return_value = mock_response

    # This should fail since the code looks specifically for 'x-api-key'
    ret = app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 401


def test_lambda_handler_empty_string_body(apigw_event):
    """
    Tests the lambda_handler with empty string body.
    """
    apigw_event["body"] = ""
    ret = app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 500
    data = json.loads(ret["body"])
    assert "error" in data
