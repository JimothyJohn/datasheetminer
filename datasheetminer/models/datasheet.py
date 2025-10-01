"""
Datasheet model definitions for complete datasheet documents.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from .base import BaseDatasheetModel
from .component import Component


@dataclass
class DatasheetMetadata(BaseDatasheetModel):
    """
    Metadata for datasheet documents.

    Contains information about the datasheet document itself,
    such as publication details, version, and source information.
    """

    # Document identification
    title: Optional[str] = None
    document_id: Optional[str] = None
    version: Optional[str] = None
    revision: Optional[str] = None

    # Publication information
    publication_date: Optional[str] = None  # ISO format string
    last_updated: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None

    # Source information
    source_url: Optional[str] = None
    file_size: Optional[int] = None  # in bytes
    page_count: Optional[int] = None
    language: Optional[str] = "en"

    # Processing metadata
    extraction_timestamp: Optional[str] = None
    extraction_method: Optional[str] = "gemini-ai"

    def __post_init__(self):
        """Set extraction timestamp if not provided."""
        if not self.extraction_timestamp:
            self.extraction_timestamp = datetime.utcnow().isoformat()


@dataclass
class Datasheet(BaseDatasheetModel):
    """
    Complete datasheet document model.

    Represents a full datasheet with all extracted components,
    metadata, and structured information.
    """

    # Document metadata
    metadata: DatasheetMetadata

    # Primary component (main subject of the datasheet)
    primary_component: Optional[Component] = None

    # Additional components (if datasheet covers multiple components)
    additional_components: List[Component] = field(default_factory=list)

    # Document sections and content
    abstract: Optional[str] = None
    key_features: List[str] = field(default_factory=list)
    applications: List[str] = field(default_factory=list)

    # Raw extracted content (for reference)
    raw_content_summary: Optional[str] = None

    # Quality indicators
    extraction_confidence: Optional[float] = None  # 0.0 to 1.0
    completeness_score: Optional[float] = None  # 0.0 to 1.0

    def validate(self) -> bool:
        """Validate datasheet data."""
        if not self.metadata:
            raise ValueError("Metadata is required")

        self.metadata.validate()

        if self.primary_component:
            self.primary_component.validate()

        for component in self.additional_components:
            component.validate()

        if self.extraction_confidence is not None:
            if not 0.0 <= self.extraction_confidence <= 1.0:
                raise ValueError("Extraction confidence must be between 0.0 and 1.0")

        if self.completeness_score is not None:
            if not 0.0 <= self.completeness_score <= 1.0:
                raise ValueError("Completeness score must be between 0.0 and 1.0")

        return True

    def get_all_components(self) -> List[Component]:
        """Get all components in the datasheet."""
        components = []
        if self.primary_component:
            components.append(self.primary_component)
        components.extend(self.additional_components)
        return components

    def get_component_count(self) -> int:
        """Get total number of components in the datasheet."""
        return len(self.get_all_components())
