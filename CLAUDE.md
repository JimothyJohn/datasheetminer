# Datasheetminer

A UI and API that sorts and filters industrial product specs from a database, plus an autonomous agent that scrapes datasheets online. Stupid simple on purpose.

## Entry point

Everything goes through `./Quickstart <command>`. It's a bash shim that delegates to `cli/quickstart.py`. Available commands:

    ./Quickstart dev              Local dev servers (default)
    ./Quickstart test             Unit tests only (fast feedback during dev)
    ./Quickstart verify           Pre-push gate: lint + tests + build (alias: ci).
                                  Mirrors .github/workflows/ci.yml exactly. Run this
                                  before pushing — green here means CI will be green.
                                  --only python|backend|frontend  Run one stage
    ./Quickstart staging [URL]    Staging contract tests
    ./Quickstart deploy [--stage] Deploy to AWS via CDK
    ./Quickstart smoke [URL]      Post-deploy smoke tests
    ./Quickstart process          Process S3 upload queue
    ./Quickstart admin <sub>      Blacklist, data movement, purge
    ./Quickstart bench            Benchmark the ingress pipeline
    ./Quickstart schemagen PDF... --type NAME
                                  Propose a new Pydantic product model from one
                                  or more datasheets. Multi-source is preferred:
                                  pass 3-5 vendors' PDFs so the LLM generalizes
                                  instead of tuning to one catalog's quirks.
                                  Writes <type>.py + <type>.md (reasoning doc
                                  with source citations).
    ./Quickstart price-enrich     Backfill MSRP on existing products
    ./Quickstart ingest-report    Group ingest-log quality-fails by manufacturer
                                  for vendor outreach. --email-template emits
                                  a ready-to-send email body per manufacturer.

All CLI modules live in `cli/`. Quickstart is the single entry point — don't run `python -m cli.foo` in docs or scripts unless there's a reason.

## Pipeline architecture

PDF → **page finder** (text heuristic, free) → **LLM extraction** (Gemini 2.5 Flash) → **Pydantic validation** → **quality gate** → **DynamoDB write**

- `specodex/page_finder.py` — text keyword heuristic (`find_spec_pages_by_text`) identifies spec-table pages without an API call. Falls back to Gemini Flash for image-based classification.
- `specodex/llm.py` — Gemini extraction (sole LLM path for product extraction).
- `specodex/models/llm_schema.py` — `to_gemini_schema` builds the uppercase OpenAPI-subset schema Gemini accepts via `response_schema`.
- `specodex/utils.py` — `parse_gemini_response` maps raw LLM JSON through `common.py` BeforeValidators into structured `ValueUnit` / `MinMaxUnit` instances (`{value, unit}` / `{min, max, unit}` dicts on serialisation — same shape Gemini emits, DynamoDB stores, and the frontend consumes).
- `specodex/schemagen/` — proposes new Pydantic models from a PDF (also Gemini, via `response_schema=ProposedModel`).
- `specodex/pricing/extract.py` — price extraction cascade; LLM last-resort uses Gemini 2.5 Flash.
- `specodex/quality.py` — scores completeness, rejects below threshold.
- `specodex/models/` — Pydantic models per product type: `drive.py`, `motor.py`, `gearhead.py`, `robot_arm.py`, `electric_cylinder.py`, `contactor.py`. New types get auto-discovered via `specodex/config.py:_discover_schema_models` — drop a file here and `SCHEMA_CHOICES[product_type]` is populated at import time.

Single provider: everything uses `GEMINI_API_KEY`. Model id is pinned in `specodex/config.py` (`MODEL = "gemini-2.5-flash"`).

**Rule: never feed a raw multi-hundred-page PDF to the LLM.** Always route through `page_finder` first — either `find_spec_pages_by_text` (free) or `find_spec_pages_scored` (density-ranked, capped). The scraper's bundled path tops out around 30 pages before Gemini truncates the JSON mid-string; `scraper.process_datasheet` auto-switches to per-page extraction when `pages <= MAX_PER_PAGE_CALLS`, so pass an explicit `pages=` list when ingesting big catalogs.

## Adding a new product type

The Python side auto-discovers, but the TypeScript side has four hardcoded allowlists that silently drop unknown types. Touch all of them or the type won't show up on the site:

1. `specodex/models/<type>.py` — Pydantic model inheriting `ProductBase`, with `product_type: Literal["<type>"] = "<type>"`.
2. `specodex/models/common.py` — add `"<type>"` to the `ProductType` literal.
3. `app/backend/src/config/productTypes.ts` — add to `VALID_PRODUCT_TYPES`. Without this, `getCategories()` filters the type out of the dropdown.
4. `app/backend/src/types/models.ts` — add a `<Type>` interface + include it in the `Product` and `ProductType` unions.
5. `app/backend/src/routes/search.ts` — add to the zod `type` enum. Without this, `/api/v1/search?type=<type>` returns 400.
6. `app/frontend/src/types/models.ts` — add to the `ProductType` union.

Step 1 can be scaffolded with `./Quickstart schemagen <pdf>... --type <name>`, which runs the standard `page_finder → Gemini → ProposedModel` pipeline and writes the model file plus the `common.py` patch. **Pass 3-5 vendors' datasheets** (ABB, Schneider, Siemens, Allen-Bradley, etc.) so the LLM generalizes across vendors instead of tuning the schema to one catalog's quirks — a single-source proposal will happily hardcode vendor-specific voltage columns or frame codes. The CLI also writes a companion `<type>.md` doc citing the sources and explaining non-obvious design decisions; treat that `.md` as the schema's reviewable ADR, not scratchwork.

### Smoke-testing a new type end-to-end

After touching the six files above, run this loop locally before pushing. Skipping any step is how types silently 400 in prod.

1. **Pre-push gate.** `./Quickstart verify` runs the same lint + tests + build that CI runs (Python ruff + pytest, backend lint + jest + tsc, frontend lint + vitest + tsc + vite). Green here means CI will be green; red here is your problem to fix before pushing. A missing `common.py` patch fails the Python pytest stage; a missing zod enum or interface fails the TypeScript build stage.
2. **Seed at least one record.** Drop a PDF in `tests/benchmark/datasheets/`, add a fixture entry, and run `./Quickstart bench --live --update-cache --filter <slug>` — the extraction path writes nothing to DynamoDB but validates the model end-to-end. To actually populate dev DynamoDB, point `./Quickstart process` at a local S3 upload (see "Processing the upload queue" in `cli/processor.py`).
3. **Start dev servers** with `./Quickstart dev` (backend: `localhost:3001`, frontend Vite: `localhost:5173`).
4. **Verify API surface:**

        curl -s localhost:3001/api/products/categories | jq '.data[].type'       # new type listed
        curl -s "localhost:3001/api/v1/search?type=<new>" | jq '.success'         # returns true (not 400)

   If `categories` omits the type, step 3 (`VALID_PRODUCT_TYPES`) is missing. If `search` 400s, step 5 (zod enum) is missing.
5. **UI check.** Load `http://localhost:5173`, select the new type in the sidebar dropdown, confirm filter chips and table columns render. Missing frontend `ProductType` entry manifests as "type is not assignable" at compile time OR as the type silently filtered out by `deriveAttributesFromRecords`.

## Frontend UI conventions

The filter chips and the results-table columns both derive their attribute list from a merge of **static per-type metadata** (rich display names, tuned units) and **records-derived attributes** (caught at runtime from the actual DynamoDB rows). See `app/frontend/src/types/filters.ts:deriveAttributesFromRecords` + `mergeAttributesByKey`. Adding a new product type no longer requires editing `filters.ts` — the table will auto-populate from whatever fields the records carry, with auto-generated display names from the snake_case keys. Curated `getXxxAttributes()` lists are an override, not a requirement. User preferences (hidden columns, row density, column cap, sort direction) persist in `localStorage`.

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

- **[FIXED 2026-04-16]** Page finder keywords were motor-centric. `SPEC_KEYWORDS` in `specodex/page_finder.py` now has 18 groups covering electronics, mechanics, mechatronics (switching devices, linear actuation, rotary/gearing, robotics, sensors, environmental, certifications). Mitsubishi contactor catalog: 4/410 → 77/410 spec pages after the broadening.
- **Nidec: 1/14 spec pages found** — added `cogging torque`/`thermal resistance` keywords didn't move the needle; this PDF may use non-English phrasings page_finder can't match. Revisit when someone cares about frameless coverage specifically.
- **`ambient_temp` validation bug**: Gemini emits `{"unit": "V"}` (dict) where Drive model expects MinMaxUnit string. Drops rows silently.
- **Omron: 80% precision / 42% recall**: 13 variants extracted but missing over half the fields on matched ground-truth record.
- **`scraper.py:batch_create(parsed_models)` bug**: the DB write passes `parsed_models` (raw) instead of `valid_models` (quality-filtered). Low-quality products get written anyway. The "Successfully pushed 99 items to DynamoDB, -75 items failed" log line is the tell — negative failure count means the filter was bypassed.

## Post-deploy verification

After `./Quickstart deploy --stage <stage>` returns, confirm the stack is actually live before closing the loop. `./Quickstart smoke <URL>` runs the full `tests/post_deploy/` suite; the ad-hoc checks below are what to reach for when a single endpoint is misbehaving.

**URLs per stage.** Prod uses the configured custom domain; staging/dev come from the Frontend stack's `CloudFrontUrl` output:

    # staging / dev
    aws cloudformation describe-stacks \
      --stack-name DatasheetMiner-<Stage>-Frontend \
      --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' --output text

    # prod
    https://datasheets.advin.io

**Canonical endpoints** — each of these must 200 with the shape noted:

| Endpoint                          | Expected (HTTP 200)                                                        |
|-----------------------------------|----------------------------------------------------------------------------|
| `/health`                         | `{"status": "healthy", "timestamp": "...", "environment": "production", "mode": "public"}` |
| `/api/products/categories`        | `{"success": true, "data": [{type, count, display_name}, ...]}`            |
| `/api/products/summary`           | `{"success": true, "data": {"total": N, ...}}`                              |
| `/api/products`                   | `{"success": true, "data": [...]}` (array, possibly empty)                  |
| `/api/v1/search?type=<valid>`     | `{"success": true, ...}` (400 if type not in the zod enum)                  |

**One-shot smoke:**

    ./Quickstart smoke https://datasheets.advin.io          # prod
    ./Quickstart smoke "$(aws cloudformation describe-stacks \
      --stack-name DatasheetMiner-Staging-Frontend \
      --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' \
      --output text)"                                       # staging

**Common failure fingerprints:**

- `/health` times out but `/api/products` 200s → CloudFront behavior for `/health` is wrong (it should route to API Gateway, same as `/api/*`). Check `frontend-stack.ts` behaviors.
- `/health` returns `"mode": "admin"` → Lambda is running with the local dev env. `APP_MODE=public` is hardcoded in `api-stack.ts`; verify that code shipped.
- `/api/products/categories` returns `data: []` → DynamoDB table is empty OR the Lambda is pointed at the wrong table. Check the `DYNAMODB_TABLE_NAME` env in the Lambda config.
- `/api/v1/search?type=<new>` returns 400 → new product type wasn't added to the zod enum in `routes/search.ts` (see "Adding a new product type" above).

## Key directories

    cli/                    CLI modules (bench, intake, processor, admin, batch_*, agent, triage)
    specodex/              Core library (LLM, scraper, models, DB, page_finder, quality, units)
    specodex/models/        Pydantic product models + schema builders
    specodex/db/            DynamoDB client
    app/                    Node.js frontend + backend (Express API, React UI)
    tests/                  Python tests (unit/, integration/, staging/, post_deploy/, benchmark/)
    outputs/                Extraction outputs and benchmark results

## Environment

- `.env` at repo root — `GEMINI_API_KEY`, `DYNAMODB_TABLE_NAME`, `AWS_REGION`
- `app/.env` — frontend/backend config
- Stage-specific: `app/.env.dev`, `app/.env.prod`
