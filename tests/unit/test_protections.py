"""Tests for PDF protections: content hash dedup, blacklist, spec density, auto-blacklist."""

from unittest.mock import MagicMock, patch

import pytest

from cli.intake import IntakeScanResult, intake_single
from cli.intake_guards import _DENSITY_THRESHOLDS, _DEFAULT_DENSITY_THRESHOLD


def _threshold_for(product_type: str) -> float:
    """Resolve the per-product-type density threshold used by intake guards."""
    return _DENSITY_THRESHOLDS.get(product_type, _DEFAULT_DENSITY_THRESHOLD)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _scan_result(*, valid: bool = True, **overrides) -> IntakeScanResult:
    defaults = {
        "is_valid_datasheet": valid,
        "has_table_of_contents": valid,
        "has_specification_tables": valid,
        "product_type": "motor",
        "manufacturer": "Acme Corp",
        "product_name": "X100",
        "product_family": "X-Series",
        "category": "brushless dc motor",
        "spec_pages": [3, 4, 5],
        "spec_density": 0.7,
        "rejection_reason": None if valid else "no specification data",
    }
    defaults.update(overrides)
    return IntakeScanResult(**defaults)


# Must be ≥ 1024 bytes and start with %PDF to pass check_file_integrity in
# cli/intake_guards.py — the guard rolled out after these tests were written.
_VALID_PDF_BYTES = b"%PDF-1.4\n" + b"x" * 1200


def _mock_s3(content: bytes = _VALID_PDF_BYTES):
    s3 = MagicMock()
    body = MagicMock()
    body.read.return_value = content
    s3.get_object.return_value = {"Body": body}
    return s3


# ---------------------------------------------------------------------------
# Content hash dedup
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestContentHashDedup:
    @patch("cli.intake._find_by_content_hash")
    @patch("cli.intake.scan_pdf")
    def test_duplicate_hash_skips_without_scanning(self, mock_scan, mock_find):
        """If content hash already exists, skip immediately — don't even call Gemini."""
        mock_find.return_value = {
            "datasheet_id": "existing-id",
            "status": "processed",
        }

        s3 = _mock_s3()
        dynamo = MagicMock()

        result = intake_single(
            "test-bucket",
            "triage/motor.pdf",
            "fake-key",
            s3_client=s3,
            dynamo_client=dynamo,
        )

        assert result["status"] == "skipped"
        assert result["reason"] == "duplicate content hash"
        assert result["existing_datasheet_id"] == "existing-id"
        mock_scan.assert_not_called()
        dynamo.create.assert_not_called()

    @patch("cli.intake._find_by_content_hash")
    @patch("cli.intake.scan_pdf")
    def test_new_hash_proceeds_to_scan(self, mock_scan, mock_find):
        """No existing hash → proceed normally."""
        mock_find.return_value = None
        mock_scan.return_value = _scan_result(valid=True, spec_density=0.8)

        s3 = _mock_s3()
        dynamo = MagicMock()
        dynamo.create.return_value = True

        result = intake_single(
            "test-bucket",
            "triage/motor.pdf",
            "fake-key",
            s3_client=s3,
            dynamo_client=dynamo,
        )

        assert result["status"] == "approved"
        assert "content_hash" in result
        mock_scan.assert_called_once()

    @patch("cli.intake._find_by_content_hash")
    @patch("cli.intake.scan_pdf")
    def test_content_hash_stored_on_datasheet(self, mock_scan, mock_find):
        """Promoted datasheet should have content_hash set."""
        mock_find.return_value = None
        mock_scan.return_value = _scan_result(valid=True, spec_density=0.8)

        s3 = _mock_s3()
        dynamo = MagicMock()
        dynamo.create.return_value = True

        intake_single(
            "test-bucket",
            "triage/motor.pdf",
            "fake-key",
            s3_client=s3,
            dynamo_client=dynamo,
        )

        ds = dynamo.create.call_args[0][0]
        assert ds.content_hash is not None
        assert len(ds.content_hash) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# Spec density gate
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSpecDensity:
    @patch("cli.intake._find_by_content_hash")
    @patch("cli.intake.scan_pdf")
    def test_low_density_rejected(self, mock_scan, mock_find):
        """PDF marked valid but with low spec density should be rejected."""
        mock_find.return_value = None
        mock_scan.return_value = _scan_result(valid=True, spec_density=0.1)

        s3 = _mock_s3()
        dynamo = MagicMock()

        result = intake_single(
            "test-bucket",
            "triage/sparse.pdf",
            "fake-key",
            s3_client=s3,
            dynamo_client=dynamo,
        )

        assert result["status"] == "rejected"
        assert "spec density" in result["reason"]
        dynamo.create.assert_not_called()

    @patch("cli.intake._find_by_content_hash")
    @patch("cli.intake.scan_pdf")
    def test_high_density_approved(self, mock_scan, mock_find):
        mock_find.return_value = None
        mock_scan.return_value = _scan_result(valid=True, spec_density=0.8)

        s3 = _mock_s3()
        dynamo = MagicMock()
        dynamo.create.return_value = True

        result = intake_single(
            "test-bucket",
            "triage/dense.pdf",
            "fake-key",
            s3_client=s3,
            dynamo_client=dynamo,
        )

        assert result["status"] == "approved"

    @patch("cli.intake._find_by_content_hash")
    @patch("cli.intake.scan_pdf")
    def test_density_at_threshold_passes(self, mock_scan, mock_find):
        """At exactly the calibrated per-type threshold, the guard must pass."""
        mock_find.return_value = None
        threshold = _threshold_for("motor")
        mock_scan.return_value = _scan_result(
            valid=True, product_type="motor", spec_density=threshold
        )

        s3 = _mock_s3()
        dynamo = MagicMock()
        dynamo.create.return_value = True

        result = intake_single(
            "test-bucket",
            "triage/borderline.pdf",
            "fake-key",
            s3_client=s3,
            dynamo_client=dynamo,
        )

        assert result["status"] == "approved"

    @patch("cli.intake._find_by_content_hash")
    @patch("cli.intake.scan_pdf")
    def test_none_density_treated_as_zero(self, mock_scan, mock_find):
        """If Gemini doesn't return spec_density, treat as 0 → reject."""
        mock_find.return_value = None
        mock_scan.return_value = _scan_result(valid=True, spec_density=None)

        s3 = _mock_s3()
        dynamo = MagicMock()

        result = intake_single(
            "test-bucket",
            "triage/no_density.pdf",
            "fake-key",
            s3_client=s3,
            dynamo_client=dynamo,
        )

        assert result["status"] == "rejected"

    def test_spec_density_on_scan_result(self):
        r = _scan_result(spec_density=0.85)
        assert r.spec_density == 0.85

    def test_spec_density_stored_on_datasheet(self):
        from specodex.models.datasheet import Datasheet

        ds = Datasheet(
            url="s3://test/x.pdf",
            product_type="motor",
            product_name="Test",
            manufacturer="Test",
            spec_density=0.75,
        )
        assert ds.spec_density == 0.75


# ---------------------------------------------------------------------------
# Blacklist check in process
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBlacklistCheck:
    def test_is_blacklisted_true(self):
        from cli.agent import _is_blacklisted

        assert _is_blacklisted({"status": "blacklisted"}) is True

    def test_is_blacklisted_false_for_approved(self):
        from cli.agent import _is_blacklisted

        assert _is_blacklisted({"status": "approved"}) is False

    def test_is_blacklisted_false_for_none(self):
        from cli.agent import _is_blacklisted

        assert _is_blacklisted(None) is False

    def test_is_blacklisted_false_for_failed(self):
        from cli.agent import _is_blacklisted

        assert _is_blacklisted({"status": "failed"}) is False


# ---------------------------------------------------------------------------
# Auto-blacklist after repeated failures
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAutoBlacklist:
    @patch("boto3.resource")
    def test_first_failure_increments_count(self, mock_resource):
        from cli.agent import _record_failure

        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table

        mock_table.scan.return_value = {
            "Items": [
                {
                    "PK": "DATASHEET#MOTOR",
                    "SK": "DATASHEET#abc",
                    "s3_key": "good_examples/test.pdf",
                    "failure_count": 0,
                }
            ]
        }

        _record_failure("good_examples/test.pdf")

        mock_table.update_item.assert_called_once()
        update_args = mock_table.update_item.call_args
        assert update_args.kwargs["ExpressionAttributeValues"][":fc"] == 1
        assert update_args.kwargs["ExpressionAttributeValues"][":s"] == "failed"

    @patch("boto3.resource")
    def test_second_failure_blacklists(self, mock_resource):
        from cli.agent import _record_failure

        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table

        mock_table.scan.return_value = {
            "Items": [
                {
                    "PK": "DATASHEET#MOTOR",
                    "SK": "DATASHEET#abc",
                    "s3_key": "good_examples/test.pdf",
                    "failure_count": 1,
                }
            ]
        }

        _record_failure("good_examples/test.pdf")

        update_args = mock_table.update_item.call_args
        assert update_args.kwargs["ExpressionAttributeValues"][":fc"] == 2
        assert update_args.kwargs["ExpressionAttributeValues"][":s"] == "blacklisted"

    @patch("boto3.resource")
    def test_no_datasheet_record_is_noop(self, mock_resource):
        from cli.agent import _record_failure

        mock_table = MagicMock()
        mock_resource.return_value.Table.return_value = mock_table

        mock_table.scan.return_value = {"Items": []}

        _record_failure("good_examples/missing.pdf")

        mock_table.update_item.assert_not_called()


# ---------------------------------------------------------------------------
# Datasheet model fields
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDatasheetModelFields:
    def test_content_hash_field(self):
        from specodex.models.datasheet import Datasheet

        ds = Datasheet(
            url="s3://test/x.pdf",
            product_type="motor",
            product_name="Test",
            manufacturer="Test",
            content_hash="a" * 64,
        )
        assert ds.content_hash == "a" * 64

    def test_failure_count_defaults_zero(self):
        from specodex.models.datasheet import Datasheet

        ds = Datasheet(
            url="s3://test/x.pdf",
            product_type="motor",
            product_name="Test",
            manufacturer="Test",
        )
        assert ds.failure_count == 0

    def test_blacklisted_status(self):
        from specodex.models.datasheet import Datasheet

        ds = Datasheet(
            url="s3://test/x.pdf",
            product_type="motor",
            product_name="Test",
            manufacturer="Test",
            status="blacklisted",
            failure_count=2,
        )
        assert ds.status == "blacklisted"
        assert ds.failure_count == 2
