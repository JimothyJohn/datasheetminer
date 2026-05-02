from __future__ import annotations

import base64
import json

import billing.handler as handler


def _reset_init():
    handler._CONFIG = None
    handler._DB = None


def test_lambda_function_url_event_v2(dynamodb_client, monkeypatch):
    _reset_init()
    event = {
        "version": "2.0",
        "rawPath": "/health",
        "requestContext": {"http": {"method": "GET", "path": "/health"}},
        "headers": {},
        "body": "",
        "isBase64Encoded": False,
    }
    response = handler.lambda_handler(event, None)
    assert response["statusCode"] == 200
    assert response["headers"]["content-type"] == "application/json"
    assert json.loads(response["body"]) == {"status": "ok", "mode": "test"}


def test_lambda_handles_base64_body(dynamodb_client, mocker):
    _reset_init()
    mocker.patch(
        "stripe.Webhook.construct_event",
        return_value={"type": "customer.created", "data": {"object": {}}},
    )
    raw = b'{"any": "json"}'
    event = {
        "requestContext": {"http": {"method": "POST", "path": "/webhook"}},
        "headers": {"stripe-signature": "sig"},
        "body": base64.b64encode(raw).decode(),
        "isBase64Encoded": True,
    }
    response = handler.lambda_handler(event, None)
    assert response["statusCode"] == 200


def test_lambda_unknown_route(dynamodb_client):
    _reset_init()
    event = {
        "requestContext": {"http": {"method": "GET", "path": "/unknown"}},
        "headers": {},
        "body": "",
    }
    response = handler.lambda_handler(event, None)
    assert response["statusCode"] == 404
