"""Tests for cli.audit_dedupes — DEDUPE Phase 1 grouping + classification.

No DynamoDB mocking — the audit logic operates on plain dicts and is
tested directly. The boto3-bound `fetch_rows_from_dynamo` shim isn't
covered here.
"""

from __future__ import annotations

import json
from pathlib import Path

from cli import audit_dedupes


def row(
    *,
    manufacturer: str = "Parker",
    part_number: str | None = "MPP-1152C",
    product_family: str | None = "MPP",
    pk: str = "PRODUCT#motor",
    product_id: str | None = None,
    **fields,
) -> dict:
    base = {
        "PK": pk,
        "SK": f"PRODUCT#{product_id or part_number}",
        "product_id": product_id or part_number,
        "manufacturer": manufacturer,
        "part_number": part_number,
        "product_family": product_family,
    }
    base.update(fields)
    return base


class TestFamilyAwareCore:
    def test_strips_family_from_part_number(self) -> None:
        assert audit_dedupes.family_aware_core("MPP-1152C", "MPP") == "1152c"

    def test_no_strip_without_family(self) -> None:
        assert audit_dedupes.family_aware_core("MPP-1152C", None) == "mpp1152c"

    def test_no_strip_when_family_doesnt_match(self) -> None:
        assert audit_dedupes.family_aware_core("MPP-1152C", "SGM7") == "mpp1152c"

    def test_empty_part_number_returns_empty(self) -> None:
        assert audit_dedupes.family_aware_core(None, "MPP") == ""


class TestIsJunkPartNumber:
    def test_unknown_is_junk(self) -> None:
        assert audit_dedupes.is_junk_part_number("Unknown")

    def test_real_part_is_not(self) -> None:
        assert not audit_dedupes.is_junk_part_number("MPP-1152C")

    def test_none_is_junk(self) -> None:
        assert audit_dedupes.is_junk_part_number(None)


class TestGroupRows:
    def test_collapses_prefix_drift(self) -> None:
        rows = [
            row(part_number="MPP-1152C"),
            row(part_number="MPP1152C"),
            row(part_number="1152C"),
        ]
        groups = audit_dedupes.group_rows(rows)
        assert len(groups) == 1
        (((_, core), members),) = groups.items()
        assert core == "1152c"
        assert len(members) == 3

    def test_keeps_distinct_skus_separate(self) -> None:
        rows = [
            row(part_number="MPP-1152C"),
            row(part_number="MPP-2200B"),
        ]
        groups = audit_dedupes.group_rows(rows)
        assert len(groups) == 2

    def test_skips_rows_missing_manufacturer(self) -> None:
        rows = [row(manufacturer=""), row()]
        groups = audit_dedupes.group_rows(rows)
        assert len(groups) == 1

    def test_does_not_cross_manufacturers(self) -> None:
        rows = [
            row(manufacturer="Parker", part_number="MPP-1152C"),
            row(manufacturer="Yaskawa", part_number="MPP-1152C"),
        ]
        groups = audit_dedupes.group_rows(rows)
        assert len(groups) == 2


class TestClassifyField:
    def test_all_equal_is_identical(self) -> None:
        assert audit_dedupes.classify_field([10, 10, 10]) == "identical"

    def test_some_null_rest_equal_is_complementary(self) -> None:
        assert audit_dedupes.classify_field([10, None, 10]) == "complementary"

    def test_one_value_rest_null_is_complementary(self) -> None:
        assert audit_dedupes.classify_field([None, 10, None]) == "complementary"

    def test_distinct_non_null_is_conflicting(self) -> None:
        assert audit_dedupes.classify_field([10, 20]) == "conflicting"

    def test_all_null_is_identical_vacuously(self) -> None:
        assert audit_dedupes.classify_field([None, None]) == "identical"

    def test_dict_value_equality(self) -> None:
        a = {"value": 10, "unit": "Nm"}
        b = {"unit": "Nm", "value": 10}  # different key order, same dict
        assert audit_dedupes.classify_field([a, b]) == "identical"

    def test_dict_value_difference(self) -> None:
        a = {"value": 10, "unit": "Nm"}
        b = {"value": 12, "unit": "Nm"}
        assert audit_dedupes.classify_field([a, b]) == "conflicting"


class TestSuggestAction:
    def test_all_identical_or_complementary_is_merge(self) -> None:
        cls = {"rated_torque": "identical", "max_speed": "complementary"}
        assert audit_dedupes.suggest_action(cls, [row(), row()]) == "merge"

    def test_any_conflicting_is_review(self) -> None:
        cls = {"rated_torque": "identical", "max_speed": "conflicting"}
        assert audit_dedupes.suggest_action(cls, [row(), row()]) == "review"

    def test_mixed_junk_is_delete_junk(self) -> None:
        rows = [row(part_number="Unknown"), row(part_number="MPP-1152C")]
        assert audit_dedupes.suggest_action({}, rows) == "delete-junk"

    def test_all_junk_falls_through_to_merge(self) -> None:
        # All rows are junk-named — caller decides; default to merge.
        rows = [row(part_number="Unknown"), row(part_number="N/A")]
        assert audit_dedupes.suggest_action({}, rows) == "merge"


class TestAudit:
    def test_singletons_are_excluded(self) -> None:
        report = audit_dedupes.audit([row(part_number="MPP-1152C")])
        assert report == []

    def test_safe_merge_group_classified(self) -> None:
        rows = [
            row(part_number="MPP-1152C", rated_torque={"value": 10, "unit": "Nm"}),
            row(
                part_number="MPP1152C",
                rated_torque=None,
                max_speed={"value": 5000, "unit": "rpm"},
            ),
        ]
        report = audit_dedupes.audit(rows)
        assert len(report) == 1
        r = report[0]
        assert r["suggested_action"] == "merge"
        assert r["row_count"] == 2
        assert r["normalized_core"] == "1152c"
        assert r["field_classifications"]["rated_torque"] == "complementary"
        assert r["field_classifications"]["max_speed"] == "complementary"

    def test_conflicting_group_marked_review(self) -> None:
        rows = [
            row(part_number="MPP-1152C", rated_torque={"value": 10, "unit": "Nm"}),
            row(part_number="MPP1152C", rated_torque={"value": 12, "unit": "Nm"}),
        ]
        report = audit_dedupes.audit(rows)
        assert len(report) == 1
        assert report[0]["suggested_action"] == "review"
        assert report[0]["field_classifications"]["rated_torque"] == "conflicting"

    def test_family_mismatch_demotes_to_review(self) -> None:
        # Same normalized core, two different families. Even with all
        # spec fields identical, the family mismatch forces manual review.
        rows = [
            row(part_number="MPP-1152C", product_family="MPP", rated_torque=10),
            row(part_number="MPJ-1152C", product_family="MPJ", rated_torque=10),
        ]
        report = audit_dedupes.audit(rows)
        # MPP-1152C strips to "1152c", MPJ-1152C strips to "1152c" — same.
        assert len(report) == 1
        assert report[0]["family_mismatch"] is True
        assert report[0]["suggested_action"] == "review"

    def test_pages_field_excluded_from_classification(self) -> None:
        # `pages` is provenance, not spec — its diff shouldn't gate merge.
        rows = [
            row(part_number="MPP-1152C", pages=[10, 11], rated_torque=10),
            row(part_number="MPP1152C", pages=[15, 16], rated_torque=10),
        ]
        report = audit_dedupes.audit(rows)
        assert "pages" not in report[0]["field_classifications"]
        assert report[0]["suggested_action"] == "merge"


class TestRenderReviewMd:
    def test_empty_review_says_so(self) -> None:
        out = audit_dedupes.render_review_md([])
        assert "Nothing to review" in out

    def test_review_groups_only_listed(self) -> None:
        reports = [
            {
                "manufacturer": "parker",
                "normalized_core": "1152c",
                "row_count": 2,
                "rows": [
                    {
                        "part_number": "MPP-1152C",
                        "product_family": "MPP",
                        "datasheet_url": "x",
                    },
                    {
                        "part_number": "MPP1152C",
                        "product_family": "MPP",
                        "datasheet_url": "y",
                    },
                ],
                "field_classifications": {"rated_torque": "conflicting"},
                "family_mismatch": False,
                "suggested_action": "review",
            },
            {
                "manufacturer": "parker",
                "normalized_core": "2200b",
                "row_count": 2,
                "rows": [],
                "field_classifications": {"max_speed": "complementary"},
                "family_mismatch": False,
                "suggested_action": "merge",
            },
        ]
        out = audit_dedupes.render_review_md(reports)
        assert "1152c" in out
        assert "2200b" not in out  # merge groups skipped
        assert "Conflicting fields" in out

    def test_family_mismatch_warning_rendered(self) -> None:
        reports = [
            {
                "manufacturer": "parker",
                "normalized_core": "1152c",
                "row_count": 2,
                "rows": [
                    {
                        "part_number": "MPP-1152C",
                        "product_family": "MPP",
                        "datasheet_url": "",
                    },
                    {
                        "part_number": "MPJ-1152C",
                        "product_family": "MPJ",
                        "datasheet_url": "",
                    },
                ],
                "field_classifications": {},
                "family_mismatch": True,
                "suggested_action": "review",
            }
        ]
        out = audit_dedupes.render_review_md(reports)
        assert "family mismatch" in out


class TestMain:
    def test_with_rows_file_writes_artifacts(self, tmp_path: Path, monkeypatch) -> None:
        # Override OUTPUT_DIR so the test doesn't pollute repo's outputs/.
        monkeypatch.setattr(audit_dedupes, "OUTPUT_DIR", tmp_path)
        rows_file = tmp_path / "rows.json"
        rows_file.write_text(
            json.dumps(
                [
                    row(part_number="MPP-1152C", rated_torque=10),
                    row(part_number="MPP1152C", rated_torque=12),
                    row(part_number="MPP-2200B"),
                ]
            )
        )
        rc = audit_dedupes.main(["--stage", "dev", "--rows", str(rows_file), "--quiet"])
        assert rc == 0
        json_files = list(tmp_path.glob("dedupe_audit_dev_*.json"))
        md_files = list(tmp_path.glob("dedupe_review_dev_*.md"))
        assert len(json_files) == 1
        assert len(md_files) == 1
        report = json.loads(json_files[0].read_text())
        assert report["stage"] == "dev"
        assert (
            report["total_groups"] == 1
        )  # only the duplicate group, singleton excluded
        assert (
            report["groups"][0]["suggested_action"] == "review"
        )  # rated_torque conflicts

    def test_rejects_non_dev_stage(self, tmp_path: Path) -> None:
        rows_file = tmp_path / "r.json"
        rows_file.write_text("[]")
        # argparse choices=['dev'] makes this a SystemExit, not a return.
        try:
            audit_dedupes.main(["--stage", "prod", "--rows", str(rows_file)])
            raise AssertionError("expected SystemExit for --stage prod")
        except SystemExit as e:
            assert e.code != 0
