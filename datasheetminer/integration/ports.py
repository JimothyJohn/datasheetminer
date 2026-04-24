"""Port schemas — the shape of each integration interface.

A port is a physical-quantity bundle that a product exposes at one of
its interfaces. Ports are normalised (unit-aware via ValueUnit /
MinMaxUnit) so compatibility checks compare apples to apples regardless
of vendor.

Design notes:

- Ports are pure data; they hold no reference back to the parent
  product. That keeps them composable and trivial to serialise.
- ``direction`` distinguishes the two sides of every physical interface
  — a motor's shaft_output mates with a gearhead's shaft_input, never
  two inputs or two outputs.
- Fields are Optional because datasheets rarely publish the full
  spec. Compat checks skip fields that are missing on either side and
  downgrade the result to ``partial`` rather than ``fail``.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel

from datasheetminer.models.common import MinMaxUnit, ValueUnit


Direction = Literal["input", "output"]
CurrentKind = Literal["ac", "dc"]


class ElectricalPowerPort(BaseModel):
    """Main power interface — mains → drive, drive → motor, contactor → load."""

    kind: Literal["electrical_power"] = "electrical_power"
    direction: Direction
    # Accepts ValueUnit for a single rating, or MinMaxUnit for a range
    # (e.g. drive input 380-480 V). Consumers upcast via the compat layer.
    voltage: Optional[Union[ValueUnit, MinMaxUnit]] = None
    current: Optional[ValueUnit] = None
    power: Optional[ValueUnit] = None
    phases: Optional[int] = None
    frequency: Optional[Union[ValueUnit, MinMaxUnit]] = None
    ac_dc: Optional[CurrentKind] = None


class MechanicalShaftPort(BaseModel):
    """Rotary shaft — motor output couples to gearhead input."""

    kind: Literal["mechanical_shaft"] = "mechanical_shaft"
    direction: Direction
    shaft_diameter: Optional[ValueUnit] = None
    frame_size: Optional[str] = None
    max_speed: Optional[ValueUnit] = None
    rated_torque: Optional[ValueUnit] = None
    peak_torque: Optional[ValueUnit] = None


class FeedbackPort(BaseModel):
    """Encoder / position feedback.

    Motors expose exactly one type (``provides``); drives accept one of
    a list (``supports``). The compat check verifies membership.
    """

    kind: Literal["feedback"] = "feedback"
    direction: Direction
    provides: Optional[str] = None  # motor side — single encoder type
    supports: Optional[list[str]] = None  # drive side — list of accepted types


class FieldbusPort(BaseModel):
    """Industrial fieldbus — drive ↔ PLC, e-cylinder ↔ PLC."""

    kind: Literal["fieldbus"] = "fieldbus"
    direction: Direction
    protocols: Optional[list[str]] = None


class CoilPort(BaseModel):
    """Contactor coil — control-circuit voltage from a PLC or panel."""

    kind: Literal["coil"] = "coil"
    direction: Direction
    voltage_range: Optional[MinMaxUnit] = None
    voltage_options: Optional[list[str]] = None
    ac_dc: Optional[CurrentKind] = None


Port = Union[
    ElectricalPowerPort,
    MechanicalShaftPort,
    FeedbackPort,
    FieldbusPort,
    CoilPort,
]
