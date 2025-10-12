# AI-generated comment:
# This module defines the Pydantic models for representing motor data.
# The models are derived from the structure of the `schema/motor.json` file.
# By defining a strict data model, we can leverage Pydantic's data validation,
# serialization, and documentation capabilities. This approach ensures data consistency
# and provides a clear, maintainable structure for working with motor specifications.

from __future__ import annotations
from typing import Literal, Optional

from pydantic import BaseModel, Field

from datasheetminer.models.common import Datasheet, Dimensions, MinMaxUnit, ValueUnit


class Motor(BaseModel):
    """A Pydantic model representing the specifications of a motor."""

    item_id: str = Field(..., alias="_id")
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
    part_number: Optional[str] = None
    series: Optional[str] = None
    datasheet_url: Optional[Datasheet] = None
    input_voltage: Optional[MinMaxUnit] = None
    manufacturer: Optional[str] = None
    release_year: Optional[int] = None
    rated_speed: Optional[ValueUnit] = None
    rated_torque: Optional[ValueUnit] = None
    peak_torque: Optional[ValueUnit] = None
    rated_power: Optional[ValueUnit] = None
    encoder_feedback_support: Optional[str] = None
    poles: Optional[int] = None
    rated_current: Optional[ValueUnit] = None
    peak_current: Optional[ValueUnit] = None
    weight: Optional[ValueUnit] = None
    dimensions: Optional[Dimensions] = None
    voltage_constant: Optional[ValueUnit] = None
    torque_constant: Optional[ValueUnit] = None
    resistance: Optional[ValueUnit] = None
    inductance: Optional[ValueUnit] = None
    ip_rating: Optional[int] = None
    warranty: Optional[ValueUnit] = None
    rotor_inertia: Optional[ValueUnit] = None
