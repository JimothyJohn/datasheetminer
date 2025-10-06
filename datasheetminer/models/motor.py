# AI-generated comment:
# This module defines the Pydantic models for representing motor data.
# The models are derived from the structure of the `schema/motor.json` file.
# By defining a strict data model, we can leverage Pydantic's data validation,
# serialization, and documentation capabilities. This approach ensures data consistency
# and provides a clear, maintainable structure for working with motor specifications.

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .common import Datasheet, Dimensions, MinMaxUnit, ValueUnit


# AI-generated comment:
# The main `Motor` model definition. This class acts as a factory for creating
# validated motor data objects. It can be instantiated with data that conforms
# to the defined structure. Pydantic's `BaseModel` handles the parsing and
# validation. The `Field` function with an `alias` is used to map the JSON's `_id`
# field to a more Python-friendly `id` attribute.


class Motor(BaseModel):
    """A Pydantic model representing the specifications of a motor."""

    item_id: str = Field(..., alias="_id")
    type: str
    part_number: str
    series: str
    datasheet: Datasheet
    input_voltage: MinMaxUnit
    manufacturer: str
    release_year: int
    rated_speed: ValueUnit
    rated_torque: ValueUnit
    peak_torque: ValueUnit
    rated_power: ValueUnit
    encoder_feedback_support: str
    poles: int
    rated_current: ValueUnit
    peak_current: ValueUnit
    weight: ValueUnit
    dimensions: Dimensions
    voltage_constant: ValueUnit
    torque_constant: ValueUnit
    resistance: ValueUnit
    inductance: ValueUnit
    ip_rating: int
    warranty: ValueUnit
    rotor_inertia: ValueUnit
