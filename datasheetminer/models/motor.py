# AI-generated comment:
# This module defines the Pydantic models for representing motor data.
# The models are derived from the structure of the `schema/motor.json` file.
# By defining a strict data model, we can leverage Pydantic's data validation,
# serialization, and documentation capabilities. This approach ensures data consistency
# and provides a clear, maintainable structure for working with motor specifications.

from __future__ import annotations
from typing import Literal, Optional

from datasheetminer.models.common import MinMaxUnit, ValueUnit
from datasheetminer.models.product import ProductBase


class Motor(ProductBase):
    """A Pydantic model representing the specifications of a motor."""

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
    rated_voltage: Optional[MinMaxUnit] = None
    rated_speed: Optional[ValueUnit] = None
    rated_torque: Optional[ValueUnit] = None
    peak_torque: Optional[ValueUnit] = None
    rated_power: Optional[ValueUnit] = None
    encoder_feedback_support: Optional[str] = None
    poles: Optional[int] = None
    rated_current: Optional[ValueUnit] = None
    peak_current: Optional[ValueUnit] = None
    voltage_constant: Optional[ValueUnit] = None
    torque_constant: Optional[ValueUnit] = None
    resistance: Optional[ValueUnit] = None
    inductance: Optional[ValueUnit] = None
    ip_rating: Optional[int] = None
    rotor_inertia: Optional[ValueUnit] = None
