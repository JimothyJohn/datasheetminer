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


def compute_product_id(
    manufacturer: str,
    part_number: Optional[str],
    product_name: Optional[str],
) -> Optional[uuid.UUID]:
    """Return a deterministic UUID5 or None if inputs are too sparse."""
    norm_mfg = normalize_string(manufacturer)
    norm_pn = normalize_string(part_number)
    norm_name = normalize_string(product_name)

    if norm_mfg and norm_pn:
        return uuid.uuid5(PRODUCT_NAMESPACE, f"{norm_mfg}:{norm_pn}")
    if norm_mfg and norm_name:
        return uuid.uuid5(PRODUCT_NAMESPACE, f"{norm_mfg}:{norm_name}")
    return None
