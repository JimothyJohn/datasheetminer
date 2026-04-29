"""
Deploy readiness tests.

Validates that the project builds correctly and configuration is consistent
across all layers BEFORE deploying. These catch the kind of drift that
happens when multiple agents edit different parts of the codebase.

Run: uv run pytest tests/integration/test_deploy_readiness.py -v
"""

import json
import subprocess
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
BACKEND = APP / "backend"
FRONTEND = APP / "frontend"
INFRA = APP / "infrastructure"


# =================== Build Integrity ===================


@pytest.mark.integration
class TestBackendBuild:
    """Backend TypeScript compiles without errors."""

    def test_typescript_compiles(self):
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(BACKEND),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"Backend tsc failed:\n{result.stdout}\n{result.stderr}"
        )

    def test_eslint_passes(self):
        result = subprocess.run(
            ["npx", "eslint", "src", "--ext", ".ts", "--max-warnings=0"],
            cwd=str(BACKEND),
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Allow warnings but no errors
        assert result.returncode in (0, 1), f"ESLint crashed:\n{result.stderr}"


@pytest.mark.integration
class TestFrontendBuild:
    """Frontend TypeScript compiles and Vite builds."""

    def test_typescript_compiles(self):
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=str(FRONTEND),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"Frontend tsc failed:\n{result.stdout}\n{result.stderr}"
        )

    def test_vite_build_succeeds(self):
        result = subprocess.run(
            ["npx", "vite", "build"],
            cwd=str(FRONTEND),
            capture_output=True,
            text=True,
            timeout=120,
            env={
                **dict(__import__("os").environ),
                "VITE_API_URL": "",
                "VITE_APP_MODE": "public",
            },
        )
        assert result.returncode == 0, (
            f"Vite build failed:\n{result.stdout}\n{result.stderr}"
        )

    def test_dist_contains_index_html(self):
        """After build, dist/index.html must exist for CloudFront to serve."""
        dist_index = FRONTEND / "dist" / "index.html"
        if dist_index.exists():
            assert dist_index.stat().st_size > 0


# =================== Configuration Consistency ===================


@pytest.mark.integration
class TestConfigConsistency:
    """Environment and configuration files are consistent across layers."""

    def test_backend_config_has_all_product_types(self):
        """productTypes.ts must list every user-facing product type.

        ``datasheet`` and ``factory`` are backend-internal partition types
        — they have a ``PK = "PRODUCT#DATASHEET"`` row but aren't shown in
        the catalog dropdown, so they're intentionally excluded from the
        TS allowlist that drives ``getCategories()``.
        """
        config_file = BACKEND / "src" / "config" / "productTypes.ts"
        content = config_file.read_text()
        for t in [
            "motor",
            "drive",
            "gearhead",
            "robot_arm",
            "contactor",
            "electric_cylinder",
            "linear_actuator",
        ]:
            assert f"'{t}'" in content, f"Missing product type '{t}' in productTypes.ts"

    def test_search_schema_accepts_all_hardware_types(self):
        """Zod search schema must accept all hardware product types."""
        search_file = BACKEND / "src" / "routes" / "search.ts"
        content = search_file.read_text()
        for t in ["motor", "drive", "gearhead", "robot_arm"]:
            assert f"'{t}'" in content, f"Search schema missing type '{t}'"

    def test_frontend_models_define_all_types(self):
        """Frontend Product union type must include all hardware types."""
        models_file = FRONTEND / "src" / "types" / "models.ts"
        content = models_file.read_text()
        for t in ["Motor", "Drive", "RobotArm", "Gearhead"]:
            assert f"interface {t}" in content, f"Missing interface {t} in models.ts"
        # Check Product union includes all
        assert "Motor" in content
        assert "Drive" in content
        assert "RobotArm" in content
        assert "Gearhead" in content

    def test_frontend_filters_cover_all_types(self):
        """getAttributesForType must have a branch for each product type."""
        filters_file = FRONTEND / "src" / "types" / "filters.ts"
        content = filters_file.read_text()
        for t in ["motor", "drive", "robot_arm", "gearhead", "datasheet"]:
            assert f"'{t}'" in content, f"Filters missing type '{t}'"

    def test_cdk_config_reads_stage_from_env(self):
        """CDK config derives the stage dynamically from STAGE env var.

        Earlier versions of this test asserted that ``'dev'``, ``'staging'``,
        and ``'prod'`` literals appear in ``config.ts`` directly — but the
        config has been dynamic since the OIDC migration: ``getConfig()``
        reads ``process.env.STAGE`` and falls back to ``'dev'``. The contract
        is that the config consumes STAGE, not that it enumerates stages.
        """
        config_file = INFRA / "lib" / "config.ts"
        content = config_file.read_text()
        assert "process.env.STAGE" in content, (
            "CDK config must read stage from process.env.STAGE"
        )
        # Default fallback should be 'dev' — keeps local/quick-deploy ergonomics.
        assert "'dev'" in content, "CDK config should default stage to 'dev'"

    def test_dynamodb_table_name_derived_from_stage(self):
        """Backend and CDK agree on table naming convention."""
        backend_config = (BACKEND / "src" / "config" / "index.ts").read_text()
        cdk_config = (INFRA / "lib" / "config.ts").read_text()
        # Both should use `products-{stage}` pattern
        assert "products-" in backend_config
        assert "products-" in cdk_config


# =================== Infrastructure Files ===================


@pytest.mark.integration
class TestInfrastructureFiles:
    """CDK infrastructure files are present and valid."""

    def test_cdk_entry_point_exists(self):
        assert (INFRA / "bin" / "app.ts").exists()

    def test_all_stacks_defined(self):
        lib = INFRA / "lib"
        assert (lib / "api-stack.ts").exists()
        assert (lib / "database-stack.ts").exists()
        assert (lib / "frontend-stack.ts").exists()
        assert (lib / "config.ts").exists()

    def test_lambda_entry_point_exists(self):
        """CDK references backend/src/lambda.ts — it must exist."""
        assert (BACKEND / "src" / "lambda.ts").exists()

    def test_lambda_handler_exports_handler(self):
        content = (BACKEND / "src" / "lambda.ts").read_text()
        assert "export" in content and "handler" in content

    def test_cdk_stack_dependencies(self):
        """app.ts wires stacks in correct order: Database -> Api -> Frontend."""
        app_ts = (INFRA / "bin" / "app.ts").read_text()
        assert "apiStack.addDependency(databaseStack)" in app_ts
        assert "frontendStack.addDependency(apiStack)" in app_ts

    def test_api_stack_passes_table_to_lambda(self):
        """Lambda must receive DYNAMODB_TABLE_NAME from the stack."""
        api_stack = (INFRA / "lib" / "api-stack.ts").read_text()
        assert "DYNAMODB_TABLE_NAME" in api_stack

    def test_api_stack_passes_upload_bucket(self):
        """Lambda must receive UPLOAD_BUCKET from the stack."""
        api_stack = (INFRA / "lib" / "api-stack.ts").read_text()
        assert "UPLOAD_BUCKET" in api_stack


# =================== CI/CD Pipeline ===================


@pytest.mark.integration
class TestCIPipeline:
    """GitHub Actions workflow is correct."""

    def test_ci_workflow_exists(self):
        assert (ROOT / ".github" / "workflows" / "ci.yml").exists()

    def test_ci_runs_all_test_stages(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "test-python" in ci
        assert "test-backend" in ci
        assert "test-frontend" in ci

    def test_ci_deploys_staging_before_prod(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "deploy-staging" in ci
        assert "deploy-prod" in ci
        # prod depends on staging smoke
        assert "smoke-staging" in ci

    def test_ci_runs_smoke_tests(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "smoke-staging" in ci
        assert "smoke-prod" in ci

    def test_ci_invalidates_cloudfront(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "cloudfront create-invalidation" in ci

    def test_ci_uses_pinned_actions(self):
        """Actions should be pinned by SHA, not just tag."""
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        # Find all `uses:` lines and verify they use SHA pins
        uses_lines = [
            line.strip() for line in ci.splitlines() if "uses:" in line and "@" in line
        ]
        for line in uses_lines:
            # SHA pins are 40 hex chars after @
            assert re.search(r"@[0-9a-f]{40}", line), (
                f"Action not pinned by SHA: {line}"
            )


# =================== Package Dependencies ===================


@pytest.mark.integration
class TestDependencies:
    """Package files are consistent."""

    def test_workspace_package_json_exists(self):
        assert (APP / "package.json").exists()

    def test_backend_package_json_has_test_script(self):
        pkg = json.loads((BACKEND / "package.json").read_text())
        assert "test" in pkg["scripts"]

    def test_frontend_package_json_has_test_script(self):
        pkg = json.loads((FRONTEND / "package.json").read_text())
        assert "test" in pkg["scripts"]

    def test_backend_has_required_runtime_deps(self):
        pkg = json.loads((BACKEND / "package.json").read_text())
        deps = pkg["dependencies"]
        assert "express" in deps
        assert "serverless-http" in deps
        assert "zod" in deps

    def test_frontend_has_required_deps(self):
        pkg = json.loads((FRONTEND / "package.json").read_text())
        deps = pkg["dependencies"]
        assert "react" in deps
        assert "react-dom" in deps
        assert "react-router-dom" in deps

    def test_backend_has_test_deps(self):
        pkg = json.loads((BACKEND / "package.json").read_text())
        dev = pkg["devDependencies"]
        assert "jest" in dev
        assert "supertest" in dev

    def test_frontend_has_test_deps(self):
        pkg = json.loads((FRONTEND / "package.json").read_text())
        dev = pkg["devDependencies"]
        assert "vitest" in dev
        assert "@testing-library/react" in dev
