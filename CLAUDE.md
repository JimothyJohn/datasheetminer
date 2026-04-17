# Datasheetminer

A UI and API that sorts and filters industrial product specs from a database, plus an autonomous agent that scrapes datasheets online. Stupid simple on purpose.

## Entry point

Everything goes through `./Quickstart <command>`. It's a bash shim that delegates to `cli/quickstart.py`. Available commands:

    ./Quickstart dev              Local dev servers (default)
    ./Quickstart test             Unit tests (Python + Node)
    ./Quickstart staging [URL]    Staging contract tests
    ./Quickstart deploy [--stage] Deploy to AWS via CDK
    ./Quickstart smoke [URL]      Post-deploy smoke tests
    ./Quickstart process          Process S3 upload queue
    ./Quickstart admin <sub>      Blacklist, data movement, purge
    ./Quickstart bench            Benchmark the ingress pipeline

All CLI modules live in `cli/`. Quickstart is the single entry point — don't run `python -m cli.foo` in docs or scripts unless there's a reason.

## Pipeline architecture

PDF → **page finder** (text heuristic, free) → **LLM extraction** (Gemini 2.5 Flash) → **Pydantic validation** → **quality gate** → **DynamoDB write**

- `datasheetminer/page_finder.py` — text keyword heuristic (`find_spec_pages_by_text`) identifies spec-table pages without an API call. Falls back to Gemini Flash for image-based classification.
- `datasheetminer/llm.py` — Gemini extraction (sole LLM path for product extraction).
- `datasheetminer/models/llm_schema.py` — `to_gemini_schema` builds the uppercase OpenAPI-subset schema Gemini accepts via `response_schema`.
- `datasheetminer/utils.py` — `parse_gemini_response` maps raw LLM JSON through `common.py` BeforeValidators into canonical `"value;unit"` strings.
- `datasheetminer/schemagen/` — proposes new Pydantic models from a PDF (also Gemini, via `response_schema=ProposedModel`).
- `datasheetminer/pricing/extract.py` — price extraction cascade; LLM last-resort uses Gemini 2.5 Flash.
- `datasheetminer/quality.py` — scores completeness, rejects below threshold.
- `datasheetminer/models/` — Pydantic models per product type: `drive.py`, `motor.py`, `gearhead.py`, `robot_arm.py`, `electric_cylinder.py`.

Single provider: everything uses `GEMINI_API_KEY`. Model id is pinned in `datasheetminer/config.py` (`MODEL = "gemini-2.5-flash"`).

## Benchmarking

`./Quickstart bench` measures the ingress pipeline against control datasheets with known ground truth.

### What it measures

| Metric | How |
|--------|-----|
| **Redundancy** | Pages skipped by text heuristic / total pages. Lower = more sent to LLM than necessary. |
| **Speed** | Wall-clock ms for page-finding + LLM extraction per fixture. |
| **Cost** | Input/output tokens × configurable $/1M token pricing. |
| **Quality** | Per-field precision/recall vs ground truth (5% tolerance on numerics, unit-aware). |

### Fixture layout

    tests/benchmark/
    ├── fixtures.json                  # manifest: slug → PDF, product_type, context, expected file
    ├── datasheets/                    # control PDFs (the test inputs)
    │   ├── j5.pdf                     # 110 MB, 616 pages — full Mitsubishi MR-J5 catalog
    │   ├── j5-filtered.pdf            # 2 MB, 15 pages — pre-filtered spec pages
    │   ├── nidec-d-series-frameless.pdf
    │   ├── omron-g-series-servo-motors.pdf
    │   └── orientalmotor-nx-series.pdf
    ├── expected/                       # ground-truth JSON (one array of product dicts per fixture)
    │   ├── j5.json                     # from outputs/drives/ — 20 drive variants
    │   ├── nidec-d-series-frameless.json  # from DynamoDB — richest motor record
    │   ├── omron-g-series-servo-motors.json
    │   └── orientalmotor-nx-series.json   # empty placeholder, needs population
    └── cache/                          # cached LLM responses (--update-cache writes here)

### Usage

    ./Quickstart bench                          # offline: page-finding + quality diff against cached responses
    ./Quickstart bench --live                   # live: calls Gemini, costs real money
    ./Quickstart bench --live --update-cache    # live + save responses for future offline runs
    ./Quickstart bench --filter j5-filtered     # single fixture
    ./Quickstart bench -o results.json          # custom output path

Results write to `outputs/benchmarks/<timestamp>.json` and `outputs/benchmarks/latest.json`.

### Adding a new fixture

1. Drop the PDF in `tests/benchmark/datasheets/`.
2. Add an entry to `tests/benchmark/fixtures.json` with slug, pdf filename, product_type, manufacturer, and product_name.
3. Create `tests/benchmark/expected/<slug>.json` with ground-truth product array (or `[]` as placeholder).
4. Run `./Quickstart bench --live --update-cache --filter <slug>` to populate the cache.

### Known issues (from first dry run, 2025-04-15)

- **Page finder is product-type-blind**: text heuristic keywords are motor-centric. J5 catalog sent motor pages to a drive schema, producing zero part-number overlap with expected. Need product-type-aware keyword groups.
- **Nidec: 1/14 spec pages found**: frameless motor keywords (cogging torque, thermal resistance) not in the heuristic keyword list.
- **`ambient_temp` validation bug**: Gemini emits `{"unit": "V"}` (dict) where Drive model expects MinMaxUnit string. Drops rows silently.
- **Omron: 80% precision / 42% recall**: 13 variants extracted but missing over half the fields on matched ground-truth record.

## Key directories

    cli/                    CLI modules (bench, intake, processor, admin, batch_*, agent, triage)
    datasheetminer/         Core library (LLM, scraper, models, DB, page_finder, quality, units)
    datasheetminer/models/  Pydantic product models + schema builders
    datasheetminer/db/      DynamoDB client
    app/                    Node.js frontend + backend (Express API, React UI)
    tests/                  Python tests (unit/, integration/, staging/, post_deploy/, benchmark/)
    outputs/                Extraction outputs and benchmark results

## Environment

- `.env` at repo root — `GEMINI_API_KEY`, `DYNAMODB_TABLE_NAME`, `AWS_REGION`
- `app/.env` — frontend/backend config
- Stage-specific: `app/.env.dev`, `app/.env.prod`
