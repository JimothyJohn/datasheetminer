"""Tests for datasheetminer.merge — per-page product merging."""

from datasheetminer.merge import merge_per_page_products

# Use Drive as a concrete ProductBase subclass for testing
from datasheetminer.models.drive import Drive


def _make_drive(**kwargs) -> Drive:
    defaults = {
        "product_type": "drive",
        "product_name": "Test Drive",
        "manufacturer": "TestCorp",
    }
    defaults.update(kwargs)
    return Drive(**defaults)


class TestMergePerPageProducts:
    def test_single_product_passthrough(self):
        d = _make_drive(part_number="X-100", pages=[3])
        result = merge_per_page_products([d])
        assert len(result) == 1
        assert result[0].pages == [3]

    def test_pages_union(self):
        d1 = _make_drive(part_number="X-100", pages=[5])
        d2 = _make_drive(part_number="X-100", pages=[6])
        result = merge_per_page_products([d1, d2])
        assert len(result) == 1
        assert result[0].pages == [5, 6]

    def test_fill_nulls_across_records(self):
        d1 = _make_drive(
            part_number="X-100",
            pages=[5],
            rated_current={"value": 10, "unit": "A"},
        )
        d2 = _make_drive(
            part_number="X-100",
            pages=[6],
            peak_current={"value": 20, "unit": "A"},
        )
        result = merge_per_page_products([d1, d2])
        assert len(result) == 1
        assert result[0].rated_current is not None
        assert result[0].peak_current is not None

    def test_more_populated_record_wins_conflict(self):
        d_sparse = _make_drive(
            part_number="X-100",
            pages=[5],
            rated_current={"value": 999, "unit": "A"},
        )
        d_rich = _make_drive(
            part_number="X-100",
            pages=[6],
            rated_current={"value": 10, "unit": "A"},
            peak_current={"value": 20, "unit": "A"},
            output_power={"value": 500, "unit": "W"},
        )
        result = merge_per_page_products([d_sparse, d_rich])
        assert len(result) == 1
        # ValueUnit fields are stored as "value;unit" strings
        assert result[0].rated_current == "10;A"

    def test_no_id_products_passthrough(self):
        d1 = _make_drive(manufacturer="", product_name="", part_number=None, pages=[1])
        d2 = _make_drive(manufacturer="", product_name="", part_number=None, pages=[2])
        result = merge_per_page_products([d1, d2])
        assert len(result) == 2

    def test_different_products_stay_separate(self):
        d1 = _make_drive(part_number="X-100", pages=[5])
        d2 = _make_drive(part_number="X-200", pages=[6])
        result = merge_per_page_products([d1, d2])
        assert len(result) == 2

    def test_normalization_merges_variants(self):
        d1 = _make_drive(
            manufacturer="Nidec",
            part_number="M-100",
            pages=[3],
        )
        d2 = _make_drive(
            manufacturer="nidec",
            part_number="m100",
            pages=[4],
            rated_current={"value": 5, "unit": "A"},
        )
        result = merge_per_page_products([d1, d2])
        assert len(result) == 1
        assert result[0].pages == [3, 4]
        assert result[0].rated_current is not None
