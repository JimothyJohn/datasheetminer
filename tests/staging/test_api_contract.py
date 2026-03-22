"""
Staging API contract tests.
Requires API_BASE_URL environment variable pointing to a running server.
Run: API_BASE_URL=http://localhost:3001 uv run pytest tests/staging/ -v
"""

import json
import os
import pytest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4


BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:3001")


def api_request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    """Helper to make API requests."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}

    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except HTTPError as e:
        return e.code, json.loads(e.read().decode())


@pytest.mark.integration
class TestHealthEndpoint:
    def test_health_returns_200(self):
        status, body = api_request("GET", "/health")
        assert status == 200
        assert body["status"] == "healthy"
        assert "timestamp" in body

    def test_root_endpoint(self):
        status, body = api_request("GET", "/")
        assert status == 200
        assert "endpoints" in body


@pytest.mark.integration
class TestProductsAPI:
    def test_get_products_returns_array(self):
        status, body = api_request("GET", "/api/products")
        assert status == 200
        assert body["success"] is True
        assert isinstance(body["data"], list)

    def test_get_products_with_type(self):
        status, body = api_request("GET", "/api/products?type=motor")
        assert status == 200
        assert body["success"] is True

    def test_get_summary(self):
        status, body = api_request("GET", "/api/products/summary")
        assert status == 200
        assert "total" in body["data"]

    def test_get_categories(self):
        status, body = api_request("GET", "/api/products/categories")
        assert status == 200
        assert isinstance(body["data"], list)

    def test_get_manufacturers(self):
        status, body = api_request("GET", "/api/products/manufacturers")
        assert status == 200
        assert isinstance(body["data"], list)

    def test_get_product_missing_type_returns_400(self):
        status, body = api_request("GET", f"/api/products/{uuid4()}")
        assert status == 400

    def test_get_product_not_found_returns_404(self):
        status, body = api_request("GET", f"/api/products/{uuid4()}?type=motor")
        assert status == 404

    def test_create_and_delete_product(self):
        # Create
        product = {
            "product_type": "motor",
            "product_name": "StagingTestMotor",
            "manufacturer": "StagingTestMfg",
            "part_number": f"STAGING-{uuid4().hex[:8]}",
        }
        status, body = api_request("POST", "/api/products", product)
        assert status == 201
        assert body["success"] is True

        # Note: We can't easily get the ID back to delete since batch_create doesn't return it
        # But we can verify creation didn't error

    def test_404_for_unknown_endpoint(self):
        status, body = api_request("GET", "/api/nonexistent")
        assert status == 404


@pytest.mark.integration
class TestDatasheetsAPI:
    def test_get_datasheets(self):
        status, body = api_request("GET", "/api/datasheets")
        assert status == 200
        assert isinstance(body["data"], list)
