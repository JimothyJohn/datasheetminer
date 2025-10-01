"""
Comprehensive error handling tests for datasheetminer.

This module focuses on testing various error conditions, edge cases,
and failure scenarios to ensure robust error handling throughout the application.
"""

import json
import pytest
from unittest.mock import patch, Mock, MagicMock
import httpx

from datasheetminer import app, gemini
from tests.fixtures import create_test_event, assert_error_response, lambda_context


class TestErrorHandling:
    """Test suite for error handling scenarios."""

    def test_json_decode_error(self):
        """Test handling of JSON decode errors in request body."""
        event = create_test_event()
        event["body"] = '{"prompt": "test", invalid json}'

        response = app.lambda_handler(event, None)
        assert_error_response(response, 500)

    def test_missing_body_key(self):
        """Test handling when 'body' key is missing from event."""
        event = create_test_event()
        del event["body"]

        response = app.lambda_handler(event, None)
        assert_error_response(response, 500)

    def test_none_body_value(self):
        """Test handling when body is None."""
        event = create_test_event()
        event["body"] = None

        response = app.lambda_handler(event, None)
        assert_error_response(response, 500)

    def test_missing_headers_key(self):
        """Test handling when 'headers' key is missing from event."""
        event = create_test_event()
        del event["headers"]

        response = app.lambda_handler(event, None)
        assert_error_response(response, 401, "authentication_error")

    def _test_none_headers_value(self):
        """Test handling when headers is None."""
        event = create_test_event()
        event["headers"] = None

        response = app.lambda_handler(event, None)
        assert_error_response(response, 401, "authentication_error")

    def test_api_key_various_whitespace(self):
        """Test API key validation with various whitespace patterns."""
        whitespace_keys = [
            "   ",  # spaces
            "\t\t",  # tabs
            "\n\n",  # newlines
            " \t\n ",  # mixed whitespace
            "",  # empty string
        ]

        for key in whitespace_keys:
            event = create_test_event(api_key=key)
            response = app.lambda_handler(event, None)
            assert_error_response(response, 401, "authentication_error")

    @patch("datasheetminer.app.analyze_document")
    def _test_analyze_document_timeout_error(self, mock_analyze_document):
        """Test handling of timeout errors from analyze_document."""
        mock_analyze_document.side_effect = TimeoutError("Request timed out")

        event = create_test_event()
        response = app.lambda_handler(event, None)

        assert_error_response(response, 500)

    @patch("datasheetminer.app.analyze_document")
    def test_analyze_document_memory_error(self, mock_analyze_document):
        """Test handling of memory errors from analyze_document."""
        mock_analyze_document.side_effect = MemoryError("Out of memory")

        event = create_test_event()
        response = app.lambda_handler(event, None)

        assert_error_response(response, 500)

    def test_extremely_large_prompt(self):
        """Test handling of extremely large prompts."""
        # Create a 1MB prompt
        large_prompt = "x" * (1024 * 1024)
        event = create_test_event(prompt=large_prompt)

        # This should either succeed or fail gracefully
        response = app.lambda_handler(event, None)
        assert response["statusCode"] in [200, 500]

    def test_extremely_long_url(self):
        """Test handling of extremely long URLs."""
        # Create a very long URL
        long_url = "https://example.com/" + "x" * 10000 + ".pdf"
        event = create_test_event(url=long_url)

        response = app.lambda_handler(event, None)
        # Should fail when trying to fetch the URL
        assert_error_response(response, 500)

    def test_unicode_in_json_structure(self):
        """Test handling of Unicode characters in JSON structure itself."""
        event = create_test_event()
        # Manually create JSON with Unicode in keys (invalid JSON)
        event["body"] = '{"prompté": "test", "url": "https://example.com/test.pdf"}'

        response = app.lambda_handler(event, None)
        # Should still work since JSON is valid, just different key name
        assert_error_response(response, 500)  # Will fail at analyze_document level

    def test_null_values_in_body(self):
        """Test handling of null values in request body."""
        event = create_test_event()
        event["body"] = json.dumps({"prompt": None, "url": None})

        response = app.lambda_handler(event, None)
        # Should handle null values gracefully
        assert response["statusCode"] in [200, 500]

    def test_boolean_values_in_body(self):
        """Test handling of boolean values in request body."""
        event = create_test_event()
        event["body"] = json.dumps({"prompt": True, "url": False})

        response = app.lambda_handler(event, None)
        # Should handle boolean values (will be converted to strings)
        assert response["statusCode"] in [200, 500]

    def test_numeric_values_in_body(self):
        """Test handling of numeric values in request body."""
        event = create_test_event()
        event["body"] = json.dumps({"prompt": 12345, "url": 67890})

        response = app.lambda_handler(event, None)
        # Should handle numeric values (will be converted to strings)
        assert response["statusCode"] in [200, 500]

    def test_nested_objects_in_body(self):
        """Test handling of nested objects in request body."""
        event = create_test_event()
        event["body"] = json.dumps(
            {"prompt": {"nested": "object"}, "url": ["list", "of", "values"]}
        )

        response = app.lambda_handler(event, None)
        # Should handle complex objects (get() will return them as-is)
        assert response["statusCode"] in [200, 500]


class _TestGeminiErrorHandling:
    """Test suite for Gemini-specific error handling."""

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_gemini_client_creation_failure(self, mock_genai_client, mock_httpx_client):
        """Test handling when Gemini client creation fails."""
        mock_genai_client.side_effect = Exception("Failed to create Gemini client")

        with pytest.raises(Exception, match="Failed to create Gemini client"):
            gemini.analyze_document(
                "test", "https://example.com/test.pdf", "invalid-key"
            )

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_http_client_creation_failure(self, mock_genai_client, mock_httpx_client):
        """Test handling when HTTP client creation fails."""
        mock_httpx_client.side_effect = Exception("Failed to create HTTP client")

        with pytest.raises(Exception, match="Failed to create HTTP client"):
            gemini.analyze_document("test", "https://example.com/test.pdf", "test-key")

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_http_response_content_access_error(
        self, mock_genai_client, mock_httpx_client
    ):
        """Test handling when accessing response.content fails."""
        # Mock HTTP client
        mock_http_response = Mock()
        mock_http_response.raise_for_status = Mock()
        # Make content property raise an exception
        type(mock_http_response).content = PropertyError("Content access failed")

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Mock Gemini client
        mock_genai_client.return_value = Mock()

        with pytest.raises(PropertyError, match="Content access failed"):
            gemini.analyze_document("test", "https://example.com/test.pdf", "test-key")

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_types_part_creation_failure(self, mock_genai_client, mock_httpx_client):
        """Test handling when types.Part.from_bytes fails."""
        # Mock HTTP response
        mock_http_response = Mock()
        mock_http_response.content = b"fake content"
        mock_http_response.raise_for_status = Mock()

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Mock Gemini client
        mock_genai_instance = Mock()
        mock_genai_client.return_value = mock_genai_instance

        # Mock types.Part.from_bytes to fail
        with patch("datasheetminer.gemini.types.Part.from_bytes") as mock_from_bytes:
            mock_from_bytes.side_effect = Exception("Failed to create Part from bytes")

            with pytest.raises(Exception, match="Failed to create Part from bytes"):
                gemini.analyze_document(
                    "test", "https://example.com/test.pdf", "test-key"
                )

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_context_manager_exit_error(self, mock_genai_client, mock_httpx_client):
        """Test handling when HTTP client context manager exit fails."""
        # Mock HTTP client with failing context manager
        mock_http_client_instance = Mock()
        mock_http_client_instance.get.side_effect = httpx.RequestError("Request failed")

        mock_context_manager = Mock()
        mock_context_manager.__enter__.return_value = mock_http_client_instance
        # Simulate that __exit__ might not be called or fails itself
        mock_context_manager.__exit__.side_effect = RuntimeError("Context exit failed")
        mock_httpx_client.return_value = mock_context_manager

        with pytest.raises(httpx.RequestError, match="Request failed"):
            gemini.analyze_document("test", "https://example.com/test.pdf", "test-key")

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_generate_content_attribute_error(
        self, mock_genai_client, mock_httpx_client
    ):
        """Test handling when models.generate_content attribute doesn't exist."""
        # Mock HTTP response
        mock_http_response = Mock()
        mock_http_response.content = b"fake content"
        mock_http_response.raise_for_status = Mock()

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Mock Gemini client without models attribute
        mock_genai_instance = Mock()
        del mock_genai_instance.models  # Remove the models attribute
        mock_genai_client.return_value = mock_genai_instance

        with pytest.raises(AttributeError):
            gemini.analyze_document("test", "https://example.com/test.pdf", "test-key")


class PropertyError(Exception):
    """Custom exception for property access failures."""

    pass


class TestEdgeCaseInputs:
    """Test suite for edge case inputs."""

    def test_empty_event_dict(self):
        """Test with completely empty event dictionary."""
        response = app.lambda_handler({}, None)
        assert_error_response(response, 401, "authentication_error")

    def test_event_with_only_body(self):
        """Test with event containing only body."""
        event = {
            "body": json.dumps(
                {"prompt": "test", "url": "https://example.com/test.pdf"}
            )
        }
        response = app.lambda_handler(event, None)
        assert_error_response(response, 401, "authentication_error")

    def test_event_with_only_headers(self):
        """Test with event containing only headers."""
        event = {"headers": {"x-api-key": "test-key"}}
        response = app.lambda_handler(event, None)
        assert_error_response(response, 500)

    @patch("datasheetminer.app.analyze_document")
    def test_analyze_document_returns_none(self, mock_analyze_document):
        """Test when analyze_document returns None."""
        mock_analyze_document.return_value = None

        event = create_test_event()
        response = app.lambda_handler(event, None)

        # Should fail when trying to access .text on None
        assert_error_response(response, 500)

    @patch("datasheetminer.app.analyze_document")
    def test_analyze_document_returns_object_without_text(self, mock_analyze_document):
        """Test when analyze_document returns object without .text attribute."""
        mock_response = Mock(spec=[])  # Mock without .text attribute
        mock_analyze_document.return_value = mock_response

        event = create_test_event()
        response = app.lambda_handler(event, None)

        # Should fail when trying to access .text
        assert_error_response(response, 500)

    @patch("datasheetminer.app.analyze_document")
    def test_analyze_document_text_is_none(self, mock_analyze_document):
        """Test when analyze_document returns object with .text = None."""
        mock_response = Mock()
        mock_response.text = None
        mock_analyze_document.return_value = mock_response

        event = create_test_event()
        response = app.lambda_handler(event, None)

        # Should handle None text gracefully
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] is None
