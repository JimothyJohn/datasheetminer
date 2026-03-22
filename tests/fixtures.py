"""
Test fixtures and utilities for datasheetminer tests.

This module provides common fixtures, mock objects, and utility functions
used across unit and integration tests.
"""

import json
import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing."""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000074 00000 n \n0000000120 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n179\n%%EOF"


@pytest.fixture
def sample_large_pdf_content():
    """Large PDF content for testing memory/performance scenarios."""
    base_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
    # Create a 1MB PDF-like content
    large_content = base_content + b"x" * (1024 * 1024 - len(base_content))
    return large_content


@pytest.fixture
def mock_gemini_response():
    """Mock response from Gemini API."""
    response = Mock()
    response.text = "This is a test analysis of the document. The document contains technical specifications and product information."
    return response


@pytest.fixture
def mock_gemini_error_response():
    """Mock error response from Gemini API."""
    response = Mock()
    response.text = "Error: Unable to process document"
    response.side_effect = Exception("Gemini API error")
    return response


@pytest.fixture
def valid_api_gateway_event():
    """Valid API Gateway event for testing."""
    return {
        "body": json.dumps(
            {
                "prompt": "Analyze this document and extract key specifications",
                "url": "https://example.com/test-datasheet.pdf",
            }
        ),
        "headers": {
            "x-api-key": "test-gemini-api-key-12345",
            "Content-Type": "application/json",
            "User-Agent": "Test/1.0",
        },
        "httpMethod": "POST",
        "path": "/hello",
        "queryStringParameters": None,
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "test",
            "httpMethod": "POST",
            "resourcePath": "/hello",
        },
    }


@pytest.fixture
def invalid_api_gateway_event():
    """Invalid API Gateway event missing required fields."""
    return {
        "body": json.dumps({}),  # Empty body
        "headers": {},  # No API key
        "httpMethod": "POST",
        "path": "/hello",
    }


@pytest.fixture
def malformed_json_event():
    """API Gateway event with malformed JSON body."""
    return {
        "body": '{"prompt": "test", "url": "https://example.com/test.pdf"',  # Missing closing brace
        "headers": {"x-api-key": "test-api-key", "Content-Type": "application/json"},
        "httpMethod": "POST",
        "path": "/hello",
    }


@pytest.fixture
def unicode_content_event():
    """API Gateway event with Unicode content."""
    return {
        "body": json.dumps(
            {
                "prompt": "分析这个文档 🔬 Análisis del documento",
                "url": "https://example.com/test-datasheet.pdf",
            }
        ),
        "headers": {
            "x-api-key": "test-gemini-api-key-12345",
            "Content-Type": "application/json; charset=utf-8",
        },
        "httpMethod": "POST",
        "path": "/hello",
    }


@pytest.fixture
def mock_http_response():
    """Mock HTTP response for PDF download."""
    response = Mock()
    response.content = b"%PDF-1.4 fake pdf content"
    response.status_code = 200
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def mock_http_error_response():
    """Mock HTTP error response for PDF download."""
    import httpx

    response = Mock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=Mock(), response=Mock()
    )
    return response


@pytest.fixture
def mock_network_error():
    """Mock network error for HTTP requests."""
    import httpx

    return httpx.ConnectError("Connection failed")


@pytest.fixture
def lambda_context():
    """Mock AWS Lambda context object."""
    context = Mock()
    context.function_name = "datasheetminer-test"
    context.function_version = "$LATEST"
    context.invoked_function_arn = (
        "arn:aws:lambda:us-east-1:123456789012:function:datasheetminer-test"
    )
    context.memory_limit_in_mb = 1024
    context.remaining_time_in_millis = Mock(return_value=30000)
    context.request_id = "test-request-id-12345"
    context.log_group_name = "/aws/lambda/datasheetminer-test"
    context.log_stream_name = "2023/01/01/[$LATEST]test123"
    return context


class MockGeminiClient:
    """Mock Gemini client for testing."""

    def __init__(self, api_key, should_fail=False, failure_message="Mock failure"):
        self.api_key = api_key
        self.should_fail = should_fail
        self.failure_message = failure_message
        self.models = MockModels(should_fail, failure_message)


class MockModels:
    """Mock Gemini models interface."""

    def __init__(self, should_fail=False, failure_message="Mock failure"):
        self.should_fail = should_fail
        self.failure_message = failure_message

    def generate_content(self, model, contents):
        """Mock generate_content method."""
        if self.should_fail:
            raise Exception(self.failure_message)

        response = Mock()
        response.text = f"Mock analysis of content with model {model}. Found {len(contents)} content items."
        return response


@pytest.fixture
def mock_successful_gemini_client():
    """Mock successful Gemini client."""
    return MockGeminiClient("test-api-key")


@pytest.fixture
def mock_failing_gemini_client():
    """Mock failing Gemini client."""
    return MockGeminiClient(
        "invalid-key", should_fail=True, failure_message="Invalid API key"
    )


def create_test_event(
    prompt="Test prompt",
    url="https://example.com/test.pdf",
    api_key="test-api-key",
    headers=None,
    body_as_dict=False,
):
    """
    Utility function to create test API Gateway events.

    Args:
        prompt: The analysis prompt
        url: The PDF URL
        api_key: The API key to use
        headers: Additional headers (optional)
        body_as_dict: If True, return body as dict instead of JSON string

    Returns:
        dict: API Gateway event structure
    """
    event_headers = {"x-api-key": api_key}
    if headers:
        event_headers.update(headers)

    body = {"prompt": prompt, "url": url}

    return {
        "body": body if body_as_dict else json.dumps(body),
        "headers": event_headers,
        "httpMethod": "POST",
        "path": "/hello",
        "requestContext": {"requestId": "test-request", "stage": "test"},
    }


def assert_error_response(response, expected_status_code, expected_error_type=None):
    """
    Utility function to assert error responses.

    Args:
        response: The response dict from lambda_handler
        expected_status_code: Expected HTTP status code
        expected_error_type: Expected error type (optional)
    """
    assert response["statusCode"] == expected_status_code

    body = (
        json.loads(response["body"])
        if isinstance(response["body"], str)
        else response["body"]
    )
    assert "error" in body

    if expected_error_type:
        if isinstance(body["error"], dict):
            assert body["error"].get("type") == expected_error_type
        else:
            # Simple string error
            assert expected_error_type in str(body["error"])


def assert_success_response(response, expected_message_contains=None):
    """
    Utility function to assert successful responses.

    Args:
        response: The response dict from lambda_handler
        expected_message_contains: Text that should be in the message (optional)
    """
    assert response["statusCode"] == 200

    body = (
        json.loads(response["body"])
        if isinstance(response["body"], str)
        else response["body"]
    )
    assert "message" in body
    assert isinstance(body["message"], str)
    assert len(body["message"]) > 0

    if expected_message_contains:
        assert expected_message_contains in body["message"]
