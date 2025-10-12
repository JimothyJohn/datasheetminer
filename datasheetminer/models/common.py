# AI-generated comment:
# This module defines common, reusable Pydantic models that are shared across
# different hardware component types, such as motors and drives.
# By centralizing these common models, we avoid code duplication and improve
# maintainability. This ensures a consistent data structure for shared attributes
# like dimensions, datasheets, and value/unit pairs.

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, field_validator, model_validator


# AI-generated comment:
# The following are reusable sub-models for common data structures.
# Creating these smaller, reusable models improves maintainability and readability.


class ValueUnit(BaseModel):
    """Represents a numeric value with a corresponding unit."""

    value: Optional[float] = None
    unit: Optional[str] = None

    @field_validator("value")
    def check_value_greater_than_zero(cls, v: Optional[float]) -> Optional[float]:
        """Validate that the value is greater than zero."""
        if v is not None and v <= 0:
            return None
        return v


class MinMaxUnit(BaseModel):
    """Represents a min/max numeric range with a corresponding unit."""

    min: Optional[float] = None
    max: Optional[float] = None
    unit: Optional[str] = None

    @model_validator(mode="after")
    def check_max_ge_min(self) -> "MinMaxUnit":
        """Validate that max is greater than or equal to min."""
        if self.min is not None and self.max is not None and self.max < self.min:
            self.min = None
            self.max = None
        return self


class Dimensions(BaseModel):
    """Represents physical dimensions of an object."""

    width: Optional[float] = None
    depth: Optional[float] = None
    height: Optional[float] = None
    unit: Optional[str] = None


class Datasheet(BaseModel):
    """Represents information about a product datasheet."""

    url: Optional[str] = None
    pages: Optional[List[int]] = None
