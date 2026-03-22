"""Unit tests for datasheetminer/management.py."""

from unittest.mock import MagicMock, patch

import pytest

from datasheetminer.management import Deduplicator


@pytest.mark.unit
class TestDeduplicator:
    """Tests for the Deduplicator class."""

    @patch("datasheetminer.management.DynamoDBClient")
    def test_find_duplicates_with_duplicates(self, MockDBClient: MagicMock) -> None:
        """Two items sharing the same key triple are grouped as duplicates."""
        mock_client = MockDBClient.return_value

        motor1 = MagicMock()
        motor1.part_number = "ABC-123"
        motor1.product_name = "TestMotor"
        motor1.manufacturer = "TestMfg"
        motor1.model_dump.return_value = {
            "product_id": "id1",
            "part_number": "ABC-123",
            "product_name": "TestMotor",
            "manufacturer": "TestMfg",
            "PK": "PRODUCT#MOTOR",
            "SK": "PRODUCT#id1",
        }

        motor2 = MagicMock()
        motor2.part_number = "ABC-123"
        motor2.product_name = "TestMotor"
        motor2.manufacturer = "TestMfg"
        motor2.model_dump.return_value = {
            "product_id": "id2",
            "part_number": "ABC-123",
            "product_name": "TestMotor",
            "manufacturer": "TestMfg",
            "PK": "PRODUCT#MOTOR",
            "SK": "PRODUCT#id2",
        }

        mock_client.list_all.return_value = [motor1, motor2]

        dedup = Deduplicator(table_name="products")
        result = dedup.find_duplicates()

        assert len(result) == 1
        key = ("ABC-123", "TestMotor", "TestMfg")
        assert key in result
        assert len(result[key]) == 2

    @patch("datasheetminer.management.DynamoDBClient")
    def test_find_duplicates_no_duplicates(self, MockDBClient: MagicMock) -> None:
        """All items unique -- returns empty dict."""
        mock_client = MockDBClient.return_value

        motor1 = MagicMock()
        motor1.part_number = "ABC-123"
        motor1.product_name = "MotorA"
        motor1.manufacturer = "MfgA"
        motor1.model_dump.return_value = {
            "product_id": "id1",
            "part_number": "ABC-123",
            "product_name": "MotorA",
            "manufacturer": "MfgA",
            "PK": "PRODUCT#MOTOR",
            "SK": "PRODUCT#id1",
        }

        motor2 = MagicMock()
        motor2.part_number = "XYZ-789"
        motor2.product_name = "MotorB"
        motor2.manufacturer = "MfgB"
        motor2.model_dump.return_value = {
            "product_id": "id2",
            "part_number": "XYZ-789",
            "product_name": "MotorB",
            "manufacturer": "MfgB",
            "PK": "PRODUCT#MOTOR",
            "SK": "PRODUCT#id2",
        }

        mock_client.list_all.return_value = [motor1, motor2]

        dedup = Deduplicator(table_name="products")
        result = dedup.find_duplicates()

        assert result == {}

    @patch("datasheetminer.management.DynamoDBClient")
    def test_delete_duplicates_dry_run(self, MockDBClient: MagicMock) -> None:
        """dry_run=True reports found count but deletes nothing."""
        mock_client = MockDBClient.return_value

        motor1 = MagicMock()
        motor1.part_number = "ABC-123"
        motor1.product_name = "TestMotor"
        motor1.manufacturer = "TestMfg"
        motor1.model_dump.return_value = {
            "product_id": "id1",
            "part_number": "ABC-123",
            "product_name": "TestMotor",
            "manufacturer": "TestMfg",
            "PK": "PRODUCT#MOTOR",
            "SK": "PRODUCT#id1",
        }

        motor2 = MagicMock()
        motor2.part_number = "ABC-123"
        motor2.product_name = "TestMotor"
        motor2.manufacturer = "TestMfg"
        motor2.model_dump.return_value = {
            "product_id": "id2",
            "part_number": "ABC-123",
            "product_name": "TestMotor",
            "manufacturer": "TestMfg",
            "PK": "PRODUCT#MOTOR",
            "SK": "PRODUCT#id2",
        }

        mock_client.list_all.return_value = [motor1, motor2]

        dedup = Deduplicator(table_name="products")
        result = dedup.delete_duplicates(confirm=False, dry_run=True)

        assert result["found"] == 1
        assert result["deleted"] == 0

    @patch("datasheetminer.management.DynamoDBClient")
    def test_delete_duplicates_no_confirm_no_dry_run(
        self, MockDBClient: MagicMock
    ) -> None:
        """Neither confirm nor dry_run -- safety check returns zeros."""
        mock_client = MockDBClient.return_value

        dedup = Deduplicator(table_name="products")
        result = dedup.delete_duplicates(confirm=False, dry_run=False)

        assert result == {"found": 0, "deleted": 0}
        # list_all should never be called when neither flag is set
        mock_client.list_all.assert_not_called()
