# AI-generated comment:
# This module defines common, reusable Pydantic models that are shared across
# different hardware component types, such as motors and drives.
# By centralizing these common models, we avoid code duplication and improve
# maintainability. This ensures a consistent data structure for shared attributes
# like dimensions, datasheets, and value/unit pairs.

from __future__ import annotations

from typing import List

from pydantic import BaseModel


# AI-generated comment:
# The following are reusable sub-models for common data structures.
# Creating these smaller, reusable models improves maintainability and readability.


class ValueUnit(BaseModel):
    """Represents a numeric value with a corresponding unit."""

    value: float
    unit: str


class MinMaxUnit(BaseModel):
    """Represents a min/max numeric range with a corresponding unit."""

    min: float
    max: float
    unit: str


class Dimensions(BaseModel):
    """Represents physical dimensions of an object."""

    width: float
    depth: float
    height: float
    unit: str


class Datasheet(BaseModel):
    """Represents information about a product datasheet."""

    url: str
    pages: List[int]
