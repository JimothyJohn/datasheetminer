"""Unit tests for datasheetminer/config.py constants and schema discovery."""

import pytest

from datasheetminer.config import MODEL, REGION, SCHEMA_CHOICES
from datasheetminer.models.product import ProductBase


@pytest.mark.unit
class TestSchemaChoices:
    """Tests for the auto-discovered SCHEMA_CHOICES dictionary."""

    def test_schema_choices_contains_motor(self) -> None:
        assert "motor" in SCHEMA_CHOICES

    def test_schema_choices_contains_drive(self) -> None:
        assert "drive" in SCHEMA_CHOICES

    def test_schema_choices_contains_gearhead(self) -> None:
        assert "gearhead" in SCHEMA_CHOICES

    def test_schema_choices_contains_robot_arm(self) -> None:
        assert "robot_arm" in SCHEMA_CHOICES

    def test_schema_choices_excludes_product(self) -> None:
        """'product' is a base class and should be excluded."""
        assert "product" not in SCHEMA_CHOICES

    def test_schema_choices_excludes_common(self) -> None:
        """'common' is a utility module and should be excluded."""
        assert "common" not in SCHEMA_CHOICES

    def test_schema_choices_values_are_product_base(self) -> None:
        """All discovered schema classes must be subclasses of ProductBase."""
        for name, cls in SCHEMA_CHOICES.items():
            assert issubclass(cls, ProductBase), (
                f"SCHEMA_CHOICES['{name}'] = {cls.__name__} is not a ProductBase subclass"
            )

    def test_schema_choices_not_empty(self) -> None:
        assert len(SCHEMA_CHOICES) >= 4


@pytest.mark.unit
class TestConstants:
    """Tests for module-level constants."""

    def test_region_constant(self) -> None:
        assert REGION == "us-east-1"

    def test_model_constant(self) -> None:
        assert MODEL == "gemini-3-flash-preview"
