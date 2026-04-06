"""
Page Finder — identifies which pages in a PDF contain specification tables.

Converts each page to a low-res JPEG thumbnail, sends to a fast/cheap model
(Gemini Flash) asking "does this page contain a specification table?",
and returns the page numbers that do.

Usage:
    uv run python -m datasheetminer.page_finder --url "https://example.com/catalog.pdf"
    uv run python -m datasheetminer.page_finder --url "https://example.com/catalog.pdf" --update-db
    uv run python -m datasheetminer.page_finder --scan-all
"""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai

from datasheetminer.utils import get_document

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Use a cheap fast model for page classification
PAGE_FINDER_MODEL = "gemini-2.0-flash"


# Keywords that indicate a spec table. A page must match at least
# SPEC_KEYWORD_THRESHOLD of these to be considered a spec page.
SPEC_KEYWORDS: list[list[str]] = [
    # Each inner list is an OR group — matching any one string counts.
    ["rated torque", "rated output", "rated power"],
    ["rated speed", "max speed", "maximum speed"],
    ["rated voltage", "supply voltage", "voltage range"],
    ["rated current", "continuous current"],
    ["rotor inertia", "moment of inertia", "inertia"],
    ["torque constant", "voltage constant", "back emf"],
    ["encoder", "resolver", "feedback"],
    ["frame size", "flange size", "mounting"],
]
SPEC_KEYWORD_THRESHOLD = 3  # Must match at least 3 groups


def find_spec_pages_by_text(pdf_bytes: bytes) -> list[int]:
    """Find spec-table pages using text search — free, no API calls.

    Returns 0-indexed page numbers matching spec keyword heuristics.
    Falls back to empty list if PyMuPDF is unavailable or PDF has no text.
    """
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF not installed, skipping text-based page detection")
        return []

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    spec_pages: list[int] = []

    for i in range(total_pages):
        text = doc[i].get_text().lower()
        if not text.strip():
            continue
        matches = sum(1 for group in SPEC_KEYWORDS if any(kw in text for kw in group))
        if matches >= SPEC_KEYWORD_THRESHOLD:
            spec_pages.append(i)  # 0-indexed

    doc.close()
    logger.info(
        f"Text-based page detection: {len(spec_pages)}/{total_pages} pages "
        f"matched spec keywords"
    )
    return spec_pages


def pdf_pages_to_images(pdf_bytes: bytes, dpi: int = 100) -> List[bytes]:
    """Convert each page of a PDF to a JPEG image.

    Args:
        pdf_bytes: Raw PDF file bytes
        dpi: Resolution for rendering (lower = faster, 100 is fine for table detection)

    Returns:
        List of JPEG bytes, one per page
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) is required. Install with: pip install PyMuPDF")
        raise

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images: List[bytes] = []

    zoom = dpi / 72  # 72 is the default PDF DPI
    matrix = fitz.Matrix(zoom, zoom)

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=matrix)

        # Convert to JPEG bytes
        img_bytes = pix.tobytes(output="jpeg", jpg_quality=60)
        images.append(img_bytes)

    doc.close()
    return images


def classify_pages(
    images: List[bytes],
    api_key: str,
    product_type: str = "",
    batch_size: int = 5,
) -> List[Dict[str, Any]]:
    """Send page images to Gemini Flash to classify which contain spec tables.

    Args:
        images: List of JPEG bytes per page
        api_key: Gemini API key
        product_type: Hint about what kind of specs to look for
        batch_size: Number of pages to send per API call

    Returns:
        List of dicts with page_number (0-indexed), has_specs (bool), description
    """
    client = genai.Client(api_key=api_key)
    results: List[Dict[str, Any]] = []

    type_hint = f" for {product_type} products" if product_type else ""

    for batch_start in range(0, len(images), batch_size):
        batch_end = min(batch_start + batch_size, len(images))
        batch = images[batch_start:batch_end]

        page_numbers = list(range(batch_start, batch_end))
        page_labels = ", ".join(str(p + 1) for p in page_numbers)

        prompt = f"""You are looking at {len(batch)} pages from a product catalog/datasheet{type_hint}.
These are pages {page_labels} (1-indexed).

For EACH page, determine:
1. Does it contain a specification table, data table, or detailed technical parameters?
   - YES if: spec sheets, parameter tables, performance curves with data, comparison tables
   - NO if: cover pages, table of contents, marketing text, photos without specs, ordering info, blank pages, legal text

2. Brief description of what the page contains (5-10 words max).

Respond as a JSON array with one object per page:
[{{"page": 1, "has_specs": true, "description": "Motor rated torque table"}}]
"""

        # Build content parts
        contents: list[Any] = [prompt]
        for i, img_bytes in enumerate(batch):
            contents.append(
                genai.types.Part.from_bytes(
                    data=img_bytes,
                    mime_type="image/jpeg",
                )
            )

        try:
            response = client.models.generate_content(
                model=PAGE_FINDER_MODEL,
                contents=contents,
                config={
                    "response_mime_type": "application/json",
                },
            )

            if response.text:
                batch_results = json.loads(response.text)
                if isinstance(batch_results, list):
                    for item in batch_results:
                        # Convert 1-indexed page from LLM to 0-indexed
                        page_1idx = item.get("page", 0)
                        page_0idx = page_1idx - 1 + batch_start
                        results.append(
                            {
                                "page_number": page_0idx,
                                "page_display": page_1idx + batch_start,
                                "has_specs": item.get("has_specs", False),
                                "description": item.get("description", ""),
                            }
                        )
        except Exception as e:
            logger.error(f"Error classifying pages {page_labels}: {e}")
            # Mark failed pages as unknown
            for p in page_numbers:
                results.append(
                    {
                        "page_number": p,
                        "page_display": p + 1,
                        "has_specs": False,
                        "description": f"classification failed: {e}",
                    }
                )

    return results


def find_spec_pages(
    url: str,
    api_key: str,
    product_type: str = "",
    pages: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Find which pages in a PDF contain specification tables.

    Args:
        url: URL or local path to PDF
        api_key: Gemini API key
        product_type: Type of product (motor, drive, gearhead, robot_arm)
        pages: Optional subset of pages to check (0-indexed)

    Returns:
        Dict with spec_pages (0-indexed list), all_pages (full classification)
    """
    logger.info(f"Downloading PDF from {url}")
    pdf_bytes = get_document(url)

    if not pdf_bytes:
        raise ValueError(f"Could not download PDF from {url}")

    logger.info(f"PDF downloaded: {len(pdf_bytes)} bytes")

    logger.info("Converting pages to images...")
    all_images = pdf_pages_to_images(pdf_bytes)
    logger.info(f"Converted {len(all_images)} pages to images")

    # If specific pages requested, only classify those
    if pages:
        images_to_check = [all_images[p] for p in pages if p < len(all_images)]
        page_mapping = [p for p in pages if p < len(all_images)]
    else:
        images_to_check = all_images
        page_mapping = list(range(len(all_images)))

    logger.info(f"Classifying {len(images_to_check)} pages...")
    classifications = classify_pages(images_to_check, api_key, product_type)

    # Map classifications back to actual page numbers
    for i, cls in enumerate(classifications):
        if i < len(page_mapping):
            cls["page_number"] = page_mapping[i]
            cls["page_display"] = page_mapping[i] + 1

    spec_pages = [c["page_number"] for c in classifications if c.get("has_specs")]

    return {
        "url": url,
        "total_pages": len(all_images),
        "spec_pages": spec_pages,
        "spec_page_count": len(spec_pages),
        "all_pages": classifications,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find which pages in a PDF contain specification tables.",
    )
    parser.add_argument("--url", help="PDF URL or local path")
    parser.add_argument(
        "--type", help="Product type hint (motor, drive, gearhead, robot_arm)"
    )
    parser.add_argument(
        "--x-api-key",
        help="Gemini API key (or set GEMINI_API_KEY env var)",
    )
    parser.add_argument(
        "--update-db",
        action="store_true",
        help="Update the datasheet entry in DynamoDB with found pages",
    )
    parser.add_argument(
        "--scan-all",
        action="store_true",
        help="Scan all datasheets in the DB that have no pages set",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Save results to JSON file",
    )

    args = parser.parse_args()
    api_key = args.x_api_key or os.environ.get("GEMINI_API_KEY")

    if not api_key:
        parser.error("Gemini API key required (--x-api-key or GEMINI_API_KEY env var)")

    if args.scan_all:
        _scan_all_datasheets(api_key, args.type, args.update_db)
        return

    if not args.url:
        parser.error("--url is required (or use --scan-all)")

    result = find_spec_pages(args.url, api_key, args.type or "")

    # Print results
    print(f"\n{'=' * 60}")
    print(f"PDF: {result['url']}")
    print(f"Total pages: {result['total_pages']}")
    print(f"Pages with specs: {result['spec_page_count']}")
    print(f"Spec pages (0-indexed): {result['spec_pages']}")
    print(f"{'=' * 60}")

    for page in result["all_pages"]:
        marker = "[SPEC]" if page["has_specs"] else "      "
        print(f"  {marker} Page {page['page_display']:3d}: {page['description']}")

    if args.output:
        args.output.write_text(json.dumps(result, indent=2))
        print(f"\nResults saved to {args.output}")

    if args.update_db and result["spec_pages"]:
        _update_datasheet_pages(args.url, result["spec_pages"])


def _update_datasheet_pages(url: str, pages: List[int]) -> None:
    """Update a datasheet's pages field in DynamoDB."""
    from datasheetminer.db.dynamo import DynamoDBClient

    client = DynamoDBClient()

    # Find the datasheet by URL
    datasheets = client.get_all_datasheets()
    matching = [ds for ds in datasheets if ds.url == url]

    if not matching:
        logger.warning(f"No datasheet found in DB for URL: {url}")
        return

    for ds in matching:
        ds.pages = pages
        if client.create(ds):  # PutItem overwrites
            logger.info(f"Updated datasheet {ds.datasheet_id} with pages {pages}")
        else:
            logger.error(f"Failed to update datasheet {ds.datasheet_id}")


def _scan_all_datasheets(
    api_key: str, product_type: Optional[str], update_db: bool
) -> None:
    """Scan all datasheets and find spec pages for PDFs missing page info."""
    from datasheetminer.db.dynamo import DynamoDBClient
    from datasheetminer.utils import is_pdf_url

    client = DynamoDBClient()
    datasheets = client.get_all_datasheets()

    # Filter to PDFs that need page finding
    candidates = []
    for ds in datasheets:
        if not ds.url:
            continue
        if not is_pdf_url(ds.url):
            continue
        # Only process if pages are empty or just [0,1]
        if ds.pages and len(ds.pages) > 2:
            continue
        if product_type and ds.product_type != product_type:
            continue
        candidates.append(ds)

    logger.info(f"Found {len(candidates)} datasheets needing page discovery")

    for i, ds in enumerate(candidates):
        logger.info(
            f"[{i + 1}/{len(candidates)}] Processing: {ds.product_name} ({ds.url[:60]}...)"
        )
        try:
            result = find_spec_pages(ds.url, api_key, ds.product_type)

            spec_pages = result["spec_pages"]
            print(f"  Found {len(spec_pages)} spec pages: {spec_pages}")

            if update_db and spec_pages:
                _update_datasheet_pages(ds.url, spec_pages)

        except Exception as e:
            logger.error(f"  Failed: {e}")
            continue


if __name__ == "__main__":
    main()
