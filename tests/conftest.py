"""
Pytest configuration and shared fixtures for datasheetminer tests.

This module contains pytest configuration, markers, and fixtures
that are shared across all test modules.
"""

import pytest
import os


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
    return os.getenv("AWS_SAM_STACK_NAME", "datasheetminer-test")


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
    context.function_name = "datasheetminer-test"
    context.function_version = "$LATEST"
    context.invoked_function_arn = (
        "arn:aws:lambda:us-east-1:123456789012:function:datasheetminer-test"
    )
    context.memory_limit_in_mb = 1024
    context.remaining_time_in_millis = Mock(return_value=30000)
    context.request_id = "test-request-id"
    context.log_group_name = "/aws/lambda/datasheetminer-test"
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
