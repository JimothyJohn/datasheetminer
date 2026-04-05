"""Tests for datasheetminer.models.csv_schema (LLM schema generation)."""

import pytest

from datasheetminer.models.csv_schema import (
    EXCLUDED_FIELDS,
    UNITS,
    build_columns,
    header_row,
    reconstruct_row,
)
from datasheetminer.models.motor import Motor


@pytest.mark.unit
class TestBuildColumns:
    def test_excluded_fields_dropped(self) -> None:
        cols = build_columns(Motor)
        field_names = {c.field_name for c in cols}
        for name in EXCLUDED_FIELDS:
            assert name not in field_names, f"{name} should be excluded"

    def test_value_unit_emits_single_column_with_unit(self) -> None:
        cols = {c.header: c for c in build_columns(Motor)}
        # rated_speed is ValueUnit with rpm
        col = cols["rated_speed[rpm]"]
        assert col.field_name == "rated_speed"
        assert col.kind == "value"
        assert col.unit == "rpm"

    def test_min_max_unit_emits_two_columns(self) -> None:
        cols = {c.header: c for c in build_columns(Motor)}
        # rated_voltage is MinMaxUnit with V
        assert "rated_voltage_min[V]" in cols
        assert "rated_voltage_max[V]" in cols
        lo = cols["rated_voltage_min[V]"]
        hi = cols["rated_voltage_max[V]"]
        assert lo.field_name == hi.field_name == "rated_voltage"
        assert lo.kind == "min" and hi.kind == "max"
        assert lo.unit == hi.unit == "V"

    def test_scalar_fields_emit_plain_headers(self) -> None:
        cols = {c.header: c for c in build_columns(Motor)}
        # poles is Optional[int], type is Optional[Literal[...]], series is Optional[str]
        assert cols["poles"].kind == "int"
        assert cols["type"].kind == "str"
        assert cols["series"].kind == "str"

    def test_inherited_product_base_unit_fields_present(self) -> None:
        cols = {c.header: c for c in build_columns(Motor)}
        # weight / msrp / warranty come from ProductBase
        assert "weight[kg]" in cols
        assert "warranty[years]" in cols

    def test_header_row_is_comma_separated(self) -> None:
        cols = build_columns(Motor)
        header = header_row(cols)
        assert header.count(",") == len(cols) - 1
        assert header.startswith(cols[0].header)


@pytest.mark.unit
class TestReconstructRow:
    def test_value_unit_reconstructed(self) -> None:
        cols = build_columns(Motor)
        # Find the rated_speed column and give it a value
        row = {c.header: "" for c in cols}
        row["rated_speed[rpm]"] = "3000"
        out = reconstruct_row(row, cols)
        assert out["rated_speed"] == "3000;rpm"

    def test_min_max_reconstructed_as_range(self) -> None:
        cols = build_columns(Motor)
        row = {c.header: "" for c in cols}
        row["rated_voltage_min[V]"] = "40"
        row["rated_voltage_max[V]"] = "60"
        out = reconstruct_row(row, cols)
        assert out["rated_voltage"] == "40-60;V"

    def test_min_only_becomes_single_value(self) -> None:
        cols = build_columns(Motor)
        row = {c.header: "" for c in cols}
        row["rated_voltage_min[V]"] = "48"
        out = reconstruct_row(row, cols)
        assert out["rated_voltage"] == "48;V"

    def test_empty_cell_becomes_none(self) -> None:
        cols = build_columns(Motor)
        row = {c.header: "" for c in cols}
        out = reconstruct_row(row, cols)
        assert out["rated_speed"] is None
        assert out["rated_voltage"] is None
        assert out["series"] is None

    def test_int_and_str_typed(self) -> None:
        cols = build_columns(Motor)
        row = {c.header: "" for c in cols}
        row["poles"] = "8"
        row["series"] = "BG75"
        out = reconstruct_row(row, cols)
        assert out["poles"] == 8
        assert out["series"] == "BG75"


@pytest.mark.unit
class TestUnitsMap:
    def test_canonical_torque_matches_spec_rules(self) -> None:
        """Units stored in UNITS must be members of spec_rules valid-unit sets,
        otherwise spec validation nulls the field out after parsing."""
        from datasheetminer.spec_rules import FIELD_RULES

        for field_name, canonical_unit in UNITS.items():
            if field_name in FIELD_RULES:
                valid_units, _, _ = FIELD_RULES[field_name]
                assert canonical_unit in valid_units, (
                    f"{field_name}: canonical unit '{canonical_unit}' "
                    f"not in spec_rules valid set {valid_units}"
                )
