"""Tests for cli.bench_compare — precision/recall regression detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli import bench_compare


def _report(
    fixtures: list[dict[str, object]], timestamp: str = "20260101T000000Z"
) -> dict:
    return {"timestamp": timestamp, "live": False, "fixtures": fixtures}


def _fix(slug: str, precision: float, recall: float, status: str = "scored") -> dict:
    return {
        "slug": slug,
        "quality": {"precision": precision, "recall": recall, "status": status},
    }


def _write(tmp_path: Path, name: str, data: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(data))
    return p


class TestLoad:
    def test_extracts_precision_recall_per_slug(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "r.json", _report([_fix("a", 0.9, 0.8)]))
        out = bench_compare._load(path)
        assert out == {"a": {"precision": 0.9, "recall": 0.8, "status": "scored"}}

    def test_missing_quality_block_defaults_to_zero(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "r.json",
            _report([{"slug": "a"}]),  # no quality field
        )
        out = bench_compare._load(path)
        assert out["a"] == {"precision": 0.0, "recall": 0.0, "status": "unknown"}

    def test_skips_fixture_without_slug(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "r.json", _report([{"quality": {"precision": 0.5}}]))
        out = bench_compare._load(path)
        assert out == {}


class TestCompare:
    def test_no_change_returns_no_regressions(self) -> None:
        data = {"a": {"precision": 0.9, "recall": 0.8, "status": "scored"}}
        regressions, new_fix, dropped = bench_compare.compare(
            data, data, max_drop_pp=5.0
        )
        assert regressions == []
        assert new_fix == []
        assert dropped == []

    def test_drop_within_threshold_is_not_a_regression(self) -> None:
        baseline = {"a": {"precision": 0.90, "recall": 0.80, "status": "scored"}}
        # 4pp drop on precision — under the 5pp threshold.
        candidate = {"a": {"precision": 0.86, "recall": 0.80, "status": "scored"}}
        regressions, _, _ = bench_compare.compare(baseline, candidate, max_drop_pp=5.0)
        assert regressions == []

    def test_drop_over_threshold_flags_regression(self) -> None:
        baseline = {"a": {"precision": 0.90, "recall": 0.80, "status": "scored"}}
        # 10pp drop on precision — over the 5pp threshold.
        candidate = {"a": {"precision": 0.80, "recall": 0.80, "status": "scored"}}
        regressions, _, _ = bench_compare.compare(baseline, candidate, max_drop_pp=5.0)
        assert len(regressions) == 1
        r = regressions[0]
        assert r["slug"] == "a"
        assert r["metric"] == "precision"
        assert r["drop_pp"] == pytest.approx(-10.0)

    def test_improvement_does_not_flag(self) -> None:
        baseline = {"a": {"precision": 0.50, "recall": 0.50, "status": "scored"}}
        candidate = {"a": {"precision": 1.00, "recall": 1.00, "status": "scored"}}
        regressions, _, _ = bench_compare.compare(baseline, candidate, max_drop_pp=5.0)
        assert regressions == []

    def test_new_and_dropped_fixtures_reported_but_not_failing(self) -> None:
        baseline = {"a": {"precision": 0.9, "recall": 0.9, "status": "scored"}}
        candidate = {"b": {"precision": 0.5, "recall": 0.5, "status": "scored"}}
        regressions, new_fix, dropped = bench_compare.compare(
            baseline, candidate, max_drop_pp=5.0
        )
        assert regressions == []
        assert new_fix == ["b"]
        assert dropped == ["a"]

    def test_recall_drop_flags_independently(self) -> None:
        baseline = {"a": {"precision": 0.90, "recall": 0.90, "status": "scored"}}
        # Precision unchanged, recall drops 20pp.
        candidate = {"a": {"precision": 0.90, "recall": 0.70, "status": "scored"}}
        regressions, _, _ = bench_compare.compare(baseline, candidate, max_drop_pp=5.0)
        assert len(regressions) == 1
        assert regressions[0]["metric"] == "recall"


class TestMain:
    def test_exit_zero_when_clean(self, tmp_path: Path, capsys) -> None:
        baseline = _write(tmp_path, "b.json", _report([_fix("a", 0.9, 0.8)]))
        candidate = _write(tmp_path, "c.json", _report([_fix("a", 0.9, 0.8)]))
        rc = bench_compare.main([str(baseline), str(candidate)])
        assert rc == 0
        out = capsys.readouterr()
        assert "no precision/recall regressions" in out.err

    def test_exit_one_on_regression(self, tmp_path: Path, capsys) -> None:
        baseline = _write(tmp_path, "b.json", _report([_fix("a", 0.9, 0.9)]))
        candidate = _write(tmp_path, "c.json", _report([_fix("a", 0.5, 0.9)]))
        rc = bench_compare.main([str(baseline), str(candidate), "--max-drop", "5.0"])
        assert rc == 1
        out = capsys.readouterr()
        assert "REGRESSIONS" in out.err
        assert "a/precision" in out.err

    def test_writes_markdown_summary(self, tmp_path: Path) -> None:
        baseline = _write(tmp_path, "b.json", _report([_fix("a", 0.9, 0.8)]))
        candidate = _write(tmp_path, "c.json", _report([_fix("a", 0.92, 0.79)]))
        summary = tmp_path / "step_summary.md"
        rc = bench_compare.main(
            [str(baseline), str(candidate), "--summary-md", str(summary)]
        )
        assert rc == 0
        text = summary.read_text()
        assert "Bench precision/recall delta" in text
        assert "`a`" in text
        assert "no regressions" in text

    def test_summary_md_appends_not_overwrites(self, tmp_path: Path) -> None:
        baseline = _write(tmp_path, "b.json", _report([_fix("a", 0.9, 0.8)]))
        candidate = _write(tmp_path, "c.json", _report([_fix("a", 0.9, 0.8)]))
        summary = tmp_path / "step_summary.md"
        summary.write_text("preexisting content\n")
        bench_compare.main(
            [str(baseline), str(candidate), "--summary-md", str(summary)]
        )
        text = summary.read_text()
        assert text.startswith("preexisting content")
        assert "Bench precision/recall delta" in text

    def test_missing_baseline_returns_two(self, tmp_path: Path, capsys) -> None:
        candidate = _write(tmp_path, "c.json", _report([_fix("a", 0.9, 0.8)]))
        rc = bench_compare.main([str(tmp_path / "missing.json"), str(candidate)])
        assert rc == 2
