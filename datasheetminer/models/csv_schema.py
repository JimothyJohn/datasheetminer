"""CSV column schema for LLM extraction.

Replaces the old JSON `response_schema` approach: instead of sending a
JSON schema where every `ValueUnit` field collapses to `Optional[str]`
(leaving the LLM to guess which strings need `value;unit` formatting),
we expose a flat CSV header where the unit is baked into each column
name, e.g. `rated_current[A]`. The LLM emits plain numbers; the parser
reconstructs `value;unit` strings locally before Pydantic validation.

This eliminates the "value;unit bleeding into plain-string fields"
class of validation failure and cuts output tokens roughly in half
compared to JSON (no repeated keys, no null-fields overhead).
"""

from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import Any, List, Literal, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel

from datasheetminer.models.common import MinMaxUnit, ValueUnit


# Canonical unit per ValueUnit/MinMaxUnit field. The string on the right
# is written verbatim into the CSV column header AND used to reconstruct
# the `value;unit` string fed to Pydantic, so it MUST be a member of the
# valid-units frozenset in spec_rules.FIELD_RULES (for fields that have
# rules), otherwise spec validation will null the field out.
UNITS: dict[str, str] = {
    # --- ProductBase (inherited) ---
    "weight": "kg",
    "msrp": "USD",
    "warranty": "years",
    # --- Motor / Drive / ElectricCylinder (electrical) ---
    "rated_voltage": "V",
    "input_voltage": "V",
    "rated_current": "A",
    "peak_current": "A",
    "rated_power": "W",
    "output_power": "W",
    "rated_speed": "rpm",
    "max_speed": "rpm",
    "rated_torque": "Nm",
    "peak_torque": "Nm",
    "voltage_constant": "V/krpm",
    "torque_constant": "Nm/A",
    "resistance": "ohm",
    "inductance": "mH",
    "rotor_inertia": "kgcm²",
    "axial_load_force_rating": "N",
    "radial_load_force_rating": "N",
    "ambient_temp": "°C",
    # --- Gearhead ---
    "nominal_input_speed": "rpm",
    "max_input_speed": "rpm",
    "max_continuous_torque": "Nm",
    "max_peak_torque": "Nm",
    "backlash": "arcmin",
    "torsional_rigidity": "Nm/arcmin",
    "noise_level": "dB",
    "input_shaft_diameter": "mm",
    "output_shaft_diameter": "mm",
    "max_radial_load": "N",
    "max_axial_load": "N",
    "operating_temp": "°C",
    "service_life": "h",
    # --- ElectricCylinder ---
    "stroke": "mm",
    "max_push_force": "N",
    "max_pull_force": "N",
    "continuous_force": "N",
    "max_linear_speed": "mm/s",
    "linear_speed_at_rated_load": "mm/s",
    "positioning_repeatability": "mm",
    "lead_screw_pitch": "mm",
    # --- RobotArm (top-level only; nested sub-models are skipped) ---
    "payload": "kg",
    "reach": "mm",
    "pose_repeatability": "mm",
    "max_tcp_speed": "m/s",
}


# Fields excluded from the CSV schema because the application supplies them
# (either computed, user-provided context, or auto-generated identifiers).
EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {
        "product_id",
        "product_name",
        "product_type",
        "product_family",
        "manufacturer",
        "PK",
        "SK",
        # Computed/bookkeeping fields the LLM should never touch
        "datasheet_url",
        "pages",
    }
)


# Separator used to encode List[str] / List[int] fields in a single CSV cell.
LIST_SEP = "|"


@dataclass(frozen=True)
class ColumnSpec:
    """One column in the CSV the LLM will emit.

    header: the exact string the LLM must use as the column name.
    field_name: the target Pydantic field on the full model.
    kind: how to reconstruct the value before feeding it to Pydantic.
    unit: canonical unit for value/minmax kinds, else None.
    """

    header: str
    field_name: str
    kind: Literal["str", "int", "float", "bool", "list", "value", "min", "max"]
    unit: Optional[str] = None


def _unwrap_optional(annotation: Any) -> Any:
    """Strip outer Optional / Union[X, None] wrappers recursively.

    Keeps Annotated[...] aliases intact so they can be matched by identity
    against ValueUnit / MinMaxUnit.
    """
    while True:
        origin = get_origin(annotation)
        if origin is Union or origin is typing.Union:
            args = [a for a in get_args(annotation) if a is not type(None)]
            if len(args) == 1:
                annotation = args[0]
                continue
        break
    return annotation


def _is_list_of_str_or_int(annotation: Any) -> Optional[type]:
    """If annotation is Optional[List[str]] / List[int], return the inner type."""
    inner = _unwrap_optional(annotation)
    if get_origin(inner) in (list, List):
        args = get_args(inner)
        if len(args) == 1 and args[0] in (str, int):
            return args[0]
    return None


def _scalar_kind(annotation: Any) -> Optional[str]:
    """Classify a scalar annotation. Returns the ColumnSpec.kind or None."""
    inner = _unwrap_optional(annotation)

    # Literal[...] → treat as str
    if get_origin(inner) is Literal:
        return "str"

    # Strip Annotated[...] to reveal the underlying type.
    if get_origin(inner) is not None and hasattr(inner, "__metadata__"):
        inner = get_args(inner)[0]
        inner = _unwrap_optional(inner)

    if inner is str:
        return "str"
    if inner is int:
        return "int"
    if inner is float:
        return "float"
    if inner is bool:
        return "bool"

    return None


def build_columns(model_class: Type[BaseModel]) -> List[ColumnSpec]:
    """Build the flat CSV column list the LLM will see for one product type.

    Fields whose annotation can't be expressed as scalar CSV cells
    (nested BaseModel, List[BaseModel], List[ValueUnit], etc.) are silently
    skipped — callers can extract them later via a focused follow-up call.
    """
    columns: List[ColumnSpec] = []

    for name, field in model_class.model_fields.items():
        if name in EXCLUDED_FIELDS:
            continue

        annotation = _unwrap_optional(field.annotation)

        # ValueUnit → single numeric column with unit in header
        if annotation is ValueUnit:
            unit = UNITS.get(name)
            if unit is None:
                # No canonical unit defined: skip rather than emit a broken column.
                continue
            columns.append(
                ColumnSpec(
                    header=f"{name}[{unit}]",
                    field_name=name,
                    kind="value",
                    unit=unit,
                )
            )
            continue

        # MinMaxUnit → two numeric columns (min, max) sharing a unit
        if annotation is MinMaxUnit:
            unit = UNITS.get(name)
            if unit is None:
                continue
            columns.append(
                ColumnSpec(
                    header=f"{name}_min[{unit}]",
                    field_name=name,
                    kind="min",
                    unit=unit,
                )
            )
            columns.append(
                ColumnSpec(
                    header=f"{name}_max[{unit}]",
                    field_name=name,
                    kind="max",
                    unit=unit,
                )
            )
            continue

        # List[str] / List[int] → pipe-joined single cell
        list_inner = _is_list_of_str_or_int(annotation)
        if list_inner is not None:
            columns.append(
                ColumnSpec(
                    header=name,
                    field_name=name,
                    kind="list",
                    unit=None,
                )
            )
            continue

        # Plain scalar (str / int / float / bool / Literal)
        kind = _scalar_kind(annotation)
        if kind is not None:
            columns.append(
                ColumnSpec(
                    header=name,
                    field_name=name,
                    kind=kind,
                    unit=None,
                )
            )
            continue

        # Anything else (nested BaseModel, List[BaseModel], List[ValueUnit],
        # Dimensions, etc.) is not representable in flat CSV — skip.

    return columns


def header_row(columns: List[ColumnSpec]) -> str:
    """Render the CSV header string the LLM is instructed to emit."""
    return ",".join(col.header for col in columns)


def reconstruct_row(
    csv_row: dict[str, str], columns: List[ColumnSpec]
) -> dict[str, Any]:
    """Turn one parsed CSV row into kwargs for the full Pydantic model.

    Empty cells become None. `value`/`min`/`max` cells are rejoined into
    the `"value;unit"` / `"min-max;unit"` strings the existing
    ValueUnit/MinMaxUnit validators already know how to handle, keeping
    the spec_rules.py unit-family checks authoritative.
    """
    out: dict[str, Any] = {}
    # Track min/max pairs before we know whether both sides are present.
    range_parts: dict[str, dict[str, str]] = {}

    for col in columns:
        raw = csv_row.get(col.header, "")
        raw = raw.strip() if raw is not None else ""

        if raw == "":
            if col.kind in ("min", "max"):
                range_parts.setdefault(col.field_name, {})
            else:
                out.setdefault(col.field_name, None)
            continue

        # Strip thousand-separator commas from numeric fields so "1,500"
        # doesn't poison the value;unit compact string downstream.
        if col.kind in ("value", "min", "max", "int", "float"):
            raw = raw.replace(",", "")

        if col.kind == "str":
            out[col.field_name] = raw
        elif col.kind == "int":
            try:
                out[col.field_name] = int(float(raw))
            except ValueError:
                out[col.field_name] = None
        elif col.kind == "float":
            try:
                out[col.field_name] = float(raw)
            except ValueError:
                out[col.field_name] = None
        elif col.kind == "bool":
            out[col.field_name] = raw.lower() in ("true", "1", "yes", "y")
        elif col.kind == "list":
            items = [p.strip() for p in raw.split(LIST_SEP) if p.strip()]
            out[col.field_name] = items or None
        elif col.kind == "value":
            out[col.field_name] = f"{raw};{col.unit}"
        elif col.kind in ("min", "max"):
            range_parts.setdefault(col.field_name, {})[col.kind] = raw

    for field_name, parts in range_parts.items():
        unit = next(
            (
                c.unit
                for c in columns
                if c.field_name == field_name and c.kind in ("min", "max")
            ),
            None,
        )
        lo = parts.get("min")
        hi = parts.get("max")
        if lo and hi:
            out[field_name] = f"{lo}-{hi};{unit}"
        elif lo:
            out[field_name] = f"{lo};{unit}"
        elif hi:
            out[field_name] = f"{hi};{unit}"
        else:
            out.setdefault(field_name, None)

    return out
