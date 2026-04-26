"""
Pytest configuration and shared fixtures for specodex tests.

This module contains pytest configuration, markers, and fixtures
that are shared across all test modules.
"""

import io
import json
import os

import boto3
import moto
import pytest
from PyPDF2 import PdfWriter

from specodex.db.dynamo import DynamoDBClient
from specodex.models.datasheet import Datasheet
from specodex.models.drive import Drive
from specodex.models.manufacturer import Manufacturer
from specodex.models.motor import Motor


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line(
        "markers", "security: marks tests as security-focused tests"
    )
    config.addinivalue_line("markers", "performance: marks tests as performance tests")


@pytest.fixture(scope="session")
def test_api_key():
    """Test API key for integration tests."""
    return os.getenv("GEMINI_API_KEY", "test-api-key-for-testing")


@pytest.fixture(scope="session")
def aws_stack_name():
    """AWS stack name for integration tests."""
    return os.getenv("AWS_SAM_STACK_NAME", "specodex-test")


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment variables after each test."""
    original_env = os.environ.copy()
    yield
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_lambda_context():
    """Mock AWS Lambda context for testing."""
    from unittest.mock import Mock

    context = Mock()
    context.function_name = "specodex-test"
    context.function_version = "$LATEST"
    context.invoked_function_arn = (
        "arn:aws:lambda:us-east-1:123456789012:function:specodex-test"
    )
    context.memory_limit_in_mb = 1024
    context.remaining_time_in_millis = Mock(return_value=30000)
    context.request_id = "test-request-id"
    context.log_group_name = "/aws/lambda/specodex-test"
    context.log_stream_name = "2023/01/01/[$LATEST]test123"
    context.aws_request_id = "test-aws-request-id"

    return context


# Pytest collection modifications
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on file paths."""
    for item in items:
        # Add markers based on test file location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)  # Performance tests are typically slow

        # Add security marker for security tests
        if "security" in str(item.fspath) or "security" in item.name:
            item.add_marker(pytest.mark.security)

        # Add slow marker for tests with "slow" in the name
        if "slow" in item.name or "timeout" in item.name or "large" in item.name:
            item.add_marker(pytest.mark.slow)


# --- Model fixtures ---


@pytest.fixture
def sample_motor():
    """Motor instance with deterministic values."""
    return Motor(
        product_type="motor",
        product_name="AKM-33H",
        manufacturer="Kollmorgen",
        part_number="AKM33H-ANCNR-00",
        rated_voltage="200-240;V",
        rated_speed="3000;rpm",
        rated_torque="1.27;Nm",
    )


@pytest.fixture
def sample_drive():
    """Drive instance with deterministic values."""
    return Drive(
        product_type="drive",
        product_name="AKD-P00306",
        manufacturer="Kollmorgen",
        part_number="AKD-P00306-NBCC-0000",
        input_voltage="100-240;V",
        rated_current="3.0;A",
    )


@pytest.fixture
def sample_datasheet():
    """Datasheet instance with deterministic values."""
    return Datasheet(
        url="https://example.com/akm33h.pdf",
        product_type="motor",
        product_name="AKM-33H",
        manufacturer="Kollmorgen",
    )


@pytest.fixture
def sample_manufacturer():
    """Manufacturer instance with deterministic values."""
    return Manufacturer(
        name="Kollmorgen",
        website="https://www.kollmorgen.com",
    )


# --- DynamoDB fixtures ---


@pytest.fixture
def dynamodb_table():
    """Mocked DynamoDB table using moto."""
    with moto.mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
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
        yield table


@pytest.fixture
def db_client(dynamodb_table):
    """DynamoDBClient pointed at the mocked table."""
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    return DynamoDBClient(table_name="products")


# --- File / bytes fixtures ---


@pytest.fixture
def valid_pdf_bytes():
    """Minimal valid PDF as bytes."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def tmp_json_file(tmp_path):
    """Temporary JSON file with sample product data."""
    data = {
        "motor": [
            {
                "url": "https://example.com/test.pdf",
                "manufacturer": "TestMfg",
                "product_name": "TestMotor",
                "pages": [1, 2, 3],
            }
        ]
    }
    filepath = tmp_path / "products.json"
    filepath.write_text(json.dumps(data))
    return filepath
