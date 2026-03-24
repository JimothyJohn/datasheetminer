"""Tests for datasheetminer.db.dynamo.DynamoDBClient."""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from datasheetminer.db.dynamo import DynamoDBClient
from datasheetminer.models.datasheet import Datasheet
from datasheetminer.models.motor import Motor


def _make_client(mock_boto3: MagicMock) -> tuple[DynamoDBClient, MagicMock]:
    """Create a DynamoDBClient with fully mocked boto3, return (client, mock_table)."""
    mock_table = MagicMock()
    mock_resource = MagicMock()
    mock_resource.Table.return_value = mock_table
    mock_boto3.resource.return_value = mock_resource
    client = DynamoDBClient(table_name="products")
    return client, mock_table


def _client_error(
    code: str = "ValidationException", msg: str = "test error"
) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": msg}},
        "TestOp",
    )


# ---------------------------------------------------------------------------
# TestConvertFloatsToDecimal
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestConvertFloatsToDecimal:
    @patch("datasheetminer.db.dynamo.boto3")
    def test_float_converted(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        assert client._convert_floats_to_decimal(3.14) == Decimal("3.14")

    @patch("datasheetminer.db.dynamo.boto3")
    def test_nested_dict(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        result = client._convert_floats_to_decimal({"a": {"b": 1.5}})
        assert result == {"a": {"b": Decimal("1.5")}}

    @patch("datasheetminer.db.dynamo.boto3")
    def test_list_items(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        result = client._convert_floats_to_decimal([1.0, 2.0])
        assert result == [Decimal("1.0"), Decimal("2.0")]

    @patch("datasheetminer.db.dynamo.boto3")
    def test_non_float_unchanged(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        assert client._convert_floats_to_decimal("hello") == "hello"
        assert client._convert_floats_to_decimal(42) == 42

    @patch("datasheetminer.db.dynamo.boto3")
    def test_string_unchanged(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        assert client._convert_floats_to_decimal("3.14") == "3.14"


# ---------------------------------------------------------------------------
# TestParseCompactUnits
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestParseCompactUnits:
    @patch("datasheetminer.db.dynamo.boto3")
    def test_value_unit_string(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        result = client._parse_compact_units("20;C")
        assert result == {"value": Decimal("20"), "unit": "C"}

    @patch("datasheetminer.db.dynamo.boto3")
    def test_min_max_unit_string(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        result = client._parse_compact_units("20-40;C")
        assert result == {"min": Decimal("20"), "max": Decimal("40"), "unit": "C"}

    @patch("datasheetminer.db.dynamo.boto3")
    def test_negative_values(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        result = client._parse_compact_units("-20-40;C")
        assert result == {"min": Decimal("-20"), "max": Decimal("40"), "unit": "C"}

    @patch("datasheetminer.db.dynamo.boto3")
    def test_non_matching_string(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        result = client._parse_compact_units("hello;world")
        assert result == "hello;world"

    @patch("datasheetminer.db.dynamo.boto3")
    def test_nested_dict_recursive(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        result = client._parse_compact_units({"specs": {"temp": "20;C"}})
        assert result == {"specs": {"temp": {"value": Decimal("20"), "unit": "C"}}}

    @patch("datasheetminer.db.dynamo.boto3")
    def test_list_recursive(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        result = client._parse_compact_units(["20;C", "30;V"])
        assert result == [
            {"value": Decimal("20"), "unit": "C"},
            {"value": Decimal("30"), "unit": "V"},
        ]

    @patch("datasheetminer.db.dynamo.boto3")
    def test_no_semicolon(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        assert client._parse_compact_units("plain text") == "plain text"


# ---------------------------------------------------------------------------
# TestSerializeItem
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestSerializeItem:
    @patch("datasheetminer.db.dynamo.boto3")
    def test_motor_serialization(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        motor = Motor(
            product_name="TestMotor",
            product_type="motor",
            manufacturer="Acme",
        )
        data = client._serialize_item(motor)
        assert data["PK"] == "PRODUCT#MOTOR"
        assert data["SK"] == f"PRODUCT#{motor.product_id}"
        assert isinstance(data["product_id"], str)

    @patch("datasheetminer.db.dynamo.boto3")
    def test_datasheet_serialization(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        ds = Datasheet(
            url="https://example.com/ds.pdf",
            product_type="motor",
            product_name="TestMotor",
            manufacturer="Acme",
        )
        data = client._serialize_item(ds)
        assert data["PK"] == "DATASHEET#MOTOR"
        assert data["SK"] == f"DATASHEET#{ds.datasheet_id}"

    @patch("datasheetminer.db.dynamo.boto3")
    def test_uuid_to_string(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        motor = Motor(
            product_name="TestMotor",
            product_type="motor",
            manufacturer="Acme",
        )
        data = client._serialize_item(motor)
        assert isinstance(data["product_id"], str)
        assert data["product_id"] == str(motor.product_id)

    @patch("datasheetminer.db.dynamo.boto3")
    def test_compact_units_parsed(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        motor = Motor(
            product_name="TestMotor",
            product_type="motor",
            manufacturer="Acme",
            rated_speed="3000;rpm",
        )
        data = client._serialize_item(motor)
        assert data["rated_speed"] == {"value": Decimal("3000"), "unit": "rpm"}


# ---------------------------------------------------------------------------
# TestDeserializeItem
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestDeserializeItem:
    @patch("datasheetminer.db.dynamo.boto3")
    def test_valid_motor(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        uid = str(uuid4())
        item = {
            "PK": "PRODUCT#MOTOR",
            "SK": f"PRODUCT#{uid}",
            "product_id": uid,
            "product_type": "motor",
            "product_name": "TestMotor",
            "manufacturer": "Acme",
        }
        result = client._deserialize_item(item, Motor)
        assert isinstance(result, Motor)
        assert result.product_name == "TestMotor"

    @patch("datasheetminer.db.dynamo.boto3")
    def test_invalid_data_returns_none(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        result = client._deserialize_item({"garbage": True}, Motor)
        assert result is None


# ---------------------------------------------------------------------------
# TestCRUD
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestCRUD:
    @patch("datasheetminer.db.dynamo.boto3")
    def test_create_success(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        motor = Motor(
            product_name="TestMotor",
            product_type="motor",
            manufacturer="Acme",
        )
        assert client.create(motor) is True
        mock_table.put_item.assert_called_once()

    @patch("datasheetminer.db.dynamo.boto3")
    def test_create_client_error(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        mock_table.put_item.side_effect = _client_error()
        motor = Motor(
            product_name="TestMotor",
            product_type="motor",
            manufacturer="Acme",
        )
        assert client.create(motor) is False

    @patch("datasheetminer.db.dynamo.boto3")
    def test_read_found(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        uid = str(uuid4())
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "PRODUCT#MOTOR",
                "SK": f"PRODUCT#{uid}",
                "product_id": uid,
                "product_type": "motor",
                "product_name": "TestMotor",
                "manufacturer": "Acme",
            }
        }
        result = client.read(uid, Motor)
        assert isinstance(result, Motor)
        assert result.product_name == "TestMotor"

    @patch("datasheetminer.db.dynamo.boto3")
    def test_read_not_found(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        mock_table.get_item.return_value = {}
        result = client.read(str(uuid4()), Motor)
        assert result is None

    @patch("datasheetminer.db.dynamo.boto3")
    def test_update_success(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        motor = Motor(
            product_name="TestMotor",
            product_type="motor",
            manufacturer="Acme",
        )
        assert client.update(motor) is True
        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert "UpdateExpression" in call_kwargs
        assert call_kwargs["UpdateExpression"].startswith("SET ")

    @patch("datasheetminer.db.dynamo.boto3")
    def test_delete_success(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        uid = str(uuid4())
        assert client.delete(uid, Motor) is True
        mock_table.delete_item.assert_called_once()


# ---------------------------------------------------------------------------
# TestList
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestList:
    @patch("datasheetminer.db.dynamo.boto3")
    def test_list_by_type(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        uid = str(uuid4())
        mock_table.query.return_value = {
            "Items": [
                {
                    "PK": "PRODUCT#MOTOR",
                    "SK": f"PRODUCT#{uid}",
                    "product_id": uid,
                    "product_type": "motor",
                    "product_name": "Motor1",
                    "manufacturer": "Acme",
                }
            ]
        }
        results = client.list(Motor)
        assert len(results) == 1
        assert isinstance(results[0], Motor)

    @patch("datasheetminer.db.dynamo.boto3")
    def test_list_with_limit(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        mock_table.query.return_value = {"Items": []}
        client.list(Motor, limit=5)
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Limit"] == 5

    @patch("datasheetminer.db.dynamo.boto3")
    def test_list_pagination(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        uid1 = str(uuid4())
        uid2 = str(uuid4())
        # First page returns one item + LastEvaluatedKey; second page returns another item
        mock_table.query.side_effect = [
            {
                "Items": [
                    {
                        "PK": "PRODUCT#MOTOR",
                        "SK": f"PRODUCT#{uid1}",
                        "product_id": uid1,
                        "product_type": "motor",
                        "product_name": "Motor1",
                        "manufacturer": "Acme",
                    }
                ],
                "LastEvaluatedKey": {"PK": "PRODUCT#MOTOR", "SK": f"PRODUCT#{uid1}"},
            },
            {
                "Items": [
                    {
                        "PK": "PRODUCT#MOTOR",
                        "SK": f"PRODUCT#{uid2}",
                        "product_id": uid2,
                        "product_type": "motor",
                        "product_name": "Motor2",
                        "manufacturer": "Acme",
                    }
                ]
            },
        ]
        results = client.list(Motor)
        assert len(results) == 2
        assert mock_table.query.call_count == 2


# ---------------------------------------------------------------------------
# TestBatchCreate
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestBatchCreate:
    @patch("datasheetminer.db.dynamo.boto3")
    def test_batch_empty_list(self, mock_boto3: MagicMock) -> None:
        client, _ = _make_client(mock_boto3)
        assert client.batch_create([]) == 0

    @patch("datasheetminer.db.dynamo.boto3")
    def test_batch_success(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        mock_writer = MagicMock()
        mock_table.batch_writer.return_value.__enter__ = MagicMock(
            return_value=mock_writer
        )
        mock_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)
        motors = [
            Motor(product_name=f"Motor{i}", product_type="motor", manufacturer="Acme")
            for i in range(3)
        ]
        count = client.batch_create(motors)
        assert count == 3


# ---------------------------------------------------------------------------
# TestDatasheetOps
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestDatasheetOps:
    @patch("datasheetminer.db.dynamo.boto3")
    def test_datasheet_exists_true(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        mock_table.scan.return_value = {
            "Items": [{"url": "https://example.com/ds.pdf"}]
        }
        assert client.datasheet_exists("https://example.com/ds.pdf") is True

    @patch("datasheetminer.db.dynamo.boto3")
    def test_datasheet_exists_false(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        mock_table.scan.return_value = {"Items": []}
        assert client.datasheet_exists("https://example.com/ds.pdf") is False

    @patch("datasheetminer.db.dynamo.boto3")
    def test_product_exists(self, mock_boto3: MagicMock) -> None:
        client, mock_table = _make_client(mock_boto3)
        uid = str(uuid4())
        mock_table.query.return_value = {
            "Items": [
                {
                    "PK": "PRODUCT#MOTOR",
                    "SK": f"PRODUCT#{uid}",
                    "product_id": uid,
                    "product_type": "motor",
                    "product_name": "TestMotor",
                    "manufacturer": "Acme",
                }
            ]
        }
        assert client.product_exists("motor", "Acme", "TestMotor", Motor) is True
