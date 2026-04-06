# webscraper

Browser-based product webpage scraper. Renders JS-heavy e-commerce pages via Playwright, then feeds the content through the same Gemini AI extraction pipeline as PDF datasheets.

## Usage

```bash
# Scrape a product page
uv run web-scraper \
  --url "https://shop.example.com/products/HK-KT634WK" \
  --type motor \
  --manufacturer "Mitsubishi Electric" \
  --product-name "HK-KT634WK"

# Enrich an existing product (fill null fields without overwriting)
uv run web-scraper \
  --url "https://shop.example.com/products/HK-KT634WK" \
  --type motor \
  --manufacturer "Mitsubishi Electric" \
  --product-name "HK-KT634WK" \
  --enrich
```

## Files

| File | Purpose |
|------|---------|
| `browser.py` | Playwright page fetch, HTML cleaning (stdlib `html.parser`), JSON-LD and metadata extraction |
| `scraper.py` | `web-scraper` CLI entry point — orchestrates fetch, LLM extraction, validation, and DB push |

## How It Works

1. Playwright renders the page in headless Chromium
2. Extracts JSON-LD structured data (schema.org Product markup) and page metadata
3. Strips `<script>`, `<style>`, `<nav>`, `<footer>`, `<svg>` to reduce token usage
4. Sends cleaned HTML + structured data context to `datasheetminer.llm.generate_content`
5. Parses CSV response, validates via Pydantic, quality-scores, and pushes to DynamoDB
