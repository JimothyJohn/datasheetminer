# AI-generated comment:
# This module defines common, reusable Pydantic models that are shared across
# different hardware component types, such as motors and drives.
# By centralizing these common models, we avoid code duplication and improve
# maintainability. This ensures a consistent data structure for shared attributes
# like dimensions, datasheets, and value/unit pairs.

from __future__ import annotations


from typing import Annotated, Any, List, Literal, Optional

from pydantic import AfterValidator, BeforeValidator, BaseModel


# AI-generated comment:
# The following are reusable sub-models for common data structures.
# Creating these smaller, reusable models improves maintainability and readability.


ProductType = Literal[
    "motor",
    "drive",
    "gearhead",
    "robot_arm",
    "factory",
    "datasheet"
]



class Datasheet(BaseModel):
    """Represents information about a product datasheet."""

    url: Optional[str] = None
    pages: Optional[List[int]] = None


def validate_value_unit_str(v: str) -> str:
    if v is None:
        return v
    parts = v.split(";")
    if len(parts) != 2:
        # Try to recover if it's just a number string? No, strict format is safer for now,
        # but let's allow the LLM's "2+;Years" by relaxing the float check.
        raise ValueError('must be in "value;unit" format')
    
    # We used to enforce float(parts[0]), but "2+" or "approx 5" might occur.
    # Let's just ensure it's not empty.
    if not parts[0].strip():
        raise ValueError("value part cannot be empty")
        
    if not parts[1]:
        raise ValueError("unit cannot be empty")
    return v


def handle_value_unit_input(v: Any) -> Any:
    if isinstance(v, dict):
        val = v.get("value")
        unit = v.get("unit")
        if val is not None and unit is not None:
            # Clean value
            val = str(val).strip().strip("+~><")
            return f"{val};{unit}"
    elif isinstance(v, str) and ";" not in v:
        # Try to handle space-separated "value unit"
        parts = v.strip().split()
        if len(parts) == 2:
            val = parts[0].strip().strip("+~><")
            return f"{val};{parts[1]}"
    elif isinstance(v, str) and ";" in v:
        # Clean value in existing "val;unit" string
        parts = v.split(";")
        if len(parts) == 2:
             val = parts[0].strip().strip("+~><")
             return f"{val};{parts[1]}"
    return v

ValueUnit = Annotated[Optional[str], BeforeValidator(handle_value_unit_input), AfterValidator(validate_value_unit_str)]


def validate_min_max_unit_str(v: str) -> str:
    if v is None:
        return v
    parts = v.split(";")
    if len(parts) != 2:
        raise ValueError('must be in "range;unit" format')

    range_part = parts[0]
    # Handle " to " which LLM sometimes outputs
    range_part = range_part.replace(" to ", "-")
    
    # If it's still just a single value like "20", treat it as a range "20-20" or just accept it?
    # The regex in DynamoDBClient._parse_compact_units handles "val" and "min-max".
    # So we just need to ensure it looks reasonable.
    
    # We won't strictly validate the numbers here to allow for things like "-20" (negative)
    # which split("-") makes messy.
    # Just ensure it's not empty.
    if not range_part.strip():
         raise ValueError("range part cannot be empty")

    if not parts[1]:
        raise ValueError("unit cannot be empty")
        
    # Reconstruct with cleaned range_part
    return f"{range_part};{parts[1]}"


def handle_min_max_unit_input(v: Any) -> Any:
    if isinstance(v, dict):
        min_val = v.get("min")
        max_val = v.get("max")
        unit = v.get("unit")
        if unit is not None:
            if min_val is not None and max_val is not None:
                return f"{min_val}-{max_val};{unit}"
            elif min_val is not None:
                return f"{min_val};{unit}"
            elif max_val is not None:
                return f"{max_val};{unit}"
    return v

MinMaxUnit = Annotated[Optional[str], BeforeValidator(handle_min_max_unit_input), AfterValidator(validate_min_max_unit_str)]
