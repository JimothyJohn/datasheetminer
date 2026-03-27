"""Tests for the intake pipeline — scans triage/ PDFs for TOC/specs and promotes valid ones."""

from unittest.mock import MagicMock, patch

import pytest

from cli.intake import (
    IntakeScanResult,
    list_triage,
    promote_pdf,
    intake_single,
)


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


# ---------------------------------------------------------------------------
# IntakeScanResult validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIntakeScanResult:
    def test_valid_result(self):
        r = _scan_result(valid=True)
        assert r.is_valid_datasheet is True
        assert r.product_type == "motor"
        assert r.manufacturer == "Acme Corp"

    def test_rejected_result(self):
        r = _scan_result(valid=False)
        assert r.is_valid_datasheet is False
        assert r.rejection_reason == "no specification data"

    def test_minimal_valid(self):
        r = IntakeScanResult(
            is_valid_datasheet=True,
            has_table_of_contents=False,
            has_specification_tables=True,
        )
        assert r.product_type is None
        assert r.spec_pages is None

    def test_only_toc_is_valid(self):
        r = _scan_result(
            valid=True,
            has_table_of_contents=True,
            has_specification_tables=False,
        )
        assert r.is_valid_datasheet is True


# ---------------------------------------------------------------------------
# list_triage
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListTriage:
    def test_lists_pdfs_in_triage_prefix(self):
        s3 = MagicMock()
        paginator = MagicMock()
        s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "triage/motor.pdf",
                        "Size": 1024,
                        "LastModified": MagicMock(
                            isoformat=lambda: "2026-01-01T00:00:00"
                        ),
                    },
                    {
                        "Key": "triage/drive.pdf",
                        "Size": 2048,
                        "LastModified": MagicMock(
                            isoformat=lambda: "2026-01-02T00:00:00"
                        ),
                    },
                    {
                        "Key": "triage/readme.txt",
                        "Size": 100,
                        "LastModified": MagicMock(
                            isoformat=lambda: "2026-01-03T00:00:00"
                        ),
                    },
                ]
            }
        ]

        items = list_triage("test-bucket", s3_client=s3)
        assert len(items) == 2
        assert items[0]["s3_key"] == "triage/motor.pdf"
        assert items[1]["s3_key"] == "triage/drive.pdf"

    def test_empty_triage_returns_empty(self):
        s3 = MagicMock()
        paginator = MagicMock()
        s3.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{"Contents": []}]

        items = list_triage("test-bucket", s3_client=s3)
        assert items == []


# ---------------------------------------------------------------------------
# promote_pdf
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPromotePdf:
    def test_moves_to_good_examples_and_creates_datasheet(self):
        s3 = MagicMock()
        dynamo = MagicMock()
        dynamo.create.return_value = True
        scan = _scan_result(valid=True)

        result = promote_pdf(
            "test-bucket",
            "triage/motor_spec.pdf",
            scan,
            s3_client=s3,
            dynamo_client=dynamo,
        )

        # S3 operations
        s3.copy_object.assert_called_once()
        copy_args = s3.copy_object.call_args
        key = copy_args.kwargs["Key"]
        assert key.startswith("good_examples/")
        assert key.endswith(".pdf")
        # Flat key: good_examples/{mfg}_{name}_{short_id}.pdf
        assert "acme-corp_x100_" in key
        s3.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="triage/motor_spec.pdf"
        )

        # Datasheet record
        dynamo.create.assert_called_once()
        ds = dynamo.create.call_args[0][0]
        assert ds.product_type == "motor"
        assert ds.manufacturer == "Acme Corp"
        assert ds.product_name == "X100"
        assert ds.status == "approved"
        assert ds.s3_key.startswith("good_examples/")

        # Result
        assert result["status"] == "approved"
        assert result["product_type"] == "motor"
        assert "datasheet_id" in result

    def test_uses_filename_when_no_product_name(self):
        s3 = MagicMock()
        dynamo = MagicMock()
        dynamo.create.return_value = True
        scan = _scan_result(valid=True, product_name=None)

        result = promote_pdf(
            "test-bucket",
            "triage/some_motor.pdf",
            scan,
            s3_client=s3,
            dynamo_client=dynamo,
        )

        ds = dynamo.create.call_args[0][0]
        assert ds.product_name == "some_motor"

    def test_defaults_unknown_manufacturer(self):
        s3 = MagicMock()
        dynamo = MagicMock()
        dynamo.create.return_value = True
        scan = _scan_result(valid=True, manufacturer=None)

        promote_pdf(
            "test-bucket",
            "triage/x.pdf",
            scan,
            s3_client=s3,
            dynamo_client=dynamo,
        )

        ds = dynamo.create.call_args[0][0]
        assert ds.manufacturer == "Unknown"

    def test_spec_pages_passed_to_datasheet(self):
        s3 = MagicMock()
        dynamo = MagicMock()
        dynamo.create.return_value = True
        scan = _scan_result(valid=True, spec_pages=[1, 5, 8])

        promote_pdf(
            "test-bucket",
            "triage/x.pdf",
            scan,
            s3_client=s3,
            dynamo_client=dynamo,
        )

        ds = dynamo.create.call_args[0][0]
        assert ds.pages == [1, 5, 8]


# ---------------------------------------------------------------------------
# intake_single
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIntakeSingle:
    @patch("cli.intake._find_by_content_hash")
    @patch("cli.intake.scan_pdf")
    def test_approved_pdf_promoted(self, mock_scan, mock_find):
        mock_find.return_value = None
        mock_scan.return_value = _scan_result(valid=True, spec_density=0.7)

        s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = b"%PDF-fake-content"
        s3.get_object.return_value = {"Body": body}

        dynamo = MagicMock()
        dynamo.create.return_value = True

        result = intake_single(
            "test-bucket",
            "triage/motor.pdf",
            "fake-api-key",
            s3_client=s3,
            dynamo_client=dynamo,
        )

        assert result["status"] == "approved"
        assert "datasheet_id" in result
        mock_scan.assert_called_once_with(b"%PDF-fake-content", "fake-api-key")

    @patch("cli.intake._find_by_content_hash")
    @patch("cli.intake.scan_pdf")
    def test_rejected_pdf_stays_in_triage(self, mock_scan, mock_find):
        mock_find.return_value = None
        mock_scan.return_value = _scan_result(
            valid=False, rejection_reason="just a brochure"
        )

        s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = b"%PDF-fake-content"
        s3.get_object.return_value = {"Body": body}

        dynamo = MagicMock()

        result = intake_single(
            "test-bucket",
            "triage/brochure.pdf",
            "fake-api-key",
            s3_client=s3,
            dynamo_client=dynamo,
        )

        assert result["status"] == "rejected"
        assert result["reason"] == "just a brochure"
        # Should NOT move or create datasheet
        s3.copy_object.assert_not_called()
        dynamo.create.assert_not_called()

    @patch("cli.intake._find_by_content_hash")
    @patch("cli.intake.scan_pdf")
    def test_rejected_no_reason_gives_default(self, mock_scan, mock_find):
        mock_find.return_value = None
        mock_scan.return_value = _scan_result(valid=False, rejection_reason=None)

        s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = b"%PDF-fake"
        s3.get_object.return_value = {"Body": body}

        result = intake_single(
            "test-bucket",
            "triage/x.pdf",
            "fake-key",
            s3_client=s3,
            dynamo_client=MagicMock(),
        )

        assert result["status"] == "rejected"
        assert result["reason"] == "no specification data found"


# ---------------------------------------------------------------------------
# _build_metadata — Datasheet lookup enrichment
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildMetadata:
    @patch("cli.agent._lookup_datasheet_by_s3_key")
    def test_uses_datasheet_record_when_found(self, mock_lookup):
        from cli.agent import _build_metadata
        import argparse

        mock_lookup.return_value = {
            "datasheet_id": "abc-123",
            "product_name": "X100 Motor",
            "manufacturer": "Acme Corp",
            "product_family": "X-Series",
            "url": "s3://bucket/good_examples/abc/x.pdf",
            "pages": [3, 4],
        }

        args = argparse.Namespace(
            s3_key="good_examples/abc/x.pdf",
            product_name="",
            manufacturer="",
            product_family="",
            pages=None,
            stage="dev",
            bucket="bucket",
        )

        meta = _build_metadata(args)
        assert meta["product_name"] == "X100 Motor"
        assert meta["manufacturer"] == "Acme Corp"
        assert meta["product_family"] == "X-Series"
        assert meta["pages"] == [3, 4]

    @patch("cli.agent._lookup_datasheet_by_s3_key")
    def test_falls_back_to_cli_args(self, mock_lookup):
        from cli.agent import _build_metadata
        import argparse

        mock_lookup.return_value = None

        args = argparse.Namespace(
            s3_key="queue/abc/x.pdf",
            product_name="CLI Motor",
            manufacturer="CLI Mfg",
            product_family="",
            pages="1,2",
            stage="dev",
            bucket="bucket",
        )

        meta = _build_metadata(args)
        assert meta["product_name"] == "CLI Motor"
        assert meta["manufacturer"] == "CLI Mfg"
        assert meta["pages"] == [1, 2]

    @patch("cli.agent._lookup_datasheet_by_s3_key")
    def test_datasheet_fields_override_cli_args(self, mock_lookup):
        """Datasheet record wins over CLI args when both are present."""
        from cli.agent import _build_metadata
        import argparse

        mock_lookup.return_value = {
            "datasheet_id": "ds-1",
            "product_name": "DB Name",
            "manufacturer": "DB Mfg",
            "product_family": None,
            "url": "s3://b/good_examples/ds-1/f.pdf",
            "pages": [5],
        }

        args = argparse.Namespace(
            s3_key="good_examples/ds-1/f.pdf",
            product_name="CLI Name",
            manufacturer="CLI Mfg",
            product_family="CLI Family",
            pages="1,2",
            stage="dev",
            bucket="bucket",
        )

        meta = _build_metadata(args)
        assert meta["product_name"] == "DB Name"
        assert meta["manufacturer"] == "DB Mfg"
        # product_family is None in DB, so CLI fallback kicks in
        assert meta["product_family"] == "CLI Family"
        assert meta["pages"] == [5]


# ---------------------------------------------------------------------------
# _assign_unique_ids — deduplication by spec suffix
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAssignUniqueIds:
    def test_unique_part_numbers_unchanged(self):
        from cli.agent import _assign_unique_ids
        from unittest.mock import MagicMock

        m1 = MagicMock(part_number="A", product_name="Motor", manufacturer="Mfg")
        m2 = MagicMock(part_number="B", product_name="Motor", manufacturer="Mfg")

        result = _assign_unique_ids([(m1, "mfg:a"), (m2, "mfg:b")])
        assert len(result) == 2
        assert result[0].product_id != result[1].product_id

    def test_same_name_differentiated_by_specs(self):
        from cli.agent import _assign_unique_ids
        from unittest.mock import MagicMock

        m1 = MagicMock(
            part_number=None,
            product_name="Motor",
            manufacturer="Mfg",
            rated_speed="3000;rpm",
            rated_voltage="24;V",
            rated_torque=None,
            rated_power=None,
            rated_current=None,
            dimensions=None,
        )
        m2 = MagicMock(
            part_number=None,
            product_name="Motor",
            manufacturer="Mfg",
            rated_speed="5000;rpm",
            rated_voltage="24;V",
            rated_torque=None,
            rated_power=None,
            rated_current=None,
            dimensions=None,
        )

        result = _assign_unique_ids([(m1, "mfg:motor"), (m2, "mfg:motor")])
        assert len(result) == 2
        assert result[0].product_id != result[1].product_id

    def test_truly_identical_products_deduped(self):
        from cli.agent import _assign_unique_ids
        from unittest.mock import MagicMock

        m1 = MagicMock(
            part_number=None,
            product_name="Motor",
            manufacturer="Mfg",
            rated_speed="3000;rpm",
            rated_voltage="24;V",
            rated_torque=None,
            rated_power=None,
            rated_current=None,
            dimensions=None,
        )
        m2 = MagicMock(
            part_number=None,
            product_name="Motor",
            manufacturer="Mfg",
            rated_speed="3000;rpm",
            rated_voltage="24;V",
            rated_torque=None,
            rated_power=None,
            rated_current=None,
            dimensions=None,
        )

        result = _assign_unique_ids([(m1, "mfg:motor"), (m2, "mfg:motor")])
        assert len(result) == 1

    def test_no_specs_at_all_deduped(self):
        from cli.agent import _assign_unique_ids
        from unittest.mock import MagicMock

        m1 = MagicMock(
            part_number=None,
            product_name="Motor",
            manufacturer="Mfg",
            rated_speed=None,
            rated_voltage=None,
            rated_torque=None,
            rated_power=None,
            rated_current=None,
            dimensions=None,
        )
        m2 = MagicMock(
            part_number=None,
            product_name="Motor",
            manufacturer="Mfg",
            rated_speed=None,
            rated_voltage=None,
            rated_torque=None,
            rated_power=None,
            rated_current=None,
            dimensions=None,
        )

        result = _assign_unique_ids([(m1, "mfg:motor"), (m2, "mfg:motor")])
        assert len(result) == 1
