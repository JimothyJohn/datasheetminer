from __future__ import annotations

from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from datasheetminer.models.common import ValueUnit


class Datasheet(BaseModel):
    """
    Represents a datasheet document and its associated metadata.
    Separated from the Product model to allow independent existence and linking.
    """
    model_config = {"populate_by_name": True}

    @computed_field
    def PK(self) -> str:
        return f"DATASHEET#{self.product_type.upper()}"

    @computed_field
    def SK(self) -> str:
        return f"DATASHEET#{self.datasheet_id}"

    datasheet_id: UUID = Field(
        default_factory=uuid4, description="Unique identifier for the datasheet entry"
    )
    url: str = Field(..., description="URL to the datasheet")
    pages: Optional[List[int]] = Field(None, description="Relevant page numbers")
    
    # Shared product metadata
    product_type: str = Field(..., description="Type of product (e.g., 'motor', 'drive')")
    product_name: str = Field(..., description="Product name")
    product_family: Optional[str] = Field(None, description="Product family or sub-series")
    manufacturer: Optional[str] = Field(None, description="Manufacturer name")
    category: Optional[str] = Field(None, description="Category or type of the datasheet product")
    
    # Additional metadata
    release_year: Optional[int] = None
    warranty: Optional[ValueUnit] = None
