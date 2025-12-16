# This module defines the Pydantic models for representing manufacturer data.

from __future__ import annotations

from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


from datasheetminer.models.common import ProductType


class Manufacturer(BaseModel):
    """
    A Pydantic model representing a manufacturer of industrial equipment.
    Designed for DynamoDB single-table design.
    """

    model_config = {"populate_by_name": True}

    @computed_field
    def PK(self) -> str:
        return "MANUFACTURER"

    @computed_field
    def SK(self) -> str:
        return f"MANUFACTURER#{self.id}"

    id: UUID = Field(
        default_factory=uuid4, description="Unique identifier (auto-generated)"
    )
    name: str = Field(..., description="Name of the manufacturer")
    website: Optional[str] = Field(None, description="Official website URL")
    """
    # Brands will be implemented once there are conglomerates incorporated.
    brands: Optional[List[str]] = Field(
        default_factory=list, description="List of brands owned/operated by the manufacturer"
    )
    """
    offered_product_types: Optional[List[ProductType]] = Field(
        default_factory=list, description="List of product types offered (e.g., 'motor', 'drive')"
    )
