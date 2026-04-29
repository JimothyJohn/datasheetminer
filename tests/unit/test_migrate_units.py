"""Unit tests for cli/migrate_units_to_dict.py — the Phase 5 backfill that
converts leaked compact-string ValueUnit/MinMaxUnit values to dicts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli.migrate_units_to_dict import (
    _looks_like_compact_unit,
    _try_parse_compact,
    _walk_and_fix,
    _write_review,
)


@pytest.mark.unit
class TestLooksLikeCompactUnit:
    @pytest.mark.parametrize(
        "value",
        [
            "100;W",
            "5.5e-5;kg·cm²",
            "0-50;°C",
            "-40-85;°C",
            "5.5e-5;kg.cm²",
            "100+;A",  # qualifier-prefixed
        ],
    )
    def test_positive_cases(self, value: str) -> None:
        assert _looks_like_compact_unit(value)

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "100W",
            "100",
            ";W",
            "100;",
            "Power: 100W; Speed: 3000rpm",  # multi-semicolon free text
            "abc;def;ghi",
        ],
    )
    def test_negative_cases(self, value: str) -> None:
        assert not _looks_like_compact_unit(value)

    def test_non_string(self) -> None:
        assert not _looks_like_compact_unit(123)  # type: ignore[arg-type]
        assert not _looks_like_compact_unit(None)  # type: ignore[arg-type]


@pytest.mark.unit
class TestTryParseCompact:
    def test_scientific_notation(self) -> None:
        # The whole reason this script exists: regex didn't handle "5.5e-5".
        result = _try_parse_compact("5.5e-5;kg·cm²")
        assert result is not None
        # Inertia normalises kg·cm² → kg·cm² (canonical), value preserved.
        assert result["value"] == pytest.approx(5.5e-5)
        assert result["unit"] == "kg·cm²"

    def test_simple_value_unit(self) -> None:
        result = _try_parse_compact("100;W")
        assert result == {"value": 100.0, "unit": "W"}

    def test_min_max_range(self) -> None:
        result = _try_parse_compact("0-50;°C")
        assert result == {"min": 0.0, "max": 50.0, "unit": "°C"}

    def test_negative_range(self) -> None:
        result = _try_parse_compact("-40-85;°C")
        assert result == {"min": -40.0, "max": 85.0, "unit": "°C"}

    def test_qualifier_prefix_value(self) -> None:
        # "+100" from earlier qualifier-tolerant inputs
        result = _try_parse_compact("+100;A")
        assert result is not None
        assert result["value"] == 100.0
        assert result["unit"] == "A"

    def test_returns_none_for_garbage(self) -> None:
        assert _try_parse_compact(";") is None
        assert _try_parse_compact("not a unit;") is None
        assert _try_parse_compact("approx;5") is None

    def test_tilde_as_range_separator(self) -> None:
        # `-40~+100` is the LLM's range form when emitting from JP/KR catalogs.
        result = _try_parse_compact("-40~+100;°C")
        assert result == {"min": -40.0, "max": 100.0, "unit": "°C"}

    def test_tilde_simple_range(self) -> None:
        result = _try_parse_compact("0~50;°C")
        assert result == {"min": 0.0, "max": 50.0, "unit": "°C"}

    def test_thousands_separator_comma(self) -> None:
        result = _try_parse_compact("30,000;hr")
        assert result is not None
        assert result["value"] == 30000.0
        assert result["unit"] == "hr"

    def test_le_prefix_max_only(self) -> None:
        result = _try_parse_compact("≤3;arcmin")
        assert result == {"min": None, "max": 3.0, "unit": "arcmin"}

    def test_lte_ascii_prefix(self) -> None:
        result = _try_parse_compact("<=65;dB")
        assert result == {"min": None, "max": 65.0, "unit": "dB"}

    def test_ge_prefix_min_only(self) -> None:
        result = _try_parse_compact("≥10;V")
        assert result == {"min": 10.0, "max": None, "unit": "V"}

    def test_gte_ascii_prefix(self) -> None:
        result = _try_parse_compact(">=100;Hz")
        assert result == {"min": 100.0, "max": None, "unit": "Hz"}

    def test_pm_left_alone(self) -> None:
        # ± is intentionally NOT auto-fixed — semantically ambiguous between
        # scalar tolerance (pose_repeatability: ±0.02 mm) and bilateral
        # range (working_range: ±360°). Stays in review for human triage.
        assert _try_parse_compact("±0.02;mm") is None
        assert _try_parse_compact("±360;°") is None


@pytest.mark.unit
class TestWalkAndFix:
    def test_top_level_string_replaced(self) -> None:
        item = {"PK": "PRODUCT#MOTOR", "rotor_inertia": "5.5e-5;kg·cm²"}
        fixes: list = []
        unparseable: list = []
        _walk_and_fix(item, fixes=fixes, unparseable=unparseable)
        assert isinstance(item["rotor_inertia"], dict)
        assert item["rotor_inertia"]["value"] == pytest.approx(5.5e-5)
        assert item["rotor_inertia"]["unit"] == "kg·cm²"
        assert len(fixes) == 1
        assert fixes[0][0] == ("rotor_inertia",)
        assert unparseable == []

    def test_nested_dict_string_replaced(self) -> None:
        item = {
            "PK": "PRODUCT#ROBOT_ARM",
            "controller": {"power_source": "100-240;VAC"},
        }
        fixes: list = []
        _walk_and_fix(item, fixes=fixes, unparseable=[])
        assert item["controller"]["power_source"] == {
            "min": 100.0,
            "max": 240.0,
            "unit": "VAC",
        }
        assert fixes[0][0] == ("controller", "power_source")

    def test_list_of_strings_replaced(self) -> None:
        item = {"speeds": ["100;rpm", "200;rpm"]}
        fixes: list = []
        _walk_and_fix(item, fixes=fixes, unparseable=[])
        assert item["speeds"][0] == {"value": 100.0, "unit": "rpm"}
        assert item["speeds"][1] == {"value": 200.0, "unit": "rpm"}
        assert len(fixes) == 2

    def test_already_dict_untouched(self) -> None:
        item = {"rated_power": {"value": 100.0, "unit": "W"}}
        original = dict(item["rated_power"])
        fixes: list = []
        _walk_and_fix(item, fixes=fixes, unparseable=[])
        assert item["rated_power"] == original
        assert fixes == []

    def test_unparseable_recorded_not_replaced(self) -> None:
        item = {"weird": "approx;5"}
        fixes: list = []
        unparseable: list = []
        _walk_and_fix(item, fixes=fixes, unparseable=unparseable)
        assert item["weird"] == "approx;5"
        assert fixes == []
        assert unparseable == [(("weird",), "approx;5")]

    def test_free_text_with_semicolons_skipped(self) -> None:
        # Multi-semicolon strings don't look like compact units, so they're
        # left alone — neither fixed nor flagged.
        item = {"description": "Power: 100W; Speed: 3000rpm; IP: 65"}
        fixes: list = []
        unparseable: list = []
        _walk_and_fix(item, fixes=fixes, unparseable=unparseable)
        assert item["description"] == "Power: 100W; Speed: 3000rpm; IP: 65"
        assert fixes == []
        assert unparseable == []

    def test_non_string_non_unit_values_preserved(self) -> None:
        item = {
            "product_id": "abc-123",
            "release_year": 2024,
            "active": True,
            "tags": ["motor", "servo"],
        }
        snapshot = {
            "product_id": "abc-123",
            "release_year": 2024,
            "active": True,
            "tags": ["motor", "servo"],
        }
        fixes: list = []
        _walk_and_fix(item, fixes=fixes, unparseable=[])
        assert item == snapshot
        assert fixes == []


@pytest.mark.unit
class TestWriteReview:
    def test_writes_markdown_with_entries(self, tmp_path: Path) -> None:
        review_path = tmp_path / "review.md"
        entries = [
            {
                "PK": "PRODUCT#MOTOR",
                "SK": "PRODUCT#abc",
                "product_name": "Motor X",
                "manufacturer": "ACME",
                "unparseable": [(("rotor_inertia",), "approx;5")],
            }
        ]
        _write_review(review_path, "dev", "products-dev", entries)
        text = review_path.read_text()
        assert "Units migration review" in text
        assert "products-dev" in text
        assert "PRODUCT#MOTOR" in text
        assert "Motor X" in text
        assert "rotor_inertia" in text
        assert "approx;5" in text
