"""
End-to-end pipeline integration tests.

Mocks only external services (Gemini API, HTTP downloads) while using
real Pydantic model validation and moto-backed DynamoDB.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import boto3
import moto
import pytest

from specodex.db.dynamo import DynamoDBClient
from specodex.models.motor import Motor
from specodex.scraper import process_datasheet


@pytest.fixture
def pipeline_setup():
    with moto.mock_aws():
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="products",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        client = DynamoDBClient(table_name="products")
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _motor_from_parse(
    product_name: str = "Test",
    manufacturer: str = "TestMfg",
    part_number: str = "ABC-123",
) -> Motor:
    """Build a Motor with enough spec fields to clear the 25% quality gate.

    `specodex.quality.DEFAULT_MIN_QUALITY = 0.25` rejects products with
    fewer than 25% of their spec fields populated. Motor has ~28 spec
    fields, so we need ≥ 7 filled. Setting 8 below to give a margin.
    """
    return Motor(
        product_type="motor",
        product_name=product_name,
        manufacturer=manufacturer,
        part_number=part_number,
        rated_voltage={"value": 230.0, "unit": "V"},
        rated_power={"value": 100.0, "unit": "W"},
        rated_torque={"value": 0.5, "unit": "Nm"},
        rated_speed={"value": 3000.0, "unit": "rpm"},
        rated_current={"value": 1.0, "unit": "A"},
        peak_torque={"value": 1.5, "unit": "Nm"},
        peak_current={"value": 3.0, "unit": "A"},
        weight={"value": 2.0, "unit": "kg"},
    )


def _fake_gemini_response(motors: List[Motor]) -> Mock:
    """Create a mock Gemini response whose .parsed and .text both work."""
    resp = Mock()
    resp.parsed = motors
    resp.text = json.dumps([m.model_dump(mode="json") for m in motors])
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPdfToDbPipeline:
    # `find_spec_pages_by_text` and `_extract_bundled_pdf` both parse the
    # PDF bytes — the fake bytes from `get_document` aren't a valid PDF,
    # so we mock those steps too. Everything past Gemini stays real.
    @patch("specodex.scraper.find_spec_pages_by_text", return_value=[1])
    @patch("specodex.scraper._extract_bundled_pdf", return_value=b"fake page bytes")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    @patch("specodex.scraper.get_document", return_value=b"fake pdf")
    @patch("specodex.extract.generate_content")
    @patch("specodex.extract.parse_gemini_response")
    def test_pdf_to_db_pipeline(
        self,
        mock_parse: MagicMock,
        mock_gen: MagicMock,
        mock_doc: MagicMock,
        mock_is_pdf: MagicMock,
        mock_extract_bundled: MagicMock,
        mock_find_pages: MagicMock,
        pipeline_setup: DynamoDBClient,
    ) -> None:
        """PDF download -> Gemini -> parse -> Motor written to DB."""
        client = pipeline_setup

        motor = _motor_from_parse()
        mock_gen.return_value = _fake_gemini_response([motor])
        mock_parse.return_value = [motor]

        result = process_datasheet(
            client=client,
            api_key="fake-api-key-0123456789",
            product_type="motor",
            manufacturer="TestMfg",
            product_name="Test",
            product_family="",
            url="https://example.com/motor.pdf",
            pages=None,
        )

        assert result == "success"
        motors = client.list(Motor)
        assert len(motors) == 1
        assert motors[0].part_number == "ABC-123"


@pytest.mark.integration
class TestHtmlToDbPipeline:
    @patch("specodex.scraper.is_pdf_url", return_value=False)
    @patch("specodex.scraper.get_web_content", return_value="<html>specs</html>")
    @patch("specodex.extract.generate_content")
    @patch("specodex.extract.parse_gemini_response")
    def test_html_to_db_pipeline(
        self,
        mock_parse: MagicMock,
        mock_gen: MagicMock,
        mock_web: MagicMock,
        mock_is_pdf: MagicMock,
        pipeline_setup: DynamoDBClient,
    ) -> None:
        """HTML page -> Gemini -> parse -> Motor written to DB."""
        client = pipeline_setup

        motor = _motor_from_parse(product_name="HtmlMotor", part_number="HTML-001")
        mock_gen.return_value = _fake_gemini_response([motor])
        mock_parse.return_value = [motor]

        result = process_datasheet(
            client=client,
            api_key="fake-api-key-0123456789",
            product_type="motor",
            manufacturer="TestMfg",
            product_name="HtmlMotor",
            product_family="",
            url="https://example.com/product-page",
            pages=None,
        )

        assert result == "success"
        motors = client.list(Motor)
        assert len(motors) == 1
        assert motors[0].part_number == "HTML-001"


@pytest.mark.integration
class TestDuplicateSkipping:
    def test_duplicate_skipping(self, pipeline_setup: DynamoDBClient) -> None:
        """Pre-existing product with same manufacturer+name causes skip."""
        client = pipeline_setup

        existing = Motor(
            product_id=UUID("00000000-0000-0000-0000-000000000001"),
            product_type="motor",
            product_name="M3AA",
            manufacturer="ABB",
            part_number="EXIST-001",
        )
        client.create(existing)

        # process_datasheet checks product_exists before calling the LLM
        result = process_datasheet(
            client=client,
            api_key="fake-api-key-0123456789",
            product_type="motor",
            manufacturer="ABB",
            product_name="M3AA",
            product_family="",
            url="https://example.com/m3aa.pdf",
            pages=None,
        )

        assert result == "skipped"
        assert len(client.list(Motor)) == 1


@pytest.mark.integration
class TestBatchFromJson:
    # Same mock chain as TestPdfToDbPipeline — the fake PDF bytes need
    # find_spec_pages_by_text and _extract_bundled_pdf bypassed too.
    @patch("specodex.scraper.find_spec_pages_by_text", return_value=[1])
    @patch("specodex.scraper._extract_bundled_pdf", return_value=b"fake page bytes")
    @patch("specodex.scraper.is_pdf_url", return_value=True)
    @patch("specodex.scraper.get_document", return_value=b"fake pdf")
    @patch("specodex.extract.generate_content")
    @patch("specodex.extract.parse_gemini_response")
    def test_batch_from_json(
        self,
        mock_parse: MagicMock,
        mock_gen: MagicMock,
        mock_doc: MagicMock,
        mock_is_pdf: MagicMock,
        mock_extract_bundled: MagicMock,
        mock_find_pages: MagicMock,
        pipeline_setup: DynamoDBClient,
        tmp_path: Path,
    ) -> None:
        """Load product info from JSON, feed through pipeline, verify DB."""
        client = pipeline_setup

        # Write temp JSON
        data: dict[str, Any] = {
            "motor": [
                {
                    "url": "https://example.com/batch.pdf",
                    "manufacturer": "BatchMfg",
                    "product_name": "BatchMotor",
                    "pages": [1, 2],
                }
            ]
        }
        json_path = tmp_path / "batch.json"
        json_path.write_text(json.dumps(data))

        # Load from JSON (the real utility function)
        from specodex.utils import get_product_info_from_json

        info = get_product_info_from_json(str(json_path), "motor", 0)

        motor = _motor_from_parse(
            product_name="BatchMotor",
            manufacturer="BatchMfg",
            part_number="BATCH-001",
        )
        mock_gen.return_value = _fake_gemini_response([motor])
        mock_parse.return_value = [motor]

        result = process_datasheet(
            client=client,
            api_key="fake-api-key-0123456789",
            product_type="motor",
            manufacturer=info["manufacturer"],
            product_name=info["product_name"],
            product_family="",
            url=info["url"],
            pages=None,
        )

        assert result == "success"
        motors = client.list(Motor)
        assert len(motors) == 1
        assert motors[0].manufacturer == "BatchMfg"
