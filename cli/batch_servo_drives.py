"""Batch-ingest servo drive catalogs to help the agent learn extraction gaps.

This is a one-shot driver script for a learning exercise, not a long-lived
pipeline tool. It loops over a curated list of direct PDF URLs, invokes the
library entry point ``specodex.scraper.process_datasheet`` on each,
captures per-catalog status + error snippets to a JSON log, and — because
``DYNAMODB_TABLE_NAME=products-dev`` is set — writes successful extractions
to the dev DynamoDB table as it goes.

Usage:
    uv run python -m cli.batch_servo_drives             # run everything
    uv run python -m cli.batch_servo_drives --limit 3   # pilot first N
    uv run python -m cli.batch_servo_drives --only yaskawa,mitsubishi
    uv run python -m cli.batch_servo_drives --json-only # write JSON, no DB

The report JSON lands at outputs/batch_servo_drives_report.json and each
catalog's extracted payload lands at outputs/drives/<slug>.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Ensure repo root is on sys.path so "cli" imports work when run as module.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from specodex.config import TABLE_NAME  # noqa: E402
from specodex.db.dynamo import DynamoDBClient  # noqa: E402
from specodex.scraper import process_datasheet  # noqa: E402

logger = logging.getLogger("batch-servo-drives")
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
    # Optional page hints. None → let scraper auto-detect.
    pages: Optional[List[int]] = None


# Curated list — one PDF per vendor, biased toward catalog/datasheet
# documents over 500-page installation manuals. Two already in urls.json
# (Digitax HD, Powerdrive MD) are intentionally left off since process_
# datasheet skips on product_exists.
TARGETS: List[Target] = [
    Target(
        slug="yaskawa-sigma7",
        manufacturer="Yaskawa",
        product_name="Sigma-7",
        product_family="Sigma-7 Series AC Servo Drives",
        url=(
            "https://www.yaskawa.com/delegate/getAttachment"
            "?documentId=BL.Sigma-7.01&cmd=documents"
            "&documentName=BL.Sigma-7.01.pdf"
        ),
    ),
    Target(
        slug="mitsubishi-mr-j5",
        manufacturer="Mitsubishi Electric",
        product_name="MELSERVO-J5",
        product_family="MR-J5 400V Class Servo Amplifiers",
        url=(
            "https://eu-assets.contentstack.com/v3/assets/blt5412ff9af9aef77f/"
            "blt209211edac0549ce/61f6636afe4fd2454a9ddfec/"
            "efccc385-7b46-11eb-8592-b8ca3a62a094_sv2011-2e.pdf"
        ),
    ),
    Target(
        slug="rockwell-kinetix-5700",
        manufacturer="Rockwell Automation",
        product_name="Kinetix 5700",
        product_family="Kinetix Servo Drives Technical Data",
        url=(
            "https://literature.rockwellautomation.com/idc/groups/literature/"
            "documents/td/knx-td003_-en-p.pdf"
        ),
    ),
    Target(
        slug="siemens-sinamics-s210",
        manufacturer="Siemens",
        product_name="SINAMICS S210",
        product_family="SINAMICS S210 Servo Drive System",
        url=(
            "https://cache.industry.siemens.com/dl/files/800/109753800/"
            "att_937523/v1/S210_1FK2_op_instr_011217_eng.pdf"
        ),
    ),
    Target(
        slug="abb-microflex-e190",
        manufacturer="ABB",
        product_name="MicroFlex e190",
        product_family="MicroFlex e190 Servo Drive",
        url=(
            "https://scciclient.blob.core.windows.net/ecdcontrolscom/"
            "uploads/documents/productdetail/"
            "abb-microflex-e190-leaflet-06-21-18-2627.pdf"
        ),
    ),
    Target(
        slug="schneider-lexium32",
        manufacturer="Schneider Electric",
        product_name="Lexium 32",
        product_family="Lexium 32 Servo Drive Catalog",
        url=(
            "https://media.distributordatasolutions.com/228/schneider_synd_json/"
            "bc3de59554d5bd35a6188ac34643c0819e5bd187.pdf"
        ),
    ),
    Target(
        slug="kollmorgen-akd2g",
        manufacturer="Kollmorgen",
        product_name="AKD2G",
        product_family="AKD2G Servo Drive",
        url="https://www.micromech.co.uk/wp-content/uploads/2023/10/akd2g_servo_drive.pdf",
    ),
    Target(
        slug="delta-asda-a3",
        manufacturer="Delta Electronics",
        product_name="ASDA-A3",
        product_family="ASDA-A3 Series AC Servo Drive",
        url="https://deltaacdrives.com/Delta-ASDA-A3-Servo-Drive-Catalog.pdf",
    ),
    Target(
        slug="omron-1s",
        manufacturer="Omron",
        product_name="1S-series",
        product_family="1S-series Servo Drive with EtherCAT",
        url=(
            "https://files.omron.eu/downloads/latest/datasheet/en/"
            "i188e_r88d-1sn_-ect_1s-series_servo_drive_datasheet_en.pdf"
        ),
    ),
    Target(
        slug="rexroth-indradrive-cs",
        manufacturer="Bosch Rexroth",
        product_name="IndraDrive Cs",
        product_family="IndraDrive Cs Servo Drives",
        url=(
            "https://www.cmafh.com/images/Master%20PDFs/BRC/Drives/"
            "Rexroth%20CS%20Drive%20Data%20Sheet%20p146994_en.pdf"
        ),
    ),
    Target(
        slug="panasonic-minas-a6",
        manufacturer="Panasonic",
        product_name="MINAS A6",
        product_family="MINAS A6 AC Servo Drives",
        url="https://isecontrols.com/wp-content/uploads/2017/03/panasonic-minas-a6_ctlg_e.pdf",
    ),
    Target(
        slug="lenze-i950",
        manufacturer="Lenze",
        product_name="i950",
        product_family="i950 Servo Inverters",
        url=(
            "https://www.lenze.com/fileadmin/lenze/documents/en/flyer/"
            "Flyer_i950_servo_inverters_13569164_en-GB.pdf"
        ),
    ),
    Target(
        slug="beckhoff-ax5000",
        manufacturer="Beckhoff",
        product_name="AX5000",
        product_family="AX5000 Digital Compact Servo Drives",
        url="https://download.beckhoff.com/download/document/motion/ax5000_hw2_functional_description_en.pdf",
    ),
    Target(
        slug="parker-compax3",
        manufacturer="Parker Hannifin",
        product_name="Compax3",
        product_family="Compax3 Servo Drive Systems",
        url="https://www.parkermotion.com/literature/Compax3Brochure_Sept2010.pdf",
    ),
    Target(
        slug="br-acopos-p3",
        manufacturer="B&R Industrial Automation",
        product_name="ACOPOS P3",
        product_family="ACOPOS P3 Servo Drive",
        url=(
            "https://www.br-automation.com/downloads_br_productcatalogue/"
            "BRP44400000000000000528896/MAACPP3-ENG_V1.10.pdf"
        ),
    ),
    Target(
        slug="sanyo-sanmotion-r",
        manufacturer="Sanyo Denki",
        product_name="SANMOTION R",
        product_family="SANMOTION R 3E 400V AC Servo",
        url=(
            "https://www.sanyodenki.com/archive/document/product/servo/"
            "catalog_E_pdf/SANMOTION_R_3E_AC400V_550W-55kW_E.pdf"
        ),
    ),
    Target(
        slug="estun-pronet",
        manufacturer="ESTUN",
        product_name="ProNet",
        product_family="ProNet Series AC Servo",
        url="http://www.myostat.ca/documents/Estun%20ProNet%20servo%20system%20brochure2.pdf",
    ),
    Target(
        slug="nidec-unidrive-m700",
        manufacturer="Nidec Control Techniques",
        product_name="Unidrive M700",
        product_family="Unidrive M700 High Performance AC/Servo",
        url=(
            "https://acim.nidec.com/drives/control-techniques/-/media/Project/"
            "Nidec/ControlTechniques/Documents/Datasheets/"
            "Unidrive-M700-Datasheet.pdf"
        ),
    ),
    Target(
        slug="inovance-is620",
        manufacturer="Inovance",
        product_name="IS620",
        product_family="IS620 Series Single Axis Servo",
        url=(
            "https://www.inovance.eu/fileadmin/downloads/Brochures/EN/"
            "IS620_Br_EN_Spreads_Web_V4.1.pdf"
        ),
    ),
    Target(
        slug="emerson-epsilon-ep",
        manufacturer="Emerson",
        product_name="Epsilon EP",
        product_family="Epsilon EP Compact Servo Drive",
        url="https://www.rgspeed.com/assets/documents/servo/control-technique/epsilon-ep.pdf",
    ),
]


@dataclass
class Result:
    slug: str
    manufacturer: str
    product_name: str
    url: str
    status: str  # success | skipped | failed
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    trace_tail: Optional[str] = None
    duration_s: float = 0.0


def _slug_to_output_path(slug: str) -> Path:
    out_dir = ROOT / "outputs" / "drives"
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
            product_type="drive",
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
        # Keep only the last 12 lines of the traceback for the report.
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
    parser.add_argument(
        "--limit", type=int, default=None, help="Run first N targets only"
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated substring filters on slug (e.g. yaskawa,rockwell)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Write JSON, do NOT push to DynamoDB (overrides env table)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "outputs" / "batch_servo_drives_report.json",
        help="Where to write the structured run report",
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("GEMINI_API_KEY not set in environment or .env")
        return 2

    # Filter targets
    targets = TARGETS
    if args.only:
        needles = [n.strip().lower() for n in args.only.split(",") if n.strip()]
        targets = [t for t in targets if any(n in t.slug.lower() for n in needles)]
    if args.limit is not None:
        targets = targets[: args.limit]

    if not targets:
        logger.error("No targets selected (check --only / --limit filters)")
        return 2

    # Point DynamoDB client at dev table (honor env var, error if suspicious)
    table_name = TABLE_NAME
    if args.json_only:
        logger.warning(
            "--json-only: DynamoDB writes disabled (using fake table handle)"
        )
        # process_datasheet still needs a client; point it at a non-existent
        # table and rely on product_exists returning False + batch_create failing
        # silently. Cleaner would be to pass None, but the scraper doesn't allow
        # that. We accept that --json-only may log DynamoDB errors.
        table_name = "products-dev-noop"
    logger.info("Table: %s  Targets: %d", table_name, len(targets))

    client = DynamoDBClient(table_name=table_name)

    results: List[Result] = []
    for i, target in enumerate(targets, 1):
        logger.info("--- [%d/%d] ---", i, len(targets))
        results.append(run_target(target, client, api_key))

    # Summary
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    logger.info("=" * 72)
    logger.info("DONE. %s", " ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
    for r in results:
        if r.status == "failed":
            logger.info("  FAIL %s: %s — %s", r.slug, r.error_class, r.error_message)

    # Write report
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
