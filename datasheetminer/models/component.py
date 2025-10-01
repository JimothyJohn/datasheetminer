"""
Component model definitions for electronic components and their specifications.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from .base import BaseDatasheetModel


@dataclass
class ComponentSpecifications(BaseDatasheetModel):
    """
    Technical specifications for electronic components.

    This class captures the key technical parameters that are commonly
    found in datasheets across different component types.
    """

    # Electrical specifications
    voltage_rating: Optional[str] = None
    current_rating: Optional[str] = None
    power_rating: Optional[str] = None
    frequency_range: Optional[str] = None

    # Physical specifications
    package_type: Optional[str] = None
    dimensions: Optional[str] = None
    weight: Optional[str] = None
    operating_temperature: Optional[str] = None

    # Performance specifications
    efficiency: Optional[str] = None
    accuracy: Optional[str] = None
    resolution: Optional[str] = None
    bandwidth: Optional[str] = None

    # Additional specifications (flexible for component-specific parameters)
    additional_specs: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """Validate component specifications."""
        # At least one specification should be provided
        specs = [
            self.voltage_rating,
            self.current_rating,
            self.power_rating,
            self.frequency_range,
            self.package_type,
            self.dimensions,
            self.weight,
            self.operating_temperature,
            self.efficiency,
            self.accuracy,
            self.resolution,
            self.bandwidth,
        ]

        if not any(spec for spec in specs) and not self.additional_specs:
            raise ValueError("At least one specification must be provided")

        return True


@dataclass
class Component(BaseDatasheetModel):
    """
    Electronic component model.

    Represents a single electronic component with its identifying
    information and technical specifications.
    """

    # Component identification
    part_number: str
    manufacturer: str
    component_type: str  # e.g., "Motor Drive", "Microcontroller", "Sensor"

    # Component details
    description: Optional[str] = None
    family: Optional[str] = None  # Product family/series
    datasheet_url: Optional[str] = None

    # Technical specifications
    specifications: Optional[ComponentSpecifications] = None

    # Classification and features
    features: List[str] = field(default_factory=list)
    applications: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate component data."""
        if not self.part_number:
            raise ValueError("Part number is required")

        if not self.manufacturer:
            raise ValueError("Manufacturer is required")

        if not self.component_type:
            raise ValueError("Component type is required")

        if self.specifications:
            self.specifications.validate()

        return True
