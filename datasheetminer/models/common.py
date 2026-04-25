"""Shared Pydantic types for product models.

Holds the ``ValueUnit`` / ``MinMaxUnit`` compact-string aliases, the
per-quantity narrowed variants (``Voltage``, ``Current``, ...), the
``IpRating`` coercer, and the ``ProductType`` literal.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated, Any, List, Literal, Optional

from pydantic import AfterValidator, BaseModel, BeforeValidator

from datasheetminer.units import normalize_value_unit

_logger = logging.getLogger(__name__)


ProductType = Literal[
    "motor",
    "drive",
    "gearhead",
    "robot_arm",
    "factory",
    "datasheet",
    "contactor",
    "electric_cylinder",
    "linear_actuator",
]


class Datasheet(BaseModel):
    """Represents information about a product datasheet."""

    url: Optional[str] = None
    pages: Optional[List[int]] = None


def _normalize_compact_str(v: str) -> str:
    """Normalize units in a validated compact string to canonical forms."""
    if v is None:
        return v
    return normalize_value_unit(v)


def validate_value_unit_str(v: str) -> str:
    if v is None:
        return v
    parts = v.split(";")
    if len(parts) != 2:
        # Reject multi-semicolon strings at the writer. The reader's regex
        # (`_parse_compact_units`) greedily captures the unit via `(.*)`, so
        # "1;2;V" would read back as {value=1, unit="2;V"} — see
        # todo/fundamental-flaws.md, flaw #1. Exactly one semicolon is the
        # invariant; anything else is malformed LLM output.
        raise ValueError('must be in "value;unit" format (exactly one semicolon)')

    # We used to enforce float(parts[0]), but "2+" or "approx 5" might occur.
    # Let's just ensure it's not empty.
    if not parts[0].strip():
        raise ValueError("value part cannot be empty")

    if not parts[1]:
        raise ValueError("unit cannot be empty")
    return v


def handle_value_unit_input(v: Any) -> Any:
    if isinstance(v, dict):
        # Gemini sometimes emits {} for fields it has no value for. Drop these
        # before any key probing so the str validator doesn't crash on a dict.
        if not v:
            return None
        val = v.get("value")
        unit = v.get("unit")
        if val is not None and unit is not None:
            # Clean value
            val = str(val).strip().strip("+~><")
            return f"{val};{unit}"
        # Handle min/max dicts stored as ValueUnit (e.g., payload stored as {min, max, unit})
        min_val = v.get("min")
        max_val = v.get("max")
        if unit is not None and (min_val is not None or max_val is not None):
            if min_val is not None and max_val is not None:
                return f"{min_val}-{max_val};{unit}"
            elif min_val is not None:
                return f"{min_val};{unit}"
            elif max_val is not None:
                return f"{max_val};{unit}"
        # Unit-only dicts ({"unit": "V"}) with no numeric payload are bogus
        # LLM output; drop them instead of crashing the string validator.
        if unit is not None and val is None and min_val is None and max_val is None:
            return None
    elif isinstance(v, str) and ";" not in v:
        # Try to handle space-separated "value unit"
        parts = v.strip().split()
        if len(parts) == 2:
            val = parts[0].strip().strip("+~><")
            return f"{val};{parts[1]}"
    elif isinstance(v, str) and ";" in v:
        # Clean value in existing "val;unit" string
        parts = v.split(";")
        if len(parts) == 2:
            val = parts[0].strip().strip("+~><")
            return f"{val};{parts[1]}"
    return v


@dataclass(frozen=True)
class ValueUnitMarker:
    """Marker attached to a ValueUnit-family field's metadata.

    Pydantic strips the outer ``Annotated`` wrapper off ``field.annotation``,
    so identity checks against ``ValueUnit`` / ``Voltage`` / ... fail. Each
    alias carries this marker as a metadata element; ``llm_schema.py``
    scans ``field.metadata`` to identify ValueUnit-family fields and
    their quantity.
    """

    family: "UnitFamily | None" = None


@dataclass(frozen=True)
class MinMaxUnitMarker:
    """Marker for MinMaxUnit-family fields — see ``ValueUnitMarker``."""

    family: "UnitFamily | None" = None


ValueUnit = Annotated[
    Optional[str],
    BeforeValidator(handle_value_unit_input),
    AfterValidator(validate_value_unit_str),
    AfterValidator(_normalize_compact_str),
    ValueUnitMarker(),
]


def validate_min_max_unit_str(v: str) -> str:
    if v is None:
        return v
    parts = v.split(";")
    if len(parts) != 2:
        # Same invariant as validate_value_unit_str — unit cannot contain ';'.
        raise ValueError('must be in "range;unit" format (exactly one semicolon)')

    range_part = parts[0]
    # Handle " to " which LLM sometimes outputs
    range_part = range_part.replace(" to ", "-")

    # If it's still just a single value like "20", treat it as a range "20-20" or just accept it?
    # The regex in DynamoDBClient._parse_compact_units handles "val" and "min-max".
    # So we just need to ensure it looks reasonable.

    # We won't strictly validate the numbers here to allow for things like "-20" (negative)
    # which split("-") makes messy.
    # Just ensure it's not empty.
    if not range_part.strip():
        raise ValueError("range part cannot be empty")

    if not parts[1]:
        raise ValueError("unit cannot be empty")

    # Reconstruct with cleaned range_part
    return f"{range_part};{parts[1]}"


def handle_min_max_unit_input(v: Any) -> Any:
    if isinstance(v, dict):
        if not v:
            return None
        min_val = v.get("min")
        max_val = v.get("max")
        val = v.get("value")
        unit = v.get("unit")
        if unit is not None:
            if min_val is not None and max_val is not None:
                return f"{min_val}-{max_val};{unit}"
            elif min_val is not None:
                return f"{min_val};{unit}"
            elif max_val is not None:
                return f"{max_val};{unit}"
            # Handle {value, unit} dicts (stored by TypeScript backend as single-value)
            elif val is not None:
                return f"{val};{unit}"
        # Gemini occasionally emits unit-only dicts like {"unit": "V"} with no
        # min/max/value; treat as absent instead of letting the downstream
        # string validator AttributeError on a dict.
        if unit is not None and min_val is None and max_val is None and val is None:
            return None
    return v


MinMaxUnit = Annotated[
    Optional[str],
    BeforeValidator(handle_min_max_unit_input),
    AfterValidator(validate_min_max_unit_str),
    AfterValidator(_normalize_compact_str),
    MinMaxUnitMarker(),
]


def _coerce_ip_rating(v: Any) -> Any:
    """Coerce legacy IP-rating shapes to a plain int.

    Accepts:
        int  54              → 54
        str  "54"            → 54
        str  "IP54" / "ip54" → 54
        dict {"value": 54}   → 54 (legacy TS serialisation)
    Anything else becomes None so Pydantic validation doesn't crash on
    a dict-shaped LLM mis-extraction.
    """
    if v is None or isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip().upper().removeprefix("IP").strip()
        try:
            return int(s)
        except ValueError:
            return None
    if isinstance(v, dict):
        for key in ("value", "min"):
            inner = v.get(key)
            if inner is not None:
                return _coerce_ip_rating(inner)
        return None
    return v


IpRating = Annotated[Optional[int], BeforeValidator(_coerce_ip_rating)]


# ---------------------------------------------------------------------------
# Per-quantity ValueUnit / MinMaxUnit aliases
#
# ``ValueUnit`` and ``MinMaxUnit`` above are untyped — any unit string
# parses. Fields where the quantity is known (a voltage, a current) use
# the narrowed aliases below, which reject wrong-family units at Pydantic
# validation time (e.g. "5;rpm" on a ``Current`` field becomes None).
#
# Conventions:
#   - Canonical unit matches ``datasheetminer/units.py`` ``UNIT_CONVERSIONS``
#     so normalisation and family-check agree.
#   - Each family lists every form the LLM might emit — both aliases that
#     normalise to the canonical (mA → A) and aliases that pass through
#     unchanged (Vac, Arms, ohm).
#   - Fields whose quantity is fuzzy (``warranty``, ``msrp``, ``backlash``
#     in arcmin, compound units like V/krpm) stay on plain ValueUnit.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnitFamily:
    """A physical-quantity family: canonical unit + accepted aliases."""

    name: str
    canonical: str
    accepted: frozenset[str]

    def contains(self, unit: str) -> bool:
        return unit == self.canonical or unit in self.accepted


VOLTAGE = UnitFamily(
    "voltage",
    "V",
    frozenset({"V", "Vac", "Vdc", "Vrms", "VAC", "VDC", "VRMS", "mV", "kV"}),
)
CURRENT = UnitFamily(
    "current",
    "A",
    frozenset({"A", "mA", "μA", "uA", "Arms", "Adc", "ARMS"}),
)
POWER = UnitFamily(
    "power",
    "W",
    frozenset({"W", "mW", "kW", "hp", "HP", "VA", "kVA"}),
)
TORQUE = UnitFamily(
    "torque",
    "Nm",
    frozenset(
        {
            "Nm",
            "N-m",
            "N·m",
            "mNm",
            "mN-m",
            "mN·m",
            "μNm",
            "oz-in",
            "oz·in",
            "ozin",
            "lb-ft",
            "lb·ft",
            "lbft",
            "lb-in",
            "lb·in",
            "lbin",
            "kgf·cm",
            "kgf.cm",
            "kgfcm",
            "kNm",
        }
    ),
)
SPEED = UnitFamily(
    "speed",
    "rpm",
    frozenset({"rpm", "RPM", "rad/s", "rps"}),
)
FORCE = UnitFamily(
    "force",
    "N",
    frozenset({"N", "mN", "kN", "lbf", "kgf"}),
)
LENGTH = UnitFamily(
    "length",
    "mm",
    frozenset({"mm", "m", "cm", "in", "inch", "ft", "μm", "um"}),
)
MASS = UnitFamily(
    "mass",
    "kg",
    frozenset({"kg", "g", "lb", "oz"}),
)
TEMPERATURE = UnitFamily(
    "temperature",
    "°C",
    frozenset({"°C", "C", "°F", "F", "K"}),
)
FREQUENCY = UnitFamily(
    "frequency",
    "Hz",
    frozenset({"Hz", "kHz", "MHz", "GHz"}),
)
INERTIA = UnitFamily(
    "inertia",
    "kg·cm²",
    frozenset(
        {
            "kg·cm²",
            "kg-cm²",
            "kgcm²",
            "g·cm²",
            "g-cm²",
            "gcm²",
            "g.cm²",
            "g·cm2",
            "gcm2",
            "kg·m²",
            "kg-m²",
            "kgm²",
            "kg.m²",
            "kg·m2",
            "kgm2",
            "oz-in²",
            "oz·in²",
            "oz-in2",
            "oz·in2",
        }
    ),
)
RESISTANCE = UnitFamily(
    "resistance",
    "Ω",
    frozenset({"Ω", "mΩ", "kΩ", "ohm", "ohms", "Ohm", "Ohms"}),
)
INDUCTANCE = UnitFamily(
    "inductance",
    "mH",
    frozenset({"mH", "H", "μH", "uH", "nH"}),
)


def _enforce_family(family: UnitFamily):
    """AfterValidator that nulls values whose unit isn't in ``family``.

    Runs after ``_normalize_compact_str`` has already converted aliases
    in ``UNIT_CONVERSIONS`` to their canonical form, so the unit we see
    here is either canonical or an un-normalised family member (Vac,
    Arms, ohm). Anything outside the family is a wrong-family
    extraction — return None so the quality filter can reject the row.
    """

    def _check(v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if ";" not in v:
            return None
        _, unit = v.split(";", 1)
        if family.contains(unit):
            return v
        _logger.debug(
            "rejecting %s value '%s' — unit '%s' not in family",
            family.name,
            v,
            unit,
        )
        return None

    return _check


def _typed_value_unit(family: UnitFamily):
    """Build a ValueUnit-shape Annotated alias narrowed to one quantity."""
    return Annotated[
        Optional[str],
        BeforeValidator(handle_value_unit_input),
        AfterValidator(validate_value_unit_str),
        AfterValidator(_normalize_compact_str),
        AfterValidator(_enforce_family(family)),
        ValueUnitMarker(family=family),
    ]


def _typed_min_max_unit(family: UnitFamily):
    """Build a MinMaxUnit-shape Annotated alias narrowed to one quantity."""
    return Annotated[
        Optional[str],
        BeforeValidator(handle_min_max_unit_input),
        AfterValidator(validate_min_max_unit_str),
        AfterValidator(_normalize_compact_str),
        AfterValidator(_enforce_family(family)),
        MinMaxUnitMarker(family=family),
    ]


# --- Scalar quantity types ---------------------------------------------------
Voltage = _typed_value_unit(VOLTAGE)
Current = _typed_value_unit(CURRENT)
Power = _typed_value_unit(POWER)
Torque = _typed_value_unit(TORQUE)
Speed = _typed_value_unit(SPEED)
Force = _typed_value_unit(FORCE)
Length = _typed_value_unit(LENGTH)
Mass = _typed_value_unit(MASS)
Temperature = _typed_value_unit(TEMPERATURE)
Frequency = _typed_value_unit(FREQUENCY)
Inertia = _typed_value_unit(INERTIA)
Resistance = _typed_value_unit(RESISTANCE)
Inductance = _typed_value_unit(INDUCTANCE)


# --- Range quantity types ----------------------------------------------------
VoltageRange = _typed_min_max_unit(VOLTAGE)
CurrentRange = _typed_min_max_unit(CURRENT)
TemperatureRange = _typed_min_max_unit(TEMPERATURE)
FrequencyRange = _typed_min_max_unit(FREQUENCY)
ForceRange = _typed_min_max_unit(FORCE)


def find_value_unit_marker(metadata) -> Optional[ValueUnitMarker]:
    """Return the ValueUnitMarker in a Pydantic FieldInfo.metadata, if any."""
    for m in metadata or ():
        if isinstance(m, ValueUnitMarker):
            return m
    return None


def find_min_max_unit_marker(metadata) -> Optional[MinMaxUnitMarker]:
    """Return the MinMaxUnitMarker in a Pydantic FieldInfo.metadata, if any."""
    for m in metadata or ():
        if isinstance(m, MinMaxUnitMarker):
            return m
    return None
