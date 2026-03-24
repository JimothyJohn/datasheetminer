"""Unit normalization for datasheet specifications.

Converts common unit variants to canonical forms so that all products
store specs in consistent, comparable units. Unknown units pass through
unchanged.

Focused on the most common LLM extraction inconsistencies:
- Torque prefix/imperial variants → Nm
- Power prefix variants → W
- Current prefix variants → A
- Inertia prefix/imperial variants → kg·cm²
- Resistance text aliases → Ω
- Inductance prefix variants → mH
- Force prefix/imperial variants → N
- Temperature °F → °C

Intentionally excluded (too context-dependent):
- Length (m/in/cm/ft) — cable length in m vs shaft diameter in mm
- Frequency (kHz/MHz) — kHz is idiomatic for switching frequency
- Mass (lb/oz) — ambiguous without field context
- Voltage (mV/kV) — rare in practice, kV implies different equipment class
"""

from __future__ import annotations

import logging
import math
import re

logger: logging.Logger = logging.getLogger(__name__)


# Each entry: (canonical_unit, {alias: multiplier_to_canonical})
# multiplier means: canonical_value = raw_value * multiplier
UNIT_CONVERSIONS: dict[str, dict[str, float]] = {
    # --- Torque → Nm ---
    "Nm": {
        "mNm": 1e-3,
        "mnm": 1e-3,
        "μNm": 1e-6,
        "oz-in": 7.0615518e-3,
        "oz·in": 7.0615518e-3,
        "ozin": 7.0615518e-3,
        "lb-ft": 1.3558179,
        "lb·ft": 1.3558179,
        "lbft": 1.3558179,
        "lb-in": 0.1129848,
        "lb·in": 0.1129848,
        "lbin": 0.1129848,
        "kgf·cm": 0.0980665,
        "kgf.cm": 0.0980665,
        "kgfcm": 0.0980665,
        "kNm": 1e3,
    },
    # --- Power → W ---
    "W": {
        "mW": 1e-3,
        "kW": 1e3,
        "hp": 745.69987,
        "HP": 745.69987,
    },
    # --- Current → A ---
    "A": {
        "mA": 1e-3,
        "μA": 1e-6,
        "uA": 1e-6,
    },
    # --- Force → N ---
    "N": {
        "mN": 1e-3,
        "kN": 1e3,
        "lbf": 4.4482216,
        "kgf": 9.80665,
    },
    # --- Rotational speed → rpm ---
    "rpm": {
        "rad/s": 60.0 / (2.0 * math.pi),
        "rps": 60.0,
    },
    # --- Inertia → kg·cm² ---
    "kg·cm²": {
        "g·cm²": 1e-3,
        "gcm²": 1e-3,
        "g.cm²": 1e-3,
        "g·cm2": 1e-3,
        "gcm2": 1e-3,
        "kg·m²": 1e4,
        "kgm²": 1e4,
        "kg.m²": 1e4,
        "kg·m2": 1e4,
        "kgm2": 1e4,
        "oz-in²": 0.0720078,
        "oz·in²": 0.0720078,
        "oz-in2": 0.0720078,
        "oz·in2": 0.0720078,
    },
    # --- Inductance → mH ---
    "mH": {
        "H": 1e3,
        "μH": 1e-3,
        "uH": 1e-3,
        "nH": 1e-6,
    },
    # --- Resistance → Ω ---
    "Ω": {
        "mΩ": 1e-3,
        "kΩ": 1e3,
        "ohm": 1.0,
        "ohms": 1.0,
        "Ohm": 1.0,
        "Ohms": 1.0,
    },
    # --- Temperature → °C ---
    "°C": {
        "°F": None,  # special case, not a simple multiplier
    },
}

# Build reverse lookup: alias → (canonical_unit, multiplier)
_ALIAS_MAP: dict[str, tuple[str, float | None]] = {}
for _canonical, _aliases in UNIT_CONVERSIONS.items():
    for _alias, _multiplier in _aliases.items():
        _ALIAS_MAP[_alias] = (_canonical, _multiplier)


def _convert_temperature(value: float, from_unit: str) -> float:
    """Convert Fahrenheit to Celsius."""
    return (value - 32.0) * 5.0 / 9.0


def _round_converted(value: float) -> float:
    """Round converted values to avoid floating point noise.

    Keeps up to 6 significant figures.
    """
    if value == 0:
        return 0.0
    magnitude = math.floor(math.log10(abs(value)))
    precision = max(0, 5 - magnitude)
    return round(value, precision)


def normalize_unit(value_str: str, unit: str) -> tuple[str, str]:
    """Normalize a value+unit pair to canonical form.

    Args:
        value_str: The numeric value as a string (may contain non-numeric chars).
        unit: The unit string from the datasheet.

    Returns:
        Tuple of (possibly converted value string, canonical unit string).
        If the unit is unknown or already canonical, returns inputs unchanged.
    """
    unit_clean = unit.strip()

    # Already canonical or unknown — pass through
    if unit_clean not in _ALIAS_MAP:
        return value_str, unit_clean

    canonical, multiplier = _ALIAS_MAP[unit_clean]

    # Try to parse the value as a float for conversion
    try:
        raw_value = float(value_str)
    except (ValueError, TypeError):
        # Non-numeric value (e.g., "2+"), can't convert — pass through
        return value_str, unit_clean

    if multiplier is None:
        converted = _convert_temperature(raw_value, unit_clean)
    else:
        converted = raw_value * multiplier

    converted = _round_converted(converted)

    # Format: use int if it's a whole number, otherwise float
    if converted == int(converted) and abs(converted) < 1e12:
        converted_str = str(int(converted))
    else:
        converted_str = f"{converted:g}"

    logger.info(
        "Unit conversion: %s %s → %s %s",
        value_str,
        unit_clean,
        converted_str,
        canonical,
    )
    return converted_str, canonical


def normalize_value_unit(compact: str) -> str:
    """Normalize a 'value;unit' compact string in place.

    Args:
        compact: String in 'value;unit' format.

    Returns:
        Normalized 'value;unit' string with canonical units.
    """
    if ";" not in compact:
        return compact

    parts = compact.split(";", 1)
    if len(parts) != 2:
        return compact

    value_part, unit = parts

    # Handle range values like "20-40" or "-20-40"
    range_match = re.match(r"^(-?[\d.]+)-(-?[\d.]+)$", value_part)
    if range_match:
        min_str, max_str = range_match.groups()
        min_converted, canonical = normalize_unit(min_str, unit)
        max_converted, _ = normalize_unit(max_str, unit)
        return f"{min_converted}-{max_converted};{canonical}"

    # Single value
    converted_value, canonical = normalize_unit(value_part, unit)
    return f"{converted_value};{canonical}"
