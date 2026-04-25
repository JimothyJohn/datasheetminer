"""Tests for the bench wall-clock budget check (Phase 5a)."""

from __future__ import annotations

import json

import pytest

from cli.bench import (
    BUDGET_OVERSHOOT_TOLERANCE,
    BUDGETS_PATH,
    _check_budgets,
    _load_budgets,
)


@pytest.mark.unit
class TestLoadBudgets:
    def test_repo_budgets_file_parses(self) -> None:
        budgets = _load_budgets()
        # Every entry must be a dict with at least one numeric key.
        for slug, body in budgets.items():
            assert not slug.startswith("_"), "underscore keys should be filtered out"
            assert isinstance(body, dict)
            assert any(isinstance(v, (int, float)) for v in body.values())

    def test_repo_budgets_file_covers_every_fixture(self) -> None:
        budgets = _load_budgets()
        from cli.bench import BENCHMARK_DIR

        fixtures = json.loads((BENCHMARK_DIR / "fixtures.json").read_text())
        for fx in fixtures:
            assert fx["slug"] in budgets, (
                f"fixture {fx['slug']} has no budget entry; add one to "
                f"{BUDGETS_PATH.relative_to(BUDGETS_PATH.parent.parent.parent)}"
            )


@pytest.mark.unit
class TestCheckBudgets:
    def test_within_budget_no_overshoot(self) -> None:
        results = [
            {
                "slug": "x",
                "page_finding": {"page_find_ms": 80},
                "extraction": {"extraction_ms": 10000},
            }
        ]
        budgets = {"x": {"page_find_ms": 100, "llm_extract_ms": 12000}}
        assert _check_budgets(results, budgets) == []

    def test_at_tolerance_boundary_no_overshoot(self) -> None:
        # actual == budget * (1 + tolerance) is still considered within;
        # only > triggers a fail.
        budget = 100
        actual = budget * (1.0 + BUDGET_OVERSHOOT_TOLERANCE)
        results = [
            {
                "slug": "x",
                "page_finding": {"page_find_ms": actual},
                "extraction": {},
            }
        ]
        budgets = {"x": {"page_find_ms": budget}}
        assert _check_budgets(results, budgets) == []

    def test_over_tolerance_flagged(self) -> None:
        # 100ms budget, 200ms actual = +100% overshoot, well past the 25% line
        results = [
            {
                "slug": "x",
                "page_finding": {"page_find_ms": 200},
                "extraction": {},
            }
        ]
        budgets = {"x": {"page_find_ms": 100}}
        out = _check_budgets(results, budgets)
        assert len(out) == 1
        assert out[0]["slug"] == "x"
        assert out[0]["metric"] == "page_find_ms"
        assert out[0]["overshoot_pct"] == 100.0

    def test_offline_run_skips_extraction_check(self) -> None:
        # No extraction_ms in the result (cache hit, not --live) — must
        # not flag the missing extraction as an overshoot.
        results = [
            {
                "slug": "x",
                "page_finding": {"page_find_ms": 80},
                "extraction": {"from_cache": True},
            }
        ]
        budgets = {"x": {"page_find_ms": 100, "llm_extract_ms": 5000}}
        assert _check_budgets(results, budgets) == []

    def test_unbudgeted_fixture_skipped(self) -> None:
        results = [
            {
                "slug": "no-budget",
                "page_finding": {"page_find_ms": 9_999_999},
                "extraction": {},
            }
        ]
        # Empty budgets map → nothing checked
        assert _check_budgets(results, {}) == []

    def test_multiple_overshoots_collected(self) -> None:
        results = [
            {
                "slug": "a",
                "page_finding": {"page_find_ms": 500},
                "extraction": {"extraction_ms": 99999},
            },
            {
                "slug": "b",
                "page_finding": {"page_find_ms": 50},
                "extraction": {"extraction_ms": 1000},
            },
        ]
        budgets = {
            "a": {"page_find_ms": 100, "llm_extract_ms": 1000},
            "b": {"page_find_ms": 100, "llm_extract_ms": 5000},
        }
        out = _check_budgets(results, budgets)
        slugs = {(o["slug"], o["metric"]) for o in out}
        assert ("a", "page_find_ms") in slugs
        assert ("a", "llm_extract_ms") in slugs
        assert not any(o["slug"] == "b" for o in out)
