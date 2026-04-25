"""Tests for cli/ingest_report.py formatters and grouping."""

from __future__ import annotations

import json

import pytest

from cli.ingest_report import (
    _group_by_manufacturer,
    _latest_per_url,
    render_csv,
    render_email_template,
    render_json,
    render_markdown,
)


def _rec(
    *,
    url: str,
    manufacturer: str = "Acme",
    status: str = "quality_fail",
    sk: str = "INGEST#2026-04-24T00:00:00Z",
    product_name_hint: str = "M1",
    product_family_hint: str = "M-series",
    product_type: str = "motor",
    fields_filled_avg: float = 5.0,
    fields_total: int = 20,
    fields_missing: list[str] | None = None,
    extracted_part_numbers: list[str] | None = None,
) -> dict:
    return {
        "PK": f"INGEST#{hash(url) & 0xFFFF:04x}",
        "SK": sk,
        "url": url,
        "manufacturer": manufacturer,
        "status": status,
        "product_name_hint": product_name_hint,
        "product_family_hint": product_family_hint,
        "product_type": product_type,
        "fields_filled_avg": fields_filled_avg,
        "fields_total": fields_total,
        "fields_missing": fields_missing or ["stroke", "rated_power"],
        "extracted_part_numbers": extracted_part_numbers or ["M1-A", "M1-B"],
    }


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLatestPerUrl:
    def test_collapses_to_newest(self) -> None:
        r_old = _rec(url="https://x.com/a.pdf", sk="INGEST#2026-01-01T00:00:00Z")
        r_new = _rec(
            url="https://x.com/a.pdf",
            sk="INGEST#2026-04-01T00:00:00Z",
            status="success",
        )
        out = _latest_per_url([r_old, r_new])
        assert len(out) == 1
        assert out[0]["status"] == "success"

    def test_preserves_distinct_urls(self) -> None:
        out = _latest_per_url(
            [
                _rec(url="https://x.com/a.pdf"),
                _rec(url="https://x.com/b.pdf"),
            ]
        )
        assert {r["url"] for r in out} == {"https://x.com/a.pdf", "https://x.com/b.pdf"}


@pytest.mark.unit
class TestGroupByManufacturer:
    def test_groups_sorted(self) -> None:
        grouped = _group_by_manufacturer(
            [
                _rec(url="https://x.com/a.pdf", manufacturer="Zeta"),
                _rec(url="https://x.com/b.pdf", manufacturer="Acme"),
            ]
        )
        assert list(grouped.keys()) == ["Acme", "Zeta"]


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRenderMarkdown:
    def test_empty_grouped(self) -> None:
        assert "No ingest-log records" in render_markdown({})

    def test_includes_url_and_missing(self) -> None:
        grouped = _group_by_manufacturer([_rec(url="https://x.com/a.pdf")])
        md = render_markdown(grouped)
        assert "# Acme" in md
        assert "https://x.com/a.pdf" in md
        assert "stroke" in md
        assert "rated_power" in md

    def test_lists_variants(self) -> None:
        grouped = _group_by_manufacturer(
            [
                _rec(
                    url="https://x.com/a.pdf",
                    extracted_part_numbers=["A", "B", "C"],
                )
            ]
        )
        md = render_markdown(grouped)
        assert "Variants extracted: 3 (A, B, C)" in md


@pytest.mark.unit
class TestRenderJson:
    def test_round_trips(self) -> None:
        grouped = _group_by_manufacturer([_rec(url="https://x.com/a.pdf")])
        out = render_json(grouped)
        parsed = json.loads(out)
        assert "Acme" in parsed
        assert parsed["Acme"][0]["url"] == "https://x.com/a.pdf"

    def test_handles_decimal(self) -> None:
        from decimal import Decimal

        grouped = {"Acme": [{"url": "u", "fields_filled_avg": Decimal("7.5")}]}
        parsed = json.loads(render_json(grouped))
        assert parsed["Acme"][0]["fields_filled_avg"] == 7.5


@pytest.mark.unit
class TestRenderCsv:
    def test_has_header(self) -> None:
        out = render_csv({})
        first_line = out.splitlines()[0]
        assert "manufacturer" in first_line
        assert "missing_fields" in first_line

    def test_row_per_record(self) -> None:
        grouped = _group_by_manufacturer([_rec(url="https://x.com/a.pdf")])
        out = render_csv(grouped)
        assert "Acme" in out
        assert "https://x.com/a.pdf" in out
        assert "stroke|rated_power" in out


@pytest.mark.unit
class TestRenderEmailTemplate:
    def test_empty(self) -> None:
        assert "No manufacturers" in render_email_template({})

    def test_includes_missing_and_parts(self) -> None:
        grouped = _group_by_manufacturer(
            [
                _rec(
                    url="https://x.com/a.pdf",
                    fields_missing=["stroke"],
                    extracted_part_numbers=["M1-A"],
                )
            ]
        )
        email = render_email_template(grouped)
        assert "Email to Acme" in email
        assert "M-series" in email
        assert "M1-A" in email
        assert "stroke" in email

    def test_unions_across_rows(self) -> None:
        grouped = _group_by_manufacturer(
            [
                _rec(
                    url="https://x.com/a.pdf",
                    fields_missing=["stroke"],
                    extracted_part_numbers=["A"],
                ),
                _rec(
                    url="https://x.com/b.pdf",
                    fields_missing=["rated_power"],
                    extracted_part_numbers=["B"],
                ),
            ]
        )
        email = render_email_template(grouped)
        assert "stroke" in email
        assert "rated_power" in email
        assert "A" in email
        assert "B" in email
