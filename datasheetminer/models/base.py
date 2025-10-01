"""
Base model classes for datasheet schema definitions.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import json


@dataclass
class BaseDatasheetModel:
    """
    Base class for all datasheet models.

    Provides common functionality for serialization, validation,
    and data conversion across all datasheet objects.
    """

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert model to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseDatasheetModel":
        """Create model instance from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "BaseDatasheetModel":
        """Create model instance from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def validate(self) -> bool:
        """
        Validate model data.

        Override in subclasses for custom validation logic.
        Returns True if valid, raises ValueError if invalid.
        """
        return True
