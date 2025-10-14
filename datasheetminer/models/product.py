# AI-generated comment:
# This module defines a base Pydantic model for tangible products, encapsulating
# common attributes that are shared across different types of hardware like drives,
# motors, etc. By creating a common base model, we ensure consistency,
# reduce code duplication, and improve maintainability of product-related models.

from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from datasheetminer.models.common import Dimensions, ValueUnit


class ProductBase(BaseModel):
    """
    A base model for products with common attributes, designed for DynamoDB.

    This model uses a composite primary key (PK, SK) to align with DynamoDB's
    single-table design best practices.

    Attributes:
        PK: The Partition Key. Formatted as 'PRODUCT#<product_type>'.
        SK: The Sort Key. Formatted as 'PRODUCT#<product_id>'.
        product_id: The unique identifier (UUID) for the product.
    """

    model_config = {"populate_by_name": True}

    @computed_field
    @property
    def PK(self) -> str:
        return f"PRODUCT#{self.product_type.upper()}"

    @computed_field
    @property
    def SK(self) -> str:
        return f"PRODUCT#{self.product_id}"

    product_id: UUID = Field(default_factory=uuid4)
    product_type: str
    part_number: Optional[str] = None
    manufacturer: str
    datasheet_url: Optional[str] = None
    release_year: Optional[int] = None
    dimensions: Optional[Dimensions] = None
    weight: Optional[ValueUnit] = None
    msrp: Optional[ValueUnit] = None
    warranty: Optional[ValueUnit] = None
