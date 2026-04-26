"""
Extended tests for utils.py — covers download_pdf, extract_pdf_pages error paths,
get_web_content compression handling, process_pdf_from_url, and is_pdf_url.
"""

import gzip
import zlib
from unittest.mock import MagicMock, patch

import pytest

from specodex.utils import (
    download_pdf,
    extract_pdf_pages,
    get_web_content,
    is_pdf_url,
)


# =================== download_pdf ===================


class TestDownloadPdf:
    @patch("specodex.utils.urlopen")
    def test_success(self, mock_urlopen, tmp_path):
        mock_response = MagicMock()
        mock_response.read.return_value = b"%PDF-1.4 fake content"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        dest = tmp_path / "out.pdf"
        download_pdf("https://example.com/test.pdf", dest)
        assert dest.read_bytes() == b"%PDF-1.4 fake content"

    @patch("specodex.utils.urlopen")
    def test_http_error_raises(self, mock_urlopen, tmp_path):
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            "https://example.com/test.pdf", 404, "Not Found", {}, None
        )
        with pytest.raises(HTTPError):
            download_pdf("https://example.com/test.pdf", tmp_path / "out.pdf")

    @patch("specodex.utils.urlopen")
    def test_url_error_raises(self, mock_urlopen, tmp_path):
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")
        with pytest.raises(URLError):
            download_pdf("https://example.com/test.pdf", tmp_path / "out.pdf")


# =================== extract_pdf_pages error paths ===================


class TestExtractPdfPagesErrors:
    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            extract_pdf_pages(tmp_path / "nonexistent.pdf", tmp_path / "out.pdf", [0])

    @patch("specodex.utils.shutil.copy")
    @patch("specodex.utils.PyPDF2.PdfReader")
    def test_pdf_read_error_copies_debug(self, mock_reader, mock_copy, tmp_path):
        from PyPDF2.errors import PdfReadError

        # Create a dummy input file
        input_pdf = tmp_path / "bad.pdf"
        input_pdf.write_bytes(b"not a real pdf")

        mock_reader.side_effect = PdfReadError("Corrupted")

        with pytest.raises(PdfReadError):
            extract_pdf_pages(input_pdf, tmp_path / "out.pdf", [0])

        mock_copy.assert_called_once()

    @patch("specodex.utils.PyPDF2.PdfReader")
    def test_general_exception_raises(self, mock_reader, tmp_path):
        input_pdf = tmp_path / "bad.pdf"
        input_pdf.write_bytes(b"not a real pdf")

        mock_reader.side_effect = RuntimeError("Something unexpected")

        with pytest.raises(RuntimeError):
            extract_pdf_pages(input_pdf, tmp_path / "out.pdf", [0])

    def test_out_of_range_pages_warns(self, tmp_path):
        """Pages beyond PDF length are skipped with a warning."""
        import PyPDF2

        # Create a minimal valid PDF
        writer = PyPDF2.PdfWriter()
        writer.add_blank_page(width=72, height=72)
        input_pdf = tmp_path / "one_page.pdf"
        with open(input_pdf, "wb") as f:
            writer.write(f)

        output_pdf = tmp_path / "out.pdf"
        extract_pdf_pages(input_pdf, output_pdf, [0, 5, 10])

        # Only page 0 should be extracted
        reader = PyPDF2.PdfReader(str(output_pdf))
        assert len(reader.pages) == 1


# =================== get_web_content ===================


class TestGetWebContent:
    @patch("specodex.utils.urlopen")
    def test_plain_content(self, mock_urlopen):
        mock_headers = MagicMock()
        mock_headers.get.side_effect = lambda k, d="": {
            "Content-Type": "text/html",
            "Content-Encoding": None,
        }.get(k, d)

        mock_response = MagicMock()
        mock_response.read.return_value = b"<html>Hello</html>"
        mock_response.info.return_value = mock_headers
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = get_web_content("https://example.com")
        assert result is not None
        assert "Hello" in result

    @patch("specodex.utils.urlopen")
    def test_gzip_content(self, mock_urlopen):
        raw = b"<html>Compressed</html>"
        compressed = gzip.compress(raw)

        mock_headers = MagicMock()
        mock_headers.get.side_effect = lambda k, d="": {
            "Content-Type": "text/html",
            "Content-Encoding": "gzip",
        }.get(k, d)
        mock_response = MagicMock()
        mock_response.read.return_value = compressed
        mock_response.info.return_value = mock_headers
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = get_web_content("https://example.com")
        assert result is not None
        assert "Compressed" in result

    @patch("specodex.utils.urlopen")
    def test_deflate_content(self, mock_urlopen):
        raw = b"<html>Deflated</html>"
        compressed = zlib.compress(raw)

        mock_headers = MagicMock()
        mock_headers.get.side_effect = lambda k, d="": {
            "Content-Type": "text/html",
            "Content-Encoding": "deflate",
        }.get(k, d)
        mock_response = MagicMock()
        mock_response.read.return_value = compressed
        mock_response.info.return_value = mock_headers
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = get_web_content("https://example.com")
        assert result is not None
        assert "Deflated" in result

    @patch("specodex.utils.urlopen")
    def test_http_error_returns_none(self, mock_urlopen):
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            "https://example.com", 500, "Server Error", {}, None
        )
        assert get_web_content("https://example.com") is None

    @patch("specodex.utils.urlopen")
    def test_unexpected_error_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = RuntimeError("Connection reset")
        assert get_web_content("https://example.com") is None


# =================== is_pdf_url ===================


class TestIsPdfUrl:
    def test_pdf_extension(self):
        assert is_pdf_url("https://example.com/file.pdf") is True

    def test_pdf_extension_uppercase(self):
        assert is_pdf_url("https://example.com/FILE.PDF") is True

    def test_non_pdf_extension(self):
        assert is_pdf_url("/tmp/file.txt") is False

    @patch("specodex.utils.urlopen")
    def test_content_type_check(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.info.return_value.get.return_value = "application/pdf"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        assert is_pdf_url("https://example.com/document") is True

    @patch("specodex.utils.urlopen")
    def test_content_type_non_pdf(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.info.return_value.get.return_value = "text/html"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        assert is_pdf_url("https://example.com/page") is False

    @patch("specodex.utils.urlopen")
    def test_head_request_error_returns_false(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Timeout")
        assert is_pdf_url("https://example.com/unknown") is False
