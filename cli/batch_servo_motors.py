"""Batch-ingest brushless / AC servo motor catalogs to populate products-dev.

Sibling to ``cli.batch_servo_drives`` — same shape, but ``product_type="motor"``
and a curated list of vendor motor catalogs (Yaskawa Sigma-7, Mitsubishi MR-J5,
Rockwell Kinetix, Siemens SIMOTICS S, ABB BSM, Panasonic MINAS A6, ...).

Usage:
    uv run python -m cli.batch_servo_motors             # run everything
    uv run python -m cli.batch_servo_motors --limit 3
    uv run python -m cli.batch_servo_motors --only yaskawa,siemens
    uv run python -m cli.batch_servo_motors --json-only

Per-catalog payloads land at outputs/motors/<slug>.json; the structured report
lands at outputs/batch_servo_motors_report.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from specodex.config import TABLE_NAME  # noqa: E402
from specodex.db.dynamo import DynamoDBClient  # noqa: E402
from specodex.scraper import process_datasheet  # noqa: E402

logger = logging.getLogger("batch-servo-motors")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@dataclass
class Target:
    slug: str
    manufacturer: str
    product_name: str
    product_family: str
    url: str
    pages: Optional[List[int]] = None


# All URLs verified to return Content-Type: application/pdf with HTTP 200.
TARGETS: List[Target] = [
    Target(
        slug="yaskawa-sigma7-rotary",
        manufacturer="Yaskawa",
        product_name="Sigma-7 Rotary Servomotor",
        product_family="Sigma-7 SGM7J / SGM7A / SGM7P / SGM7G / SGMMV",
        url=(
            "https://www.yaskawa.com.sg/editor/source/Sigma7series/"
            "7S_Rotary_sieps80000136d_3_0.pdf"
        ),
    ),
    Target(
        slug="yaskawa-sigma7-emech",
        manufacturer="Yaskawa",
        product_name="Sigma-7 Servo Drives & Motors",
        product_family="Sigma-7 SGD7 / SGM7",
        url=(
            "https://www.e-mechatronics.com/download/datas/catalog/"
            "cheps80000061/cheps80000061d_3_0.pdf"
        ),
    ),
    Target(
        slug="mitsubishi-mr-j5-hk-motor",
        manufacturer="Mitsubishi Electric",
        product_name="MELSERVO-J5 HK Rotary Servo Motors",
        product_family="HK-KT / HK-MT / HK-ST / HK-RT",
        url=(
            "https://dl.mitsubishielectric.com/dl/fa/document/manual/servo/"
            "sh030314eng/sh030314engl.pdf"
        ),
    ),
    Target(
        slug="rockwell-kinetix-rotary",
        manufacturer="Allen-Bradley",
        product_name="Kinetix Rotary Motion Specifications",
        product_family="VPL / VPC / VPF / VPH / VPS / MPL / MPM / MPF / MPS",
        url=(
            "https://literature.rockwellautomation.com/idc/groups/literature/"
            "documents/td/knx-td001_-en-p.pdf"
        ),
    ),
    Target(
        slug="rockwell-mp-series-low-inertia",
        manufacturer="Allen-Bradley",
        product_name="MP-Series Low-Inertia Motors",
        product_family="MPL Brushless Servo Motors",
        url=(
            "https://literature.rockwellautomation.com/idc/groups/literature/"
            "documents/pp/mp-pp001_-en-p.pdf"
        ),
    ),
    Target(
        slug="siemens-simotics-1fk7-preferred",
        manufacturer="Siemens",
        product_name="SIMOTICS S-1FK7 Preferred Servomotors",
        product_family="SIMOTICS S-1FK7",
        url=(
            "https://assets.new.siemens.com/siemens/assets/api/"
            "uuid:15a2381c-7e4a-40f5-9df9-48f818dbe768/"
            "simotics-s-1fk7-preferred-servomotors-brochure.pdf"
        ),
    ),
    Target(
        slug="siemens-simotics-1fk7-hmk",
        manufacturer="Siemens",
        product_name="SIMOTICS S-1FK7 Servomotors",
        product_family="SIMOTICS S-1FK7 Compact / High Dynamic / High Inertia",
        url=(
            "https://www.hmkdirect.com/downloads/motrona_10products/products/"
            "motors/servo/simotics_1fk7.pdf"
        ),
    ),
    Target(
        slug="abb-bsm-servo",
        manufacturer="ABB",
        product_name="BSM Series AC Servo Motors",
        product_family="BSM N-series Brushless Servo",
        url=(
            "https://library.e.abb.com/public/d7e5741298fe4760a818106caec8a45a/"
            "9AKK106417%20E%20Servo%20Motors_1215_WEB.pdf"
        ),
    ),
    Target(
        slug="abb-bsm-b-series",
        manufacturer="ABB",
        product_name="BSM B-Series Servo Motors",
        product_family="BSM B-Series Brushless Servo",
        url="https://library.e.abb.com/public/5fdf83537c10402abacd829dc8a0a97b/9AKK108329.pdf",
    ),
    Target(
        slug="panasonic-minas-a6-motor",
        manufacturer="Panasonic",
        product_name="MINAS A6 Family AC Servo Motors",
        product_family="MSMF / MQMF / MDMF / MHMF",
        url=(
            "https://www.motiontech.com.au/wp-content/uploads/2021/05/"
            "Panasonic-AC-Servo-Motor-and-Driver-Minas-A6-Family-"
            "Battery-Less-Absolute-Encoder-Motor.pdf"
        ),
    ),
]


@dataclass
class Result:
    slug: str
    manufacturer: str
    product_name: str
    url: str
    status: str
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    trace_tail: Optional[str] = None
    duration_s: float = 0.0


def _slug_to_output_path(slug: str) -> Path:
    out_dir = ROOT / "outputs" / "motors"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{slug}.json"


def run_target(
    target: Target,
    client: DynamoDBClient,
    api_key: str,
    write_json: bool = True,
) -> Result:
    logger.info("=" * 72)
    logger.info("[%s] %s — %s", target.slug, target.manufacturer, target.product_name)
    logger.info("URL: %s", target.url)
    started = datetime.now(timezone.utc)

    out_path = _slug_to_output_path(target.slug) if write_json else None

    try:
        status = process_datasheet(
            client=client,
            api_key=api_key,
            product_type="motor",
            manufacturer=target.manufacturer,
            product_name=target.product_name,
            product_family=target.product_family,
            url=target.url,
            pages=target.pages,
            output_path=out_path,
        )
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info("[%s] -> %s (%.1fs)", target.slug, status, elapsed)
        return Result(
            slug=target.slug,
            manufacturer=target.manufacturer,
            product_name=target.product_name,
            url=target.url,
            status=status,
            duration_s=elapsed,
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        tb = traceback.format_exc()
        trace_tail = "\n".join(tb.strip().splitlines()[-12:])
        logger.error("[%s] FAILED after %.1fs: %s", target.slug, elapsed, exc)
        return Result(
            slug=target.slug,
            manufacturer=target.manufacturer,
            product_name=target.product_name,
            url=target.url,
            status="failed",
            error_class=exc.__class__.__name__,
            error_message=str(exc),
            trace_tail=trace_tail,
            duration_s=elapsed,
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only", type=str, default=None)
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "outputs" / "batch_servo_motors_report.json",
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("GEMINI_API_KEY not set in environment or .env")
        return 2

    targets = TARGETS
    if args.only:
        needles = [n.strip().lower() for n in args.only.split(",") if n.strip()]
        targets = [t for t in targets if any(n in t.slug.lower() for n in needles)]
    if args.limit is not None:
        targets = targets[: args.limit]

    if not targets:
        logger.error("No targets selected (check --only / --limit filters)")
        return 2

    table_name = TABLE_NAME
    if args.json_only:
        logger.warning("--json-only: DynamoDB writes disabled")
        table_name = "products-dev-noop"
    logger.info("Table: %s  Targets: %d", table_name, len(targets))

    client = DynamoDBClient(table_name=table_name)

    results: List[Result] = []
    for i, target in enumerate(targets, 1):
        logger.info("--- [%d/%d] ---", i, len(targets))
        results.append(run_target(target, client, api_key))

    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    logger.info("=" * 72)
    logger.info("DONE. %s", " ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
    for r in results:
        if r.status == "failed":
            logger.info("  FAIL %s: %s — %s", r.slug, r.error_class, r.error_message)

    report = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "table": table_name,
        "total": len(results),
        "by_status": by_status,
        "results": [asdict(r) for r in results],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    logger.info("Report: %s", args.report)

    return 0 if by_status.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
