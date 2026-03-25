"""Tests for the agent-facing CLI (cli/agent.py).

All tests are offline — S3, DynamoDB, and Gemini are mocked.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cli.agent import (
    _build_metadata,
    _extract_products,
    _json_out,
    _normalize,
    _parse_pages,
    _resolve_bucket,
    build_parser,
    cmd_schemas,
)


MFG = "TestMfg"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(**overrides) -> SimpleNamespace:
    """Build a minimal argparse-like namespace with sane defaults."""
    defaults = {
        "stage": "dev",
        "bucket": None,
        "s3_key": "queue/abc123/test.pdf",
        "type": "motor",
        "product_name": "TestMotor",
        "manufacturer": MFG,
        "product_family": "",
        "pages": None,
        "output": None,
        "keep": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParser:
    def test_schemas_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["schemas"])
        assert args.command == "schemas"

    def test_list_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_status_requires_id(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["status"])

    def test_status_with_id(self):
        parser = build_parser()
        args = parser.parse_args(["status", "abc-123"])
        assert args.datasheet_id == "abc-123"

    def test_extract_requires_type(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["extract", "queue/id/file.pdf"])

    def test_extract_full(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "extract",
                "queue/id/file.pdf",
                "-t",
                "motor",
                "--manufacturer",
                "Maxon",
                "--product-name",
                "EC-45",
                "--pages",
                "1,3,5",
                "-o",
                "out.json",
            ]
        )
        assert args.type == "motor"
        assert args.manufacturer == "Maxon"
        assert args.pages == "1,3,5"
        assert args.output == "out.json"

    def test_process_requires_type(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["process", "queue/id/file.pdf"])

    def test_process_keep_flag(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "process",
                "queue/id/file.pdf",
                "-t",
                "drive",
                "--keep",
            ]
        )
        assert args.keep is True
        assert args.type == "drive"

    def test_process_all_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["process-all"])
        assert args.command == "process-all"
        assert args.keep is False

    def test_global_stage(self):
        parser = build_parser()
        args = parser.parse_args(["--stage", "prod", "schemas"])
        assert args.stage == "prod"

    def test_global_bucket_override(self):
        parser = build_parser()
        args = parser.parse_args(["--bucket", "my-bucket", "list"])
        assert args.bucket == "my-bucket"


# ---------------------------------------------------------------------------
# _resolve_bucket
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResolveBucket:
    def test_explicit_bucket(self):
        args = _make_args(bucket="custom-bucket")
        assert _resolve_bucket(args) == "custom-bucket"

    @patch.dict("os.environ", {"UPLOAD_BUCKET": "env-bucket"}, clear=False)
    def test_env_bucket(self):
        args = _make_args()
        assert _resolve_bucket(args) == "env-bucket"

    @patch.dict(
        "os.environ", {"AWS_ACCOUNT_ID": "123456", "STAGE": "prod"}, clear=False
    )
    def test_auto_bucket_with_account(self):
        args = _make_args(stage="prod")
        result = _resolve_bucket(args)
        assert result == "datasheetminer-uploads-prod-123456"

    @patch.dict("os.environ", {}, clear=True)
    def test_auto_bucket_no_account(self):
        args = _make_args(stage="dev")
        result = _resolve_bucket(args)
        assert result == "datasheetminer-uploads-dev"


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNormalize:
    def test_basic(self):
        assert _normalize("Maxon Motor") == "maxonmotor"

    def test_special_chars(self):
        assert _normalize("Nidec Corp.") == "nideccorp"

    def test_none(self):
        assert _normalize(None) == ""

    def test_empty(self):
        assert _normalize("") == ""

    def test_hyphens_removed(self):
        assert _normalize("EC-45") == "ec45"


# ---------------------------------------------------------------------------
# _parse_pages
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParsePages:
    def test_none(self):
        assert _parse_pages(None) is None

    def test_empty(self):
        assert _parse_pages("") is None

    def test_single(self):
        assert _parse_pages("3") == [3]

    def test_multiple(self):
        assert _parse_pages("1,3,5") == [1, 3, 5]

    def test_invalid_falls_back(self):
        assert _parse_pages("a,b,c") is None


# ---------------------------------------------------------------------------
# _build_metadata
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildMetadata:
    @patch.dict("os.environ", {}, clear=True)
    def test_basic(self):
        args = _make_args(
            product_name="EC-45",
            manufacturer="Maxon",
            product_family="EC",
            pages="1,3",
        )
        meta = _build_metadata(args)
        assert meta["product_name"] == "EC-45"
        assert meta["manufacturer"] == "Maxon"
        assert meta["product_family"] == "EC"
        assert meta["pages"] == [1, 3]
        assert "s3://" in meta["datasheet_url"]

    @patch.dict("os.environ", {}, clear=True)
    def test_no_pages(self):
        args = _make_args()
        meta = _build_metadata(args)
        assert meta["pages"] is None


# ---------------------------------------------------------------------------
# _json_out
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestJsonOut:
    def test_outputs_json_to_stdout(self, capsys):
        with pytest.raises(SystemExit) as exc:
            _json_out({"key": "value"})
        assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["key"] == "value"

    def test_exit_code_propagated(self):
        with pytest.raises(SystemExit) as exc:
            _json_out({"err": "bad"}, exit_code=1)
        assert exc.value.code == 1


# ---------------------------------------------------------------------------
# cmd_schemas
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCmdSchemas:
    def test_returns_known_types(self, capsys):
        with pytest.raises(SystemExit) as exc:
            cmd_schemas(_make_args())
        assert exc.value.code == 0
        data = json.loads(capsys.readouterr().out)
        type_names = [s["type"] for s in data]
        assert "motor" in type_names
        assert "drive" in type_names
        for schema in data:
            assert "fields" in schema
            assert schema["spec_fields"] > 0


# ---------------------------------------------------------------------------
# _extract_products (mocked Gemini)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractProducts:
    def test_unknown_product_type_raises(self):
        with pytest.raises(ValueError, match="Unknown product type"):
            _extract_products(b"fake-pdf", "nonexistent", "key", {})

    @patch("datasheetminer.llm.generate_content")
    @patch("datasheetminer.utils.parse_gemini_response")
    def test_no_products_raises(self, mock_parse, mock_gen):
        mock_gen.return_value = MagicMock()
        mock_parse.return_value = []

        with pytest.raises(ValueError, match="no valid products"):
            _extract_products(b"pdf", "motor", "key", {"manufacturer": MFG})

    @patch("datasheetminer.llm.generate_content")
    @patch("datasheetminer.utils.parse_gemini_response")
    @patch("datasheetminer.quality.filter_products")
    def test_successful_extraction(self, mock_filter, mock_parse, mock_gen):
        from datasheetminer.models.motor import Motor

        motor = Motor(
            product_name="TestMotor",
            product_type="motor",
            manufacturer=MFG,
            part_number="MTR-001",
            rated_voltage="24;V",
            rated_speed="3000;rpm",
            rated_torque="0.5;Nm",
            rated_power="150;W",
            rated_current="6;A",
            peak_current="12;A",
        )
        mock_gen.return_value = MagicMock()
        mock_parse.return_value = [motor]
        mock_filter.return_value = ([motor], [])

        result = _extract_products(
            b"pdf-bytes",
            "motor",
            "key",
            {"manufacturer": MFG, "product_name": "TestMotor"},
        )
        assert len(result) == 1
        # Verify deterministic ID was assigned
        assert result[0].product_id is not None
