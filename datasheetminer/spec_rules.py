"""Spec-level validation rules for extracted product data.

Catches semantic errors that pass structural validation — wrong units on
fields (e.g. "rpm" on a voltage field), implausible magnitudes,
cross-field duplication where the LLM copied one field into another,
and unidentifiable products extracted from informational PDFs.

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
# Unit families — sets of units considered valid for a given physical quantity
# ---------------------------------------------------------------------------

VOLTAGE_UNITS = frozenset(
    {
        "V",
        "Vac",
        "Vdc",
        "Vrms",
        "VAC",
        "VDC",
        "VRMS",
    }
)
SPEED_UNITS = frozenset(
    {
        "rpm",
        "RPM",
        "rad/s",
        "rps",
    }
)
CURRENT_UNITS = frozenset(
    {
        "A",
        "Arms",
        "Adc",
        "ARMS",
        "mA",
    }
)
TORQUE_UNITS = frozenset(
    {
        "Nm",
        "N-m",
        "N·m",
        "mNm",
        "mN-m",
        "mN·m",
    }
)
POWER_UNITS = frozenset(
    {
        "W",
        "kW",
        "mW",
        "hp",
        "HP",
    }
)
RESISTANCE_UNITS = frozenset(
    {
        "Ω",
        "mΩ",
        "kΩ",
        "ohm",
        "ohms",
        "Ohm",
        "Ohms",
    }
)
INDUCTANCE_UNITS = frozenset(
    {
        "mH",
        "H",
        "μH",
        "uH",
        "nH",
    }
)
INERTIA_UNITS = frozenset(
    {
        "kg·cm²",
        "kg-cm²",
        "g·cm²",
        "g-cm²",
        "gcm²",
        "kgcm²",
        "kg·m²",
        "kgm²",
        "oz-in²",
        "oz·in²",
    }
)
FORCE_UNITS = frozenset(
    {
        "N",
        "kN",
        "mN",
        "lbf",
        "kgf",
    }
)


# ---------------------------------------------------------------------------
# Per-field rules: (valid_units, min_plausible, max_plausible)
#
# The range bounds are intentionally generous to avoid false positives.
# They catch order-of-magnitude errors (e.g. 4500 "V") not borderline
# values (e.g. 520 V on a 480-class motor).
# ---------------------------------------------------------------------------

FieldRule = tuple[frozenset[str], float, float]

FIELD_RULES: dict[str, FieldRule] = {
    # Voltage fields — motors/drives top out around 800 Vac, 1000 Vdc
    "rated_voltage": (VOLTAGE_UNITS, 1.0, 1500.0),
    "input_voltage": (VOLTAGE_UNITS, 1.0, 1500.0),
    # Speed
    "rated_speed": (SPEED_UNITS, 0.1, 300_000.0),
    "max_speed": (SPEED_UNITS, 0.1, 500_000.0),
    # Current
    "rated_current": (CURRENT_UNITS, 0.001, 10_000.0),
    "peak_current": (CURRENT_UNITS, 0.001, 20_000.0),
    # Torque
    "rated_torque": (TORQUE_UNITS, 0.0, 100_000.0),
    "peak_torque": (TORQUE_UNITS, 0.0, 200_000.0),
    # Power
    "rated_power": (POWER_UNITS, 0.0, 5_000_000.0),
    # Electrical
    "resistance": (RESISTANCE_UNITS, 0.0, 100_000.0),
    "inductance": (INDUCTANCE_UNITS, 0.0, 100_000.0),
    # Mechanical
    "rotor_inertia": (INERTIA_UNITS, 0.0, 10_000_000.0),
    "axial_load_force_rating": (FORCE_UNITS, 0.0, 1_000_000.0),
    "radial_load_force_rating": (FORCE_UNITS, 0.0, 1_000_000.0),
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

    # --- Per-field unit + range checks ---
    for field_name, (valid_units, min_val, max_val) in FIELD_RULES.items():
        raw = getattr(product, field_name, None)
        parsed = _parse_compact(raw)
        if parsed is None:
            continue

        values, unit = parsed

        # Wrong unit family
        if unit not in valid_units:
            msg = (
                f"[{part_id}] {field_name}: unit '{unit}' is not a valid "
                f"unit for this field (got '{raw}')"
            )
            logger.warning("Spec rule FAIL: %s", msg)
            violations.append(msg)
            setattr(product, field_name, None)
            continue  # skip range check — field is already nulled

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
