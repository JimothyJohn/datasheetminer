"""One-off: re-ingest the Mitsubishi contactor catalog under the current schema.

Runs the standard page_finder → Gemini → quality-filter → DynamoDB pipeline
on tests/benchmark/datasheets/mitsubishi-contactors-catalog.pdf, storing
the public Mitsubishi knowledge-base URL as datasheet_url rather than the
local file path.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

load_dotenv(REPO / ".env")

# 3 pages per Gemini call — fewer calls keeps us under rate limits
os.environ.setdefault("MAX_PER_PAGE_CALLS", "100")
os.environ.setdefault("PAGES_PER_CHUNK", "3")

from datasheetminer.config import SCHEMA_CHOICES  # noqa: E402
from datasheetminer.db.dynamo import DynamoDBClient  # noqa: E402
from datasheetminer.ids import compute_product_id  # noqa: E402
from datasheetminer.merge import merge_per_page_products  # noqa: E402
from datasheetminer.page_finder import find_spec_pages_scored  # noqa: E402
from datasheetminer.quality import filter_products  # noqa: E402
from datasheetminer.scraper import _extract_per_page  # noqa: E402

PDF = REPO / "tests/benchmark/datasheets/mitsubishi-contactors-catalog.pdf"
PUBLIC_URL = (
    "https://us.mitsubishielectric.com/fa/en/support/technical-support/"
    "knowledge-base/getdocument/?docid=3E26SJWH3ZZR-38-3004"
)

PRODUCT_TYPE = "contactor"
MANUFACTURER = "Mitsubishi Electric"
PRODUCT_NAME = "MS-T/N Series Magnetic Contactors"
PRODUCT_FAMILY = "MS-T/N Series"


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set", file=sys.stderr)
        return 1

    pdf_bytes = PDF.read_bytes()
    print(f"Loaded {len(pdf_bytes) / 1e6:.1f} MB PDF", flush=True)

    # Score-and-cap to stay under Gemini free-tier rate limits (~15 RPM).
    # 25 pages chunked 3-per-call ≈ 9 Gemini calls.
    pages_0idx, _details = find_spec_pages_scored(pdf_bytes, max_pages=25)
    print(f"page_finder scored+capped: {len(pages_0idx)} spec pages", flush=True)

    # find_spec_pages_scored returns 0-indexed; _extract_per_page wants 0-indexed.
    pages_1idx = [p + 1 for p in pages_0idx]
    context = {
        "product_name": PRODUCT_NAME,
        "manufacturer": MANUFACTURER,
        "product_family": PRODUCT_FAMILY,
        "datasheet_url": PUBLIC_URL,
        "pages": pages_1idx,
    }

    parsed_models = _extract_per_page(
        pdf_bytes, pages_0idx, api_key, PRODUCT_TYPE, context, "pdf"
    )
    if not parsed_models:
        print("No products extracted", file=sys.stderr)
        return 2

    parsed_models = merge_per_page_products(parsed_models)
    print(f"After merge: {len(parsed_models)} candidate products", flush=True)

    client = DynamoDBClient()
    model_class = SCHEMA_CHOICES[PRODUCT_TYPE]

    valid_models = []
    for model in parsed_models:
        if model.pages:
            model.datasheet_url = f"{PUBLIC_URL}#page={model.pages[0]}"
        else:
            model.datasheet_url = PUBLIC_URL

        mfg = model.manufacturer or MANUFACTURER
        pid = compute_product_id(mfg, model.part_number, model.product_name)
        if pid is None:
            print(
                f"  skipped '{model.product_name}' — missing mfg+part/name",
                flush=True,
            )
            continue
        model.product_id = pid

        existing = client.read(model.product_id, model_class)
        if existing:
            print(
                f"  skipped '{model.product_name}' — already in DB as {pid}",
                flush=True,
            )
            continue

        valid_models.append(model)

    kept, rejected = filter_products(valid_models)
    if rejected:
        print(
            f"Quality filter dropped {len(rejected)} low-quality products", flush=True
        )

    success_count = client.batch_create(kept)
    print(f"Wrote {success_count}/{len(kept)} to DynamoDB", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
