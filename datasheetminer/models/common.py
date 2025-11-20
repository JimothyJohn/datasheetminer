# AI-generated comment:
# This module defines common, reusable Pydantic models that are shared across
# different hardware component types, such as motors and drives.
# By centralizing these common models, we avoid code duplication and improve
# maintainability. This ensures a consistent data structure for shared attributes
# like dimensions, datasheets, and value/unit pairs.

from __future__ import annotations

from typing import Annotated, List, Optional

from pydantic import AfterValidator, BaseModel


# AI-generated comment:
# The following are reusable sub-models for common data structures.
# Creating these smaller, reusable models improves maintainability and readability.


class Datasheet(BaseModel):
    """Represents information about a product datasheet."""

    url: Optional[str] = None
    pages: Optional[List[int]] = None


def validate_value_unit_str(v: str) -> str:
    if v is None:
        return v
    parts = v.split(";")
    if len(parts) != 2:
        raise ValueError('must be in "value;unit" format')
    try:
        float(parts[0])
    except (ValueError, TypeError):
        raise ValueError("first part must be a number")
    if not parts[1]:
        raise ValueError("unit cannot be empty")
    return v


ValueUnit = Annotated[Optional[str], AfterValidator(validate_value_unit_str)]


def validate_min_max_unit_str(v: str) -> str:
    if v is None:
        return v
    parts = v.split(";")
    if len(parts) != 2:
        raise ValueError('must be in "range;unit" format')

    range_part = parts[0]
    range_values = range_part.split("-")
    if len(range_values) > 2 or (len(range_values) == 1 and not range_values[0]):
        raise ValueError(f'Invalid range format: "{range_part}"')

    for val_str in range_values:
        if val_str:  # handles cases like "-200" or "100-"
            try:
                float(val_str)
            except (ValueError, TypeError):
                raise ValueError(f'Invalid number in range: "{val_str}"')

    if not parts[1]:
        raise ValueError("unit cannot be empty")
    return v


MinMaxUnit = Annotated[Optional[str], AfterValidator(validate_min_max_unit_str)]
