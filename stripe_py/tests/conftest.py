"""Pytest fixtures: env vars, moto-backed DynamoDB, no live network calls."""

from __future__ import annotations

from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws


@pytest.fixture(autouse=True)
def _stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_dummy")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_dummy")
    monkeypatch.setenv("USERS_TABLE_NAME", "test-users")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")


@pytest.fixture
def dynamodb_client():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="test-users",
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield client


@pytest.fixture
def db(dynamodb_client):
    from billing.db import UsersDb

    return UsersDb("test-users", client=dynamodb_client)


@pytest.fixture
def now_iso():
    return datetime.now(UTC).isoformat()
