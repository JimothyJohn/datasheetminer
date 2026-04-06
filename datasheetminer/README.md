# datasheetminer

Core Python library for extracting product specs from PDFs and webpages using Gemini AI.

## Pipeline

```
Document (PDF bytes or HTML string)
  → Gemini AI emits flat CSV with unit-in-header columns
  → csv_schema.py reconstructs "value;unit" compact strings
  → Pydantic model validates types, units, and magnitudes
  → quality.py rejects products with too many missing fields
  → db/dynamo.py pushes to DynamoDB with deterministic UUIDs
```

## Modules

| File | Purpose |
|------|---------|
| `llm.py` | Gemini API call with retry logic, builds CSV prompt from schema |
| `scraper.py` | `datasheetminer` CLI entry point — single URL or batch-from-DB |
| `page_finder.py` | `page-finder` CLI — identifies which PDF pages contain spec tables |
| `utils.py` | PDF/web fetching, CSV parsing, page range handling |
| `config.py` | Auto-discovers product schemas, LLM guardrails, env config |
| `quality.py` | Scores data completeness, rejects below 25% threshold |
| `spec_rules.py` | Unit-family validation (catches "rpm" on a voltage field) |
| `units.py` | Normalizes unit strings to canonical forms |
| `mapper.py` | Data transformation utilities |

## Subpackages

- `models/` — Pydantic product schemas (auto-discovered)
- `db/` — DynamoDB interface
