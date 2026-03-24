"""Shared fixtures for post-deployment smoke tests."""

import json
import os
import pytest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:3001")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def api_get():
    """Returns a callable for GET requests that returns (status, body, headers)."""

    def _get(path: str, *, timeout: int = 10) -> tuple[int, dict, dict]:
        url = f"{BASE_URL}{path}"
        req = Request(url, method="GET")
        req.add_header("Accept", "application/json")
        try:
            with urlopen(req, timeout=timeout) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}
                body = json.loads(resp.read().decode())
                return resp.status, body, headers
        except HTTPError as e:
            headers = {k.lower(): v for k, v in e.headers.items()}
            body = json.loads(e.read().decode())
            return e.code, body, headers

    return _get
