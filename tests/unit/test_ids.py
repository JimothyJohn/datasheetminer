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


class TestFamilyPrefixCollapse:
    """Family-aware ID collapses prefix variants of the same physical SKU.

    The Parker MPP catalog motivated this: a single ingest pulled one row
    as ``MPP-1152C``, another as ``MPP1152C``, another as bare ``1152C``.
    Without this rule those land as three different UUIDs.
    """

    def test_dashed_prefix_collapses(self):
        a = compute_product_id("Parker", "MPP-1152C", None, "MPP")
        b = compute_product_id("Parker", "1152C", None, "MPP")
        assert a == b

    def test_no_dash_prefix_collapses(self):
        a = compute_product_id("Parker", "MPP1152C", None, "MPP")
        b = compute_product_id("Parker", "1152C", None, "MPP")
        assert a == b

    def test_all_three_variants_collapse(self):
        a = compute_product_id("Parker", "MPP-1152C", None, "MPP")
        b = compute_product_id("Parker", "MPP1152C", None, "MPP")
        c = compute_product_id("Parker", "1152C", None, "MPP")
        assert a == b == c

    def test_without_family_no_collapse(self):
        # Without product_family the legacy behavior holds — three rows.
        a = compute_product_id("Parker", "MPP-1152C", None)
        b = compute_product_id("Parker", "1152C", None)
        assert a != b

    def test_short_leftover_does_not_collapse(self):
        # If stripping leaves <3 chars or no digits, keep the full SKU.
        # E.g. family "FOO" with part "FOOX" → leftover "X", keep "foox".
        a = compute_product_id("Acme", "FOOX", None, "FOO")
        b = compute_product_id("Acme", "X", None, "FOO")
        assert a != b

    def test_unrelated_family_no_op(self):
        # When the part doesn't start with the family, the part is left
        # alone — same ID as if no family were supplied at all.
        with_unrelated_family = compute_product_id("Parker", "BE231F", None, "MPP")
        without_family = compute_product_id("Parker", "BE231F", None)
        assert with_unrelated_family == without_family

    def test_mpj_and_mpp_differ_when_part_has_distinct_prefix(self):
        # MPP-1152C and MPJ-1152C are physically different motors. The
        # family normalizer collapses each within its own family but
        # MUST NOT cross-collapse them. Here the family is the same
        # ("MPP" series) but the part numbers carry the variant marker
        # — different SKUs, different IDs.
        a = compute_product_id("Parker", "MPP-1152C", None, "MPP")
        b = compute_product_id("Parker", "MPJ-1152C", None, "MPP")
        assert a != b
