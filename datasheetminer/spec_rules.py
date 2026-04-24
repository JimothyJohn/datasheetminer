"""Spec-level validation rules for extracted product data.

Catches semantic errors that pass structural validation:

- **Implausible magnitudes** (e.g. 4500 V on a motor rated_voltage).
- **Cross-field duplication** where the LLM copied one field into another.
- **Unidentifiable products** extracted from informational PDFs.

Wrong-unit rejection (e.g. "rpm" on a voltage field) used to live here
but now runs inside the per-quantity Pydantic aliases (``Voltage``,
``Current``, etc. in ``datasheetminer.models.common``). By the time
``validate_product`` sees a field, the validator has already nulled
wrong-family values.

Runs after Pydantic model validation but before quality scoring so that
nulled-out fields correctly reduce the quality score.
"""

from __future__ import annotations

import logging
import re
from typing import List

from datasheetminer.models.product import ProductBase

logger: logging.Logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-field magnitude rules: (min_plausible, max_plausible)
#
# The bounds are intentionally generous to avoid false positives; they
# catch order-of-magnitude errors (e.g. 4500 V on a 480-class motor),
# not borderline values. Unit-family is enforced upstream by the typed
# Pydantic aliases, so by the time we read a field the unit is already
# known-good and we only need to parse the numeric value.
# ---------------------------------------------------------------------------

FieldRule = tuple[float, float]

FIELD_RULES: dict[str, FieldRule] = {
    # Voltage fields — motors/drives top out around 800 Vac, 1000 Vdc
    "rated_voltage": (1.0, 1500.0),
    "input_voltage": (1.0, 1500.0),
    # Speed
    "rated_speed": (0.1, 300_000.0),
    "max_speed": (0.1, 500_000.0),
    # Current
    "rated_current": (0.001, 10_000.0),
    "peak_current": (0.001, 20_000.0),
    # Torque
    "rated_torque": (0.0, 100_000.0),
    "peak_torque": (0.0, 200_000.0),
    # Power
    "rated_power": (0.0, 5_000_000.0),
    # Electrical
    "resistance": (0.0, 100_000.0),
    "inductance": (0.0, 100_000.0),
    # Mechanical
    "rotor_inertia": (0.0, 10_000_000.0),
    "axial_load_force_rating": (0.0, 1_000_000.0),
    "radial_load_force_rating": (0.0, 1_000_000.0),
}


# Fields where the LLM is known to copy one into the other when
# the source PDF is ambiguous.  If value AND unit are identical,
# the first field (the less likely candidate) is nulled out.
DUPLICATE_PAIRS: list[tuple[str, str]] = [
    ("rated_voltage", "rated_speed"),
]


# ---------------------------------------------------------------------------
# Identity validation — reject products from informational/educational PDFs
# that don't describe a specific purchasable product.
#
# A product with no part_number AND a generic manufacturer is almost
# certainly not a real product.  Nulling all its spec fields ensures
# the quality filter rejects it (0% completeness).
# ---------------------------------------------------------------------------

GENERIC_MANUFACTURERS = frozenset(
    {
        "unknown",
        "n/a",
        "na",
        "none",
        "various",
        "generic",
        "unspecified",
        "",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_compact(compact: str | None) -> tuple[list[float], str] | None:
    """Parse a 'value;unit' or 'min-max;unit' compact string.

    Returns (list_of_numeric_values, unit) or None if unparseable.
    """
    if compact is None:
        return None

    parts = compact.split(";", 1)
    if len(parts) != 2:
        return None

    value_part, unit = parts[0].strip(), parts[1].strip()
    if not unit:
        return None

    # Range: "200-240" or "-20-40" (negative min)
    range_match = re.match(r"^(-?[\d.]+)-(-?[\d.]+)$", value_part)
    if range_match:
        try:
            values = [float(range_match.group(1)), float(range_match.group(2))]
        except ValueError:
            return None
    else:
        try:
            values = [float(value_part)]
        except ValueError:
            return None

    return values, unit


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _null_all_spec_fields(product: ProductBase) -> None:
    """Set every non-meta field on the product to None.

    This guarantees the product will fail even the lowest quality threshold,
    which is the intended outcome for unidentifiable products.
    """
    from datasheetminer.quality import spec_fields_for_model

    for field_name in spec_fields_for_model(type(product)):
        try:
            setattr(product, field_name, None)
        except (ValueError, TypeError):
            pass


def validate_product(product: ProductBase) -> list[str]:
    """Validate a single product's spec fields against domain rules.

    Invalid fields are set to None on the product model in-place.
    Returns a list of human-readable violation descriptions.
    """
    violations: list[str] = []
    part_id = product.part_number or product.product_name

    # --- Identity check: reject unidentifiable products ---
    # A product with no part_number from a generic/unknown manufacturer
    # is not a real product — it was likely extracted from an educational
    # or informational PDF.
    has_part_number = bool(product.part_number and product.part_number.strip())
    manufacturer_normalized = (product.manufacturer or "").strip().lower()
    is_generic_manufacturer = manufacturer_normalized in GENERIC_MANUFACTURERS

    if not has_part_number and is_generic_manufacturer:
        msg = (
            f"[{part_id}] Unidentifiable product: no part_number and "
            f"manufacturer is '{product.manufacturer}' — "
            f"likely not a real product datasheet"
        )
        logger.warning("Spec rule FAIL: %s", msg)
        violations.append(msg)
        _null_all_spec_fields(product)
        return violations  # no point checking individual fields

    # --- Per-field magnitude checks ---
    # Wrong-unit rejection already happened at Pydantic validation time
    # (see typed aliases in datasheetminer.models.common). Here we only
    # need to catch values that passed the unit check but are still
    # physically implausible.
    for field_name, (min_val, max_val) in FIELD_RULES.items():
        raw = getattr(product, field_name, None)
        parsed = _parse_compact(raw)
        if parsed is None:
            continue

        values, _unit = parsed

        # Implausible magnitude
        for v in values:
            if v < min_val or v > max_val:
                msg = (
                    f"[{part_id}] {field_name}: value {v} outside plausible "
                    f"range [{min_val}, {max_val}] (got '{raw}')"
                )
                logger.warning("Spec rule FAIL: %s", msg)
                violations.append(msg)
                setattr(product, field_name, None)
                break  # one bad value is enough to null the field

    # --- Cross-field duplication ---
    for field_a, field_b in DUPLICATE_PAIRS:
        val_a = getattr(product, field_a, None)
        val_b = getattr(product, field_b, None)
        if val_a is not None and val_b is not None and val_a == val_b:
            msg = (
                f"[{part_id}] {field_a} is identical to {field_b} "
                f"('{val_a}') — likely LLM copy error"
            )
            logger.warning("Spec rule FAIL: %s", msg)
            violations.append(msg)
            setattr(product, field_a, None)

    return violations


def validate_products(products: List[ProductBase]) -> List[ProductBase]:
    """Run spec validation on a list of products.

    Invalid fields are nulled in-place. Returns the same list (for chaining).
    Logs a summary of all violations found.
    """
    total_violations = 0
    for product in products:
        v = validate_product(product)
        total_violations += len(v)

    if total_violations:
        logger.warning(
            "Spec validation found %d violation(s) across %d product(s)",
            total_violations,
            len(products),
        )
    else:
        logger.info("Spec validation passed for all %d product(s)", len(products))

    return products
