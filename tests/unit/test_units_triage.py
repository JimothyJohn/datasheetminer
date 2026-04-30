"""Tests for cli.units_triage — parsing + classification of UNITS review MD."""

from __future__ import annotations

from pathlib import Path

from cli import units_triage

SAMPLE = """\
# Units migration review — dev (products-dev)

_Generated 2026-04-28T23:35:05+00:00_

7 row(s) had string values resembling compact units that the new ValueUnit/MinMaxUnit coercer could not parse.

## `PRODUCT#ROBOT_ARM` / `PRODUCT#abc-123`

- **product_name:** Test Robot
- **manufacturer:** Acme

| Field path | Raw string |
|---|---|
| `pose_repeatability` | `±0.1;mm` |
| `joints.[0].working_range` | `±180°;null` |
| `weird_field` | `IP65;mm` |

## `PRODUCT#MOTOR` / `PRODUCT#def-456`

- **product_name:** Big Motor
- **manufacturer:** Beta

| Field path | Raw string |
|---|---|
| `voltage_range` | `100-240V;null` |
| `idle_current` | `0.5;unknown` |
| `gear_ratio` | `1/2;null` |
| `torque` | `unknown;Nm` |
"""


class TestParseReview:
    def test_extracts_section_metadata(self) -> None:
        rows = units_triage.parse_review(SAMPLE)
        # First section: pose_repeatability + working_range + weird_field = 3
        # Second section: voltage + idle + gear + torque = 4
        assert len(rows) == 7

    def test_first_row_carries_pk_sk_and_meta(self) -> None:
        rows = units_triage.parse_review(SAMPLE)
        r = rows[0]
        assert r.pk == "PRODUCT#ROBOT_ARM"
        assert r.sk == "PRODUCT#abc-123"
        assert r.product_name == "Test Robot"
        assert r.manufacturer == "Acme"
        assert r.field_path == "pose_repeatability"
        assert r.raw == "±0.1;mm"

    def test_second_section_resets_meta(self) -> None:
        rows = units_triage.parse_review(SAMPLE)
        # The voltage_range row is in the Beta/Big Motor section.
        voltage = next(r for r in rows if r.field_path == "voltage_range")
        assert voltage.product_name == "Big Motor"
        assert voltage.manufacturer == "Beta"

    def test_header_row_not_captured(self) -> None:
        # `| Field path | Raw string |` doesn't have backticks — should not be
        # picked up as a data row.
        rows = units_triage.parse_review(SAMPLE)
        assert all(r.field_path != "Field path" for r in rows)


class TestClassify:
    def test_plusminus(self) -> None:
        cat, _ = units_triage.classify("±0.1;mm")
        assert cat == "plusminus_tolerance"

    def test_ip_rating_with_wrong_unit(self) -> None:
        cat, _ = units_triage.classify("IP65;mm")
        assert cat == "ip_rating_wrong_unit"

    def test_ip_rating_with_null_unit_is_not_wrong(self) -> None:
        # `IP65;null` is a benign trailing-null pattern, not a wrong unit.
        cat, _ = units_triage.classify("IP65;null")
        assert cat == "trailing_null_unit"

    def test_trailing_null(self) -> None:
        cat, _ = units_triage.classify("100-240V;null")
        # Range-with-dash matcher comes after IP-wrong-unit but before
        # trailing-null in the matcher list — so this hits range_with_dash.
        # That's OK; the broader "range form" suggestion is still right.
        assert cat in {"range_with_dash", "trailing_null_unit"}

    def test_trailing_unknown(self) -> None:
        cat, _ = units_triage.classify("0.5;unknown")
        assert cat == "trailing_unknown_unit"

    def test_fraction(self) -> None:
        cat, _ = units_triage.classify("1/2;in")
        assert cat == "fraction"

    def test_approximate(self) -> None:
        cat, _ = units_triage.classify("~10;Nm")
        assert cat == "approximate"

    def test_uncategorized_falls_to_other(self) -> None:
        cat, _ = units_triage.classify("xyz")
        assert cat == "other"


class TestGroupByPattern:
    def test_groups_in_matcher_order(self) -> None:
        rows = [
            units_triage.Row("p", "s", None, None, "f", "1/2;in"),
            units_triage.Row("p", "s", None, None, "f", "±5;mm"),
            units_triage.Row("p", "s", None, None, "f", "0.5;unknown"),
        ]
        groups = units_triage.group_by_pattern(rows)
        # PATTERN_MATCHERS order: plusminus first, then unknown, then fraction.
        assert [g.category for g in groups] == [
            "plusminus_tolerance",
            "trailing_unknown_unit",
            "fraction",
        ]


class TestRender:
    def test_summary_table_lists_every_group(self) -> None:
        rows = units_triage.parse_review(SAMPLE)
        groups = units_triage.group_by_pattern(rows)
        out = units_triage.render_triage_md(Path("source.md"), rows, groups)
        assert "Total flagged rows: **7**" in out
        assert "## Summary" in out
        for g in groups:
            assert f"`{g.category}`" in out

    def test_pipe_in_raw_is_escaped(self) -> None:
        rows = [
            units_triage.Row(
                "p", "s", "Foo", "Bar", "field", "5|6;Nm"
            )  # pipe would corrupt MD table
        ]
        groups = units_triage.group_by_pattern(rows)
        out = units_triage.render_triage_md(Path("s.md"), rows, groups)
        assert "5\\|6;Nm" in out


class TestMain:
    def test_real_format_end_to_end(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(units_triage, "OUTPUT_DIR", tmp_path)
        src = tmp_path / "review.md"
        src.write_text(SAMPLE)
        out = tmp_path / "triage.md"
        rc = units_triage.main([str(src), "--output", str(out), "--quiet"])
        assert rc == 0
        text = out.read_text()
        assert "Total flagged rows: **7**" in text
        assert "plusminus_tolerance" in text

    def test_missing_source_returns_two(self, tmp_path: Path) -> None:
        rc = units_triage.main([str(tmp_path / "missing.md"), "--quiet"])
        assert rc == 2
