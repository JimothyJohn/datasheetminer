"""Unit tests for datasheetminer/scraper.py."""

import logging
from unittest.mock import MagicMock, Mock, patch

import pytest

from datasheetminer.models.motor import Motor
from datasheetminer.scraper import ElapsedTimeFormatter, process_datasheet


@pytest.mark.unit
class TestElapsedTimeFormatter:
    """Tests for the ElapsedTimeFormatter logging formatter."""

    def test_format_time(self) -> None:
        """formatTime returns elapsed time in M:SS format."""
        formatter = ElapsedTimeFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        # Simulate a record created 65 seconds after the formatter was created
        record.created = formatter.start_time + 65

        result = formatter.formatTime(record)

        assert result == "1:05"


@pytest.mark.unit
class TestProcessDatasheet:
    """Tests for process_datasheet()."""

    def test_product_exists_skipped(self) -> None:
        """Product already in DB -- returns 'skipped'."""
        mock_client = MagicMock()
        mock_client.product_exists.return_value = True

        result = process_datasheet(
            client=mock_client,
            api_key="test-key",
            product_type="motor",
            manufacturer="TestMfg",
            product_name="Test",
            product_family="",
            url="https://example.com/test.pdf",
            pages=None,
        )

        assert result == "skipped"
        mock_client.product_exists.assert_called_once()

    @patch("datasheetminer.scraper.parse_gemini_response")
    @patch("datasheetminer.scraper.generate_content")
    @patch("datasheetminer.scraper.is_pdf_url")
    @patch("datasheetminer.scraper.get_document")
    def test_pdf_success(
        self,
        mock_get_doc: MagicMock,
        mock_is_pdf: MagicMock,
        mock_generate: MagicMock,
        mock_parse: MagicMock,
    ) -> None:
        """PDF downloaded and parsed successfully -- returns 'success'."""
        mock_is_pdf.return_value = True
        mock_get_doc.return_value = b"pdf bytes"
        mock_response = Mock()
        mock_response.text = '{"products": []}'
        mock_generate.return_value = mock_response

        motor = Motor(
            product_type="motor",
            product_name="Test",
            manufacturer="TestMfg",
            part_number="ABC-123",
        )
        mock_parse.return_value = [motor]

        mock_client = MagicMock()
        mock_client.product_exists.return_value = False
        mock_client.read.return_value = None
        mock_client.batch_create.return_value = 1

        result = process_datasheet(
            client=mock_client,
            api_key="test-key",
            product_type="motor",
            manufacturer="TestMfg",
            product_name="Test",
            product_family="",
            url="https://example.com/test.pdf",
            pages=None,
        )

        assert result == "success"
        mock_client.batch_create.assert_called_once()

    @patch("datasheetminer.scraper.parse_gemini_response")
    @patch("datasheetminer.scraper.generate_content")
    @patch("datasheetminer.scraper.is_pdf_url")
    @patch("datasheetminer.scraper.get_web_content")
    def test_html_success(
        self,
        mock_get_web: MagicMock,
        mock_is_pdf: MagicMock,
        mock_generate: MagicMock,
        mock_parse: MagicMock,
    ) -> None:
        """Web page scraped and parsed successfully -- returns 'success'."""
        mock_is_pdf.return_value = False
        mock_get_web.return_value = "<html><body>specs</body></html>"
        mock_response = Mock()
        mock_response.text = '{"products": []}'
        mock_generate.return_value = mock_response

        motor = Motor(
            product_type="motor",
            product_name="WebMotor",
            manufacturer="WebMfg",
            part_number="WEB-001",
        )
        mock_parse.return_value = [motor]

        mock_client = MagicMock()
        mock_client.product_exists.return_value = False
        mock_client.read.return_value = None
        mock_client.batch_create.return_value = 1

        result = process_datasheet(
            client=mock_client,
            api_key="test-key",
            product_type="motor",
            manufacturer="WebMfg",
            product_name="WebMotor",
            product_family="",
            url="https://example.com/product",
            pages=None,
        )

        assert result == "success"

    @patch("datasheetminer.scraper.is_pdf_url")
    @patch("datasheetminer.scraper.get_document")
    def test_download_failure(
        self,
        mock_get_doc: MagicMock,
        mock_is_pdf: MagicMock,
    ) -> None:
        """PDF download returns None -- returns 'failed'."""
        mock_is_pdf.return_value = True
        mock_get_doc.return_value = None

        mock_client = MagicMock()
        mock_client.product_exists.return_value = False

        result = process_datasheet(
            client=mock_client,
            api_key="test-key",
            product_type="motor",
            manufacturer="TestMfg",
            product_name="Test",
            product_family="",
            url="https://example.com/broken.pdf",
            pages=None,
        )

        assert result == "failed"

    @patch("datasheetminer.scraper.parse_gemini_response")
    @patch("datasheetminer.scraper.generate_content")
    @patch("datasheetminer.scraper.is_pdf_url")
    @patch("datasheetminer.scraper.get_document")
    def test_parse_failure(
        self,
        mock_get_doc: MagicMock,
        mock_is_pdf: MagicMock,
        mock_generate: MagicMock,
        mock_parse: MagicMock,
    ) -> None:
        """parse_gemini_response raises ValueError -- returns 'failed'."""
        mock_is_pdf.return_value = True
        mock_get_doc.return_value = b"pdf bytes"
        mock_response = Mock()
        mock_response.text = "garbage"
        mock_generate.return_value = mock_response
        mock_parse.side_effect = ValueError("Invalid JSON")

        mock_client = MagicMock()
        mock_client.product_exists.return_value = False

        result = process_datasheet(
            client=mock_client,
            api_key="test-key",
            product_type="motor",
            manufacturer="TestMfg",
            product_name="Test",
            product_family="",
            url="https://example.com/test.pdf",
            pages=None,
        )

        assert result == "failed"

    @patch("datasheetminer.scraper.parse_gemini_response")
    @patch("datasheetminer.scraper.generate_content")
    @patch("datasheetminer.scraper.is_pdf_url")
    @patch("datasheetminer.scraper.get_document")
    def test_deterministic_id(
        self,
        mock_get_doc: MagicMock,
        mock_is_pdf: MagicMock,
        mock_generate: MagicMock,
        mock_parse: MagicMock,
    ) -> None:
        """product_id is generated via uuid5 from manufacturer+part_number."""
        import re
        import uuid

        mock_is_pdf.return_value = True
        mock_get_doc.return_value = b"pdf bytes"
        mock_response = Mock()
        mock_response.text = "{}"
        mock_generate.return_value = mock_response

        motor = Motor(
            product_type="motor",
            product_name="Test",
            manufacturer="TestMfg",
            part_number="ABC-123",
        )
        mock_parse.return_value = [motor]

        mock_client = MagicMock()
        mock_client.product_exists.return_value = False
        mock_client.read.return_value = None
        mock_client.batch_create.return_value = 1

        process_datasheet(
            client=mock_client,
            api_key="test-key",
            product_type="motor",
            manufacturer="TestMfg",
            product_name="Test",
            product_family="",
            url="https://example.com/test.pdf",
            pages=None,
        )

        # Reproduce the expected deterministic ID
        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
        norm_mfg = re.sub(r"[^a-z0-9]", "", "TestMfg".lower().strip())
        norm_pn = re.sub(r"[^a-z0-9]", "", "ABC-123".lower().strip())
        expected_id = uuid.uuid5(namespace, f"{norm_mfg}:{norm_pn}")

        # The model passed to batch_create should have the deterministic ID
        saved_models = mock_client.batch_create.call_args[0][0]
        assert saved_models[0].product_id == expected_id

    @patch("datasheetminer.scraper.parse_gemini_response")
    @patch("datasheetminer.scraper.generate_content")
    @patch("datasheetminer.scraper.is_pdf_url")
    @patch("datasheetminer.scraper.get_document")
    def test_no_manufacturer_skips(
        self,
        mock_get_doc: MagicMock,
        mock_is_pdf: MagicMock,
        mock_generate: MagicMock,
        mock_parse: MagicMock,
    ) -> None:
        """Model without manufacturer AND part_number is excluded from valid_models."""
        mock_is_pdf.return_value = True
        mock_get_doc.return_value = b"pdf bytes"
        mock_response = Mock()
        mock_response.text = "{}"
        mock_generate.return_value = mock_response

        # Motor with empty manufacturer and no part_number -- cannot generate robust ID
        motor = Motor(
            product_type="motor",
            product_name="Orphan",
            manufacturer="",
            part_number=None,
        )
        mock_parse.return_value = [motor]

        mock_client = MagicMock()
        mock_client.product_exists.return_value = False
        mock_client.read.return_value = None
        mock_client.batch_create.return_value = 0

        result = process_datasheet(
            client=mock_client,
            api_key="test-key",
            product_type="motor",
            # Pass empty manufacturer at the call-site level too
            manufacturer="",
            product_name="Orphan",
            product_family="",
            url="https://example.com/test.pdf",
            pages=None,
        )

        # No valid models means batch_create gets an empty list (or is called with 0 items)
        # The function returns "failed" because success_count == 0
        assert result == "failed"
