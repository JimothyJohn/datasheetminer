# AI-generated comment:
# This module defines a base Pydantic model for tangible products, encapsulating
# common attributes that are shared across different types of hardware like drives,
# motors, etc. By creating a common base model, we ensure consistency,
# reduce code duplication, and improve maintainability of product-related models.

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from datasheetminer.models.common import Datasheet, Dimensions, ValueUnit


class ProductBase(BaseModel):
    """A base model for products with common attributes."""

    id: UUID = Field(..., alias="_id")
    part_number: Optional[str] = None
    manufacturer: Optional[str] = None
    datasheet_url: Optional[str] = None
    release_year: Optional[int] = None
    dimensions: Optional[Dimensions] = None
    weight: Optional[ValueUnit] = None
    msrp: Optional[ValueUnit] = None
    warranty: Optional[ValueUnit] = None
