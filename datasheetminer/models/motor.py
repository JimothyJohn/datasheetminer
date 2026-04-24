# AI-generated comment:
# This module defines the Pydantic models for representing motor data.
# The models are derived from the structure of the `schema/motor.json` file.
# By defining a strict data model, we can leverage Pydantic's data validation,
# serialization, and documentation capabilities. This approach ensures data consistency
# and provides a clear, maintainable structure for working with motor specifications.

from __future__ import annotations
from typing import Literal, Optional

from datasheetminer.models.common import (
    Current,
    ForceRange,
    Inductance,
    Inertia,
    IpRating,
    Length,
    Power,
    Resistance,
    Speed,
    Torque,
    ValueUnit,
    VoltageRange,
)
from datasheetminer.models.product import ProductBase


class Motor(ProductBase):
    """A Pydantic model representing the specifications of a motor."""

    product_type: Literal["motor"] = "motor"
    type: Optional[
        Literal[
            "brushless dc",
            "brushed dc",
            "ac induction",
            "ac synchronous",
            "ac servo",
            "permanent magnet",
            "hybrid",
        ]
    ] = None
    series: Optional[str] = None
    rated_voltage: VoltageRange = None
    rated_speed: Speed = None
    max_speed: Speed = None
    rated_torque: Torque = None
    peak_torque: Torque = None
    rated_power: Power = None
    encoder_feedback_support: Optional[str] = None
    poles: Optional[int] = None
    rated_current: Current = None
    peak_current: Current = None
    # Compound units (V/krpm, Nm/A) don't belong to a single family — keep generic.
    voltage_constant: ValueUnit = None
    torque_constant: ValueUnit = None
    resistance: Resistance = None
    inductance: Inductance = None
    ip_rating: IpRating = None
    rotor_inertia: Inertia = None
    axial_load_force_rating: ForceRange = None
    radial_load_force_rating: ForceRange = None
    # Mechanical output — couples motor to a gearhead. frame_size is the
    # vendor flange designation (e.g. "60", "NEMA 23"); shaft_diameter is
    # the output shaft OD the gearhead input bore must match.
    shaft_diameter: Length = None
    frame_size: Optional[str] = None
