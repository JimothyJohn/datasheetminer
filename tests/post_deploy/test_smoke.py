"""
Post-deployment smoke tests.
Lightweight checks to verify the system is operational after deployment.
Requires API_BASE_URL environment variable.
Run: API_BASE_URL=https://api.prod.example.com uv run pytest tests/post_deploy/ -v
"""

import json
import os
import time
import pytest
from urllib.request import Request, urlopen


BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:3001")


@pytest.mark.integration
class TestSmoke:
    def test_health_check_200(self):
        """Service is running and healthy."""
        req = Request(f"{BASE_URL}/health")
        with urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            body = json.loads(resp.read().decode())
            assert body["status"] == "healthy"

    def test_products_endpoint_200(self):
        """Products endpoint is accessible."""
        req = Request(f"{BASE_URL}/api/products")
        with urlopen(req, timeout=5) as resp:
            assert resp.status == 200

    def test_summary_endpoint_200(self):
        """Summary endpoint returns data."""
        req = Request(f"{BASE_URL}/api/products/summary")
        with urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            body = json.loads(resp.read().decode())
            assert "total" in body.get("data", {})

    def test_response_time_under_5s(self):
        """Health check responds within 5 seconds."""
        start = time.time()
        req = Request(f"{BASE_URL}/health")
        with urlopen(req, timeout=5) as resp:
            elapsed = time.time() - start
            assert resp.status == 200
            assert elapsed < 5.0, f"Response took {elapsed:.2f}s"

    def test_datasheets_endpoint_200(self):
        """Datasheets endpoint is accessible."""
        req = Request(f"{BASE_URL}/api/datasheets")
        with urlopen(req, timeout=5) as resp:
            assert resp.status == 200
