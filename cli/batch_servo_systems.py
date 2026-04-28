"""Batch-ingest the *missing half* of joint servo system catalogs.

Many vendor PDFs document both the drive amplifier and the rotary servo
motor for a product family in a single document (Yaskawa Sigma-7
e-mechatronics catalog, Panasonic MINAS A6 "Motor and Driver" catalog,
Mitsubishi MR-J5 SV2011 catalog, ESTUN ProNet system brochure, …). The
sibling scripts ``cli.batch_servo_drives`` and ``cli.batch_servo_motors``
have already ingested *one side* of each of these. Each entry here picks
up the *other side* — same URL, opposite ``product_type`` — for a free
extraction with no new datasheet sourcing.

Why this is its own script and not new entries in the sibling lists:

* The ingest log is keyed by URL; ``should_skip`` would short-circuit a
  second pass on a URL that previously succeeded. We pass ``force=True``
  here to bypass that. ``product_exists`` (keyed by
  ``(product_type, manufacturer, product_name)``) remains the dedupe
  authority and prevents collisions with the side that's already ingested.
* Targets are intentionally narrow — high-confidence joint catalogs only
  (filename or family name explicitly mentions both drive and motor, or
  the matching sibling extraction yielded enough rows to confirm the PDF
  is dense enough to also contain the other half).

Usage:
    uv run python -m cli.batch_servo_systems              # run everything
    uv run python -m cli.batch_servo_systems --limit 2
    uv run python -m cli.batch_servo_systems --only mitsubishi,panasonic
    uv run python -m cli.batch_servo_systems --json-only

Per-target payloads land at outputs/<product_type>s/<slug>.json (matching
sibling-script conventions). The structured run report lands at
outputs/batch_servo_systems_report.json.
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

logger = logging.getLogger("batch-servo-systems")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@dataclass
class Target:
    slug: str
    manufacturer: str
    product_type: str  # "drive" | "motor" — the missing side for this URL
    product_name: str
    product_family: str
    url: str
    pages: Optional[List[int]] = None


# Each entry: a URL whose *other* side is already in products-dev via a
# sibling batch script. The product_type / name / family below describe
# the half that is NOT yet ingested.
TARGETS: List[Target] = [
    # Yaskawa Sigma-7 e-mechatronics catalog — motor side ingested as
    # ``yaskawa-sigma7-emech`` (count=20). Drive side (SGD7S/SGD7W) missing.
    Target(
        slug="yaskawa-sigma7-emech-drive",
        manufacturer="Yaskawa",
        product_type="drive",
        product_name="Sigma-7 SGD7 Servo Amplifiers",
        product_family="Sigma-7 SGD7S / SGD7W",
        url=(
            "https://www.e-mechatronics.com/download/datas/catalog/"
            "cheps80000061/cheps80000061d_3_0.pdf"
        ),
    ),
    # Panasonic MINAS A6 family catalog — filename "Servo-Motor-and-Driver"
    # makes the joint nature explicit. Motor side ingested as
    # ``panasonic-minas-a6-motor`` (count=180). Drive side missing.
    Target(
        slug="panasonic-minas-a6-drive",
        manufacturer="Panasonic",
        product_type="drive",
        product_name="MINAS A6 Family AC Servo Drives",
        product_family="MADLN / MBDLN / MCDLN / MDDLN",
        url=(
            "https://www.motiontech.com.au/wp-content/uploads/2021/05/"
            "Panasonic-AC-Servo-Motor-and-Driver-Minas-A6-Family-"
            "Battery-Less-Absolute-Encoder-Motor.pdf"
        ),
    ),
    # Mitsubishi MR-J5 SV2011 catalog — drive side ingested as
    # ``mitsubishi-mr-j5`` (count=20). The MELSERVO-J5 catalog also
    # documents the matching HK rotary servo motors (the motor
    # instruction manual sh030314engl.pdf is a separate, denser source
    # already ingested as ``mitsubishi-mr-j5-hk-motor``; this run picks
    # up whatever motor specs the sales catalog carries).
    Target(
        slug="mitsubishi-mr-j5-catalog-motor",
        manufacturer="Mitsubishi Electric",
        product_type="motor",
        product_name="MELSERVO-J5 HK Series Servo Motors (catalog)",
        product_family="HK-KT / HK-MT / HK-ST / HK-RT",
        url=(
            "https://eu-assets.contentstack.com/v3/assets/blt5412ff9af9aef77f/"
            "blt209211edac0549ce/61f6636afe4fd2454a9ddfec/"
            "efccc385-7b46-11eb-8592-b8ca3a62a094_sv2011-2e.pdf"
        ),
    ),
    # ESTUN ProNet "servo system brochure" — drive side ingested as
    # ``estun-pronet`` (count=68). System brochure → motor side present.
    Target(
        slug="estun-pronet-motor",
        manufacturer="ESTUN",
        product_type="motor",
        product_name="EM Series AC Servo Motors",
        product_family="EMG / EMJ / EML",
        url="http://www.myostat.ca/documents/Estun%20ProNet%20servo%20system%20brochure2.pdf",
    ),
    # Sanyo Denki SANMOTION R 3E AC400V catalog. Filename power range
    # "550W-55kW" is motor sizing; the catalog covers both the R 3E
    # amplifiers and the matching motor frames. Drive side ingested as
    # ``sanyo-sanmotion-r``. Motor side missing.
    Target(
        slug="sanyo-sanmotion-r-motor",
        manufacturer="Sanyo Denki",
        product_type="motor",
        product_name="SANMOTION R 3E AC400V Servo Motors",
        product_family="SANMOTION R 3E AC400V",
        url=(
            "https://www.sanyodenki.com/archive/document/product/servo/"
            "catalog_E_pdf/SANMOTION_R_3E_AC400V_550W-55kW_E.pdf"
        ),
    ),
]


@dataclass
class Result:
    slug: str
    manufacturer: str
    product_type: str
    product_name: str
    url: str
    status: str  # success | skipped | failed
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    trace_tail: Optional[str] = None
    duration_s: float = 0.0


def _output_path(slug: str, product_type: str) -> Path:
    out_dir = ROOT / "outputs" / f"{product_type}s"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{slug}.json"


def run_target(
    target: Target,
    client: DynamoDBClient,
    api_key: str,
    write_json: bool = True,
) -> Result:
    logger.info("=" * 72)
    logger.info(
        "[%s] %s — %s (%s)",
        target.slug,
        target.manufacturer,
        target.product_name,
        target.product_type,
    )
    logger.info("URL: %s", target.url)
    started = datetime.now(timezone.utc)

    out_path = _output_path(target.slug, target.product_type) if write_json else None

    try:
        status = process_datasheet(
            client=client,
            api_key=api_key,
            product_type=target.product_type,
            manufacturer=target.manufacturer,
            product_name=target.product_name,
            product_family=target.product_family,
            url=target.url,
            pages=target.pages,
            output_path=out_path,
            force=True,  # bypass ingest-log skip; product_exists still dedupes
        )
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info("[%s] -> %s (%.1fs)", target.slug, status, elapsed)
        return Result(
            slug=target.slug,
            manufacturer=target.manufacturer,
            product_type=target.product_type,
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
            product_type=target.product_type,
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
        default=ROOT / "outputs" / "batch_servo_systems_report.json",
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
