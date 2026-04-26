"""Merge per-page product extractions into consolidated records.

When the pipeline extracts specs one page at a time, the same product
may appear on multiple pages with partial fields filled. This module
groups by deterministic product ID, fills nulls across records, and
resolves conflicts by preferring the most-populated source record.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from specodex.ids import compute_product_id
from specodex.models.product import ProductBase

logger = logging.getLogger(__name__)

# Fields that accumulate (union) rather than pick-a-winner.
_UNION_FIELDS = frozenset({"pages"})

# Metadata fields that the merge step should not touch — they're
# injected by the caller after merge.
_SKIP_FIELDS = frozenset({"product_id", "PK", "SK"})


def _count_spec_fields(model: ProductBase) -> int:
    """Count non-null fields excluding metadata/bookkeeping."""
    count = 0
    for name in type(model).model_fields:
        if name in _SKIP_FIELDS or name in _UNION_FIELDS:
            continue
        if getattr(model, name, None) is not None:
            count += 1
    return count


def _merge_group(group: List[ProductBase]) -> ProductBase:
    """Merge a list of records that share the same product ID."""
    if len(group) == 1:
        return group[0]

    ranked = sorted(group, key=_count_spec_fields, reverse=True)
    base = ranked[0]
    base_data: Dict[str, Any] = base.model_dump()

    for field_name in type(base).model_fields:
        if field_name in _SKIP_FIELDS:
            continue

        if field_name in _UNION_FIELDS:
            merged: List[Any] = []
            seen: set = set()
            for record in group:
                vals = getattr(record, field_name, None) or []
                for v in vals:
                    if v not in seen:
                        seen.add(v)
                        merged.append(v)
            base_data[field_name] = sorted(merged) if merged else None
            continue

        if base_data.get(field_name) is not None:
            continue

        for other in ranked[1:]:
            val = getattr(other, field_name, None)
            if val is not None:
                base_data[field_name] = (
                    val.model_dump() if hasattr(val, "model_dump") else val
                )
                break

    return type(base).model_validate(base_data)


def merge_per_page_products(products: List[ProductBase]) -> List[ProductBase]:
    """Group products by deterministic ID and merge partial records.

    Products without a resolvable ID pass through un-merged.
    """
    groups: Dict[Optional[str], List[ProductBase]] = defaultdict(list)
    no_id: List[ProductBase] = []

    for product in products:
        pid = compute_product_id(
            product.manufacturer,
            product.part_number,
            product.product_name,
            getattr(product, "product_family", None),
        )
        if pid is None:
            no_id.append(product)
        else:
            groups[str(pid)].append(product)

    merged: List[ProductBase] = []
    for pid_str, group in groups.items():
        result = _merge_group(group)
        if len(group) > 1:
            logger.info(
                "Merged %d per-page records for product %s (pages %s)",
                len(group),
                getattr(result, "part_number", None) or result.product_name,
                result.pages,
            )
        merged.append(result)

    merged.extend(no_id)
    return merged
