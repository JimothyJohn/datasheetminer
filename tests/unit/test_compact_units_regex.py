"""Direct tests for DynamoDBClient._parse_compact_units.

This is the boundary between stored strings and typed values. Bugs here
silently corrupt every read. Existing coverage sits below 35% on dynamo.py;
this file hits the regex + Decimal conversion path exhaustively.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from specodex.db.dynamo import DynamoDBClient


@pytest.fixture
def parse():
    """Bind `_parse_compact_units` without constructing a real boto3 client."""
    client = DynamoDBClient.__new__(DynamoDBClient)
    return client._parse_compact_units


class TestSingleValue:
    def test_positive_int(self, parse) -> None:
        assert parse("20;C") == {"value": Decimal("20"), "unit": "C"}

    def test_negative_int(self, parse) -> None:
        assert parse("-20;C") == {"value": Decimal("-20"), "unit": "C"}

    def test_decimal(self, parse) -> None:
        assert parse("1.25;V") == {"value": Decimal("1.25"), "unit": "V"}

    def test_negative_decimal(self, parse) -> None:
        assert parse("-1.25;V") == {"value": Decimal("-1.25"), "unit": "V"}

    def test_unit_with_slash(self, parse) -> None:
        assert parse("10;m/s") == {"value": Decimal("10"), "unit": "m/s"}

    def test_unit_empty_allowed_by_regex(self, parse) -> None:
        """Regex allows empty unit via `.*`. Document behavior."""
        assert parse("10;") == {"value": Decimal("10"), "unit": ""}


class TestRange:
    def test_positive_range(self, parse) -> None:
        out = parse("20-40;C")
        assert out == {"min": Decimal("20"), "max": Decimal("40"), "unit": "C"}

    def test_negative_to_positive(self, parse) -> None:
        out = parse("-20-40;C")
        assert out == {"min": Decimal("-20"), "max": Decimal("40"), "unit": "C"}

    def test_negative_to_negative(self, parse) -> None:
        out = parse("-20--40;C")
        assert out == {"min": Decimal("-20"), "max": Decimal("-40"), "unit": "C"}

    def test_decimal_range(self, parse) -> None:
        out = parse("0.5-1.5;A")
        assert out == {"min": Decimal("0.5"), "max": Decimal("1.5"), "unit": "A"}


class TestPathological:
    """Inputs the regex must refuse cleanly (fall back to original string)."""

    @pytest.mark.parametrize(
        "bad",
        [
            "abc;V",
            "2+;Years",
            "--5;V",
            "1.2.3;V",
            "1e3;V",
        ],
    )
    def test_malformed_returns_original(self, parse, bad: str) -> None:
        result = parse(bad)
        assert result == bad, f"expected passthrough for {bad!r}, got {result!r}"

    def test_multiple_semicolons_greedy_unit(self, parse) -> None:
        """Documented quirk: unit capture is greedy (`.*`), so extra semicolons
        get absorbed into the unit. This is current behavior; flagging it here
        means a regex tighten-up will fail this test loudly instead of silently
        breaking reads."""
        out = parse("1;2;3;V")
        assert out == {"value": Decimal("1"), "unit": "2;3;V"}

    def test_no_semicolon_returns_original(self, parse) -> None:
        assert parse("100 W") == "100 W"

    def test_empty_string_returns_original(self, parse) -> None:
        assert parse("") == ""


class TestRecursion:
    def test_dict_nested_values(self, parse) -> None:
        out = parse({"a": "20;C", "b": "raw", "c": 42})
        assert out == {"a": {"value": Decimal("20"), "unit": "C"}, "b": "raw", "c": 42}

    def test_list_of_compacts(self, parse) -> None:
        out = parse(["1;A", "2;A"])
        assert out == [
            {"value": Decimal("1"), "unit": "A"},
            {"value": Decimal("2"), "unit": "A"},
        ]

    def test_deeply_nested(self, parse) -> None:
        out = parse({"outer": {"inner": ["10;V"]}})
        assert out == {
            "outer": {"inner": [{"value": Decimal("10"), "unit": "V"}]},
        }

    def test_non_string_non_container_passthrough(self, parse) -> None:
        assert parse(42) == 42
        assert parse(None) is None
        assert parse(True) is True
