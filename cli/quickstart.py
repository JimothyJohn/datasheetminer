#!/usr/bin/env python3
"""
DatasheetMiner CLI — single entry point for all stages.

Usage:
    ./Quickstart dev              Start local dev servers (default)
    ./Quickstart test             Run all unit tests
    ./Quickstart staging [URL]    Run staging contract tests
    ./Quickstart deploy [--stage] Deploy to AWS via CDK
    ./Quickstart smoke [URL]      Run post-deployment smoke tests

Zero external dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

# ── Paths ──────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
LOG_DIR = ROOT / ".logs"

# ── Logging ────────────────────────────────────────────────────────

LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(LOG_DIR / "quickstart.log"),
    ],
)
log = logging.getLogger("quickstart")

# ── Colors ─────────────────────────────────────────────────────────

_USE_COLOR = sys.stderr.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def info(msg: str) -> None:
    log.info(_c("0;32", f"==> {msg}"))


def warn(msg: str) -> None:
    log.info(_c("1;33", f"    {msg}"))


def fail(msg: str) -> None:
    log.error(_c("0;31", f"ERROR: {msg}"))
    sys.exit(1)


# ── Helpers ────────────────────────────────────────────────────────


def _local_ip() -> str:
    """Get the LAN IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "localhost"


def require_cmd(name: str) -> str:
    """Return the path to a command, or fail."""
    path = shutil.which(name)
    if not path:
        fail(f"Missing dependency: {name}. Install it and re-run.")
    return path


def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> None:
    """Run a command, streaming output. Exit on failure."""
    merged = {**os.environ, **(env or {})}
    result = subprocess.run(cmd, cwd=cwd, env=merged)
    if result.returncode != 0:
        fail(f"Command failed (exit {result.returncode}): {' '.join(cmd)}")


def run_quiet(cmd: list[str], *, cwd: Path | None = None) -> str:
    """Run a command, capture output. Return stdout."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.stdout.strip()


def check_node_version() -> str:
    require_cmd("node")
    version = run_quiet(["node", "-v"]).lstrip("v")
    major = int(version.split(".")[0])
    if major < 18:
        fail(f"Node.js >= 18 required (found {version})")
    return version


def check_python_version() -> str:
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 11):
        fail(f"Python >= 3.11 required (found {v.major}.{v.minor})")
    return f"{v.major}.{v.minor}"


def ensure_env_files() -> None:
    info("Checking environment files")
    root_env = ROOT / ".env"
    app_env = APP / ".env"
    if not root_env.exists():
        shutil.copy(ROOT / ".env.example", root_env)
        warn("Created .env from .env.example — edit it with your API keys")
    if not app_env.exists():
        shutil.copy(APP / ".env.example", app_env)
        warn("Created app/.env from app/.env.example — edit it with your AWS config")


def install_python_deps() -> None:
    info("Installing Python dependencies")
    run(["uv", "sync", "--quiet"], cwd=ROOT)


def install_node_deps() -> None:
    info("Installing Node.js dependencies")
    run(["npm", "install", "--silent"], cwd=APP)


def health_check(url: str, retries: int = 30) -> bool:
    """Poll a health endpoint. Return True if it responds 200."""
    for i in range(retries):
        try:
            req = Request(f"{url}/health")
            with urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (URLError, OSError):
            pass
        time.sleep(1)
    return False


# ── Commands ───────────────────────────────────────────────────────


def cmd_dev(args: argparse.Namespace) -> None:
    """Start local dev servers with hot reload."""
    info("Checking dependencies")
    node_v = check_node_version()
    py_v = check_python_version()
    require_cmd("npm")
    require_cmd("uv")
    uv_v = run_quiet(["uv", "--version"]).split()[-1]
    log.info(f"  node {node_v}  python {py_v}  uv {uv_v}")

    ensure_env_files()
    install_python_deps()
    install_node_deps()

    port = os.environ.get("PORT", "3001")
    info(f"Starting backend (port {port}) and frontend (port 3000)")

    backend_log = open(LOG_DIR / "backend.log", "w")
    frontend_log = open(LOG_DIR / "frontend.log", "w")

    # Local dev always runs in admin mode (full write access)
    admin_env = {**os.environ, "APP_MODE": "admin"}

    backend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=APP / "backend",
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        env=admin_env,
    )
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=APP / "frontend",
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
    )

    procs = [backend, frontend]

    def shutdown(signum: int = 0, frame: object = None) -> None:
        info("Shutting down...")
        for p in procs:
            try:
                p.terminate()
                p.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                p.kill()
        backend_log.close()
        frontend_log.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    url = f"http://localhost:{port}"
    if not health_check(url):
        warn(f"Backend may not be ready — check {LOG_DIR}/backend.log")

    host = _local_ip()
    print()
    info("DatasheetMiner is running")
    print(f"  Frontend:  http://{host}:3000")
    print(f"  Backend:   http://{host}:{port}")
    print("  Mode:      admin (full access)")
    print(f"  Stage:     {os.environ.get('STAGE', 'dev')}")
    print(f"  Table:     {os.environ.get('DYNAMODB_TABLE_NAME', 'products-dev')}")
    print(f"  Logs:      {LOG_DIR}/")
    print()
    print("  Press Ctrl+C to stop")
    print()

    # Wait for either process to exit
    try:
        while True:
            for p in procs:
                ret = p.poll()
                if ret is not None:
                    warn(f"Process exited with code {ret}")
                    shutdown()
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


def cmd_test(args: argparse.Namespace) -> None:
    """Run all unit tests across Python, backend, and frontend."""
    info("Checking dependencies")
    check_node_version()
    check_python_version()
    require_cmd("npm")
    require_cmd("uv")

    ensure_env_files()

    info("Python unit tests")
    run(["uv", "run", "pytest", "tests/unit/", "-m", "not slow", "-q"], cwd=ROOT)

    info("Backend unit tests")
    run(["npm", "test"], cwd=APP / "backend")

    info("Frontend unit tests")
    run(["npm", "test"], cwd=APP / "frontend", env={"CI": "true"})

    info("All unit tests passed")


def cmd_staging(args: argparse.Namespace) -> None:
    """Run staging contract tests against a running server."""
    url = args.url
    info(f"Running staging contract tests against {url}")
    warn("Staging tests create/mutate data — do not run against production.")

    check_python_version()
    require_cmd("uv")

    run(
        ["uv", "run", "pytest", "tests/staging/", "-v"],
        cwd=ROOT,
        env={"API_BASE_URL": url},
    )
    info("Staging tests passed")


def _load_env_file(stage: str) -> dict[str, str]:
    """Load app/.env.{stage} if it exists. Returns key-value pairs."""
    env_file = APP / f".env.{stage}"
    if not env_file.exists():
        return {}
    info(f"Loading {env_file.relative_to(ROOT)}")
    result: dict[str, str] = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if key and value:
            result[key.strip()] = value.strip()
    return result


def cmd_deploy(args: argparse.Namespace) -> None:
    """Deploy to AWS via CDK."""
    stage = args.stage
    info(f"Deploying to AWS (stage={stage})")

    check_node_version()
    require_cmd("npm")
    require_cmd("aws")

    # Load stage-specific env file (os.environ takes precedence)
    stage_env = _load_env_file(stage)

    # Validate AWS credentials
    result = subprocess.run(
        ["aws", "sts", "get-caller-identity"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fail("AWS credentials not configured. Run: aws configure")

    account_id = os.environ.get("AWS_ACCOUNT_ID") or stage_env.get("AWS_ACCOUNT_ID")
    if not account_id:
        account_id = run_quiet(
            [
                "aws",
                "sts",
                "get-caller-identity",
                "--query",
                "Account",
                "--output",
                "text",
            ]
        )
        if not account_id:
            fail("AWS_ACCOUNT_ID not set. Export it or configure AWS CLI.")
        info(f"Auto-detected AWS_ACCOUNT_ID: {account_id}")

    if stage == "dev":
        warn("STAGE=dev (default). Use --stage prod for production deployments.")

    region = os.environ.get("AWS_REGION") or stage_env.get("AWS_REGION", "us-east-1")

    deploy_env = {
        "STAGE": stage,
        "APP_MODE": "public",
        "AWS_ACCOUNT_ID": account_id,
        "AWS_REGION": region,
        "CDK_DEFAULT_ACCOUNT": account_id,
        "CDK_DEFAULT_REGION": region,
        "DYNAMODB_TABLE_NAME": os.environ.get(
            "DYNAMODB_TABLE_NAME",
            stage_env.get("DYNAMODB_TABLE_NAME", f"products-{stage}"),
        ),
    }
    # Domain config: os.environ > stage env file
    domain_keys = ("DOMAIN_NAME", "CERTIFICATE_ARN", "HOSTED_ZONE_ID")
    for key in domain_keys:
        val = os.environ.get(key) or stage_env.get(key)
        if val:
            deploy_env[key] = val

    # Prod must have domain config — refuse to deploy without it
    if stage == "prod":
        missing = [k for k in domain_keys if k not in deploy_env]
        if missing:
            fail(
                f"Production deploy requires domain config: {', '.join(missing)}. "
                f"Set them in app/.env.prod or export as environment variables."
            )

    info("Installing workspace dependencies")
    run(["npm", "install", "--silent"], cwd=APP)

    info("Building frontend (public mode)")
    run(
        ["npm", "run", "build"],
        cwd=APP / "frontend",
        env={"VITE_API_URL": "", "VITE_APP_MODE": "public"},
    )

    info("Bootstrapping CDK")
    run(
        ["npx", "cdk", "bootstrap", f"aws://{account_id}/{region}"],
        cwd=APP / "infrastructure",
        env=deploy_env,
    )

    info("Deploying all stacks")
    run(
        [
            "npx",
            "cdk",
            "deploy",
            "--all",
            "--require-approval",
            "never",
            "--outputs-file",
            "cdk-outputs.json",
        ],
        cwd=APP / "infrastructure",
        env=deploy_env,
    )

    # Print results
    outputs_file = APP / "infrastructure" / "cdk-outputs.json"
    if outputs_file.exists():
        data = json.loads(outputs_file.read_text())
        site_url = cf_url = api_url = ""
        for stack in data.values():
            for key, val in stack.items():
                if "SiteUrl" in key:
                    site_url = val
                elif "CloudFrontUrl" in key:
                    cf_url = val
                elif "ApiEndpoint" in key:
                    api_url = val

        print()
        info("DatasheetMiner deployed successfully")
        print(f"  Stage:      {stage}")
        print(f"  Table:      {deploy_env['DYNAMODB_TABLE_NAME']}")
        if site_url:
            print(f"  App URL:    {site_url}")
            print(f"  CloudFront: {cf_url}")
        elif cf_url:
            print(f"  App URL:    {cf_url}")
        if api_url:
            print(f"  API URL:    {api_url}")
        print(f"  Region:     {region}")
        print(f"  Account:    {account_id}")
        base = site_url or cf_url
        if base:
            print(f"  Health:     {base}/health")
        print()


def cmd_smoke(args: argparse.Namespace) -> None:
    """Run post-deployment smoke tests."""
    url = args.url
    info(f"Smoke testing {url}")

    check_python_version()
    require_cmd("uv")

    # Quick health check before running the full suite
    info("Checking health endpoint")
    if not health_check(url, retries=5):
        warn(f"Health check failed at {url}/health — running tests anyway")

    run(
        ["uv", "run", "pytest", "tests/post_deploy/", "-v"],
        cwd=ROOT,
        env={"API_BASE_URL": url},
    )
    info("Smoke tests passed")


def cmd_process(args: argparse.Namespace) -> None:
    """Process queued PDF uploads from S3."""
    stage = args.stage
    bucket = (
        args.bucket
        or f"datasheetminer-uploads-{stage}-{os.environ.get('AWS_ACCOUNT_ID', 'unknown')}"
    )

    info(f"Processing upload queue: s3://{bucket}/queue/")
    check_python_version()
    require_cmd("uv")

    process_env = {
        "STAGE": stage,
        "DYNAMODB_TABLE_NAME": os.environ.get(
            "DYNAMODB_TABLE_NAME", f"products-{stage}"
        ),
        "AWS_REGION": os.environ.get("AWS_REGION", "us-east-1"),
    }
    once_flag = ["--once"] if args.once else []

    run(
        [
            "uv",
            "run",
            "python",
            "-c",
            f"from cli.processor import run; run('{bucket}', once={'True' if args.once else 'False'})",
        ],
        cwd=ROOT,
        env=process_env,
    )


# ── CLI ────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Quickstart",
        description="DatasheetMiner — dev, test, deploy, and verify.",
    )
    sub = parser.add_subparsers(dest="command")

    # dev (default)
    sub.add_parser("dev", help="Start local dev servers with hot reload")

    # test
    sub.add_parser("test", help="Run all unit tests (Python + backend + frontend)")

    # staging
    p = sub.add_parser("staging", help="Run staging contract tests against a server")
    p.add_argument(
        "url",
        nargs="?",
        default="http://localhost:3001",
        help="API base URL (default: localhost:3001)",
    )

    # deploy
    p = sub.add_parser("deploy", help="Deploy to AWS via CDK")
    p.add_argument(
        "--stage",
        default=os.environ.get("STAGE", "dev"),
        choices=["dev", "staging", "prod"],
        help="Deployment stage (default: dev)",
    )

    # smoke
    p = sub.add_parser("smoke", help="Run post-deployment smoke tests")
    p.add_argument(
        "url",
        nargs="?",
        default="http://localhost:3001",
        help="API base URL (default: localhost:3001)",
    )

    # process
    p = sub.add_parser("process", help="Process queued PDF uploads from S3")
    p.add_argument(
        "--stage",
        default=os.environ.get("STAGE", "dev"),
        choices=["dev", "staging", "prod"],
        help="Stage (determines bucket and table names)",
    )
    p.add_argument("--bucket", default=None, help="Override S3 bucket name")
    p.add_argument(
        "--once", action="store_true", help="Process queue once and exit (don't poll)"
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Default to dev if no subcommand given
    if not args.command:
        args.command = "dev"
        args = parser.parse_args(["dev"])

    commands = {
        "dev": cmd_dev,
        "test": cmd_test,
        "staging": cmd_staging,
        "deploy": cmd_deploy,
        "smoke": cmd_smoke,
        "process": cmd_process,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
