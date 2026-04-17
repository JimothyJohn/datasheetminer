"""Tests for datasheetminer.ids — deterministic product ID generation."""

import uuid

from datasheetminer.ids import PRODUCT_NAMESPACE, compute_product_id, normalize_string


class TestNormalizeString:
    def test_basic(self):
        assert normalize_string("Nidec Corp.") == "nideccorp"

    def test_spaces_dashes(self):
        assert normalize_string("Model A") == normalize_string("Model-A")

    def test_none(self):
        assert normalize_string(None) == ""

    def test_empty(self):
        assert normalize_string("") == ""

    def test_unicode(self):
        assert normalize_string("Ünit") == "nit"


class TestComputeProductId:
    def test_mfg_plus_part_number(self):
        pid = compute_product_id("Nidec", "M-100", None)
        assert pid == uuid.uuid5(PRODUCT_NAMESPACE, "nidec:m100")

    def test_mfg_plus_name_fallback(self):
        pid = compute_product_id("Nidec", None, "D-Series Motor")
        assert pid == uuid.uuid5(PRODUCT_NAMESPACE, "nidec:dseriesmotor")

    def test_part_number_preferred_over_name(self):
        pid_pn = compute_product_id("Nidec", "M-100", "D-Series Motor")
        pid_name = compute_product_id("Nidec", None, "D-Series Motor")
        assert pid_pn != pid_name

    def test_none_when_sparse(self):
        assert compute_product_id("", None, None) is None
        assert compute_product_id("", "", "") is None

    def test_deterministic(self):
        a = compute_product_id("Mitsubishi", "MR-J5-40G", None)
        b = compute_product_id("Mitsubishi", "MR-J5-40G", None)
        assert a == b

    def test_normalization_resilience(self):
        a = compute_product_id("Nidec", "M-100", None)
        b = compute_product_id("nidec", "m100", None)
        assert a == b

    def test_different_mfg_strings_differ(self):
        a = compute_product_id("Nidec Corp.", "M-100", None)
        b = compute_product_id("Nidec", "M-100", None)
        assert a != b
