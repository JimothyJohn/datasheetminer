"""Unit tests for datasheetminer.utils module."""

import argparse
import io
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from uuid import uuid4

import PyPDF2
import pytest

from datasheetminer.utils import (
    PageRangeError,
    UUIDEncoder,
    extract_pdf_pages,
    get_document,
    get_product_info_from_json,
    get_web_content,
    is_pdf_url,
    parse_gemini_response,
    parse_page_ranges,
    validate_api_key,
)
from datasheetminer.models.motor import Motor


def _make_pdf(num_pages: int) -> bytes:
    """Create a minimal in-memory PDF with the given number of blank pages."""
    writer = PyPDF2.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# TestParsePageRanges
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestParsePageRanges:
    def test_single_page(self):
        assert parse_page_ranges("1") == [0]

    def test_comma_separated(self):
        assert parse_page_ranges("1,3,5") == [0, 2, 4]

    def test_colon_range(self):
        assert parse_page_ranges("1:5") == [0, 1, 2, 3, 4]

    def test_dash_range(self):
        assert parse_page_ranges("1-5") == [0, 1, 2, 3, 4]

    def test_mixed_format(self):
        assert parse_page_ranges("1,3:5,8") == [0, 2, 3, 4, 7]

    def test_duplicates_removed(self):
        assert parse_page_ranges("1,1,2") == [0, 1]

    def test_empty_parts_skipped(self):
        assert parse_page_ranges("1,,3") == [0, 2]

    def test_invalid_range_start_gt_end(self):
        with pytest.raises(PageRangeError):
            parse_page_ranges("5:1")

    def test_invalid_non_numeric(self):
        with pytest.raises(PageRangeError):
            parse_page_ranges("abc")


# ---------------------------------------------------------------------------
# TestValidateApiKey
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestValidateApiKey:
    def test_valid_key(self):
        key = "AIzaSyCumTiS5n_long_key"
        assert validate_api_key(key) == key

    def test_too_short(self):
        with pytest.raises(argparse.ArgumentTypeError):
            validate_api_key("short")

    def test_empty_raises(self):
        with pytest.raises(argparse.ArgumentTypeError):
            validate_api_key("")

    def test_none_raises(self):
        with pytest.raises(argparse.ArgumentTypeError):
            validate_api_key(None)

    def test_strips_whitespace(self):
        assert validate_api_key("  validlongkey123  ") == "validlongkey123"


# ---------------------------------------------------------------------------
# TestUUIDEncoder
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestUUIDEncoder:
    def test_uuid_serialized(self):
        test_uuid = uuid4()
        result = json.dumps({"id": test_uuid}, cls=UUIDEncoder)
        parsed = json.loads(result)
        assert parsed["id"] == str(test_uuid)

    def test_non_uuid_delegates(self):
        result = json.dumps({"key": "value"}, cls=UUIDEncoder)
        assert json.loads(result) == {"key": "value"}


# ---------------------------------------------------------------------------
# TestGetProductInfoFromJson
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestGetProductInfoFromJson:
    def test_valid_extraction(self, tmp_path):
        data = {"motor": [{"url": "https://example.com", "manufacturer": "Test"}]}
        f = tmp_path / "products.json"
        f.write_text(json.dumps(data))
        result = get_product_info_from_json(str(f), "motor", 0)
        assert result["manufacturer"] == "Test"
        assert result["url"] == "https://example.com"

    def test_product_key_renamed(self, tmp_path):
        data = {"motor": [{"product": "ServoX", "manufacturer": "Acme"}]}
        f = tmp_path / "products.json"
        f.write_text(json.dumps(data))
        result = get_product_info_from_json(str(f), "motor", 0)
        assert "product_name" in result
        assert result["product_name"] == "ServoX"
        assert "product" not in result

    def test_pages_converted_to_string(self, tmp_path):
        data = {"motor": [{"pages": [1, 2, 3], "manufacturer": "X"}]}
        f = tmp_path / "products.json"
        f.write_text(json.dumps(data))
        result = get_product_info_from_json(str(f), "motor", 0)
        assert result["pages"] == "1,2,3"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            get_product_info_from_json("/nonexistent/file.json", "motor", 0)

    def test_invalid_type(self, tmp_path):
        data = {"motor": [{"manufacturer": "X"}]}
        f = tmp_path / "products.json"
        f.write_text(json.dumps(data))
        with pytest.raises(ValueError):
            get_product_info_from_json(str(f), "drive", 0)

    def test_invalid_index(self, tmp_path):
        data = {"motor": [{"manufacturer": "X"}]}
        f = tmp_path / "products.json"
        f.write_text(json.dumps(data))
        with pytest.raises(ValueError):
            get_product_info_from_json(str(f), "motor", 5)


# ---------------------------------------------------------------------------
# TestParseGeminiResponse
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestParseGeminiResponse:
    def _motor_kwargs(self, **overrides):
        """Minimal valid Motor field set for constructing test data."""
        defaults = {
            "product_name": "TestMotor",
            "part_number": "TM-100",
            "manufacturer": "TestCo",
        }
        defaults.update(overrides)
        return defaults

    def test_pre_parsed_response(self):
        motor = Motor(**self._motor_kwargs(), product_type="motor")
        response = Mock()
        response.parsed = [motor]
        result = parse_gemini_response(response, Motor, "motor")
        assert len(result) == 1
        assert result[0].product_name == "TestMotor"

    def test_raw_text_response_list(self):
        response = Mock(spec=[])
        response.parsed = None
        response.text = json.dumps([self._motor_kwargs()])
        result = parse_gemini_response(response, Motor, "motor")
        assert len(result) == 1
        assert result[0].product_name == "TestMotor"

    def test_raw_text_response_dict(self):
        response = Mock(spec=[])
        response.parsed = None
        response.text = json.dumps(self._motor_kwargs())
        result = parse_gemini_response(response, Motor, "motor")
        assert len(result) == 1

    def test_invalid_response_raises(self):
        response = Mock(spec=[])
        # No .parsed and no .text attributes
        del response.parsed
        del response.text
        with pytest.raises(ValueError):
            parse_gemini_response(response, Motor, "motor")

    def test_context_merged(self):
        response = Mock(spec=[])
        response.parsed = None
        response.text = json.dumps([self._motor_kwargs()])
        ctx = {"datasheet_url": "https://example.com/ds.pdf"}
        result = parse_gemini_response(response, Motor, "motor", context=ctx)
        assert result[0].datasheet_url == "https://example.com/ds.pdf"

    def test_product_type_set(self):
        response = Mock(spec=[])
        response.parsed = None
        response.text = json.dumps([self._motor_kwargs()])
        result = parse_gemini_response(response, Motor, "motor")
        assert result[0].product_type == "motor"

    def test_validation_failure_skips_item(self):
        # First item is invalid (missing product_name), second is valid
        items = [
            {"part_number": "BAD"},  # missing product_name
            self._motor_kwargs(),
        ]
        response = Mock(spec=[])
        response.parsed = None
        response.text = json.dumps(items)
        result = parse_gemini_response(response, Motor, "motor")
        assert len(result) == 1
        assert result[0].product_name == "TestMotor"

    def test_all_invalid_raises(self):
        items = [
            {"part_number": "BAD1"},
            {"part_number": "BAD2"},
        ]
        response = Mock(spec=[])
        response.parsed = None
        response.text = json.dumps(items)
        with pytest.raises(ValueError):
            parse_gemini_response(response, Motor, "motor")


# ---------------------------------------------------------------------------
# TestIsPdfUrl
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestIsPdfUrl:
    def test_pdf_extension(self):
        assert is_pdf_url("https://example.com/doc.pdf") is True

    @patch("datasheetminer.utils.urlopen")
    def test_non_pdf_extension(self, mock_urlopen):
        assert is_pdf_url("https://example.com/page.html") is False

    @patch("datasheetminer.utils.urlopen")
    def test_content_type_pdf(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_info = Mock()
        mock_info.get.return_value = "application/pdf"
        mock_response.info.return_value = mock_info
        mock_urlopen.return_value = mock_response
        assert is_pdf_url("https://example.com/document") is True


# ---------------------------------------------------------------------------
# TestExtractPdfPages
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestExtractPdfPages:
    def test_valid_extraction(self, tmp_path):
        src = tmp_path / "source.pdf"
        src.write_bytes(_make_pdf(3))
        dst = tmp_path / "output.pdf"
        extract_pdf_pages(src, dst, [0, 1])
        reader = PyPDF2.PdfReader(str(dst))
        assert len(reader.pages) == 2

    def test_out_of_range_warned(self, tmp_path):
        src = tmp_path / "source.pdf"
        src.write_bytes(_make_pdf(3))
        dst = tmp_path / "output.pdf"
        extract_pdf_pages(src, dst, [99])
        # No valid pages extracted, output file should not be created
        assert not dst.exists()

    def test_file_not_found(self, tmp_path):
        dst = tmp_path / "output.pdf"
        with pytest.raises(FileNotFoundError):
            extract_pdf_pages(Path("/nonexistent/source.pdf"), dst, [0])


# ---------------------------------------------------------------------------
# TestGetDocument
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestGetDocument:
    def test_local_file_read(self, tmp_path):
        pdf_bytes = _make_pdf(1)
        f = tmp_path / "local.pdf"
        f.write_bytes(pdf_bytes)
        result = get_document(str(f))
        assert result == pdf_bytes

    def test_local_file_with_pages(self, tmp_path):
        pdf_bytes = _make_pdf(3)
        f = tmp_path / "multi.pdf"
        f.write_bytes(pdf_bytes)
        result = get_document(str(f), pages="1,2")
        assert result is not None
        reader = PyPDF2.PdfReader(io.BytesIO(result))
        assert len(reader.pages) == 2


# ---------------------------------------------------------------------------
# TestGetWebContent
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestGetWebContent:
    @patch("datasheetminer.utils.urlopen")
    def test_success_mocked(self, mock_urlopen):
        html = b"<html><body>Hello</body></html>"
        mock_response = MagicMock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_response.read.return_value = html
        mock_info = Mock()
        mock_info.get.side_effect = lambda key, default="": {
            "Content-Type": "text/html",
            "Content-Encoding": None,
        }.get(key, default)
        mock_response.info.return_value = mock_info
        mock_urlopen.return_value = mock_response
        result = get_web_content("https://example.com")
        assert result is not None
        assert "Hello" in result

    @patch("datasheetminer.utils.urlopen")
    def test_http_error_returns_none(self, mock_urlopen):
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            url="https://example.com",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )
        result = get_web_content("https://example.com")
        assert result is None
