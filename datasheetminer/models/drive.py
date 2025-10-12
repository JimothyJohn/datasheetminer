# AI-generated comment:
# This module defines the Pydantic models for representing drive data.
# The models are derived from the structure of the `schema/drive.json` file.
# By defining a strict data model, we can leverage Pydantic's data validation,
# serialization, and documentation capabilities. This approach ensures data consistency
# and provides a clear, maintainable structure for working with drive specifications.

from __future__ import annotations

from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from datasheetminer.models.common import (
    Datasheet,
    Dimensions,
    MinMaxUnit,
    ValueUnit,
)


# AI-generated comment:
# The main `Drive` model definition. This class acts as a factory for creating
# validated drive data objects. It can be instantiated with data that conforms
# to the defined structure. Pydantic's `BaseModel` handles the parsing and
# validation. The `Field` function with an `alias` is used to map the JSON's `_id`
# field to a more Python-friendly `id` attribute.


class Drive(BaseModel):
    """A Pydantic model representing the specifications of a servo drive."""

    id: UUID = Field(..., alias="_id")
    type: Optional[Literal["servo", "variable frequency"]] = None
    part_number: Optional[str] = None
    series: Optional[str] = None
    datasheet_url: Optional[Datasheet] = None
    manufacturer: Optional[str] = None
    release_year: Optional[int] = None
    input_voltage: Optional[MinMaxUnit] = None
    input_voltage_frequency: Optional[List[ValueUnit]] = None
    input_voltage_phases: Optional[List[int]] = None
    rated_current: Optional[ValueUnit] = None
    peak_current: Optional[ValueUnit] = None
    output_power: Optional[ValueUnit] = None
    switching_frequency: Optional[List[ValueUnit]] = None
    dimensions: Optional[Dimensions] = None
    fieldbus: Optional[List[str]] = None
    control_modes: Optional[List[str]] = None
    encoder_feedback_support: Optional[List[str]] = None
    ethernet_ports: Optional[int] = None
    digital_inputs: Optional[int] = None
    digital_outputs: Optional[int] = None
    analog_inputs: Optional[int] = None
    analog_outputs: Optional[int] = None
    safety_features: Optional[List[str]] = None
    safety_rating: Optional[List[str]] = None
    approvals: Optional[List[str]] = None
    max_humidity: Optional[float] = None
    weight: Optional[ValueUnit] = None
    ip_rating: Optional[int] = None
    warranty: Optional[ValueUnit] = None
    max_ambient_temp: Optional[ValueUnit] = None
    min_ambient_temp: Optional[ValueUnit] = None
