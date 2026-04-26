"""Property-based tests for the ValueUnit / MinMaxUnit validation stack.

Targets the three-stage pipeline in `specodex/models/common.py`:
    BeforeValidator handle_value_unit_input
    AfterValidator validate_value_unit_str
    AfterValidator _normalize_compact_str  (from units.normalize_value_unit)

and the symmetric stack for MinMaxUnit. Rationale: these validators are the
single boundary between LLM-emitted JSON and the canonical `"value;unit"`
strings we store in DynamoDB. Hand-rolled examples catch ~5 cases; a property
test covers the whole string space at a cost of a few seconds.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from specodex.db.dynamo import DynamoDBClient
from specodex.models.common import (
    handle_min_max_unit_input,
    handle_value_unit_input,
    validate_min_max_unit_str,
    validate_value_unit_str,
)
from specodex.units import normalize_value_unit


_ASCII_UNIT = st.text(
    alphabet=st.characters(min_codepoint=65, max_codepoint=90),
    min_size=1,
    max_size=4,
)
_FINITE_FLOATS = st.floats(
    allow_nan=False, allow_infinity=False, min_value=-1e9, max_value=1e9
).filter(lambda v: abs(v) > 1e-9 or v == 0.0)
_FINITE_INTS = st.integers(min_value=-10_000_000, max_value=10_000_000)


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(value=_FINITE_INTS, unit=_ASCII_UNIT)
def test_int_dict_input_produces_parseable_compact(value: int, unit: str) -> None:
    result = handle_value_unit_input({"value": value, "unit": unit})
    assert isinstance(result, str)
    validated = validate_value_unit_str(result)
    assert validated.startswith(f"{value};") or validated == f"{value};{unit}"


@settings(max_examples=200)
@given(
    prefix=st.sampled_from(["", "+", "~", ">", "<", "+~", "~>"]),
    value=_FINITE_INTS,
    unit=_ASCII_UNIT,
)
def test_prefixed_value_is_stripped(prefix: str, value: int, unit: str) -> None:
    """Any leading +, ~, >, < must be stripped before the semicolon."""
    result = handle_value_unit_input({"value": f"{prefix}{value}", "unit": unit})
    assert isinstance(result, str)
    left, _, right = result.partition(";")
    assert not left.startswith(("+", "~", ">", "<"))
    assert right == unit


@settings(max_examples=200)
@given(lo=_FINITE_INTS, hi=_FINITE_INTS, unit=_ASCII_UNIT)
def test_minmax_dict_roundtrips_through_parser(lo: int, hi: int, unit: str) -> None:
    """dict{min,max,unit} -> compact -> parsed back preserves the numbers + unit."""
    compact = handle_min_max_unit_input({"min": lo, "max": hi, "unit": unit})
    validated = validate_min_max_unit_str(compact)
    parsed = DynamoDBClient._parse_compact_units(
        DynamoDBClient.__new__(DynamoDBClient), validated
    )
    assert isinstance(parsed, dict)
    assert parsed["unit"] == unit
    assert float(parsed["min"]) == float(lo)
    assert float(parsed["max"]) == float(hi)


@settings(max_examples=150)
@given(s=st.text(min_size=0, max_size=40))
def test_value_unit_validator_never_crashes_on_strings(s: str) -> None:
    """validate_value_unit_str must either pass or raise ValueError — never anything else."""
    try:
        validate_value_unit_str(s)
    except ValueError:
        pass
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"validator raised non-ValueError on {s!r}: {e!r}")


class TestRogueInputs:
    """Hand-picked cases that property tests might miss or that need exact behavior."""

    @pytest.mark.parametrize("bad", ["", ";", "1;", ";V", "1;2;3", "  ;  ", "1;2;V"])
    def test_malformed_strings_raise(self, bad: str) -> None:
        # "1;2;V" is now rejected — writer-side invariant against the
        # greedy-unit regex bug. See todo/fundamental-flaws.md (flaw #1).
        with pytest.raises(ValueError):
            validate_value_unit_str(bad)

    @pytest.mark.parametrize("ok", ["0;V", "-0;V", "1e3;W", "inf;W", "nan;W"])
    def test_numeric_edge_values_accepted_or_rejected_cleanly(self, ok: str) -> None:
        # Whatever the policy, validator must not crash for common LLM outputs.
        try:
            validate_value_unit_str(ok)
        except ValueError:
            pass

    def test_dict_missing_unit_passes_through(self) -> None:
        """Without a unit, the BeforeValidator cannot canonicalize — leaves dict alone."""
        assert handle_value_unit_input({"value": 100}) == {"value": 100}

    def test_dict_with_none_values_passes_through(self) -> None:
        """Explicit Nones must not coerce to the literal string "None"."""
        result = handle_value_unit_input({"value": None, "unit": None})
        assert result == {"value": None, "unit": None}

    def test_nested_dict_value_not_coerced_silently(self) -> None:
        """If the LLM nests a dict as a value, we should not produce "{'x':1};W"."""
        result = handle_value_unit_input({"value": {"x": 1}, "unit": "W"})
        # Document current behavior: str(dict) ends up on the left. That's ugly but
        # not a crash; if we ever tighten this, flip the assertion.
        assert result.endswith(";W")

    def test_list_value_not_coerced_to_multiple_records(self) -> None:
        result = handle_value_unit_input({"value": [1, 2], "unit": "W"})
        assert result.endswith(";W")

    def test_bool_value_handled_deterministically(self) -> None:
        # bool is a subclass of int in Python. "True;V" is a concrete regression.
        result = handle_value_unit_input({"value": True, "unit": "V"})
        assert ";" in result
        assert result.endswith(";V")

    def test_whitespace_value(self) -> None:
        with pytest.raises(ValueError):
            validate_value_unit_str("   ;V")

    def test_whitespace_unit(self) -> None:
        """Unit ' ' is non-empty by .split and passes — document this."""
        # Not ideal but not a crash. If tightened, flip assertion.
        result = validate_value_unit_str("100; ")
        assert result == "100; "

    def test_unicode_digit(self) -> None:
        """U+FF11 is a full-width 1. Validator should not crash."""
        try:
            validate_value_unit_str("\uff11;V")
        except ValueError:
            pass


class TestIdempotenceOnNormalize:
    """normalize_value_unit(normalize_value_unit(x)) == normalize_value_unit(x)."""

    @pytest.mark.parametrize(
        "compact",
        [
            "100;W",
            "100;kW",
            "100;mW",
            "100;hp",
            "100;HP",
            "100;Nm",
            "100;mNm",
            "100;oz-in",
            "100;A",
            "100;mA",
            "-20-40;C",
            "10-50;V",
            "100;Ω",
            "100;ohm",
            "100;ohms",
            "100;°F",
        ],
    )
    def test_normalize_is_idempotent(self, compact: str) -> None:
        once = normalize_value_unit(compact)
        twice = normalize_value_unit(once)
        assert once == twice

    def test_unknown_unit_passes_through_unchanged(self) -> None:
        assert normalize_value_unit("100;floopwatt") == "100;floopwatt"

    def test_no_semicolon_passes_through_unchanged(self) -> None:
        assert normalize_value_unit("100 W") == "100 W"
