# Token Reduction Plan

Current estimated cost: **1.5–27M tokens per datasheet** depending on PDF size and retries.
Target: **50–200K tokens per datasheet** — a 10–50x reduction.

## Current Token Flow

```
PDF (5-15MB) → page_finder (JPEG thumbnails to LLM, 2.5M tokens)
            → full PDF bytes to Gemini (1-6M tokens)
            → JSON structured output (34-63 field schema, 5-10K output tokens)
            → quality filter rejects 30-40% → wasted tokens
```

## Proposed Token Flow

```
PDF → PyMuPDF text extract (0 tokens, local)
    → TOC parsing → jump to spec pages (0 tokens, local)
    → fallback: keyword page scoring (0 tokens, local)
    → fallback: OCR via PyMuPDF (0 tokens, local)
    → 2-5 spec pages only → Gemini 3 Flash (50-200K tokens)
    → CSV output format (50% smaller than JSON)
    → no quality rejects (schema is tight)
```

---

## 1. Local Page Detection — Replace page_finder LLM calls (biggest win)

**Current:** Sends JPEG thumbnails of every page to Gemini in batches of 5.
100-page PDF = 20 API calls = ~2.5M tokens just to find which pages have specs.

**Proposed:** Three-tier local detection, zero tokens:

### Tier A: Table of Contents Parsing

Most multi-page datasheets and catalogs have a TOC. PyMuPDF can extract it natively:

```python
import fitz  # PyMuPDF, already a dependency

def find_spec_pages_from_toc(pdf_path: str) -> list[int]:
    """Parse PDF TOC/bookmarks to find specification sections."""
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()  # returns [[level, title, page_num], ...]

    SPEC_TITLES = {"specification", "technical data", "parameters",
                   "electrical data", "mechanical data", "performance",
                   "ratings", "characteristics", "ordering"}

    pages = []
    for level, title, page_num in toc:
        title_lower = title.lower()
        if any(kw in title_lower for kw in SPEC_TITLES):
            pages.append(page_num - 1)  # PyMuPDF uses 0-indexed
    return pages
```

This is instant, zero cost, and highly accurate for structured catalogs. If the TOC
points to "Technical Data" on page 47, go straight there.

### Tier B: Keyword Density Scoring (text-layer PDFs)

If no TOC or TOC doesn't have spec sections, fall back to full-text keyword search:

```python
SPEC_KEYWORDS = {"voltage", "current", "torque", "speed", "power", "rpm",
                 "weight", "dimension", "rating", "specification", "parameter",
                 "payload", "reach", "ratio", "backlash", "efficiency",
                 "temperature", "inertia", "resistance", "inductance"}

def find_spec_pages_by_keywords(pdf_path: str, top_n: int = 5) -> list[int]:
    """Score each page by spec-keyword density. Works on text-layer PDFs."""
    doc = fitz.open(pdf_path)
    scores = []
    for i, page in enumerate(doc):
        text = page.get_text().lower()
        score = sum(text.count(kw) for kw in SPEC_KEYWORDS)
        # Bonus: pages with tables (lots of numbers + units together)
        import re
        table_score = len(re.findall(r'\d+\.?\d*\s*(?:V|A|W|rpm|Nm|kg|mm|°C)', text))
        scores.append((score + table_score * 2, i))
    scores.sort(reverse=True)
    return [page for _, page in scores[:top_n] if _ > 0]
```

### Tier C: OCR Fallback (scanned/image PDFs)

Some datasheets are scanned images with no text layer. PyMuPDF can detect this
and do basic OCR without any new dependencies:

```python
def find_spec_pages_with_ocr(pdf_path: str, top_n: int = 5) -> list[int]:
    """For scanned PDFs with no text layer, use PyMuPDF's built-in OCR."""
    doc = fitz.open(pdf_path)
    scores = []
    for i, page in enumerate(doc):
        text = page.get_text()

        # If text layer is empty/tiny, this is likely a scanned page
        if len(text.strip()) < 50:
            # PyMuPDF can extract text from images via Tesseract if installed,
            # or use get_text("rawdict") to check for image blocks
            # Fallback: render page to pixmap and use basic pattern matching
            tp = page.get_textpage_ocr(flags=fitz.TEXT_PRESERVE_WHITESPACE)
            text = page.get_text(textpage=tp)

        text_lower = text.lower()
        score = sum(text_lower.count(kw) for kw in SPEC_KEYWORDS)
        scores.append((score, i))

    scores.sort(reverse=True)
    return [page for _, page in scores[:top_n] if _ > 0]
```

**Note:** `get_textpage_ocr()` requires Tesseract installed on the system.
For environments without Tesseract, fall back to Tier B (which returns empty
for scanned PDFs) and then send just the first 5 pages to Gemini as a last resort.

### Combined Detection Pipeline

```python
def detect_spec_pages(pdf_path: str) -> list[int]:
    """Find spec pages using cheapest method first."""
    # Tier A: TOC (instant, most accurate for catalogs)
    pages = find_spec_pages_from_toc(pdf_path)
    if pages:
        log.info(f"TOC found spec pages: {pages}")
        return pages

    # Tier B: Keyword scoring (fast, works on text-layer PDFs)
    pages = find_spec_pages_by_keywords(pdf_path)
    if pages:
        log.info(f"Keyword scoring found spec pages: {pages}")
        return pages

    # Tier C: OCR fallback (slower, for scanned PDFs)
    pages = find_spec_pages_with_ocr(pdf_path)
    if pages:
        log.info(f"OCR found spec pages: {pages}")
        return pages

    # Last resort: send first 5 pages (most single-product datasheets
    # have specs on pages 1-3)
    log.warning("No spec pages detected, using first 5 pages")
    return list(range(min(5, page_count)))
```

**Savings:** ~2.5M tokens → 0 tokens per document.

---

## 2. Send Only Spec Pages — Not Full PDF

**Current:** `get_document()` downloads the full PDF and sends all bytes to Gemini.
Even when `pages` param is provided, it first downloads the full file.

**Proposed:** After local page detection, extract only the identified pages into
a minimal PDF using PyPDF2 (already a dependency), then send that to Gemini.

For a 200-page catalog where 3 pages have specs:
- Before: 10MB PDF = ~2.5M input tokens
- After: 150KB PDF (3 pages) = ~37K input tokens

**Savings:** 60-95% of input tokens.

---

## 3. CSV Structured Output — Replace JSON Schema

**Current:** Gemini returns JSON with full field names repeated per product:
```json
[
  {"product_name": "BG 75x75", "manufacturer": "Dunkermotoren", "rated_power": "530;W", ...},
  {"product_name": "BG 75x50", "manufacturer": "Dunkermotoren", "rated_power": "380;W", ...}
]
```
Field names repeated N times for N products. A 20-product extraction repeats
34 field names × 20 = 680 redundant name tokens.

**Proposed:** Request CSV with a header row:
```
product_name,part_number,rated_power,rated_voltage,rated_speed,rated_torque
BG 75x75,BG 75x75,530;W,40;V,3370;rpm,150;Ncm
BG 75x50,BG 75x50,380;W,40;V,3370;rpm,110;Ncm
```

Header is 1 row. Data is N rows. No repeated keys. For 20 products with 15 fields:
- JSON: ~20 × 15 field names = 300 name tokens + 300 value tokens = ~600 output tokens
- CSV: 15 header tokens + 300 value tokens = ~315 output tokens
- **~50% fewer output tokens**

Parsing: `csv.DictReader` on the response text, then feed rows into Pydantic models.

---

## 4. Slim Extraction Schema — Core Fields Only

**Current:** Motor schema sends 34 fields, RobotArm sends 63+ fields.
Many return null — quality.py rejects products with <25% fields filled.

**Proposed:** Two-tier extraction:

**Tier 1 (always extracted, ~12 fields):**
```
product_name, part_number, manufacturer, product_family,
rated_power, rated_voltage, rated_current, rated_speed,
rated_torque, weight, ip_rating, dimensions
```

**Tier 2 (optional, only if Tier 1 succeeds and user needs full detail):**
All remaining fields via a targeted follow-up prompt on the same pages.

Most use cases (search, filtering, comparison) only need Tier 1.
Tier 2 is only needed for detailed product pages.

**Savings:** Schema definition ~750 → ~200 tokens. Output tokens drop proportionally.

---

## 5. Strip HTML Boilerplate

**Current:** `get_web_content()` returns full HTML including `<script>`, `<style>`,
navigation, footers, ads. A typical product page is 500KB HTML where specs are 50KB.

**Proposed:** Strip non-content elements before sending to LLM using stdlib `re`:
```python
def strip_html_boilerplate(html: str) -> str:
    for tag in ["script", "style", "nav", "footer", "header", "aside"]:
        html = re.sub(f"<{tag}[^>]*>.*?</{tag}>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html).strip()
    return html
```

No new dependencies (stdlib `re` only).

**Savings:** 80-90% of HTML input tokens.

---

## 6. Model: Use Gemini 3 Flash

**Current:** `config.py` line 35: `MODEL = "gemini-3-flash-preview"`

**Action:** Confirm this is the correct model ID once Gemini 3 Flash goes GA.
Flash models are ~10x cheaper per token than Pro. Gemini 3 Flash with structured
output and the spec pages visually shown to it should be highly accurate.

---

## Impact Summary

| Optimization | Token Savings | Effort |
|---|---|---|
| Local page detection (TOC → keywords → OCR) | ~2.5M/doc | Medium |
| Send only spec pages | 60-95% of input | Low |
| CSV output format | ~50% of output | Medium |
| Slim schema (Tier 1 only) | ~60% of schema + output | Low |
| Strip HTML boilerplate | 80-90% of HTML input | Low |
| Gemini 3 Flash | ~10x cost reduction | Already set |

**Combined estimated reduction: 90-97% fewer tokens per datasheet.**

A 200-page catalog currently costing ~5M tokens → ~100-250K tokens.

---

## Files to Modify

| File | Change |
|---|---|
| `datasheetminer/config.py` | Verify model name |
| `datasheetminer/llm.py` | Add CSV output mode, slim schema option |
| `datasheetminer/scraper.py` | Use local page detection, send only spec pages |
| `datasheetminer/utils.py` | Add `strip_html_boilerplate()`, add local page detection functions |
| `datasheetminer/models/factory.py` | Add Tier 1 slim schema generator |
| `datasheetminer/page_finder.py` | Refactor: local detection as primary, LLM as fallback |

## Implementation Order

1. Local page detection + send only spec pages (biggest win, uses existing deps)
2. Strip HTML boilerplate (quick win, stdlib only)
3. Slim schema / Tier 1 extraction
4. CSV output format (most work, moderate payoff)
