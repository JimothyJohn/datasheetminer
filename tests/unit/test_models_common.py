"""
Extended tests for models/common.py validators.
Covers uncovered branches in handle_value_unit_input and handle_min_max_unit_input.
"""

import pytest
from datasheetminer.models.common import (
    handle_value_unit_input,
    handle_min_max_unit_input,
    validate_value_unit_str,
    validate_min_max_unit_str,
    _normalize_compact_str,
)


class TestHandleValueUnitInput:
    """Covers all branches of handle_value_unit_input."""

    def test_dict_with_value_and_unit(self):
        assert handle_value_unit_input({"value": 100, "unit": "W"}) == "100;W"

    def test_dict_cleans_plus_signs(self):
        assert handle_value_unit_input({"value": "100+", "unit": "W"}) == "100;W"

    def test_dict_cleans_tilde(self):
        assert handle_value_unit_input({"value": "~50", "unit": "rpm"}) == "50;rpm"

    def test_dict_with_min_max_unit(self):
        result = handle_value_unit_input({"min": 10, "max": 50, "unit": "V"})
        assert result == "10-50;V"

    def test_dict_with_min_only(self):
        result = handle_value_unit_input({"min": 10, "unit": "V"})
        assert result == "10;V"

    def test_dict_with_max_only(self):
        result = handle_value_unit_input({"max": 50, "unit": "V"})
        assert result == "50;V"

    def test_space_separated_string(self):
        assert handle_value_unit_input("100 W") == "100;W"

    def test_space_separated_cleans_prefix(self):
        assert handle_value_unit_input(">100 W") == "100;W"

    def test_semicolon_string_passthrough(self):
        assert handle_value_unit_input("100;W") == "100;W"

    def test_semicolon_string_cleans_value(self):
        assert handle_value_unit_input("+100;W") == "100;W"

    def test_non_matching_passthrough(self):
        assert handle_value_unit_input(42) == 42

    def test_none_passthrough(self):
        assert handle_value_unit_input(None) is None

    def test_dict_without_unit(self):
        result = handle_value_unit_input({"value": 100})
        assert result == {"value": 100}

    def test_empty_dict(self):
        result = handle_value_unit_input({})
        assert result == {}


class TestHandleMinMaxUnitInput:
    """Covers all branches of handle_min_max_unit_input."""

    def test_dict_with_min_max_unit(self):
        assert (
            handle_min_max_unit_input({"min": 0, "max": 100, "unit": "C"}) == "0-100;C"
        )

    def test_dict_with_min_only(self):
        assert handle_min_max_unit_input({"min": -20, "unit": "C"}) == "-20;C"

    def test_dict_with_max_only(self):
        assert handle_min_max_unit_input({"max": 80, "unit": "C"}) == "80;C"

    def test_dict_with_value_unit(self):
        assert handle_min_max_unit_input({"value": 24, "unit": "V"}) == "24;V"

    def test_dict_without_unit(self):
        result = handle_min_max_unit_input({"min": 0, "max": 100})
        assert result == {"min": 0, "max": 100}

    def test_non_dict_passthrough(self):
        assert handle_min_max_unit_input("10-20;C") == "10-20;C"

    def test_none_passthrough(self):
        assert handle_min_max_unit_input(None) is None


class TestValidateValueUnitStr:
    def test_valid_format(self):
        assert validate_value_unit_str("100;W") == "100;W"

    def test_none_passthrough(self):
        assert validate_value_unit_str(None) is None

    def test_missing_semicolon_raises(self):
        with pytest.raises(ValueError, match="value;unit"):
            validate_value_unit_str("100W")

    def test_empty_value_raises(self):
        with pytest.raises(ValueError, match="value part cannot be empty"):
            validate_value_unit_str(";W")

    def test_empty_unit_raises(self):
        with pytest.raises(ValueError, match="unit cannot be empty"):
            validate_value_unit_str("100;")

    def test_non_numeric_value_allowed(self):
        """LLM sometimes outputs things like '2+;Years'."""
        assert validate_value_unit_str("2+;Years") == "2+;Years"


class TestValidateMinMaxUnitStr:
    def test_valid_range(self):
        assert validate_min_max_unit_str("10-50;V") == "10-50;V"

    def test_none_passthrough(self):
        assert validate_min_max_unit_str(None) is None

    def test_missing_semicolon_raises(self):
        with pytest.raises(ValueError, match="range;unit"):
            validate_min_max_unit_str("10-50V")

    def test_empty_range_raises(self):
        with pytest.raises(ValueError, match="range part cannot be empty"):
            validate_min_max_unit_str(";V")

    def test_empty_unit_raises(self):
        with pytest.raises(ValueError, match="unit cannot be empty"):
            validate_min_max_unit_str("10-50;")

    def test_to_separator_replaced(self):
        """'10 to 50;V' should be normalized to '10-50;V'."""
        assert validate_min_max_unit_str("10 to 50;V") == "10-50;V"


class TestNormalizeCompactStr:
    def test_none_passthrough(self):
        assert _normalize_compact_str(None) is None
