"""Scraper integration: degraded inputs and routing decisions.

Feeds ``process_datasheet`` real (synthetic or malformed) PDF bytes and
mocks only the external surface (LLM + DynamoDB). The goal is to verify:

- Bad PDF bytes (truncated, HTML-disguised, encrypted) hit the
  exception-handling path and write an ``extract_fail`` ingest log,
  rather than crashing silently or writing partial data.
- Page routing logic — per-page extraction vs bundled fallback vs
  full-doc extraction — picks the right branch given page count and
  ``MAX_PER_PAGE_CALLS``.
- The text-keyword heuristic actually runs end-to-end and feeds its
  output into the LLM call site.

Tests deliberately short-circuit *before* the Pydantic-model code path
(``parse_gemini_response`` returns ``[]``) so they don't depend on any
particular product schema. This insulates them from in-flight model
changes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import fitz  # PyMuPDF
import pytest

from specodex.ingest_log import (
    STATUS_EXTRACT_FAIL,
    STATUS_SUCCESS,
    SCHEMA_VERSION,
)
from specodex.page_finder import SPEC_KEYWORDS


# ---------------------------------------------------------------------------
# PDF builders
# ---------------------------------------------------------------------------


def _spec_text(group_count: int = 5) -> str:
    return "\n".join(g[0] for g in SPEC_KEYWORDS[:group_count])


def _build_pdf(pages: list[str]) -> bytes:
    """Build an in-memory PDF with one body string per page."""
    doc = fitz.open()
    for body in pages:
        page = doc.new_page()
        if body:
            page.insert_text((50, 72), body)
    data = doc.tobytes()
    doc.close()
    return data


def _truncated_pdf(full_pdf: bytes, keep: int = 1024) -> bytes:
    """Lop off all but the first ``keep`` bytes — keeps the %PDF magic
    but loses the trailer so fitz refuses to open it."""
    return full_pdf[:keep]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


FAKE_API_KEY = "fake-api-key"


@pytest.fixture
def db():
    client = MagicMock()
    client.product_exists.return_value = False
    client.read_ingest.return_value = None  # no prior attempt — don't skip
    client.batch_create.return_value = 0
    return client


def _last_ingest_status(db_mock: MagicMock) -> str:
    """Pull the ``status`` field off the most recent ``write_ingest`` call."""
    assert db_mock.write_ingest.called, "scraper did not write an ingest log"
    record = db_mock.write_ingest.call_args.args[0]
    assert record["schema_version"] == SCHEMA_VERSION
    return record["status"]


# ---------------------------------------------------------------------------
# Bad PDF bytes — must land in extract_fail, not crash
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDegradedPdfInputs:
    @patch("specodex.scraper.get_document")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    def test_html_disguised_as_pdf(
        self, _is_pdf: MagicMock, mock_get: MagicMock, db: MagicMock
    ) -> None:
        """A 162-byte HTML response served at a `.pdf` URL — fitz refuses
        to open it; scraper must extract_fail rather than crash."""
        from specodex.scraper import process_datasheet

        mock_get.return_value = b"<html><body>404 not found</body></html>"

        result = process_datasheet(
            db,
            FAKE_API_KEY,
            "motor",
            "Acme",
            "M1",
            "Mfam",
            "https://x/y.pdf",
            pages=None,
        )
        assert result == "failed"
        assert _last_ingest_status(db) == STATUS_EXTRACT_FAIL

    @patch("specodex.scraper.get_document")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    def test_truncated_pdf(
        self, _is_pdf: MagicMock, mock_get: MagicMock, db: MagicMock
    ) -> None:
        """First-1KB of a real PDF: header parses but body/trailer doesn't."""
        from specodex.scraper import process_datasheet

        full = _build_pdf([_spec_text(5)] * 5)
        mock_get.return_value = _truncated_pdf(full, keep=1024)

        result = process_datasheet(
            db,
            FAKE_API_KEY,
            "motor",
            "Acme",
            "M1",
            "Mfam",
            "https://x/y.pdf",
            pages=None,
        )
        assert result == "failed"
        assert _last_ingest_status(db) == STATUS_EXTRACT_FAIL

    @patch("specodex.scraper.get_document")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    def test_pdf_with_no_text_layer(
        self, _is_pdf: MagicMock, mock_get: MagicMock, db: MagicMock
    ) -> None:
        """A PDF with no text content — page_finder returns 0 pages,
        scraper falls through to the full-doc bundled-extraction path,
        and the LLM-parse stub returns []. Result: extract_fail."""
        from specodex.scraper import process_datasheet

        mock_get.return_value = _build_pdf(["", "", ""])  # 3 blank pages

        with (
            patch("specodex.scraper.generate_content") as mock_gen,
            patch(
                "specodex.scraper.parse_gemini_response", return_value=[]
            ) as mock_parse,
        ):
            mock_gen.return_value = MagicMock(text="[]", usage_metadata=None)
            result = process_datasheet(
                db,
                FAKE_API_KEY,
                "motor",
                "Acme",
                "M1",
                "Mfam",
                "https://x/y.pdf",
                pages=None,
            )

        assert result == "failed"
        assert _last_ingest_status(db) == STATUS_EXTRACT_FAIL
        # The LLM was called once on the full PDF (no pages detected → no
        # subset extraction).
        assert mock_parse.call_count == 1


# ---------------------------------------------------------------------------
# Routing — per-page vs bundled vs full-doc
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPageRouting:
    @patch("specodex.scraper.get_document")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    def test_explicit_pages_routes_to_per_page(
        self,
        _is_pdf: MagicMock,
        mock_get: MagicMock,
        db: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If caller supplies pages and the count is under
        MAX_PER_PAGE_CALLS, scraper extracts per-page (one LLM call per
        page chunk), not bundled."""
        from specodex import scraper
        from specodex.scraper import process_datasheet

        # PAGES_PER_CHUNK default is 4 — pages=[0,1,2] would coalesce to
        # one chunk. BRIDGE_GAP default is 1 which also fills gaps. Force
        # both to per-page so this test verifies what it says it does.
        monkeypatch.setattr(scraper, "PAGES_PER_CHUNK", 1)
        monkeypatch.setattr(scraper, "BRIDGE_GAP", 0)

        mock_get.return_value = _build_pdf([_spec_text(5)] * 4)
        with (
            patch("specodex.scraper.generate_content") as mock_gen,
            patch(
                "specodex.scraper.parse_gemini_response", return_value=[]
            ) as mock_parse,
        ):
            mock_gen.return_value = MagicMock(text="[]", usage_metadata=None)
            process_datasheet(
                db,
                FAKE_API_KEY,
                "motor",
                "Acme",
                "M1",
                "Mfam",
                "https://x/y.pdf",
                pages=[0, 1, 2],
            )

        assert mock_parse.call_count == 3

    @patch("specodex.scraper.get_document")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    def test_pages_exceeding_cap_falls_back_to_bundled(
        self,
        _is_pdf: MagicMock,
        mock_get: MagicMock,
        db: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When detected/explicit pages > MAX_PER_PAGE_CALLS, scraper
        extracts the page subset into one bundled PDF and makes ONE
        LLM call, not N."""
        from specodex import scraper

        monkeypatch.setattr(scraper, "MAX_PER_PAGE_CALLS", 2)

        mock_get.return_value = _build_pdf([_spec_text(5)] * 6)

        with (
            patch("specodex.scraper.generate_content") as mock_gen,
            patch(
                "specodex.scraper.parse_gemini_response", return_value=[]
            ) as mock_parse,
        ):
            mock_gen.return_value = MagicMock(text="[]", usage_metadata=None)
            scraper.process_datasheet(
                db,
                FAKE_API_KEY,
                "motor",
                "Acme",
                "M1",
                "Mfam",
                "https://x/y.pdf",
                pages=[0, 1, 2, 3, 4],  # 5 > cap of 2
            )

        assert mock_parse.call_count == 1, "should bundle, not per-page"

    @patch("specodex.scraper.get_document")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    def test_no_pages_no_detected_falls_through_to_full_doc(
        self,
        _is_pdf: MagicMock,
        mock_get: MagicMock,
        db: MagicMock,
    ) -> None:
        """pages=None and the heuristic finds nothing → scraper hands the
        full PDF to the LLM in one call (the legacy bundled path)."""
        from specodex.scraper import process_datasheet

        # No spec keywords anywhere → page_finder returns []
        mock_get.return_value = _build_pdf(["lorem ipsum"] * 3)

        with (
            patch("specodex.scraper.generate_content") as mock_gen,
            patch(
                "specodex.scraper.parse_gemini_response", return_value=[]
            ) as mock_parse,
        ):
            mock_gen.return_value = MagicMock(text="[]", usage_metadata=None)
            process_datasheet(
                db,
                FAKE_API_KEY,
                "motor",
                "Acme",
                "M1",
                "Mfam",
                "https://x/y.pdf",
                pages=None,
            )

        assert mock_parse.call_count == 1
        # And the LLM saw bytes whose size matches the full PDF (not a
        # subset) — i.e., the call wasn't routed through the bundled
        # extractor.
        sent_bytes = mock_gen.call_args.args[0]
        assert sent_bytes == mock_get.return_value

    @patch("specodex.scraper.get_document")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    def test_text_heuristic_drives_per_page_when_pages_none(
        self,
        _is_pdf: MagicMock,
        mock_get: MagicMock,
        db: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """pages=None and the heuristic finds 2 pages → scraper extracts
        per-page (2 LLM calls) without the caller specifying pages."""
        from specodex import scraper
        from specodex.scraper import process_datasheet

        # Disable the bridge so [0, 2] doesn't fill into [0, 1, 2] (one
        # chunk = one LLM call). BRIDGE_GAP default is 1, intentionally
        # designed to keep continuation pages with their parent — but
        # this test wants to verify per-page routing of two distinct
        # spec pages.
        monkeypatch.setattr(scraper, "BRIDGE_GAP", 0)
        monkeypatch.setattr(scraper, "PAGES_PER_CHUNK", 1)

        # Two spec pages, two filler pages — heuristic returns [0, 2].
        mock_get.return_value = _build_pdf(
            [_spec_text(5), "filler", _spec_text(5), "filler"]
        )
        with (
            patch("specodex.scraper.generate_content") as mock_gen,
            patch(
                "specodex.scraper.parse_gemini_response", return_value=[]
            ) as mock_parse,
        ):
            mock_gen.return_value = MagicMock(text="[]", usage_metadata=None)
            process_datasheet(
                db,
                FAKE_API_KEY,
                "motor",
                "Acme",
                "M1",
                "Mfam",
                "https://x/y.pdf",
                pages=None,
            )

        assert mock_parse.call_count == 2

    @patch("specodex.scraper.get_document")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    def test_ingest_log_records_pages_metadata(
        self,
        _is_pdf: MagicMock,
        mock_get: MagicMock,
        db: MagicMock,
    ) -> None:
        """The ingest log captures pages_detected, pages_used, and
        page_finder_method when auto-detection fired."""
        from specodex.scraper import process_datasheet

        mock_get.return_value = _build_pdf([_spec_text(5), "filler", _spec_text(5)])
        with (
            patch("specodex.scraper.generate_content") as mock_gen,
            patch("specodex.scraper.parse_gemini_response", return_value=[]),
        ):
            mock_gen.return_value = MagicMock(text="[]", usage_metadata=None)
            process_datasheet(
                db,
                FAKE_API_KEY,
                "motor",
                "Acme",
                "M1",
                "Mfam",
                "https://x/y.pdf",
                pages=None,
            )

        record = db.write_ingest.call_args.args[0]
        assert record["pages_detected"] == 2
        assert record["pages_used"] == [0, 2]
        assert record["page_finder_method"] == "text_keyword"


# ---------------------------------------------------------------------------
# Pre-flight short-circuit
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPreflightShortCircuit:
    @patch("specodex.scraper.get_document")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    def test_skips_when_prior_success(
        self,
        _is_pdf: MagicMock,
        mock_get: MagicMock,
        db: MagicMock,
    ) -> None:
        """A prior success in the ingest log short-circuits before any
        download or LLM call."""
        from specodex.scraper import process_datasheet

        db.read_ingest.return_value = {
            "status": STATUS_SUCCESS,
            "fields_filled_avg": 10,
            "fields_total": 30,
            "SK": "INGEST#2026-04-20T00:00:00Z",
        }

        result = process_datasheet(
            db,
            FAKE_API_KEY,
            "motor",
            "Acme",
            "M1",
            "Mfam",
            "https://x/y.pdf",
            pages=None,
        )

        assert result == "skipped"
        mock_get.assert_not_called()  # no download
        db.write_ingest.assert_not_called()  # no log re-write

    @patch("specodex.scraper.get_document")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    def test_force_overrides_prior_success(
        self,
        _is_pdf: MagicMock,
        mock_get: MagicMock,
        db: MagicMock,
    ) -> None:
        """``force=True`` re-runs the scrape even when the ingest log
        says the URL already succeeded."""
        from specodex.scraper import process_datasheet

        db.read_ingest.return_value = {
            "status": STATUS_SUCCESS,
            "fields_filled_avg": 10,
            "fields_total": 30,
            "SK": "INGEST#2026-04-20T00:00:00Z",
        }
        mock_get.return_value = b"<html>not a pdf</html>"

        result = process_datasheet(
            db,
            FAKE_API_KEY,
            "motor",
            "Acme",
            "M1",
            "Mfam",
            "https://x/y.pdf",
            pages=None,
            force=True,
        )

        assert result == "failed"  # bytes aren't a real PDF — extract_fail
        mock_get.assert_called_once()
