# Benchmark Format Diversity

Stress-test the ingress pipeline against a wider variety of datasheet formats.
Each item below is a fixture to add to `tests/benchmark/`.

## Fixture wishlist

### 1. Scanned-only PDF (no text layer)
- Tests graceful fallback when text heuristic returns nothing (no text to score).
- Must rely entirely on Gemini Flash image classification for page finding.
- Common with older Japanese/European manufacturers' catalogs.
- **Example sources**: older Fanuc, Yaskawa, Mitsubishi catalogs from manualslib.

### 2. Multi-product-type catalog
- One PDF containing both motors AND drives (or drives + gearheads).
- Tests product-type disambiguation — page finder must select pages for the right type.
- The J5 catalog already exposes this problem (motors and drives mixed).
- **Example sources**: Siemens SINAMICS/SIMOTICS combined catalog, Omron full automation catalog.

### 3. Single-page spec sheet
- A 1-2 page datasheet with all specs on one page.
- Tests that the scorer doesn't accidentally filter out the only useful page.
- Many smaller manufacturers publish these (single product, one-sheet format).
- **Example sources**: small servo drive datasheets from Oriental Motor, maxon, Teknic.

### 4. Wide-table format (landscape orientation)
- Landscape PDF with 30+ columns in a single table.
- Tests table cell detection and LLM parsing on wide tabular layouts.
- Common in comparison/selection guides.
- **Example sources**: Beckhoff AX5000 comparison table, Parker Compax3 selection guide.

### 5. HTML-sourced spec page
- Not a PDF — a product page scraped as HTML.
- Pipeline supports `content_type="html"` but the bench only tests PDFs today.
- Need to add HTML fixture support to `cli/bench.py`.
- **Example sources**: Kollmorgen AKD product page, Lenze online configurator output.

### 6. Non-English datasheet
- Japanese or German catalog with localized spec headers.
- Tests whether keyword heuristic works on translated headers (it won't — this will expose the gap).
- Useful for deciding whether to add multilingual keyword groups or pre-translate.
- **Example sources**: Mitsubishi JP catalog, Siemens DE catalog, Omron JP servo catalog.

### 7. Large multi-family catalog (>100 pages, >10MB)
- Tests the `size_category: "large"` flag on the Datasheet model.
- Pipeline should flag these for manual review rather than auto-processing.
- Benchmark should measure how well the scored page finder compacts them.
- **Example sources**: Rockwell Kinetix full catalog, Siemens SINAMICS S-series full manual.

### 8. Image-heavy marketing PDF with sparse specs
- Lots of photos, renders, application images with specs buried in small tables.
- Tests that the table-cell signal doesn't boost marketing pages with decorative tables.
- **Example sources**: ABB motion product overview, Nidec marketing brochure.

## How to add each

1. Download the PDF/HTML to `tests/benchmark/datasheets/`
2. Add entry to `tests/benchmark/fixtures.json`
3. Run `./Quickstart bench --live --update-cache --filter <slug>` to populate cache
4. Manually review extraction output, save verified subset as ground truth in `tests/benchmark/expected/<slug>.json`
5. Run `./Quickstart bench` to confirm P/R against the new ground truth
