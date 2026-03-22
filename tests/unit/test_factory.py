"""Tests for datasheetminer.models.factory.create_llm_schema."""

from typing import Optional

import pytest

from datasheetminer.models.factory import EXCLUDED_FIELDS, create_llm_schema
from datasheetminer.models.motor import Motor


@pytest.mark.unit
class TestCreateLlmSchema:
    def test_excluded_fields_removed(self) -> None:
        lean = create_llm_schema(Motor)
        lean_fields = set(lean.model_fields.keys())
        for field_name in EXCLUDED_FIELDS:
            assert field_name not in lean_fields, f"{field_name} should be excluded"

    def test_value_unit_becomes_optional_str(self) -> None:
        lean = create_llm_schema(Motor)
        # rated_speed is ValueUnit on Motor; lean model should accept plain strings
        field = lean.model_fields["rated_speed"]
        assert not field.is_required()
        assert field.default is None
        # Verify it accepts a plain string at instantiation time
        instance = lean(rated_speed="3000;rpm")
        assert instance.rated_speed == "3000;rpm"

    def test_min_max_unit_becomes_optional_str(self) -> None:
        lean = create_llm_schema(Motor)
        # rated_voltage is MinMaxUnit on Motor; lean model should accept plain strings
        field = lean.model_fields["rated_voltage"]
        assert not field.is_required()
        assert field.default is None
        instance = lean(rated_voltage="20-40;V")
        assert instance.rated_voltage == "20-40;V"

    def test_simple_types_preserved(self) -> None:
        lean = create_llm_schema(Motor)
        # poles is Optional[int] on Motor; should remain Optional[int]
        field = lean.model_fields["poles"]
        assert field.annotation == Optional[int]

    def test_generated_model_name(self) -> None:
        lean = create_llm_schema(Motor)
        assert lean.__name__ == "LLM_Motor"

    def test_lean_model_instantiation(self) -> None:
        lean = create_llm_schema(Motor)
        instance = lean(rated_speed="3000;rpm", rated_voltage="20-40;V", poles=8)
        assert instance.rated_speed == "3000;rpm"
        assert instance.rated_voltage == "20-40;V"
        assert instance.poles == 8
