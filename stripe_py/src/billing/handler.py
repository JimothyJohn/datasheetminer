"""Lambda entrypoint for AWS Lambda Function URL events.

Lazy-init pattern: ``_init`` runs on the first warm-pool invoke (not at
module import) so pytest can ``import billing.handler`` without env
vars set.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from .config import Config, load_config
from .db import UsersDb
from .router import HttpResponse, dispatch

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

_CONFIG: Config | None = None
_DB: UsersDb | None = None


def _init() -> tuple[Config, UsersDb]:
    global _CONFIG, _DB
    if _CONFIG is None or _DB is None:
        _CONFIG = load_config()
        _DB = UsersDb(_CONFIG.users_table_name)
        log.info("Billing Lambda initialised (TEST MODE)")
    return _CONFIG, _DB


def _extract_request(event: dict[str, Any]) -> tuple[str, str, dict[str, str], str]:
    rc = event.get("requestContext") or {}
    http = rc.get("http") or {}
    method = http.get("method") or event.get("httpMethod") or "GET"
    path = http.get("path") or event.get("rawPath") or event.get("path") or "/"
    headers = event.get("headers") or {}

    body = event.get("body") or ""
    if event.get("isBase64Encoded") and body:
        body = base64.b64decode(body).decode("utf-8")
    return method, path, headers, body


def _to_lambda_response(resp: HttpResponse) -> dict[str, Any]:
    return {
        "statusCode": resp.status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(resp.body),
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    config, db = _init()
    method, path, headers, body = _extract_request(event)
    response = dispatch(config, db, method, path, headers, body)
    return _to_lambda_response(response)
