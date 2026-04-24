"""Boundary tests for datasheetminer/quality.py.

Existing `test_quality.py` covers the happy paths. This file focuses on the
cliffs: exactly-at-threshold records, all-None records, records where the
part_number string is itself a placeholder.
"""

from __future__ import annotations

import pytest

from datasheetminer.models.motor import Motor
from datasheetminer.quality import (
    DEFAULT_MIN_QUALITY,
    filter_products,
    score_product,
    spec_fields_for_model,
)


# Motor ValueUnit fields paired with a unit in their family so the typed
# Pydantic aliases (Voltage / Current / Power / ...) accept the value.
# "1;W" was fine when every field was untyped ValueUnit; after the
# per-quantity narrowing a mismatched unit gets rejected and the field
# stays None — so each entry here must be unit-correct.
_VALUE_UNIT_FIELDS: list[tuple[str, str]] = [
    ("rated_speed", "1;rpm"),
    ("max_speed", "1;rpm"),
    ("rated_torque", "1;Nm"),
    ("peak_torque", "1;Nm"),
    ("rated_power", "1;W"),
    ("rated_current", "1;A"),
    ("peak_current", "1;A"),
    ("voltage_constant", "1;V/krpm"),
    ("torque_constant", "1;Nm/A"),
    ("resistance", "1;Ω"),
    ("inductance", "1;mH"),
    ("rotor_inertia", "1;kg·cm²"),
    ("weight", "1;kg"),
    ("msrp", "1;USD"),
    ("warranty", "1;years"),
]


def _motor(**specs) -> Motor:
    """Build a Motor with just the supplied spec fields populated."""
    return Motor(manufacturer="Acme", product_name="test", **specs)


def _fill_n_spec_fields(n: int) -> dict:
    """Return kwargs that populate exactly `n` ValueUnit spec fields."""
    return {name: value for name, value in _VALUE_UNIT_FIELDS[:n]}


class TestBoundary:
    def test_at_or_above_threshold_passes(self) -> None:
        """A record at or above min_quality must PASS (score >= threshold)."""
        total = len(spec_fields_for_model(Motor))
        # Fill enough fields to comfortably exceed the threshold.
        target = min(len(_VALUE_UNIT_FIELDS), int(total * DEFAULT_MIN_QUALITY) + 2)
        m = _motor(**_fill_n_spec_fields(target))
        score, *_ = score_product(m)
        assert score >= DEFAULT_MIN_QUALITY
        passed, rejected = filter_products([m])
        assert len(passed) == 1 and len(rejected) == 0

    def test_just_below_threshold_rejects(self) -> None:
        total = len(spec_fields_for_model(Motor))
        # Fill one field less than threshold demands, floor at 0.
        target = max(0, int(total * DEFAULT_MIN_QUALITY) - 1)
        m = _motor(**_fill_n_spec_fields(target))
        score, *_ = score_product(m)
        assert score < DEFAULT_MIN_QUALITY
        passed, rejected = filter_products([m])
        assert len(rejected) == 1

    def test_all_none_rejects_unless_threshold_is_zero(self) -> None:
        m = _motor()
        passed, rejected = filter_products([m])
        # DEFAULT_MIN_QUALITY > 0 today, so this must reject.
        assert DEFAULT_MIN_QUALITY > 0
        assert len(rejected) == 1

    def test_custom_threshold_zero_passes_everything(self) -> None:
        m = _motor()
        passed, rejected = filter_products([m], min_quality=0.0)
        assert len(passed) == 1
        assert len(rejected) == 0


class TestScore:
    def test_score_returns_score_filled_total_missing(self) -> None:
        m = _motor(rated_power="100;W")
        score, filled, total, missing = score_product(m)
        assert 0.0 < score < 1.0
        assert filled >= 1
        assert total == len(spec_fields_for_model(Motor))
        assert "rated_power" not in missing

    def test_meta_fields_do_not_count_toward_score(self) -> None:
        """manufacturer + product_name are set on every motor; if they counted,
        an all-None spec record would score >0. Verify they don't."""
        m = _motor()
        score, filled, total, missing = score_product(m)
        assert filled == 0


class TestPlaceholderPartNumbers:
    """Placeholder strings in `part_number` are now coerced to None at the
    ProductBase validator layer, so quality scoring sees them as missing.
    This is the fix for the latent bug documented in todo/fundamental-flaws.md."""

    @pytest.mark.parametrize("placeholder", ["N/A", "TBD", "-", "None", "null"])
    def test_placeholder_part_number_is_coerced_to_none(self, placeholder: str) -> None:
        m = _motor(part_number=placeholder)
        assert m.part_number is None

    @pytest.mark.parametrize("placeholder", ["N/A", "TBD", "-", "None", "null"])
    def test_placeholder_part_number_does_not_affect_quality(
        self, placeholder: str
    ) -> None:
        m = _motor(part_number=placeholder)
        score, filled, total, missing = score_product(m)
        # Placeholder part_number coerced to None → part_number is a meta-field
        # anyway, so filled count from specs alone is 0.
        assert filled == 0


class TestFilterProducts:
    def test_empty_list_returns_empty_pairs(self) -> None:
        passed, rejected = filter_products([])
        assert passed == []
        assert rejected == []

    def test_mixed_quality_partitions_correctly(self) -> None:
        high = _motor(**_fill_n_spec_fields(len(_VALUE_UNIT_FIELDS)))
        low = _motor()
        passed, rejected = filter_products([high, low])
        assert high in passed
        assert low in rejected
