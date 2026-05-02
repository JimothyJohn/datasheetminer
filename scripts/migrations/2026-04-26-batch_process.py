#!/usr/bin/env python3
"""Batch process all raw_pdfs/ from S3 through dsm-agent pipeline.

One-shot historical bulk ingest from 2026-04-26. The PDF list is
hardcoded; re-running blindly would re-ingest the same set. Kept under
scripts/migrations/ for provenance, not as an active tool.

Usage:
    source .env && DYNAMODB_TABLE_NAME=products-dev \\
        uv run python scripts/migrations/2026-04-26-batch_process.py
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / ".logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(LOG_DIR / "batch_process.log"),
    ],
)
log = logging.getLogger("batch")

# Mapping: s3_key -> (manufacturer, product_name, product_type)
# Best-effort from filenames; LLM handles the rest
PDFS: list[dict] = [
    {
        "key": "raw_pdfs/0900766b813e67a1.pdf",
        "manufacturer": "Phoenix Contact",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/0900766b8162b79a.pdf",
        "manufacturer": "Phoenix Contact",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/23h118s119-m1-portescap-dc-motors.pdf",
        "manufacturer": "Portescap",
        "name": "23H DC Motors",
        "type": "motor",
    },
    {"key": "raw_pdfs/8803450814494.pdf", "manufacturer": "Unknown", "type": "motor"},
    {"key": "raw_pdfs/8815460712478.pdf", "manufacturer": "Unknown", "type": "motor"},
    {
        "key": "raw_pdfs/BG_ Dunkermotoren Catalog_1508.pdf",
        "manufacturer": "Dunkermotoren",
        "name": "BG Series",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/BG_Series_Brushless_DC_Motors.pdf",
        "manufacturer": "Dunkermotoren",
        "name": "BG Series",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/BLDC Motor_BLDC Motor with Hall sensor Datasheet.pdf",
        "manufacturer": "Unknown",
        "name": "BLDC Motor",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/Brushless_DC_Motor.pdf",
        "manufacturer": "Unknown",
        "name": "Brushless DC Motor",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/D-Series-Motors.pdf",
        "manufacturer": "Unknown",
        "name": "D-Series Motors",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/E95s_3_Datasheet_R1scrn.pdf",
        "manufacturer": "Unknown",
        "name": "E95s",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/EC033A-30M0-A06-(1303)-Pittman-datasheet-48846624.pdf",
        "manufacturer": "Pittman",
        "name": "EC033A",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/EN_22L_ML_FMM.pdf",
        "manufacturer": "Faulhaber",
        "name": "22L ML",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/EN_22L_SB_FMM.pdf",
        "manufacturer": "Faulhaber",
        "name": "22L SB",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/EN_30-1S_FMM.pdf",
        "manufacturer": "Faulhaber",
        "name": "30-1S",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/EN_7000_05016.pdf",
        "manufacturer": "Murrelektronik",
        "name": "7000-05016",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/EN_7000_05061.pdf",
        "manufacturer": "Murrelektronik",
        "name": "7000-05061",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/EN_7000_05062.pdf",
        "manufacturer": "Murrelektronik",
        "name": "7000-05062",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/EN_IERS3-500_DFF.pdf",
        "manufacturer": "Dunkermotoren",
        "name": "IERS3-500",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/EN_TI_BRUSHLESS_DC-MOTORS.pdf",
        "manufacturer": "Texas Instruments",
        "name": "Brushless DC Motors",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/Gamme-Mini-Moteur-et-Micromoteur-Brushless-DC-Pas-a-pas.pdf",
        "manufacturer": "Unknown",
        "name": "Mini Brushless DC",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/Kollmorgen_KBM_Frameless_Motors_Catalog.pdf",
        "manufacturer": "Kollmorgen",
        "name": "KBM Frameless",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/Kollmorgen_Torquemotoren_KBM_Selection_Guide.pdf",
        "manufacturer": "Kollmorgen",
        "name": "KBM Torque Motors",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/L010404_-_MDC200-048051_Users_Guide.pdf",
        "manufacturer": "Faulhaber",
        "name": "MDC200-048051",
        "type": "drive",
    },
    {
        "key": "raw_pdfs/L010478 - MDC151-012601 Users Guide.pdf",
        "manufacturer": "Faulhaber",
        "name": "MDC151-012601",
        "type": "drive",
    },
    {
        "key": "raw_pdfs/L011172_-_MDC151-050101_Users_Guide.pdf",
        "manufacturer": "Faulhaber",
        "name": "MDC151-050101",
        "type": "drive",
    },
    {
        "key": "raw_pdfs/Nidec_22H.pdf",
        "manufacturer": "Nidec",
        "name": "22H Series",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/P5_43598_pittman.pdf",
        "manufacturer": "Pittman",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/PDS_Dynamo-Motors.pdf",
        "manufacturer": "Dynamo",
        "name": "Dynamo Motors",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/Product-Data-Sheet-_HRW-3_3-Motor.PDF.pdf",
        "manufacturer": "Unknown",
        "name": "HRW-3/3",
        "type": "motor",
    },
    # RPX32 is 162 bytes — likely corrupt, skip
    {"key": "raw_pdfs/SpdBlAll.pdf", "manufacturer": "Unknown", "type": "motor"},
    {
        "key": "raw_pdfs/TDA5145TS.pdf",
        "manufacturer": "Philips",
        "name": "TDA5145TS",
        "type": "drive",
    },
    # VF-24H already processed
    {
        "key": "raw_pdfs/bnhsseries.pdf",
        "manufacturer": "Unknown",
        "name": "BNHS Series",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/dunkermotoren-brushless-dc-motors-catalog.pdf",
        "manufacturer": "Dunkermotoren",
        "name": "Brushless DC Catalog",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/ec-frameless-dt-en-03-2025.pdf",
        "manufacturer": "Unknown",
        "name": "EC Frameless",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/pittman_catalog.pdf",
        "manufacturer": "Pittman",
        "name": "Motor Catalog",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/pittman_dc_motor_customization.pdf",
        "manufacturer": "Pittman",
        "name": "DC Motor Customization",
        "type": "motor",
    },
    {
        "key": "raw_pdfs/pittman_integrated_drives_ec083a_brushless_motor_with_drive.pdf",
        "manufacturer": "Pittman",
        "name": "EC083A Integrated Drive",
        "type": "motor",
    },
    {"key": "raw_pdfs/portescap.pdf", "manufacturer": "Portescap", "type": "motor"},
]


def process_one(pdf: dict) -> dict:
    """Run dsm-agent process for a single PDF. Returns result dict."""
    s3_key = pdf["key"]
    mfg = pdf.get("manufacturer", "Unknown")
    name = pdf.get("name", "")
    ptype = pdf.get("type", "motor")

    cmd = [
        "uv",
        "run",
        "dsm-agent",
        "--bucket",
        "specodex",
        "process",
        s3_key,
        "-t",
        ptype,
        "--keep",
        "--manufacturer",
        mfg,
    ]
    if name:
        cmd.extend(["--product-name", name])

    log.info(f"Processing: {s3_key} ({mfg}, {ptype})")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
        env=os.environ,
    )

    # stdout is JSON, stderr is logs
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        data = {"raw_stdout": result.stdout[:500]}

    data["exit_code"] = result.returncode
    data["s3_key"] = s3_key

    status = data.get("status", "unknown")
    written = data.get("written", 0)
    log.info(f"  Result: {status} (written={written}, exit={result.returncode})")

    return data


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()

    results: list[dict] = []
    success = fail = skip = 0

    log.info(f"Starting batch processing of {len(PDFS)} PDFs")
    start = time.time()

    for i, pdf in enumerate(PDFS, 1):
        log.info(f"[{i}/{len(PDFS)}] {pdf['key']}")
        try:
            r = process_one(pdf)
            results.append(r)
            status = r.get("status", "unknown")
            if status == "success":
                success += 1
            elif status in ("skipped", "empty"):
                skip += 1
            else:
                fail += 1
        except subprocess.TimeoutExpired:
            log.error(f"  TIMEOUT: {pdf['key']}")
            results.append({"s3_key": pdf["key"], "status": "timeout"})
            fail += 1
        except Exception as e:
            log.error(f"  ERROR: {pdf['key']}: {e}")
            results.append({"s3_key": pdf["key"], "status": "error", "error": str(e)})
            fail += 1

    elapsed = time.time() - start

    summary = {
        "total": len(PDFS),
        "success": success,
        "failed": fail,
        "skipped": skip,
        "elapsed_seconds": round(elapsed, 1),
        "results": results,
    }

    # Write full results to log file
    results_path = LOG_DIR / "batch_results.json"
    results_path.write_text(json.dumps(summary, indent=2, default=str))

    log.info(
        f"Done in {elapsed:.0f}s — success={success}, failed={fail}, skipped={skip}"
    )
    log.info(f"Full results: {results_path}")

    # Print summary to stdout
    json.dump(summary, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
