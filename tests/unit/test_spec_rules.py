"""Tests for spec-level validation rules."""

import pytest

from datasheetminer.spec_rules import (
    FIELD_RULES,
    _parse_compact,
    validate_product,
    validate_products,
)
from datasheetminer.models.drive import Drive  # noqa: F401 — used in _drive()
from datasheetminer.models.motor import Motor


MFG = "TestMfg"


def _motor(**overrides) -> Motor:
    """Build a Motor with sensible defaults, applying overrides."""
    defaults = {
        "product_name": "Test Motor",
        "manufacturer": MFG,
        "product_type": "motor",
        "part_number": "TST-001",
        "rated_voltage": "200-240;Vrms",
        "rated_speed": "6000;rpm",
        "rated_current": "5.0;A",
        "rated_torque": "1.2;Nm",
        "rated_power": "750;W",
    }
    defaults.update(overrides)
    return Motor(**defaults)


# ---------------------------------------------------------------------------
# _parse_compact
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseCompact:
    def test_single_value(self):
        assert _parse_compact("480;Vac") == ([480.0], "Vac")

    def test_range_value(self):
        assert _parse_compact("200-240;Vrms") == ([200.0, 240.0], "Vrms")

    def test_negative_range(self):
        result = _parse_compact("-20-40;°C")
        assert result == ([-20.0, 40.0], "°C")

    def test_none_input(self):
        assert _parse_compact(None) is None

    def test_no_semicolon(self):
        assert _parse_compact("480") is None

    def test_empty_unit(self):
        assert _parse_compact("480;") is None

    def test_non_numeric(self):
        assert _parse_compact("TBD;V") is None


# ---------------------------------------------------------------------------
# Unit mismatch — the core Kollmorgen bug
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUnitMismatch:
    """Wrong-family unit rejection moved to the typed Pydantic aliases
    in ``datasheetminer.models.common``. The field is nulled at
    construction time before ``validate_product`` ever sees it — no
    violation is emitted because there's nothing left to flag.
    """

    def test_rpm_in_voltage_field_is_rejected_at_model(self):
        """rpm on rated_voltage → field becomes None at validation time."""
        m = _motor(rated_voltage="4500;rpm")
        assert m.rated_voltage is None

    def test_voltage_in_speed_field_is_rejected_at_model(self):
        m = _motor(rated_speed="480;Vac")
        assert m.rated_speed is None

    def test_valid_units_pass(self):
        m = _motor(rated_voltage="200-240;Vrms", rated_speed="6000;rpm")
        violations = validate_product(m)
        assert m.rated_voltage == "200-240;Vrms"
        assert m.rated_speed == "6000;rpm"
        assert not violations


# ---------------------------------------------------------------------------
# Implausible magnitude
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestImplausibleRange:
    def test_voltage_too_high(self):
        m = _motor(rated_voltage="5000;V")
        violations = validate_product(m)
        assert m.rated_voltage is None
        assert any("outside plausible" in v for v in violations)

    def test_voltage_within_range(self):
        m = _motor(rated_voltage="480;Vac")
        violations = validate_product(m)
        assert m.rated_voltage is not None
        assert not [v for v in violations if "rated_voltage" in v]

    def test_range_max_exceeds_limit(self):
        m = _motor(rated_voltage="200-2000;V")
        validate_product(m)
        assert m.rated_voltage is None

    def test_low_voltage_valid(self):
        m = _motor(rated_voltage="12;Vdc")
        validate_product(m)
        assert m.rated_voltage is not None

    def test_zero_voltage_rejected(self):
        m = _motor(rated_voltage="0;V")
        validate_product(m)
        assert m.rated_voltage is None


# ---------------------------------------------------------------------------
# Cross-field duplication
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCrossFieldDuplication:
    def test_voltage_equals_speed_is_rejected(self):
        """If rated_voltage and rated_speed are identical, voltage is nulled.

        Unit-family enforcement now runs at the model validator, so
        rated_voltage="6000;rpm" is nulled at construction before
        validate_product even sees it. Cross-field duplication check
        runs after but has nothing to flag.
        """
        m = _motor(rated_voltage="6000;rpm", rated_speed="6000;rpm")
        validate_product(m)
        assert m.rated_voltage is None
        assert m.rated_speed is not None  # speed is preserved

    def test_different_values_not_flagged(self):
        m = _motor(rated_voltage="240;Vac", rated_speed="6000;rpm")
        violations = validate_product(m)
        assert m.rated_voltage is not None
        assert m.rated_speed is not None
        # No duplication violations (unit mismatch may fire first)
        assert not [v for v in violations if "identical" in v]


# ---------------------------------------------------------------------------
# Batch validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateProducts:
    def test_returns_same_list(self):
        products = [_motor(), _motor(part_number="TST-002")]
        result = validate_products(products)
        assert result is products

    def test_mixed_good_and_bad(self):
        good = _motor(part_number="GOOD")
        bad = _motor(part_number="BAD", rated_voltage="4500;rpm")
        validate_products([good, bad])
        assert good.rated_voltage is not None
        assert bad.rated_voltage is None

    def test_empty_list(self):
        result = validate_products([])
        assert result == []


# ---------------------------------------------------------------------------
# None / missing fields are skipped
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNoneFieldsSkipped:
    def test_none_rated_voltage_no_error(self):
        m = _motor(rated_voltage=None)
        violations = validate_product(m)
        assert not [v for v in violations if "rated_voltage" in v]

    def test_all_none_specs_no_error(self):
        m = Motor(
            product_name="Bare Motor",
            manufacturer=MFG,
            product_type="motor",
        )
        violations = validate_product(m)
        assert not violations


# ---------------------------------------------------------------------------
# Ensures every rule in FIELD_RULES is actually testable
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFieldRuleCoverage:
    def test_all_rules_have_valid_bounds(self):
        # Unit-family enforcement moved to the typed Pydantic aliases, so
        # the rule tuple is now (min, max) without the unit set.
        for name, (lo, hi) in FIELD_RULES.items():
            assert lo <= hi, f"{name}: min ({lo}) > max ({hi})"


# ---------------------------------------------------------------------------
# Identity validation — unidentifiable products from non-product PDFs
# ---------------------------------------------------------------------------


def _drive(**overrides) -> Drive:
    """Build a Drive with sensible defaults, applying overrides."""
    defaults = {
        "product_name": "Test Drive",
        "manufacturer": MFG,
        "product_type": "drive",
        "part_number": "DRV-001",
        "input_voltage": "380-480;V",
        "rated_current": "10;A",
        "rated_power": "5000;W",
    }
    defaults.update(overrides)
    return Drive(**defaults)


@pytest.mark.unit
class TestIdentityValidation:
    """Products with no part_number + generic manufacturer are rejected."""

    def test_no_part_number_unknown_manufacturer_rejected(self):
        """The exact garbage drive case: 'VFD Specifications' by 'Unknown'."""
        d = _drive(
            product_name="VFD Specifications",
            manufacturer="Unknown",
            part_number=None,
        )
        violations = validate_product(d)
        assert any("Unidentifiable" in v for v in violations)
        # All spec fields should be nulled
        assert d.input_voltage is None
        assert d.rated_current is None
        assert d.rated_power is None

    def test_no_part_number_empty_manufacturer_rejected(self):
        d = _drive(
            product_name="Air-Cooled VFD",
            manufacturer="",
            part_number=None,
        )
        violations = validate_product(d)
        assert any("Unidentifiable" in v for v in violations)

    def test_no_part_number_real_manufacturer_passes(self):
        """Missing part_number alone is not enough to reject — manufacturer
        identity still lets us know what the product is."""
        d = _drive(
            product_name="P2 Series VFD",
            manufacturer="Bardac",
            part_number=None,
        )
        violations = validate_product(d)
        assert not any("Unidentifiable" in v for v in violations)
        assert d.input_voltage is not None

    def test_generic_manufacturer_with_part_number_passes(self):
        """If there's a real part number, keep the product even with
        'Unknown' manufacturer — the part number makes it searchable."""
        m = _motor(manufacturer="Unknown", part_number="EMS-095Q6011")
        violations = validate_product(m)
        assert not any("Unidentifiable" in v for v in violations)
        assert m.rated_voltage is not None

    def test_real_product_passes(self):
        d = _drive(manufacturer="Bardac", part_number="P2-74250-3HF4N-T")
        violations = validate_product(d)
        assert not any("Unidentifiable" in v for v in violations)

    def test_all_generic_manufacturer_variants_caught(self):
        """Every value in GENERIC_MANUFACTURERS triggers rejection
        when combined with no part_number."""
        from datasheetminer.spec_rules import GENERIC_MANUFACTURERS

        for gm in GENERIC_MANUFACTURERS:
            d = _drive(manufacturer=gm, part_number=None)
            violations = validate_product(d)
            assert any("Unidentifiable" in v for v in violations), (
                f"Generic manufacturer '{gm}' was not caught"
            )

    def test_case_insensitive(self):
        d = _drive(manufacturer="UNKNOWN", part_number=None)
        violations = validate_product(d)
        assert any("Unidentifiable" in v for v in violations)

    def test_whitespace_part_number_treated_as_missing(self):
        d = _drive(manufacturer="Unknown", part_number="  ")
        violations = validate_product(d)
        assert any("Unidentifiable" in v for v in violations)
