# Test Coverage Report

Generated: 2026-04-05

## Summary

| Suite | Runner | Tests | Passing | Coverage |
|---|---|---:|---:|---:|
| Python (datasheetminer/) | pytest + pytest-cov | 671 | 638 | **60%** lines |
| Python Integration | pytest | 52 | 51 | -- |
| Python Staging (live API) | pytest | 39 | -- | -- |
| Python Post-Deploy (live API) | pytest | 17 | -- | -- |
| Backend (app/backend/) | Jest | 194 | 193 | **46%** lines |
| Frontend (app/frontend/) | Vitest | 127 | 127 | -- |
| **Total** | | **1,048** | | |

Staging and post-deploy tests require `API_BASE_URL` and are run in CI against live environments.

---

## Python Coverage (datasheetminer/)

Source: `uv run pytest tests/unit/ --cov=datasheetminer --cov-report=term`

| Module | Stmts | Miss | Cover |
|---|---:|---:|---:|
| `__init__.py` | 0 | 0 | 100% |
| `config.py` | 37 | 4 | 89% |
| `db/dynamo.py` | 538 | 372 | 31% |
| `llm.py` | 31 | 0 | 100% |
| `mapper.py` | 60 | 26 | 57% |
| `models/__init__.py` | 1 | 0 | 100% |
| `models/common.py` | 81 | 0 | **100%** |
| `models/datasheet.py` | 28 | 0 | 100% |
| `models/drive.py` | 27 | 0 | 100% |
| `models/electric_cylinder.py` | 32 | 0 | 100% |
| `models/factory.py` | 13 | 1 | 92% |
| `models/gearhead.py` | 38 | 3 | 92% |
| `models/manufacturer.py` | 18 | 0 | 100% |
| `models/motor.py` | 26 | 0 | 100% |
| `models/product.py` | 31 | 0 | 100% |
| `models/robot_arm.py` | 63 | 0 | 100% |
| `page_finder.py` | 156 | 156 | 0% |
| `quality.py` | 36 | 1 | 97% |
| `scraper.py` | 262 | 154 | **41%** |
| `spec_rules.py` | 95 | 8 | 92% |
| `units.py` | 51 | 2 | 96% |
| `utils.py` | 283 | 28 | **90%** |
| **TOTAL** | **1907** | **755** | **60%** |

### Uncovered areas

- `db/dynamo.py` (31%) -- most CRUD paths tested via moto mocks but bulk delete/dedup operations uncovered
- `page_finder.py` (0%) -- requires Playwright/browser fixtures, not offline-testable
- `scraper.py` (41%) -- CLI `main()` and multi-product orchestration paths
- `mapper.py` (57%) -- CLI `main()` entrypoint

---

## Backend Coverage (app/backend/)

Source: `npx jest --coverage`

| Module | Stmts | Branch | Funcs | Lines |
|---|---:|---:|---:|---:|
| `config/index.ts` | 90.0% | 85.0% | 100% | 90.0% |
| `config/productTypes.ts` | 100% | 100% | 100% | 100% |
| `db/dynamodb.ts` | 1.8% | 0.0% | 0.0% | 1.9% |
| `middleware/readonly.ts` | 100% | 100% | 100% | **100%** |
| `middleware/subscription.ts` | **100%** | **100%** | **100%** | **100%** |
| `routes/datasheets.ts` | 70.7% | 73.7% | 71.4% | 70.3% |
| `routes/docs.ts` | 100% | 100% | 100% | 100% |
| `routes/products.ts` | 74.6% | 64.1% | 92.8% | 74.6% |
| `routes/search.ts` | 100% | 93.8% | 100% | 100% |
| `routes/subscription.ts` | **84.6%** | **66.7%** | **100%** | **84.6%** |
| `routes/upload.ts` | **100%** | **100%** | **100%** | **100%** |
| `services/search.ts` | 89.9% | 83.3% | 95.0% | 94.0% |
| `services/gemini.ts` | 12.3% | 2.2% | 11.1% | 12.9% |
| `services/scraper.ts` | 5.3% | 0.0% | 0.0% | 5.7% |
| `services/stripe.ts` | 8.1% | 0.0% | 14.3% | 9.4% |
| **ALL FILES** | **45.0%** | **39.8%** | **38.5%** | **46.0%** |

### Uncovered areas

- `db/dynamodb.ts` (1.9%) -- fully mocked at unit level; real calls tested via staging/post-deploy
- `services/gemini.ts`, `scraper.ts` -- LLM integrations, require Gemini API key
- `services/stripe.ts` -- Stripe Lambda proxy, requires live endpoint

---

## Frontend Tests (app/frontend/)

Source: `npx vitest run`

| Test File | Tests |
|---|---:|
| `utils/sanitize.test.ts` | 9 |
| `utils/formatting.test.ts` | 25 |
| `types/product-types.test.ts` | 30 |
| `types/filters.test.ts` | 19 |
| `utils/hooks.test.ts` | 11 |
| `components/NetworkStatus.test.tsx` | 5 |
| `components/ThemeToggle.test.tsx` | 6 |
| `components/AttributeSelector.test.tsx` | 7 |
| `components/FilterChip.test.tsx` | 5 |
| `api/client.test.ts` | 10 |
| **Total** | **127** |

No line-level coverage collected (`@vitest/coverage-v8` not installed).

---

## Test Breakdown by Category

| Category | Count | Purpose |
|---|---:|---|
| Python unit | 671 | Models, config, scraping, spec rules, utilities, validators, resilience, perf |
| Python integration | 52 | Build integrity, config consistency, CI pipeline validation |
| Python staging | 39 | API contracts against live server (all product types, search, CRUD) |
| Python post-deploy | 17 | Smoke tests, response schemas, CORS, security headers, concurrency |
| Backend unit (Jest) | 194 | Routes, DB, search, upload, subscription, recommend, resilience, edge cases |
| Frontend unit (Vitest) | 127 | Filters, sorting, formatting, hooks, components, API client resilience |
| **Total** | **1,048** | |

---

## Web Scraper Tests (webscraper/)

Source: `uv run pytest tests/unit/test_webscraper.py -v`

| Test Class | Tests | Description |
|---|---:|---|
| `TestCleanHtml` | 10 | HTML tag stripping, whitespace collapse, truncation, content preservation |
| `TestExtractJsonLd` | 6 | JSON-LD extraction, multi-block, malformed handling, array support |
| `TestExtractMeta` | 5 | Title, canonical URL, description, breadcrumb extraction |
| `TestPageContent` | 2 | Dataclass defaults and construction |
| **Total** | **23** | |

---

## Pre-existing Failures (not regressions)

- `tests/unit/test_units.py` -- 15 Pydantic integration tests (unit normalization)
- `tests/unit/test_protections.py` -- 5 content-hash/density tests
- `tests/unit/test_agent_cli.py` -- 2 botocore-related failures
- `tests/unit/test_config.py` -- 1 model constant assertion
- `tests/unit/test_scraper.py` -- 1 manufacturer skip test
- `tests/unit/test_llm.py` -- 1 model name assertion
- `app/backend/tests/routes.test.ts` -- 1 auto-generate product_id test (missing required `manufacturer` field)
- `app/backend/tests/db.test.ts` -- TS compile error (Product[] type mismatch)
