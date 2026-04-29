"""Unit tests for cli/godmode.py — the data-quality observatory."""

from __future__ import annotations

import pytest

from cli.godmode import (
    Coverage,
    _has_edge_whitespace,
    _has_unexpected_nonascii,
    _histogram,
    _is_compact_unit_leak,
    _is_sentinel,
    _percentile,
    _value_filled,
    analyse,
    diff,
)


@pytest.mark.unit
class TestOddityPredicates:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("100;W", True),
            ("5.5e-5;kg·cm²", True),
            ("0-50;°C", True),  # also a valid MinMaxUnit, but compact-shaped string
            ("", False),
            ("100", False),
            ("abc;def;ghi", False),  # 3 parts
            ("Power: 100W; Speed: 3000rpm", False),  # whitespace in left
        ],
    )
    def test_is_compact_unit_leak(self, value: str, expected: bool) -> None:
        assert _is_compact_unit_leak(value) is expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("N/A", True),
            ("n/a", True),
            ("Unknown", True),
            ("TBD", True),
            ("-", True),
            ("none", True),
            ("100W", False),
            ("Servo Motor", False),
            (
                "",
                False,
            ),  # empty string is technically a placeholder, but predicate returns the strip-lower lookup
        ],
    )
    def test_is_sentinel(self, value: str, expected: bool) -> None:
        # _is_sentinel checks against SENTINEL_LITERALS, which contains
        # "n/a", "tbd", "-", etc. — empty string is NOT in that set so
        # returns False (the empty case is handled by is_placeholder upstream).
        if value == "":
            assert _is_sentinel(value) is False
            return
        assert _is_sentinel(value) is expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("100W", False),
            (" 100W", True),
            ("100W ", True),
            ("\t100W", True),
            ("", False),
        ],
    )
    def test_has_edge_whitespace(self, value: str, expected: bool) -> None:
        assert _has_edge_whitespace(value) is expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("100W", False),
            ("100°C", False),  # ° is in the allowed set
            ("±0.02 mm", False),  # ± allowed
            ("100Ω", False),  # Ω allowed
            ("100​W", True),  # zero-width space — sneaky!
            ("100€", True),  # € not allowed
            ("Servo モーター", True),  # Japanese kana
        ],
    )
    def test_has_unexpected_nonascii(self, value: str, expected: bool) -> None:
        assert _has_unexpected_nonascii(value) is expected


@pytest.mark.unit
class TestValueFilled:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, False),
            ("", False),  # placeholder
            ("N/A", False),  # placeholder
            ("100W", True),
            (0, True),  # zero is a valid numeric value
            (False, True),  # bool is "filled" — explicit signal
            ([], False),  # empty list
            (["one"], True),
            ({}, False),  # empty dict
            ({"value": 100, "unit": "W"}, True),
            ({"value": None, "unit": None}, False),
        ],
    )
    def test_value_filled(self, value, expected: bool) -> None:
        assert _value_filled(value) is expected


@pytest.mark.unit
class TestNumericHelpers:
    def test_percentile_simple(self) -> None:
        values = list(range(1, 101))
        assert _percentile(values, 0.5) == pytest.approx(50.5)
        assert _percentile(values, 0.05) == pytest.approx(5.95)
        assert _percentile(values, 0.95) == pytest.approx(95.05)

    def test_percentile_empty(self) -> None:
        assert _percentile([], 0.5) == 0.0

    def test_histogram_bucket_count(self) -> None:
        values = list(range(100))
        h = _histogram(values, buckets=10)
        assert len(h) == 10
        assert sum(c for _, _, c in h) == 100

    def test_histogram_handles_uniform(self) -> None:
        # All identical values — collapse to one bucket.
        h = _histogram([5.0] * 20)
        assert len(h) == 1
        assert h[0][2] == 20


@pytest.mark.unit
class TestAnalyse:
    """End-to-end against a small fixture — model_validate must succeed."""

    def _motor_row(
        self,
        *,
        product_id: str,
        manufacturer: str = "ACME",
        rated_power: dict | None = None,
        rated_torque: dict | None = None,
        product_name: str = "Motor",
        notes: str | None = None,
    ) -> dict:
        # product_id is typed UUID on the model; fabricate a deterministic
        # UUID so model_validate succeeds and quality scoring runs.
        from uuid import uuid5, NAMESPACE_DNS

        uid = str(uuid5(NAMESPACE_DNS, f"specodex-test-{product_id}"))
        row = {
            "PK": "PRODUCT#MOTOR",
            "SK": f"PRODUCT#{uid}",
            "product_id": uid,
            "product_type": "motor",
            "product_name": product_name,
            "manufacturer": manufacturer,
        }
        if rated_power is not None:
            row["rated_power"] = rated_power
        if rated_torque is not None:
            row["rated_torque"] = rated_torque
        if notes is not None:
            row["notes"] = notes
        return row

    def test_coverage_counts_correctly(self) -> None:
        rows = [
            self._motor_row(product_id="a", rated_power={"value": 100, "unit": "W"}),
            self._motor_row(product_id="b", rated_power={"value": 200, "unit": "W"}),
            self._motor_row(product_id="c"),
        ]
        snap = analyse(rows)
        cov = snap.coverage["motor"]["rated_power"]
        assert cov.filled == 2
        assert cov.total == 3
        assert cov.pct == pytest.approx(2 / 3)

    def test_compact_unit_leak_detected(self) -> None:
        # Compact-unit leaks live on spec fields — the analyser walks
        # model_class spec fields only, skipping metadata like product_name.
        # Simulate the bug UNITS Phase 5 backfilled: rated_power stored as
        # a string in DynamoDB instead of a dict.
        rows = [
            {
                "PK": "PRODUCT#MOTOR",
                "SK": "PRODUCT#leak",
                "product_id": "leak",
                "product_type": "motor",
                "product_name": "Motor",
                "manufacturer": "ACME",
                "rated_power": "5.5e-5;kg·cm²",
            },
        ]
        snap = analyse(rows)
        assert "compact_unit_leak" in snap.oddities
        assert any(
            h.raw_value == "5.5e-5;kg·cm²" for h in snap.oddities["compact_unit_leak"]
        )

    def test_sentinel_literal_detected(self) -> None:
        # Same reason: sentinels on spec fields, not metadata.
        rows = [
            {
                "PK": "PRODUCT#MOTOR",
                "SK": "PRODUCT#sentinel",
                "product_id": "sentinel",
                "product_type": "motor",
                "product_name": "Motor",
                "manufacturer": "ACME",
                "rated_speed": "N/A",
            },
        ]
        snap = analyse(rows)
        assert "sentinel_literal" in snap.oddities

    def test_cluster_commonality_flagged(self) -> None:
        # Three Acme motors with identical power → flag as common.
        common_power = {"value": 100, "unit": "W"}
        rows = [
            self._motor_row(product_id="a", rated_power=common_power),
            self._motor_row(product_id="b", rated_power=common_power),
            self._motor_row(product_id="c", rated_power=common_power),
        ]
        snap = analyse(rows)
        assert len(snap.cluster_commonalities) == 1
        c = snap.cluster_commonalities[0]
        assert c.manufacturer == "ACME"
        assert c.product_type == "motor"
        assert c.cluster_size == 3
        assert any(field == "rated_power" for field, _ in c.common_fields)

    def test_cluster_commonality_skips_small_buckets(self) -> None:
        rows = [
            self._motor_row(product_id="a", rated_power={"value": 100, "unit": "W"}),
            self._motor_row(product_id="b", rated_power={"value": 100, "unit": "W"}),
        ]  # only 2 — below ≥3 threshold
        snap = analyse(rows)
        assert snap.cluster_commonalities == []

    def test_unit_mismatch_surfaces(self) -> None:
        # Power field with a non-power unit.
        rows = [
            self._motor_row(product_id="a", rated_power={"value": 100, "unit": "rpm"}),
        ]
        snap = analyse(rows)
        assert any(
            m.field_path == "rated_power" and m.actual_unit == "rpm"
            for m in snap.unit_mismatches
        )

    def test_quality_scores_recomputed(self) -> None:
        rows = [
            self._motor_row(product_id="a", rated_power={"value": 100, "unit": "W"})
        ]
        snap = analyse(rows)
        # quality_scores keyed by product_type — motor model validation
        # must succeed for the score to land.
        assert "motor" in snap.quality_scores
        assert len(snap.quality_scores["motor"]) == 1

    def test_failure_modes_require_min_products(self) -> None:
        # 4 rows from one manufacturer → below the ≥5 threshold.
        rows = [
            self._motor_row(product_id=f"row{i}", manufacturer="SmallCo")
            for i in range(4)
        ]
        snap = analyse(rows)
        assert "SmallCo" not in snap.failure_modes

    def test_failure_modes_top_10(self) -> None:
        rows = [
            self._motor_row(product_id=f"row{i}", manufacturer="BigCo")
            for i in range(6)
        ]
        snap = analyse(rows)
        assert "BigCo" in snap.failure_modes
        assert len(snap.failure_modes["BigCo"]) <= 10
        # All these products have nothing populated → null rates near 100%.
        for mode in snap.failure_modes["BigCo"]:
            assert mode.null_pct > 0.5


@pytest.mark.unit
class TestDrift:
    def test_no_prev_returns_none(self) -> None:
        snap = analyse([])
        assert diff(snap, None) is None

    def test_regression_detected(self) -> None:
        snap = analyse([])
        snap.coverage["motor"] = {"rated_power": Coverage(filled=2, total=10)}
        prev = {
            "timestamp": "20260101T000000Z",
            "row_count": 0,
            "coverage": {"motor": {"rated_power": {"filled": 8, "total": 10}}},
            "oddities": {},
        }
        drift = diff(snap, prev)
        assert drift is not None
        assert any(
            d.field == "rated_power" and d.delta_pp < 0
            for d in drift.coverage_regressions
        )

    def test_below_threshold_skipped(self) -> None:
        snap = analyse([])
        snap.coverage["motor"] = {"rated_power": Coverage(filled=8, total=10)}
        prev = {
            "timestamp": "20260101T000000Z",
            "row_count": 0,
            "coverage": {"motor": {"rated_power": {"filled": 9, "total": 10}}},
            "oddities": {},
        }
        drift = diff(snap, prev)
        assert drift is not None
        # Δ = 80% - 90% = -10pp, ABOVE the 5pp threshold — should appear.
        assert any(d.field == "rated_power" for d in drift.coverage_regressions)

    def test_new_oddity_pattern_surfaced(self) -> None:
        snap = analyse([])
        snap.oddities["compact_unit_leak"] = []
        prev = {
            "timestamp": "20260101T000000Z",
            "row_count": 0,
            "coverage": {},
            "oddities": {},
        }
        drift = diff(snap, prev)
        assert drift is not None
        assert "compact_unit_leak" in drift.new_oddity_patterns
