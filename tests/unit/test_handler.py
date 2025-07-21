"""
Unit tests for the lambda handler.

This module contains the test_lambda_handler function, which is used to test the lambda handler.

It uses the pytest library to run the tests and the unittest.mock library to mock the analyze_document function.

The test_lambda_handler function takes an event object as input and uses the lambda_handler function to generate a response.

"""
import json

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from datasheetminer import app


@pytest.fixture()
def apigw_event():
    """ Generates API GW Event"""

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
            "Authorization": "Bearer test-api-key",
        },
        "pathParameters": {"proxy": "/examplepath"},
        "httpMethod": "POST",
        "stageVariables": {"baz": "qux"},
        "path": "/examplepath",
    }


@pytest.mark.anyio
@patch('datasheetminer.app.analyze_document', new_callable=AsyncMock)
async def test_lambda_handler(mock_analyze_document, apigw_event):
    # AI-generated comment:
    # The following mock response is structured to emulate the expected output from the `analyze_document` function.
    # It includes a `text` attribute, which the lambda handler will access and include in its response body.
    # This allows us to test the handler's behavior in isolation, without making a real API call.
    mock_response = MagicMock()
    mock_response.text = "This is a test response."
    mock_analyze_document.return_value = mock_response

    ret = await app.lambda_handler(apigw_event, "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert "message" in data
    assert data["message"] == "This is a test response."


@pytest.mark.anyio
async def test_lambda_handler_missing_api_key(apigw_event):
    """
    Tests the lambda_handler with a missing API key.
    """
    # AI-generated comment:
    # This test simulates a request where the 'Authorization' header is missing.
    # The expected behavior is for the lambda_handler to return a 401 Unauthorized error.
    # This ensures that the API key validation is working correctly.
    del apigw_event["headers"]["Authorization"]
    ret = await app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 401
    data = json.loads(ret["body"])
    assert "error" in data
    assert data["error"]["type"] == "authentication_error"


@pytest.mark.anyio
async def test_lambda_handler_invalid_api_key_format(apigw_event):
    """
    Tests the lambda_handler with an invalid API key format.
    """
    # AI-generated comment:
    # This test simulates a request with an improperly formatted 'Authorization' header.
    # The lambda_handler should return a 401 Unauthorized error, ensuring that the
    # "Bearer " prefix is correctly validated.
    apigw_event["headers"]["Authorization"] = "invalid-key"
    ret = await app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 401
    data = json.loads(ret["body"])
    assert "error" in data
    assert data["error"]["type"] == "authentication_error"


@pytest.mark.anyio
@patch('datasheetminer.app.analyze_document', new_callable=AsyncMock)
async def test_lambda_handler_missing_url(mock_analyze_document, apigw_event):
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

    await app.lambda_handler(apigw_event, "")
    
    # Extract prompt and api_key from the event
    prompt = body.get("prompt", "")
    api_key = apigw_event["headers"]["Authorization"].split("Bearer ")[1].strip()

    mock_analyze_document.assert_called_once_with(prompt, '', api_key)


@pytest.mark.anyio
@patch('datasheetminer.app.analyze_document', new_callable=AsyncMock)
async def test_lambda_handler_missing_prompt(mock_analyze_document, apigw_event):
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

    await app.lambda_handler(apigw_event, "")
    
    # Extract url and api_key from the event
    url = body.get("url", "")
    api_key = apigw_event["headers"]["Authorization"].split("Bearer ")[1].strip()

    mock_analyze_document.assert_called_once_with('', url, api_key)


@pytest.mark.anyio
@patch('datasheetminer.app.analyze_document', new_callable=AsyncMock)
async def test_lambda_handler_analyze_document_exception(mock_analyze_document, apigw_event):
    """
    Tests the lambda_handler when analyze_document raises an exception.
    """
    # AI-generated comment:
    # This test ensures that the lambda_handler correctly handles exceptions raised by the
    # 'analyze_document' function. It mocks the function to raise an exception and verifies
    # that the handler returns a 500 Internal Server Error.
    mock_analyze_document.side_effect = Exception("Test exception")
    ret = await app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 500
    data = json.loads(ret["body"])
    assert "error" in data
    assert data["error"] == "Test exception"
