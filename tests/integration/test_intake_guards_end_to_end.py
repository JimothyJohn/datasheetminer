"""Intake guards exercised through ``intake_single``.

Unit tests for individual guards live in ``test_intake_guards.py``; this
module wires guards into the full intake flow so we catch ordering bugs
(e.g., file_integrity must run before the LLM scan to save tokens) and
misrouted reject paths.

External surfaces — S3, DynamoDB, Gemini — are mocked. Tests don't read
any product schema and don't depend on common.py, so they're insulated
from in-flight model changes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import fitz
import pytest

from cli.intake import IntakeScanResult, intake_single

BUCKET = "test-bucket"
TRIAGE_KEY = "triage/test.pdf"
API_KEY = "fake-api-key"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_real_pdf() -> bytes:
    """Build a real PDF over the 1024-byte file_integrity floor."""
    doc = fitz.open()
    # Multiple pages of padded text — easily clears 1KB minimum.
    for _ in range(3):
        page = doc.new_page()
        page.insert_text((50, 72), "rated voltage 24V " * 200)
    data = doc.tobytes()
    doc.close()
    assert len(data) >= 1024, f"test PDF too small: {len(data)}"
    return data


def _make_s3(body: bytes) -> MagicMock:
    s3 = MagicMock()
    resp_body = MagicMock()
    resp_body.read.return_value = body
    s3.get_object.return_value = {"Body": resp_body}
    return s3


def _make_dynamo() -> MagicMock:
    return MagicMock()


def _approving_scan(**overrides: object) -> IntakeScanResult:
    """Default scan result that passes every post-scan guard."""
    base: dict = {
        "is_valid_datasheet": True,
        "has_table_of_contents": True,
        "has_specification_tables": True,
        "product_type": "motor",
        "manufacturer": "Acme",
        "product_name": "M1",
        "product_family": "M-series",
        "category": "brushless dc motor",
        "spec_pages": [1, 2, 3],
        "spec_density": 0.6,
        "rejection_reason": None,
        "distinct_product_count": 1,
        "is_multi_category": False,
    }
    base.update(overrides)  # type: ignore[arg-type]
    return IntakeScanResult.model_validate(base)


# ---------------------------------------------------------------------------
# File-integrity guard: must run BEFORE the LLM (token-cost protection)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFileIntegrityGuard:
    @patch("cli.intake.scan_pdf")
    @patch("cli.intake._find_by_content_hash", return_value=None)
    def test_empty_bytes_rejected_before_scan(
        self, _hash: MagicMock, mock_scan: MagicMock
    ) -> None:
        s3 = _make_s3(b"")
        result = intake_single(
            BUCKET, TRIAGE_KEY, API_KEY, s3_client=s3, dynamo_client=_make_dynamo()
        )
        assert result["status"] == "rejected"
        assert result["guard"] == "file_integrity"
        mock_scan.assert_not_called()  # never spent a Gemini token
        s3.delete_object.assert_called_once()  # purge from triage

    @patch("cli.intake.scan_pdf")
    @patch("cli.intake._find_by_content_hash", return_value=None)
    def test_html_disguised_as_pdf_rejected(
        self, _hash: MagicMock, mock_scan: MagicMock
    ) -> None:
        s3 = _make_s3(b"<!DOCTYPE html><html><body>404</body></html>" + b" " * 2000)
        result = intake_single(
            BUCKET, TRIAGE_KEY, API_KEY, s3_client=s3, dynamo_client=_make_dynamo()
        )
        assert result["status"] == "rejected"
        assert result["guard"] == "file_integrity"
        assert "HTML" in result["reason"]
        mock_scan.assert_not_called()

    @patch("cli.intake.scan_pdf")
    @patch("cli.intake._find_by_content_hash", return_value=None)
    def test_tiny_file_rejected(self, _hash: MagicMock, mock_scan: MagicMock) -> None:
        # %PDF magic but only 8 bytes total — under the 1024-byte floor.
        s3 = _make_s3(b"%PDF-1.4")
        result = intake_single(
            BUCKET, TRIAGE_KEY, API_KEY, s3_client=s3, dynamo_client=_make_dynamo()
        )
        assert result["status"] == "rejected"
        assert result["guard"] == "file_integrity"
        assert "too small" in result["reason"]
        mock_scan.assert_not_called()

    @patch("cli.intake.scan_pdf")
    @patch("cli.intake._find_by_content_hash", return_value=None)
    def test_missing_magic_bytes_rejected(
        self, _hash: MagicMock, mock_scan: MagicMock
    ) -> None:
        # Not HTML, not %PDF — generic garbage of sufficient size.
        s3 = _make_s3(b"GARBAGE" + b"\x00" * 2000)
        result = intake_single(
            BUCKET, TRIAGE_KEY, API_KEY, s3_client=s3, dynamo_client=_make_dynamo()
        )
        assert result["status"] == "rejected"
        assert result["guard"] == "file_integrity"
        assert "magic bytes" in result["reason"]


# ---------------------------------------------------------------------------
# Content-hash dedup
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestContentHashDedup:
    @patch("cli.intake.scan_pdf")
    @patch("cli.intake._find_by_content_hash")
    def test_duplicate_content_hash_short_circuits(
        self, mock_hash: MagicMock, mock_scan: MagicMock
    ) -> None:
        mock_hash.return_value = {
            "datasheet_id": "abc123",
            "status": "approved",
        }
        s3 = _make_s3(_build_real_pdf())

        result = intake_single(
            BUCKET, TRIAGE_KEY, API_KEY, s3_client=s3, dynamo_client=_make_dynamo()
        )

        assert result["status"] == "skipped"
        assert "duplicate" in result["reason"]
        assert result["existing_datasheet_id"] == "abc123"
        mock_scan.assert_not_called()  # no Gemini call on duplicate
        s3.delete_object.assert_called_once()  # cleaned from triage


# ---------------------------------------------------------------------------
# Scan-result rejection (LLM said "not a datasheet")
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestScanRejection:
    @patch("cli.intake.scan_pdf")
    @patch("cli.intake._find_by_content_hash", return_value=None)
    def test_invalid_datasheet_rejected_with_reason(
        self, _hash: MagicMock, mock_scan: MagicMock
    ) -> None:
        mock_scan.return_value = IntakeScanResult(
            is_valid_datasheet=False,
            has_table_of_contents=False,
            has_specification_tables=False,
            rejection_reason="marketing brochure with no specs",
            spec_density=0.0,
        )
        s3 = _make_s3(_build_real_pdf())
        result = intake_single(
            BUCKET, TRIAGE_KEY, API_KEY, s3_client=s3, dynamo_client=_make_dynamo()
        )
        assert result["status"] == "rejected"
        assert "marketing brochure" in result["reason"]


# ---------------------------------------------------------------------------
# Post-scan guards
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPostScanGuards:
    @patch("cli.intake.scan_pdf")
    @patch("cli.intake._find_by_content_hash", return_value=None)
    def test_multi_category_blocked_by_document_scope(
        self, _hash: MagicMock, mock_scan: MagicMock
    ) -> None:
        mock_scan.return_value = _approving_scan(is_multi_category=True)
        s3 = _make_s3(_build_real_pdf())
        result = intake_single(
            BUCKET, TRIAGE_KEY, API_KEY, s3_client=s3, dynamo_client=_make_dynamo()
        )
        assert result["status"] == "rejected"
        assert result["guard"] == "document_scope"

    @patch("cli.intake.scan_pdf")
    @patch("cli.intake._find_by_content_hash", return_value=None)
    def test_missing_manufacturer_blocked(
        self, _hash: MagicMock, mock_scan: MagicMock
    ) -> None:
        mock_scan.return_value = _approving_scan(manufacturer=None)
        s3 = _make_s3(_build_real_pdf())
        result = intake_single(
            BUCKET, TRIAGE_KEY, API_KEY, s3_client=s3, dynamo_client=_make_dynamo()
        )
        assert result["status"] == "rejected"
        assert result["guard"] == "manufacturer_identity"

    @patch("cli.intake.scan_pdf")
    @patch("cli.intake._find_by_content_hash", return_value=None)
    def test_low_density_blocked_by_calibrated_threshold(
        self, _hash: MagicMock, mock_scan: MagicMock
    ) -> None:
        # Motor threshold is 0.25; 0.10 is well below.
        mock_scan.return_value = _approving_scan(
            spec_density=0.10, spec_pages=[1], product_name=None, product_family=None
        )
        s3 = _make_s3(_build_real_pdf())
        result = intake_single(
            BUCKET, TRIAGE_KEY, API_KEY, s3_client=s3, dynamo_client=_make_dynamo()
        )
        assert result["status"] == "rejected"
        # Could be blocked by extraction_feasibility OR spec_density_calibrated;
        # the first matters less than that one of the post-scan guards bit.
        assert result["guard"] in {
            "extraction_feasibility",
            "spec_density_calibrated",
        }


# ---------------------------------------------------------------------------
# Happy path — all guards pass, PDF promoted
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestApprovedPath:
    @patch("cli.intake.scan_pdf")
    @patch("cli.intake._find_by_content_hash", return_value=None)
    def test_valid_pdf_promoted(self, _hash: MagicMock, mock_scan: MagicMock) -> None:
        mock_scan.return_value = _approving_scan()
        s3 = _make_s3(_build_real_pdf())
        dynamo = _make_dynamo()

        result = intake_single(
            BUCKET, TRIAGE_KEY, API_KEY, s3_client=s3, dynamo_client=dynamo
        )

        assert result["status"] == "approved"
        assert "datasheet_id" in result
        assert "content_hash" in result
        # PDF was moved (copy + delete), not just deleted
        s3.copy_object.assert_called_once()
        s3.delete_object.assert_called_once()
        # Datasheet record was written
        dynamo.create.assert_called_once()
