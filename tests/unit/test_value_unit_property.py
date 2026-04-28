"""Property-based tests for the structured ValueUnit / MinMaxUnit pipeline.

The pipeline now lives entirely inside the Pydantic ``model_validator``s on
``ValueUnit`` / ``MinMaxUnit`` in ``specodex/models/common.py``. These tests
poke the boundary between LLM-emitted JSON and the canonical structured
form we persist.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from specodex.models.common import MinMaxUnit, ValueUnit
from specodex.units import _ALIAS_MAP


_ASCII_UNIT = st.text(
    alphabet=st.characters(min_codepoint=65, max_codepoint=90),
    min_size=1,
    max_size=4,
).filter(lambda u: u not in _ALIAS_MAP)
_FINITE_INTS = st.integers(min_value=-10_000_000, max_value=10_000_000)


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(value=_FINITE_INTS, unit=_ASCII_UNIT)
def test_int_dict_input_produces_structured(value: int, unit: str) -> None:
    """{value, unit} dicts must round-trip cleanly into ValueUnit instances."""
    v = ValueUnit.model_validate({"value": value, "unit": unit})
    assert v.value == float(value)
    assert v.unit == unit


@settings(max_examples=200)
@given(
    prefix=st.sampled_from(["", "+", "~", ">", "<", "+~", "~>"]),
    value=_FINITE_INTS,
    unit=_ASCII_UNIT,
)
def test_prefixed_value_is_stripped(prefix: str, value: int, unit: str) -> None:
    """Any leading +, ~, >, < must be stripped from the numeric input."""
    v = ValueUnit.model_validate({"value": f"{prefix}{value}", "unit": unit})
    assert v.value == float(value)
    assert v.unit == unit


@settings(max_examples=200)
@given(lo=_FINITE_INTS, hi=_FINITE_INTS, unit=_ASCII_UNIT)
def test_minmax_dict_roundtrips(lo: int, hi: int, unit: str) -> None:
    """{min, max, unit} dicts round-trip as MinMaxUnit instances."""
    v = MinMaxUnit.model_validate({"min": lo, "max": hi, "unit": unit})
    assert v.min == float(lo)
    assert v.max == float(hi)
    assert v.unit == unit


class TestRogueInputs:
    """Hand-picked cases that property tests might miss or that need exact behavior."""

    @pytest.mark.parametrize("bad", ["", "abc", "no semicolon"])
    def test_malformed_strings_rejected(self, bad: str) -> None:
        with pytest.raises(Exception):
            ValueUnit.model_validate(bad)

    def test_dict_missing_unit_rejected(self) -> None:
        """Without a unit, the validator can't construct a ValueUnit."""
        with pytest.raises(Exception):
            ValueUnit.model_validate({"value": 100})

    def test_dict_with_none_values_rejected(self) -> None:
        """Explicit Nones must not coerce to bogus values."""
        with pytest.raises(Exception):
            ValueUnit.model_validate({"value": None, "unit": None})

    def test_unit_only_dict_rejected(self) -> None:
        with pytest.raises(Exception):
            ValueUnit.model_validate({"unit": "V"})

    def test_bool_value_rejected(self) -> None:
        # bool is a subclass of int in Python but unintended as a numeric input.
        with pytest.raises(Exception):
            ValueUnit.model_validate({"value": True, "unit": "V"})


class TestIdempotenceOnNormalize:
    """Re-validating a ValueUnit instance is a no-op (already canonicalised)."""

    @pytest.mark.parametrize(
        "input_dict,expected_value,expected_unit",
        [
            ({"value": 100, "unit": "W"}, 100.0, "W"),
            ({"value": 100, "unit": "kW"}, 100000.0, "W"),
            ({"value": 100, "unit": "mW"}, 0.1, "W"),
            ({"value": 100, "unit": "Nm"}, 100.0, "Nm"),
            ({"value": 100, "unit": "mNm"}, 0.1, "Nm"),
            ({"value": 100, "unit": "A"}, 100.0, "A"),
            ({"value": 100, "unit": "mA"}, 0.1, "A"),
            ({"value": 100, "unit": "Ω"}, 100.0, "Ω"),
            ({"value": 100, "unit": "ohm"}, 100.0, "Ω"),
        ],
    )
    def test_normalize_is_idempotent(
        self, input_dict: dict, expected_value: float, expected_unit: str
    ) -> None:
        once = ValueUnit.model_validate(input_dict)
        # Re-validating the dict-form of the result should yield the same.
        twice = ValueUnit.model_validate(once.model_dump())
        assert once.value == twice.value == expected_value
        assert once.unit == twice.unit == expected_unit

    def test_unknown_unit_passes_through_unchanged(self) -> None:
        v = ValueUnit.model_validate({"value": 100, "unit": "floopwatt"})
        assert v.value == 100.0
        assert v.unit == "floopwatt"
