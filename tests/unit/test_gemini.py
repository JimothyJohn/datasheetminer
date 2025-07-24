"""
Unit tests for the Gemini AI integration module.

This module contains comprehensive tests for the analyze_document function
in the gemini module, including success cases, error handling, and edge cases.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
import httpx
from google.genai import types

from datasheetminer import gemini


class TestAnalyzeDocument:
    """Test suite for the analyze_document function."""

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_analyze_document_success(self, mock_genai_client, mock_httpx_client):
        """
        Tests successful document analysis with valid inputs.
        """
        # Mock HTTP response
        mock_http_response = Mock()
        mock_http_response.content = b"fake pdf content"
        mock_http_response.raise_for_status = Mock()

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Mock Gemini client
        mock_genai_instance = Mock()
        mock_genai_response = Mock()
        mock_genai_response.text = "Analysis complete"
        mock_genai_instance.models.generate_content.return_value = mock_genai_response
        mock_genai_client.return_value = mock_genai_instance

        # Test the function
        result = gemini.analyze_document(
            "test prompt", "https://example.com/test.pdf", "test-api-key"
        )

        # Assertions
        mock_genai_client.assert_called_once_with(api_key="test-api-key")
        mock_http_client_instance.get.assert_called_once_with(
            "https://example.com/test.pdf"
        )
        mock_http_response.raise_for_status.assert_called_once()

        # Verify generate_content was called with correct parameters
        mock_genai_instance.models.generate_content.assert_called_once()
        call_args = mock_genai_instance.models.generate_content.call_args
        assert call_args[1]["model"] == "gemini-2.5-flash"
        assert len(call_args[1]["contents"]) == 2
        assert call_args[1]["contents"][1] == "test prompt"

        assert result == mock_genai_response

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_analyze_document_http_error(self, mock_genai_client, mock_httpx_client):
        """
        Tests analyze_document when HTTP request fails.
        """
        # Mock HTTP client to raise an exception
        mock_http_response = Mock()
        mock_http_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=Mock()
        )

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Test that the exception is propagated
        with pytest.raises(httpx.HTTPStatusError):
            gemini.analyze_document(
                "test prompt", "https://example.com/test.pdf", "test-api-key"
            )

        # Ensure Gemini client was created but generate_content was not called
        mock_genai_client.assert_called_once()
        mock_genai_instance = mock_genai_client.return_value
        mock_genai_instance.models.generate_content.assert_not_called()

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_analyze_document_network_error(self, mock_genai_client, mock_httpx_client):
        """
        Tests analyze_document when network request fails.
        """
        # Mock HTTP client to raise a connection error
        mock_http_client_instance = Mock()
        mock_http_client_instance.get.side_effect = httpx.ConnectError(
            "Connection failed"
        )
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Test that the exception is propagated
        with pytest.raises(httpx.ConnectError):
            gemini.analyze_document(
                "test prompt", "https://example.com/test.pdf", "test-api-key"
            )

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_analyze_document_gemini_error(self, mock_genai_client, mock_httpx_client):
        """
        Tests analyze_document when Gemini API fails.
        """
        # Mock successful HTTP response
        mock_http_response = Mock()
        mock_http_response.content = b"fake pdf content"
        mock_http_response.raise_for_status = Mock()

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Mock Gemini client to raise an exception
        mock_genai_instance = Mock()
        mock_genai_instance.models.generate_content.side_effect = Exception(
            "Gemini API error"
        )
        mock_genai_client.return_value = mock_genai_instance

        # Test that the exception is propagated
        with pytest.raises(Exception, match="Gemini API error"):
            gemini.analyze_document(
                "test prompt", "https://example.com/test.pdf", "test-api-key"
            )

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_analyze_document_empty_content(self, mock_genai_client, mock_httpx_client):
        """
        Tests analyze_document with empty PDF content.
        """
        # Mock HTTP response with empty content
        mock_http_response = Mock()
        mock_http_response.content = b""
        mock_http_response.raise_for_status = Mock()

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Mock Gemini client
        mock_genai_instance = Mock()
        mock_genai_response = Mock()
        mock_genai_response.text = "No content to analyze"
        mock_genai_instance.models.generate_content.return_value = mock_genai_response
        mock_genai_client.return_value = mock_genai_instance

        # Test the function
        result = gemini.analyze_document(
            "test prompt", "https://example.com/test.pdf", "test-api-key"
        )

        # Should still work with empty content
        assert result == mock_genai_response
        mock_genai_instance.models.generate_content.assert_called_once()

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_analyze_document_large_content(self, mock_genai_client, mock_httpx_client):
        """
        Tests analyze_document with large PDF content.
        """
        # Mock HTTP response with large content (10MB)
        large_content = b"x" * (10 * 1024 * 1024)
        mock_http_response = Mock()
        mock_http_response.content = large_content
        mock_http_response.raise_for_status = Mock()

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Mock Gemini client
        mock_genai_instance = Mock()
        mock_genai_response = Mock()
        mock_genai_response.text = "Large document analyzed"
        mock_genai_instance.models.generate_content.return_value = mock_genai_response
        mock_genai_client.return_value = mock_genai_instance

        # Test the function
        result = gemini.analyze_document(
            "test prompt", "https://example.com/test.pdf", "test-api-key"
        )

        # Should handle large content
        assert result == mock_genai_response
        mock_genai_instance.models.generate_content.assert_called_once()

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_analyze_document_unicode_prompt(
        self, mock_genai_client, mock_httpx_client
    ):
        """
        Tests analyze_document with Unicode characters in prompt.
        """
        # Mock HTTP response
        mock_http_response = Mock()
        mock_http_response.content = b"fake pdf content"
        mock_http_response.raise_for_status = Mock()

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Mock Gemini client
        mock_genai_instance = Mock()
        mock_genai_response = Mock()
        mock_genai_response.text = "Unicode prompt processed"
        mock_genai_instance.models.generate_content.return_value = mock_genai_response
        mock_genai_client.return_value = mock_genai_instance

        # Test with Unicode prompt
        unicode_prompt = "Analyze this document: 测试 🔬 análisis"
        result = gemini.analyze_document(
            unicode_prompt, "https://example.com/test.pdf", "test-api-key"
        )

        # Verify Unicode prompt was passed correctly
        call_args = mock_genai_instance.models.generate_content.call_args
        assert call_args[1]["contents"][1] == unicode_prompt
        assert result == mock_genai_response

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_analyze_document_empty_strings(self, mock_genai_client, mock_httpx_client):
        """
        Tests analyze_document with empty string parameters.
        """
        # Mock HTTP response
        mock_http_response = Mock()
        mock_http_response.content = b"fake pdf content"
        mock_http_response.raise_for_status = Mock()

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Mock Gemini client
        mock_genai_instance = Mock()
        mock_genai_response = Mock()
        mock_genai_response.text = "Empty strings handled"
        mock_genai_instance.models.generate_content.return_value = mock_genai_response
        mock_genai_client.return_value = mock_genai_instance

        # Test with empty strings
        result = gemini.analyze_document("", "", "test-api-key")

        # Should still make the calls
        mock_genai_client.assert_called_once_with(api_key="test-api-key")
        mock_http_client_instance.get.assert_called_once_with("")
        assert result == mock_genai_response

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_analyze_document_redirect_handling(
        self, mock_genai_client, mock_httpx_client
    ):
        """
        Tests that analyze_document handles HTTP redirects properly.
        """
        # Mock HTTP response with redirect (httpx handles this automatically)
        mock_http_response = Mock()
        mock_http_response.content = b"redirected content"
        mock_http_response.raise_for_status = Mock()

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Mock Gemini client
        mock_genai_instance = Mock()
        mock_genai_response = Mock()
        mock_genai_response.text = "Redirected content analyzed"
        mock_genai_instance.models.generate_content.return_value = mock_genai_response
        mock_genai_client.return_value = mock_genai_instance

        # Test the function
        result = gemini.analyze_document(
            "test prompt", "https://example.com/redirect", "test-api-key"
        )

        # Should handle redirects transparently
        assert result == mock_genai_response
        mock_http_client_instance.get.assert_called_once_with(
            "https://example.com/redirect"
        )

    @patch("datasheetminer.gemini.httpx.Client")
    @patch("datasheetminer.gemini.genai.Client")
    def test_analyze_document_invalid_api_key(
        self, mock_genai_client, mock_httpx_client
    ):
        """
        Tests analyze_document with invalid API key.
        """
        # Mock HTTP response
        mock_http_response = Mock()
        mock_http_response.content = b"fake pdf content"
        mock_http_response.raise_for_status = Mock()

        mock_http_client_instance = Mock()
        mock_http_client_instance.get.return_value = mock_http_response
        mock_httpx_client.return_value.__enter__.return_value = (
            mock_http_client_instance
        )

        # Mock Gemini client to raise authentication error
        mock_genai_client.side_effect = Exception("Invalid API key")

        # Test that the exception is propagated
        with pytest.raises(Exception, match="Invalid API key"):
            gemini.analyze_document(
                "test prompt", "https://example.com/test.pdf", "invalid-key"
            )
