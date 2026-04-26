"""Deterministic product ID generation.

Produces reproducible UUIDs from (manufacturer, part_number) or
(manufacturer, product_name) so the same product always gets the same
ID regardless of when or how many times it's extracted.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

PRODUCT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def normalize_string(s: Optional[str]) -> str:
    """Lowercase, strip non-alphanumeric — robust against formatting drift."""
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]", "", s.lower().strip())


def _strip_family_prefix(part_number_norm: str, family_norm: str) -> str:
    """Drop a leading family token from an already-normalized part number.

    Vendor catalogs frequently let the family prefix drift across pages —
    Parker's MPP catalog has the same physical motor listed as
    ``MPP-1152C``, ``MPP1152C``, and bare ``1152C`` on different pages.
    Without this strip, three independent ingests of the same PDF would
    write three rows with three different UUIDs. With this strip, all
    three collapse to one.

    We only strip when the prefix is *exactly* the family — short
    free-text prefixes that happen to overlap (e.g. a part number that
    legitimately starts with the family token followed by more letters)
    keep their full identity because the *post-strip* leftover would be
    too short to be a real SKU.
    """
    if not family_norm or not part_number_norm.startswith(family_norm):
        return part_number_norm
    leftover = part_number_norm[len(family_norm) :]
    # Only collapse if what's left looks like a SKU (≥3 chars, has a digit).
    # Otherwise we'd be munging a legitimate part number whose first
    # characters happen to spell the family.
    if len(leftover) >= 3 and any(c.isdigit() for c in leftover):
        return leftover
    return part_number_norm


def compute_product_id(
    manufacturer: str,
    part_number: Optional[str],
    product_name: Optional[str],
    product_family: Optional[str] = None,
) -> Optional[uuid.UUID]:
    """Return a deterministic UUID5 or None if inputs are too sparse.

    When ``product_family`` is supplied, a leading family token is
    stripped from the part number before hashing so identical SKUs that
    differ only by prefix punctuation collapse to one ID. See
    ``_strip_family_prefix`` for the safety constraint.
    """
    norm_mfg = normalize_string(manufacturer)
    norm_pn = normalize_string(part_number)
    norm_name = normalize_string(product_name)
    norm_family = normalize_string(product_family)

    if norm_pn and norm_family:
        norm_pn = _strip_family_prefix(norm_pn, norm_family)

    if norm_mfg and norm_pn:
        return uuid.uuid5(PRODUCT_NAMESPACE, f"{norm_mfg}:{norm_pn}")
    if norm_mfg and norm_name:
        return uuid.uuid5(PRODUCT_NAMESPACE, f"{norm_mfg}:{norm_name}")
    return None
