# AI-generated comment:
# This module defines the Pydantic models for representing drive data.
# The models are derived from the structure of the `schema/drive.json` file.
# By defining a strict data model, we can leverage Pydantic's data validation,
# serialization, and documentation capabilities. This approach ensures data consistency
# and provides a clear, maintainable structure for working with drive specifications.

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .common import Datasheet, Dimensions, MinMaxUnit, ValueUnit


# AI-generated comment:
# The following are reusable sub-models for common data structures found in the drive schema.
# Creating these smaller, reusable models improves maintainability and readability.


class ValuesUnit(BaseModel):
    """Represents a list of numeric values with a corresponding unit."""

    values: List[float]
    unit: str


# AI-generated comment:
# The main `Drive` model definition. This class acts as a factory for creating
# validated drive data objects. It can be instantiated with data that conforms
# to the defined structure. Pydantic's `BaseModel` handles the parsing and
# validation. The `Field` function with an `alias` is used to map the JSON's `_id`
# field to a more Python-friendly `id` attribute.


class Drive(BaseModel):
    """A Pydantic model representing the specifications of a drive."""

    item_id: str = Field(..., alias="_id")
    type: str
    part_number: str
    series: str
    datasheet: Datasheet
    manufacturer: str
    release_year: int
    input_voltage: MinMaxUnit
    frequency: ValuesUnit
    phases: List[int]
    rated_current: ValueUnit
    peak_current: ValueUnit
    output_power: ValueUnit
    switching_frequency: ValuesUnit
    dimensions: Dimensions
    fieldbus: List[str]
    control_modes: List[str]
    encoder_feedback_support: List[str]
    ethernet_ports: int
    digital_inputs: int
    digital_outputs: int
    analog_inputs: int
    analog_outputs: int
    safety_features: List[str]
    safety_rating: List[str]
    approvals: List[str]
    humidity: float
    weight: ValueUnit
    ip_rating: int
    warranty: ValueUnit
    max_ambient_temp: ValueUnit
    min_ambient_temp: ValueUnit
