"""Tests for cli/audit_units.py.

The boto3 scan path is exercised via a fake table; we don't actually hit AWS.
Focus: _find_dirty_strings identifies both the multi-semicolon pattern and
the non-numeric-stem pattern in nested values, and the scanning loop walks
every item it sees.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from cli.audit_units import _classify_unit_string, _find_dirty_strings, audit


class TestClassifyUnitString:
    def test_clean_value_unit(self) -> None:
        assert _classify_unit_string("230;V") is None
        assert _classify_unit_string("-20;C") is None

    def test_clean_range_unit(self) -> None:
        assert _classify_unit_string("20-40;C") is None
        assert _classify_unit_string("-20-40;C") is None

    def test_scientific_notation_is_clean(self) -> None:
        # float(0.00000198) stringifies as "1.98e-06" — the writer path
        # produces this shape legitimately; must not be flagged.
        assert _classify_unit_string("1.98e-06;kg-m²") is None
        assert _classify_unit_string("1.98E-6;kg-m2") is None
        assert _classify_unit_string("0.64e-4;kg-m²") is None

    def test_no_semicolon_is_not_a_compact_unit(self) -> None:
        # Plain strings like product names should never be flagged.
        assert _classify_unit_string("G-Series") is None
        assert _classify_unit_string("") is None

    def test_multi_semicolon(self) -> None:
        assert _classify_unit_string("1;2;V") == "multi-semicolon"

    def test_non_numeric_stem_with_hyphen(self) -> None:
        # The exact shape that shipped in prod: series name dumped in voltage.
        assert _classify_unit_string("G-Series-230;V") == "non-numeric-stem"

    def test_non_numeric_stem_alpha(self) -> None:
        # ip_rating value landing in rotor_inertia.
        assert _classify_unit_string("IP65;kgcm²") == "non-numeric-stem"

    def test_empty_unit_part(self) -> None:
        assert _classify_unit_string("230;") == "empty-part"


class TestFindDirtyStrings:
    def test_clean_single_semicolon(self) -> None:
        item = {"rated_power": "100;W", "name": "X"}
        assert _find_dirty_strings(item) == []

    def test_no_semicolon(self) -> None:
        item = {"manufacturer": "Maxon"}
        assert _find_dirty_strings(item) == []

    def test_one_multi_semicolon_field(self) -> None:
        item = {"rated_power": "1;2;V"}
        assert _find_dirty_strings(item) == [
            ("rated_power", "1;2;V", "multi-semicolon")
        ]

    def test_non_numeric_stem_field(self) -> None:
        item = {"rated_voltage": "G-Series-230;V"}
        assert _find_dirty_strings(item) == [
            ("rated_voltage", "G-Series-230;V", "non-numeric-stem")
        ]

    def test_multiple_dirty_fields_mixed_reasons(self) -> None:
        item = {"a": "1;2;V", "b": "IP65;kg"}
        found = sorted(_find_dirty_strings(item))
        assert found == [
            ("a", "1;2;V", "multi-semicolon"),
            ("b", "IP65;kg", "non-numeric-stem"),
        ]

    def test_nested_dict(self) -> None:
        item = {"dimensions": {"width": "10;20;mm"}}
        assert _find_dirty_strings(item) == [
            ("dimensions.width", "10;20;mm", "multi-semicolon")
        ]

    def test_list_of_strings(self) -> None:
        item = {"notes": ["100;V", "1;2;bad"]}
        assert _find_dirty_strings(item) == [("notes[1]", "1;2;bad", "multi-semicolon")]

    def test_deeply_nested(self) -> None:
        item = {"outer": {"middle": [{"inner": "a;b;c"}]}}
        assert _find_dirty_strings(item) == [
            ("outer.middle[0].inner", "a;b;c", "multi-semicolon")
        ]

    def test_non_string_types_ignored(self) -> None:
        item = {"x": 1, "y": 2.5, "z": None, "flag": True}
        assert _find_dirty_strings(item) == []


class TestAudit:
    def _fake_table(self, pages: list[list[dict[str, Any]]]) -> MagicMock:
        """Return a Table mock whose scan() paginates through `pages`."""
        calls = {"i": 0}

        def scan(**kwargs: Any) -> dict[str, Any]:
            idx = calls["i"]
            calls["i"] += 1
            if idx >= len(pages):
                return {"Items": []}
            resp: dict[str, Any] = {"Items": pages[idx]}
            if idx + 1 < len(pages):
                resp["LastEvaluatedKey"] = {"PK": f"marker-{idx}"}
            return resp

        table = MagicMock()
        table.scan.side_effect = scan
        return table

    @pytest.fixture(autouse=True)
    def _patch_boto3(self, monkeypatch):
        self.table = self._fake_table(
            [[{"PK": "x", "SK": "y", "rated_power": "100;W"}]]
        )
        resource = MagicMock()
        resource.Table.return_value = self.table
        monkeypatch.setattr(
            "cli.audit_units.boto3.resource",
            lambda *a, **kw: resource,
        )

    def test_exits_zero_when_clean(self, capsys) -> None:
        code = audit("products", "us-east-1", None)
        assert code == 0

    def test_exits_nonzero_when_dirty(self, monkeypatch, capsys) -> None:
        dirty_table = self._fake_table(
            [[{"PK": "x", "SK": "y", "rated_power": "1;2;V"}]]
        )
        resource = MagicMock()
        resource.Table.return_value = dirty_table
        monkeypatch.setattr(
            "cli.audit_units.boto3.resource",
            lambda *a, **kw: resource,
        )
        code = audit("products", "us-east-1", None)
        assert code == 1

    def test_output_file_is_jsonl(self, tmp_path, monkeypatch) -> None:
        dirty_table = self._fake_table(
            [[{"PK": "A", "SK": "B", "rated_power": "1;2;V"}]]
        )
        resource = MagicMock()
        resource.Table.return_value = dirty_table
        monkeypatch.setattr(
            "cli.audit_units.boto3.resource",
            lambda *a, **kw: resource,
        )
        out = tmp_path / "findings.jsonl"
        code = audit("products", "us-east-1", str(out))
        assert code == 1
        import json

        lines = out.read_text().strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["PK"] == "A"
        assert parsed["fields"][0]["value"] == "1;2;V"
        assert parsed["fields"][0]["reason"] == "multi-semicolon"

    def test_output_flags_non_numeric_stem(self, tmp_path, monkeypatch) -> None:
        # Repro of the R88M-G90010T-S2 row: series name shuffled into voltage.
        dirty_table = self._fake_table(
            [[{"PK": "P#MOTOR", "SK": "P#1", "rated_voltage": "G-Series-230;V"}]]
        )
        resource = MagicMock()
        resource.Table.return_value = dirty_table
        monkeypatch.setattr(
            "cli.audit_units.boto3.resource",
            lambda *a, **kw: resource,
        )
        out = tmp_path / "findings.jsonl"
        code = audit("products", "us-east-1", str(out))
        assert code == 1
        import json

        parsed = json.loads(out.read_text().strip())
        assert parsed["fields"][0]["path"] == "rated_voltage"
        assert parsed["fields"][0]["reason"] == "non-numeric-stem"

    def test_paginates_across_pages(self, monkeypatch) -> None:
        multi = self._fake_table(
            [
                [{"PK": "a", "SK": "1", "x": "1;W"}],
                [{"PK": "b", "SK": "2", "x": "1;V"}],
                [{"PK": "c", "SK": "3", "x": "1;A"}],
            ]
        )
        resource = MagicMock()
        resource.Table.return_value = multi
        monkeypatch.setattr(
            "cli.audit_units.boto3.resource",
            lambda *a, **kw: resource,
        )
        code = audit("products", "us-east-1", None)
        assert code == 0
        # 3 pages + 1 extra call returning Items=[] to terminate is also fine;
        # the loop exits as soon as LastEvaluatedKey is missing.
        assert multi.scan.call_count >= 3
