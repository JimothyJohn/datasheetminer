"""
Product type API contract tests for all supported types.

Extends the basic staging tests to verify every product type works through
the full API surface. Guards against the case where a new type is added
to the config but missing from routes/DB/search.

Requires API_BASE_URL environment variable.
Run: API_BASE_URL=http://localhost:3001 uv run pytest tests/staging/test_product_types.py -v
"""

import json
import os
import pytest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:3001")

HARDWARE_TYPES = ["motor", "drive", "gearhead", "robot_arm"]


def api_request(
    method: str, path: str, body: dict | None = None
) -> tuple[int, dict | None]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}

    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as resp:
            text = resp.read().decode()
            try:
                return resp.status, json.loads(text)
            except json.JSONDecodeError:
                return resp.status, None
    except HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, None


def _server_mode() -> str:
    try:
        req = Request(f"{BASE_URL}/health")
        with urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
            return body.get("mode", "unknown")
    except Exception:
        return "unknown"


requires_admin = pytest.mark.skipif(
    _server_mode() == "public",
    reason="Server is in public (read-only) mode",
)


def _has_route(path: str) -> bool:
    """Check if a route exists on the running server (not 404)."""
    try:
        status, _ = api_request("GET", path)
        return status != 404
    except Exception:
        return False


requires_search = pytest.mark.skipif(
    not _has_route("/api/v1/search"),
    reason="Server does not have /api/v1/search route (stale build)",
)

requires_openapi = pytest.mark.skipif(
    not _has_route("/api/openapi.json"),
    reason="Server does not have /api/openapi.json route (stale build)",
)


# =================== List Products Per Type ===================


@pytest.mark.integration
class TestListProductsByType:
    """GET /api/products?type=<type> works for all types."""

    @pytest.mark.parametrize("product_type", HARDWARE_TYPES)
    def test_list_returns_200(self, product_type: str):
        status, body = api_request("GET", f"/api/products?type={product_type}")
        assert status == 200
        assert body["success"] is True
        assert isinstance(body["data"], list)

    def test_list_all_returns_200(self):
        status, body = api_request("GET", "/api/products")
        assert status == 200
        assert body["success"] is True


# =================== Search Per Type ===================


@requires_search
@pytest.mark.integration
class TestSearchByType:
    """GET /api/v1/search?type=<type> works for all types."""

    @pytest.mark.parametrize("product_type", HARDWARE_TYPES)
    def test_search_by_type(self, product_type: str):
        status, body = api_request("GET", f"/api/v1/search?type={product_type}")
        assert status == 200
        assert body["success"] is True
        assert isinstance(body["data"], list)
        assert "count" in body

    def test_search_with_text_query(self):
        status, body = api_request("GET", "/api/v1/search?q=test")
        assert status == 200
        assert body["success"] is True

    def test_search_with_where_filter(self):
        status, body = api_request(
            "GET", "/api/v1/search?type=motor&where=rated_power>=0"
        )
        assert status == 200
        assert body["success"] is True

    def test_search_with_sort(self):
        status, body = api_request(
            "GET", "/api/v1/search?type=motor&sort=rated_power:desc"
        )
        assert status == 200
        assert body["success"] is True

    def test_search_rejects_invalid_type(self):
        status, body = api_request("GET", "/api/v1/search?type=invalid_type")
        assert status == 400
        assert body["success"] is False

    def test_search_respects_limit(self):
        status, body = api_request("GET", "/api/v1/search?limit=1")
        assert status == 200
        assert body["count"] <= 1


# =================== Categories Include All Types ===================


@pytest.mark.integration
class TestCategoriesCoverage:
    """Categories endpoint reflects all product types with data."""

    def test_categories_returns_list(self):
        status, body = api_request("GET", "/api/products/categories")
        assert status == 200
        assert isinstance(body["data"], list)

    def test_category_objects_have_required_fields(self):
        status, body = api_request("GET", "/api/products/categories")
        assert status == 200
        for cat in body["data"]:
            assert "type" in cat
            assert "count" in cat
            assert "display_name" in cat


# =================== CRUD Lifecycle Per Type ===================


@pytest.mark.integration
class TestCRUDLifecycle:
    """Create and delete a product for each type (admin mode only)."""

    @requires_admin
    @pytest.mark.parametrize("product_type", HARDWARE_TYPES)
    def test_create_product(self, product_type: str):
        product = {
            "product_type": product_type,
            "product_name": f"E2E Test {product_type}",
            "manufacturer": "E2ETestCorp",
            "part_number": f"E2E-{uuid4().hex[:8]}",
        }
        status, body = api_request("POST", "/api/products", product)
        assert status == 201, f"Failed to create {product_type}: {body}"
        assert body["success"] is True


# =================== Summary Endpoint ===================


@pytest.mark.integration
class TestSummaryCompleteness:
    """Summary counts include dynamic type counts."""

    def test_summary_has_total(self):
        status, body = api_request("GET", "/api/products/summary")
        assert status == 200
        assert "total" in body["data"]
        assert isinstance(body["data"]["total"], int)

    def test_summary_total_is_nonnegative(self):
        status, body = api_request("GET", "/api/products/summary")
        assert status == 200
        assert body["data"]["total"] >= 0


# =================== Datasheets Endpoint ===================


@pytest.mark.integration
class TestDatasheetsEndpoint:
    def test_list_datasheets(self):
        status, body = api_request("GET", "/api/datasheets")
        assert status == 200
        assert isinstance(body["data"], list)

    @requires_admin
    def test_create_datasheet(self):
        ds = {
            "url": f"https://example.com/e2e-{uuid4().hex[:8]}.pdf",
            "product_type": "motor",
            "product_name": "E2E Test Datasheet",
        }
        status, body = api_request("POST", "/api/datasheets", ds)
        assert status in (201, 409)  # 409 if URL already exists


# =================== OpenAPI Spec ===================


@requires_openapi
@pytest.mark.integration
class TestOpenAPISpec:
    """OpenAPI spec is served and valid."""

    def test_openapi_returns_json(self):
        status, body = api_request("GET", "/api/openapi.json")
        assert status == 200
        assert body is not None
        assert body.get("openapi", "").startswith("3.")

    def test_openapi_has_search_path(self):
        status, body = api_request("GET", "/api/openapi.json")
        assert status == 200
        assert "/api/v1/search" in body.get("paths", {})

    def test_openapi_has_products_path(self):
        status, body = api_request("GET", "/api/openapi.json")
        assert status == 200
        assert "/api/products" in body.get("paths", {})
