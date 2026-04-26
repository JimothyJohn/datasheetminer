#!/usr/bin/env python3
"""One-shot Tolomatic ingest.

Reads pre-scraped HTML pages in /tmp/tolomatic-scrape/pages/, maps each slug to
an existing product type (electric_cylinder or gearhead — brakes, pneumatic
cylinders, slides, and landing pages are skipped), picks the best PDF link per
page (family catalog > part sheet > flyer, avoiding the global PT catalog and
MSDS sheets), deduplicates PDFs, and runs the standard page_finder → Gemini →
Pydantic → DynamoDB pipeline via scraper.process_datasheet.

Usage:
    source .env && uv run python cli/ingest_tolomatic.py
    source .env && uv run python cli/ingest_tolomatic.py --dry-run    # print plan only
"""

from __future__ import annotations

import argparse
import gzip
import logging
import os
import re
import sys
from pathlib import Path

from specodex.db.dynamo import DynamoDBClient
from specodex.scraper import process_datasheet
from specodex.utils import validate_api_key

PAGES_DIR = Path("/tmp/tolomatic-scrape/pages")
MANUFACTURER = "Tolomatic"

# slug → (product_type, product_name hint)
SLUG_TO_TYPE: dict[str, tuple[str, str]] = {
    # Rod-style actuators (motor pushes/pulls a rod) → electric_cylinder
    "cswx-compact-servoweld-integrated-servo-spot-welding-actuators": (
        "electric_cylinder",
        "CSWX ServoWeld",
    ),
    "erd-low-cost-electric-cylinders-for-pneumatic-cylinder-replacement": (
        "electric_cylinder",
        "ERD",
    ),
    "erd-ss2-stainless-steel-electric-actuators-with-protective-motor-enclosure": (
        "electric_cylinder",
        "ERD-SS2",
    ),
    "ima-food-grade-servo-actuators": ("electric_cylinder", "IMA Food Grade"),
    "ima-linear-servo-actuators": ("electric_cylinder", "IMA"),
    "ima-s-hygienic-stainless-steel-actuators": ("electric_cylinder", "IMA-S"),
    "rsa-electric-linear-actuators": ("electric_cylinder", "RSA"),
    "rsa-rsm-electric-rod-actuators-archive": ("electric_cylinder", "RSA/RSM"),
    "rsh-hygienic-electric-rod-style-actuators": ("electric_cylinder", "RSH"),
    "rsx-extreme-force-electric-linear-actuators": ("electric_cylinder", "RSX"),
    "servochoke-svc-electric-choke-valve-actuator-operator": (
        "electric_cylinder",
        "ServoChoke SVC",
    ),
    "servoplace-precision-nut-placement": ("electric_cylinder", "ServoPlace"),
    "servoweld-gswa-33-resistance-spot-welding-servo-actuators": (
        "electric_cylinder",
        "ServoWeld GSWA-33",
    ),
    "servoweld-gswa-44-04-spot-welding-servo-actuators": (
        "electric_cylinder",
        "ServoWeld GSWA-44-04",
    ),
    "swa-swb-servoweld-integrated-servo-spot-welding-actuators": (
        "electric_cylinder",
        "ServoWeld SWA/SWB",
    ),
    # Rodless / slide / stage modules (carriage on a guided rail) → linear_actuator
    "b3s-ball-screw-linear-actuators": ("linear_actuator", "B3S"),
    "b3w-linear-belt-drive-actuators": ("linear_actuator", "B3W"),
    "bcs-rodless-screw-actuators": ("linear_actuator", "BCS"),
    "gsa-linear-slide-actuators": ("linear_actuator", "GSA"),
    "mxb-p-heavy-duty-linear-actuator": ("linear_actuator", "MXB-P"),
    "mxb-u-unguided-belt-driven-actuators": ("linear_actuator", "MXB-U"),
    "mxbs-linear-belt-drive-actuator": ("linear_actuator", "MXB-S"),
    "mxe-p-screw-driven-actuators": ("linear_actuator", "MXE-P"),
    "mxe-s-linear-screw-actuators": ("linear_actuator", "MXE-S"),
    "sls-electric-linear-slide-actuator": ("linear_actuator", "SLS"),
    "tkb-precision-linear-stages": ("linear_actuator", "TKB"),
    "trs-twin-profile-rail-stage-w-enclosed-design": ("linear_actuator", "TRS"),
    # Right-angle gearboxes → gearhead
    "float-a-shaft-1-1-right-angle-gearboxes-low-torque": (
        "gearhead",
        "Float-A-Shaft 1:1 Low Torque",
    ),
    "float-a-shaft-1-to-1-right-angle-gearboxes-high-torque": (
        "gearhead",
        "Float-A-Shaft 1:1 High Torque",
    ),
    "float-a-shaft-2-and-half-to-1-right-angle-gearboxes-low-torque": (
        "gearhead",
        "Float-A-Shaft 2.5:1 Low Torque",
    ),
    "float-a-shaft-2-to-1-right-angle-gearboxes-high-torque": (
        "gearhead",
        "Float-A-Shaft 2:1 High Torque",
    ),
    "float-a-shaft-2-to-1-right-angle-gearboxes-low-torque": (
        "gearhead",
        "Float-A-Shaft 2:1 Low Torque",
    ),
    "float-a-shaft-3-to-2-right-angle-gearboxes-high-torque": (
        "gearhead",
        "Float-A-Shaft 3:2 High Torque",
    ),
    "float-a-shaft-3-to-2-right-angle-gearboxes-low-torque": (
        "gearhead",
        "Float-A-Shaft 3:2 Low Torque",
    ),
    "float-a-shaft-compact-1-to-1-gearboxes-high-torque": (
        "gearhead",
        "Float-A-Shaft Compact 1:1 High Torque",
    ),
    "float-a-shaft-compact-1-to-1-right-angle-gearboxes-low-torque": (
        "gearhead",
        "Float-A-Shaft Compact 1:1 Low Torque",
    ),
    "slide-rite-compact-1-to-1-right-angle-gearboxes": (
        "gearhead",
        "Slide-Rite Compact 1:1",
    ),
    "slide-rite-corrosion-resistant-compact-1-to-1-right-angle-gearbox": (
        "gearhead",
        "Slide-Rite CR Compact 1:1",
    ),
    "slide-rite-corrosion-resistant-standard-1-to-1-right-angle-gearboxes": (
        "gearhead",
        "Slide-Rite CR Standard 1:1",
    ),
    "slide-rite-standard-1-to-1-right-angle-gearboxes": (
        "gearhead",
        "Slide-Rite Standard 1:1",
    ),
    "slide-rite-standard-2-to-1-right-angle-gearboxes": (
        "gearhead",
        "Slide-Rite Standard 2:1",
    ),
    "slide-rite-standard-3-to-2-right-angle-gearboxes": (
        "gearhead",
        "Slide-Rite Standard 3:2",
    ),
    "sgb-small-gearbox": ("gearhead", "SGB"),
}

# PDF filename patterns to exclude (MSDS sheets, manuals, grease kits, global catalogs).
EXCLUDE_PATTERNS = [
    re.compile(r"msds", re.I),
    re.compile(r"saf-t-eze", re.I),
    re.compile(r"shc-polyrex", re.I),
    re.compile(r"PTcat", re.I),  # global Power Transmission catalog
    re.compile(r"-man[-.]", re.I),  # user manuals
    re.compile(r"_Man\.pdf$", re.I),
    re.compile(r"grease", re.I),  # grease-kit part sheets (e.g. gswagreaseps.pdf)
]

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("tolomatic-ingest")


def read_html(path: Path) -> str:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_pdfs(html: str) -> list[str]:
    return re.findall(r'href="(https?://[^"]+\.pdf)"', html)


def pick_best_pdf(hrefs: list[str]) -> str | None:
    clean = [h for h in hrefs if not any(p.search(h) for p in EXCLUDE_PATTERNS)]
    if not clean:
        return None

    # 1. Product-family catalog (e.g. 2700-4000_29_IMA_cat.pdf).
    for h in clean:
        if re.search(r"_cat(-\d+)?\.pdf$", h, re.I):
            return h
    # 2. Product brochure (e.g. SWA-B-br.pdf, CSWX-br.pdf, ServoChoke-Bro.pdf).
    for h in clean:
        if re.search(r"[_-]br(o|oc|ochure)?\.pdf$", h, re.I):
            return h
    # 3. Per-SKU part sheet.
    for h in clean:
        if re.search(r"(ps|_PS)\.pdf$", h, re.I):
            return h
    # 4. Flyer.
    for h in clean:
        if re.search(r"(flyer|_fly|-fly|-f)\.pdf$", h, re.I):
            return h
    return clean[0]


def build_plan() -> list[dict]:
    """Walk PAGES_DIR, classify, pick PDF, dedupe by PDF URL."""
    plan: list[dict] = []
    seen_urls: set[str] = set()
    skipped_unmapped: list[str] = []
    skipped_no_pdf: list[str] = []

    for html_path in sorted(PAGES_DIR.iterdir()):
        slug = html_path.stem
        mapping = SLUG_TO_TYPE.get(slug)
        if mapping is None:
            skipped_unmapped.append(slug)
            continue

        product_type, product_name = mapping
        html = read_html(html_path)
        pdfs = extract_pdfs(html)
        pdf_url = pick_best_pdf(pdfs)
        if pdf_url is None:
            skipped_no_pdf.append(slug)
            continue

        if pdf_url in seen_urls:
            log.info(
                "skip dup: %s → %s (already planned under a sibling slug)",
                slug,
                pdf_url,
            )
            continue
        seen_urls.add(pdf_url)

        plan.append(
            {
                "slug": slug,
                "product_type": product_type,
                "product_name": product_name,
                "product_family": product_name,
                "url": pdf_url,
            }
        )

    log.info(
        "plan: %d ingests, %d skipped unmapped, %d skipped no-pdf",
        len(plan),
        len(skipped_unmapped),
        len(skipped_no_pdf),
    )
    if skipped_no_pdf:
        log.info("no-pdf slugs: %s", ", ".join(skipped_no_pdf))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the ingest plan without hitting Gemini or DynamoDB.",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Process only the first N items."
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Substring filter on slug (e.g. 'float-a-shaft').",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore the ingest log and re-run even previously-successful URLs.",
    )
    parser.add_argument(
        "--save-failed-pdfs",
        type=Path,
        default=None,
        help=(
            "Override directory for failed-extraction snapshots. "
            "Default: outputs/failed_datasheets/ (always on). "
            "Pass --no-save-failed to disable."
        ),
    )
    parser.add_argument(
        "--no-save-failed",
        action="store_true",
        help="Disable saving failed-extraction snapshots to disk.",
    )
    args = parser.parse_args()

    if not PAGES_DIR.is_dir():
        log.error("pages dir missing: %s", PAGES_DIR)
        return 2

    plan = build_plan()
    if args.filter:
        plan = [p for p in plan if args.filter in p["slug"]]
    if args.limit:
        plan = plan[: args.limit]

    if args.dry_run:
        for p in plan:
            print(f"{p['product_type']:20s} {p['product_name']:40s} {p['url']}")
        print(f"\n{len(plan)} PDFs would be processed.")
        return 0

    api_key = validate_api_key(os.environ.get("GEMINI_API_KEY"))
    client = DynamoDBClient()

    # Default-on snapshotting; --no-save-failed disables; --save-failed-pdfs DIR overrides.
    if args.no_save_failed:
        save_failed_to: Path | None = None
    elif args.save_failed_pdfs is not None:
        save_failed_to = args.save_failed_pdfs
    else:
        from specodex.scraper import DEFAULT_FAILED_DATASHEETS_DIR

        save_failed_to = DEFAULT_FAILED_DATASHEETS_DIR

    success = skipped = failed = 0
    for i, p in enumerate(plan, 1):
        log.info(
            "[%d/%d] %s (%s) ← %s",
            i,
            len(plan),
            p["product_name"],
            p["product_type"],
            p["url"],
        )
        try:
            result = process_datasheet(
                client=client,
                api_key=api_key,
                product_type=p["product_type"],
                manufacturer=MANUFACTURER,
                product_name=p["product_name"],
                product_family=p["product_family"],
                url=p["url"],
                pages=None,
                output_path=None,
                force=args.force,
                save_failed_to=save_failed_to,
            )
        except Exception as exc:
            log.error("  FAIL: %s", exc)
            failed += 1
            continue

        if result == "success":
            success += 1
        elif result == "skipped":
            skipped += 1
        else:
            failed += 1

    log.info(
        "done. success=%d skipped=%d failed=%d total=%d",
        success,
        skipped,
        failed,
        len(plan),
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
