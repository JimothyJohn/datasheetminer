"""Tests for intake guard functions — validate PDFs before promotion."""

import pytest

from cli.intake import IntakeScanResult
from cli.intake_guards import (
    GuardVerdict,
    any_blocking,
    check_document_scope,
    check_extraction_feasibility,
    check_file_integrity,
    check_manufacturer_identity,
    check_spec_density_calibrated,
    run_guards,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Minimal valid PDF header (enough to pass magic byte check)
VALID_PDF_BYTES = b"%PDF-1.4 " + b"\x00" * 2000

# HTML error page (the RPX32 pattern) — padded above _MIN_PDF_SIZE so
# the HTML content check fires instead of the size check
HTML_REDIRECT = (
    b"<html><head><title>301 Moved Permanently</title></head><body></body></html>"
    + b"\n" * 1100
)


def _scan(*, valid: bool = True, **overrides) -> IntakeScanResult:
    defaults = {
        "is_valid_datasheet": valid,
        "has_table_of_contents": True,
        "has_specification_tables": True,
        "product_type": "motor",
        "manufacturer": "Acme Corp",
        "product_name": "X100",
        "product_family": "X-Series",
        "category": "brushless dc motor",
        "spec_pages": [3, 4, 5],
        "spec_density": 0.7,
        "rejection_reason": None,
        "distinct_product_count": 5,
        "is_multi_category": False,
    }
    defaults.update(overrides)
    return IntakeScanResult(**defaults)


# ---------------------------------------------------------------------------
# Guard 1 — File integrity
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFileIntegrity:
    def test_valid_pdf_passes(self):
        v = check_file_integrity(VALID_PDF_BYTES)
        assert v.passed is True

    def test_html_error_page_blocked(self):
        v = check_file_integrity(HTML_REDIRECT)
        assert v.passed is False
        assert "HTML" in v.reason

    def test_empty_bytes_blocked(self):
        v = check_file_integrity(b"")
        assert v.passed is False
        assert "empty" in v.reason

    def test_tiny_file_blocked(self):
        v = check_file_integrity(b"%PDF-1.4 tiny")
        assert v.passed is False
        assert "too small" in v.reason

    def test_random_bytes_no_pdf_header(self):
        v = check_file_integrity(b"\x00\x01\x02" * 500)
        assert v.passed is False
        assert "magic bytes" in v.reason

    def test_html_doctype_blocked(self):
        html = b"<!DOCTYPE html><html><body>Not Found</body></html>" + b"\x00" * 1000
        v = check_file_integrity(html)
        assert v.passed is False
        assert "HTML" in v.reason

    def test_guard_name_set(self):
        v = check_file_integrity(VALID_PDF_BYTES)
        assert v.guard_name == "file_integrity"


# ---------------------------------------------------------------------------
# Guard 2 — Manufacturer identity
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestManufacturerIdentity:
    def test_real_manufacturer_passes(self):
        v = check_manufacturer_identity(_scan(manufacturer="Kollmorgen"))
        assert v.passed is True

    def test_unknown_blocked(self):
        v = check_manufacturer_identity(_scan(manufacturer="Unknown"))
        assert v.passed is False

    def test_none_blocked(self):
        v = check_manufacturer_identity(_scan(manufacturer=None))
        assert v.passed is False

    def test_empty_string_blocked(self):
        v = check_manufacturer_identity(_scan(manufacturer=""))
        assert v.passed is False

    def test_case_insensitive(self):
        v = check_manufacturer_identity(_scan(manufacturer="UNKNOWN"))
        assert v.passed is False

    def test_na_blocked(self):
        v = check_manufacturer_identity(_scan(manufacturer="N/A"))
        assert v.passed is False

    def test_whitespace_only_blocked(self):
        v = check_manufacturer_identity(_scan(manufacturer="   "))
        assert v.passed is False


# ---------------------------------------------------------------------------
# Guard 3 — Document scope
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDocumentScope:
    def test_single_category_passes(self):
        v = check_document_scope(_scan(is_multi_category=False))
        assert v.passed is True

    def test_multi_category_blocked(self):
        v = check_document_scope(_scan(is_multi_category=True))
        assert v.passed is False
        assert "multi-category" in v.reason

    def test_defaults_to_false(self):
        """Missing field treated as single-category."""
        scan = IntakeScanResult(
            is_valid_datasheet=True,
            has_table_of_contents=True,
            has_specification_tables=True,
        )
        v = check_document_scope(scan)
        assert v.passed is True


# ---------------------------------------------------------------------------
# Guard 4 — Extraction feasibility
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractionFeasibility:
    def test_all_signals_present_passes(self):
        v = check_extraction_feasibility(_scan())
        assert v.passed is True

    def test_only_manufacturer_present_blocked(self):
        v = check_extraction_feasibility(
            _scan(
                manufacturer="Acme",
                product_name=None,
                spec_pages=None,
                spec_density=0.0,
            )
        )
        assert v.passed is False
        assert "1/4" in v.reason

    def test_nothing_present_blocked(self):
        v = check_extraction_feasibility(
            _scan(
                manufacturer=None,
                product_name=None,
                spec_pages=None,
                spec_density=0.0,
            )
        )
        assert v.passed is False
        assert "0/4" in v.reason

    def test_two_signals_passes(self):
        v = check_extraction_feasibility(
            _scan(
                manufacturer="Acme",
                product_name="Motor X",
                spec_pages=None,
                spec_density=0.0,
            )
        )
        assert v.passed is True

    def test_density_alone_counts(self):
        v = check_extraction_feasibility(
            _scan(
                manufacturer=None,
                product_name=None,
                spec_pages=[1, 2],
                spec_density=0.5,
            )
        )
        assert v.passed is True


# ---------------------------------------------------------------------------
# Guard 5 — Calibrated spec density
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSpecDensityCalibrated:
    def test_motor_above_threshold_passes(self):
        v = check_spec_density_calibrated(_scan(product_type="motor", spec_density=0.3))
        assert v.passed is True

    def test_motor_below_threshold_blocked(self):
        v = check_spec_density_calibrated(
            _scan(product_type="motor", spec_density=0.15)
        )
        assert v.passed is False

    def test_motor_at_threshold_passes(self):
        v = check_spec_density_calibrated(
            _scan(product_type="motor", spec_density=0.25)
        )
        assert v.passed is True

    def test_gearhead_lower_threshold(self):
        v = check_spec_density_calibrated(
            _scan(product_type="gearhead", spec_density=0.20)
        )
        assert v.passed is True

    def test_unknown_type_uses_default(self):
        v = check_spec_density_calibrated(
            _scan(product_type="widget", spec_density=0.20)
        )
        assert v.passed is True

    def test_zero_density_blocked(self):
        v = check_spec_density_calibrated(_scan(spec_density=0.0))
        assert v.passed is False

    def test_none_density_blocked(self):
        v = check_spec_density_calibrated(_scan(spec_density=None))
        assert v.passed is False


# ---------------------------------------------------------------------------
# Orchestrator — run_guards
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRunGuards:
    def test_all_pass(self):
        verdicts = run_guards(_scan())
        assert all(v.passed for v in verdicts)
        assert len(verdicts) == 4  # 4 post-scan guards

    def test_collects_all_verdicts(self):
        """Even with failures, all guards run and return verdicts."""
        scan = _scan(manufacturer="Unknown", spec_density=0.01)
        verdicts = run_guards(scan)
        assert len(verdicts) == 4
        failed = [v for v in verdicts if not v.passed]
        assert len(failed) >= 2  # manufacturer + density at minimum

    def test_guard_names_unique(self):
        verdicts = run_guards(_scan())
        names = [v.guard_name for v in verdicts]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# any_blocking
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAnyBlocking:
    def test_no_blockers_returns_none(self):
        verdicts = [
            GuardVerdict(passed=True, guard_name="a"),
            GuardVerdict(passed=True, guard_name="b"),
        ]
        assert any_blocking(verdicts) is None

    def test_warn_only_returns_none(self):
        verdicts = [
            GuardVerdict(passed=False, guard_name="a", reason="meh", severity="warn"),
        ]
        assert any_blocking(verdicts) is None

    def test_returns_first_blocker(self):
        verdicts = [
            GuardVerdict(passed=True, guard_name="a"),
            GuardVerdict(passed=False, guard_name="b", reason="bad"),
            GuardVerdict(passed=False, guard_name="c", reason="also bad"),
        ]
        result = any_blocking(verdicts)
        assert result is not None
        assert result.guard_name == "b"

    def test_empty_returns_none(self):
        assert any_blocking([]) is None
