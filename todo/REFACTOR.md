# REFACTOR — Third-Party First-Principles Audit

> **⚠ STATUS: AUDIT ONLY — DO NOT IMPLEMENT ⚠**
>
> This document is a **thought experiment**, not a roadmap. It asks the question: *if a senior systems architect walked in today, looked at the codebase fresh, and had to design specodex from scratch, what would they do differently?*
>
> Nothing here is a directive. Nothing here is "the right answer." The current architecture works, ships value, and was designed for the constraints that existed when it was built. This audit exists so you (the junior maintainer) can compare the current shape against an alternative shape and **understand the tradeoffs** — not so you can rip out working code.
>
> Author note: read this top to bottom once. Then put it down. If a section here ever becomes a real proposal, it should get its own scoped doc in `todo/` with a real plan, real tests, and real exit criteria. This file is the diving board, not the pool.
>
> **Date:** 2026-04-30
> **Codebase snapshot:** `master @ 4b39ef3`
> **Audited LOC:** ~45,000 (Python ~8.5k, TypeScript ~40.7k, Rust ~500)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What the System Does Today](#2-what-the-system-does-today)
3. [What's Genuinely Good — Keep This](#3-whats-genuinely-good--keep-this)
4. [First-Principles Concerns](#4-first-principles-concerns)
5. [Greenfield Architecture (If Starting Today)](#5-greenfield-architecture-if-starting-today)
6. [Specific Design Choices, Justified](#6-specific-design-choices-justified)
7. [Migration Sketch (Hypothetical, Don't Implement)](#7-migration-sketch-hypothetical-dont-implement)
8. [Things Junior Devs Should Know Before Touching This](#8-things-junior-devs-should-know-before-touching-this)
9. [Open Questions a Senior Would Push Back On](#9-open-questions-a-senior-would-push-back-on)

---

## 1. Executive Summary

**Verdict in one paragraph:** specodex is a well-shaped prototype that grew organically into early production. The Python core (Gemini → Pydantic → DynamoDB pipeline) is principled and clean. The TypeScript app is solid but **carries a structural tax** — TypeScript types are hand-synced with Python Pydantic models, the admin/auth story is bolted on instead of designed in, and the boundary between "Python pipeline" and "Node API" is a *byte-shape contract* rather than a *generated contract*. If I were starting today, the single biggest change I would make is **collapsing the polyglot stack down to one language for the application layer** and **deriving types from a single source of truth** so adding a new product type means touching one file, not six.

**Top three "if I had to do it over"s:**

1. **Pick one app-layer language.** Today: Python (pipeline) + TypeScript (backend + frontend) + Rust (billing). Three runtimes, three test suites, three lint configs, three deploy paths. A greenfield design would pick **Python end-to-end** (FastAPI + HTMX or a thin React shell with auto-generated client) **or** **TypeScript end-to-end** (Node pipeline using the Gemini SDK + tRPC + React). Polyglot is justified only when each piece is load-bearing — the Rust billing Lambda is a 500-line side-quest that a Python Lambda could do in 100 lines.
2. **Single source of truth for product schemas.** Today: `specodex/models/*.py` (Pydantic) → `app/backend/src/types/models.ts` (hand-typed) → `app/frontend/src/types/models.ts` (hand-typed) → `routes/search.ts` zod enum (hand-typed) → `config/productTypes.ts` (hardcoded allowlist) → `app/frontend/src/types/filters.ts` (per-type metadata). Six files for one concept. CLAUDE.md acknowledges this with the "touch all of them or it silently drops" warning. **A senior would generate the TS from Pydantic** (e.g., `pydantic2ts`) or unify on one model definition.
3. **Design auth in from the start, not bolted on.** Current state: `APP_MODE=public|admin` is a *deploy-time* env var — there is no per-user role on `master`. The `feat-auth-phase1` worktree has been alive for weeks. Auth as an afterthought is the most expensive refactor in software. A greenfield design would put a Cognito (or simpler: Clerk/Auth.js) JWT layer in place on day one even if every user is anonymous, so the seams are there when you need them.

**What I would NOT change:**
- The Pydantic-first data model — `ValueUnit`/`MinMaxUnit` carrying units end-to-end is genuinely elegant and beats every "stringly-typed" alternative.
- The page-finder → LLM split — the free heuristic before the paid call is the kind of thing that separates a hobby project from a real product.
- DynamoDB single-table design — fits Lambda statelessness, pay-per-request scales to zero, no DBA needed.
- The `Quickstart` single entry point — you should never have to remember `npm run dev:backend & npm run dev:frontend & uv run python -m cli.foo`. This pattern is gold.
- The benchmark suite with control fixtures — most projects of this size have no ground-truth tests at all.

---

## 2. What the System Does Today

> Read this section even if you wrote the code. A fresh eye describes the system in different words than the original author, and those words are the ones a new engineer (or a future you) will reach for.

specodex ingests industrial product datasheets (PDFs, occasionally web pages), extracts structured specs using Google's Gemini 2.5 Flash, validates them against Pydantic models, stores the result in DynamoDB, and serves it through a React UI with filtering, comparison, and (eventually) metered billing.

**The pipeline, end to end:**

```
PDF/URL  ──►  Page Finder  ──►  LLM (Gemini)  ──►  Pydantic  ──►  Quality Gate  ──►  DynamoDB
            (free, text)      (structured JSON     (BeforeValidator   (completeness    (single-table
                               via response_schema) coercion to        scoring)         design)
                                                    ValueUnit/MinMax)
```

**The stack, at a glance:**

| Layer | Tech | Where | Lines |
|---|---|---|---|
| Pipeline core | Python 3.12, Pydantic 2, google-genai | `specodex/` | ~3,600 |
| CLI / orchestration | Python | `cli/` (31 modules) | ~10,000 |
| Backend API | Node 18+, Express, Zod, AWS SDK | `app/backend/` | ~26,000 |
| Frontend SPA | React 18, Vite, TypeScript | `app/frontend/` | ~14,500 |
| Infrastructure | AWS CDK (TypeScript) | `app/infrastructure/` | — |
| Billing Lambda | Rust, lambda_runtime | `stripe/` | ~500 |
| Web scraper | Python, Playwright | `specodex/browser.py` + `specodex/web_scraper.py` | ~550 |
| Tests | pytest (Python), vitest (frontend), jest (backend) | `tests/`, `app/*/src/test/` | ~63 Python files |

**The deploy path:**

```
./Quickstart verify   →   ./Quickstart deploy [--stage]
       │                          │
       └─ ruff + pytest +         └─ CDK synth + CloudFormation upsert
          eslint + jest +            (DatasheetMiner-<Stage>-Database,
          tsc + vitest +              -Api, -Frontend stacks)
          vite build
```

**The data shape, at a glance:**

```python
# Pydantic (specodex/models/motor.py)
class Motor(ProductBase):
    product_type: Literal["motor"] = "motor"
    rated_voltage: Voltage | None = None        # ValueUnit dict
    rated_power: Power | None = None            # ValueUnit dict
    rated_torque: Torque | None = None          # ValueUnit dict
    operating_temperature: TemperatureRange | None = None  # MinMaxUnit dict
    ...
```

```typescript
// TypeScript (app/backend/src/types/models.ts) — hand-synced
interface Motor {
  product_type: "motor"
  rated_voltage: ValueUnit | null
  rated_power: ValueUnit | null
  rated_torque: ValueUnit | null
  operating_temperature: MinMaxUnit | null
  ...
}
```

This is the contract. It's correct today. It is also the source of every "type silently dropped" bug.

---

## 3. What's Genuinely Good — Keep This

A senior architect's first job on an audit is **not** to break what's working. Here's what I would protect, with rationale:

### 3.1 Pydantic-first data modeling with unit families

**Why it's good:** Most spec-extraction projects fight units forever. specodex carries `{value, unit}` as a first-class type from Gemini's JSON output through validation, storage, and into the frontend. The `BeforeValidator` coerces messy LLM output (`"5 V"`, `{"value": 5, "unit": "V"}`, `"5"`) into the same shape. The `UnitFamily` marker rejects wrong-family units (e.g., voltage given as `Nm`) to `None`, and the quality gate drops the row.

**Why a senior would keep it:** This is the kind of design that pays off slowly and compounds. Every "X is in volts" assumption you avoid in the frontend is a future bug you don't have. The alternative (string everywhere, parse-on-display) is what every junior project does and it never recovers.

**File reference:** `specodex/models/common.py:1-80`, `specodex/units.py:1-239`.

### 3.2 Page-finder before LLM

**Why it's good:** A 600-page Mitsubishi catalog has ~20 pages of spec tables. Sending the whole PDF to Gemini truncates the response mid-string and costs 30× what it should. The text-keyword heuristic in `find_spec_pages_by_text` is **free** (runs locally), filters down to spec pages, and only falls back to a Gemini classification call when text extraction yields nothing useful (image-only PDFs).

**Why a senior would keep it:** This is the right shape for any LLM pipeline. Free filter → paid call. Always. The generalization is "every LLM call should have the cheapest possible filter in front of it." Junior engineers reach for the LLM first and the heuristic never; senior engineers do the inverse.

**File reference:** `specodex/page_finder.py:1-678`. Note the 18 keyword groups added in 2026-04-16 — that's a senior move (broaden the filter when the data shows it's too narrow, don't add a second heuristic).

### 3.3 DynamoDB single-table with deterministic IDs

**Why it's good:** `PK = PRODUCT#<type>`, `SK = PRODUCT#<uuid>` where the UUID is **deterministic** from manufacturer/product_name/variant. Re-ingesting the same datasheet writes to the same row instead of creating duplicates. Pay-per-request billing scales to zero. No DBA needed. Lambda statelessness fits naturally.

**Why a senior would keep it:** SQL would feel more "proper" but would force you to manage migrations, capacity, and a connection pool inside Lambda (a known footgun). DynamoDB's constraints (no joins, no aggregates) actually keep the data model honest — you cannot accidentally write a 14-table normalization that nobody can reason about.

**File reference:** `specodex/db/dynamo.py`, `specodex/ids.py`.

**Caveat:** No GSI is defined. Today's "search across all types" is a full-table scan filtered in-memory. This works at <10k rows; beyond that it's a real cost. See [§4.6](#46-no-gsi-on-dynamodb).

### 3.4 The `Quickstart` entry point

**Why it's good:** `./Quickstart dev` brings up everything. `./Quickstart verify` is the same lint+test+build CI runs. `./Quickstart deploy --stage staging` ships it. New engineers (and future-you) don't need to memorize the dance.

**Why a senior would keep it:** This is the single biggest thing keeping the polyglot stack tractable. Without it, the cognitive cost of "is it `npm run` or `uv run` or `cargo run`?" would have already split the team. Make sure any future refactor preserves it.

**File reference:** `Quickstart` (bash shim), `cli/quickstart.py:1-1088`.

### 3.5 Auto-discovered Pydantic models

**Why it's good:** `_discover_schema_models()` in `specodex/config.py:106` walks `specodex/models/*.py` at import time and populates `SCHEMA_CHOICES[product_type]`. Adding a new Python product type means dropping a file. No registry edits.

**Why a senior would keep it:** Convention over configuration is the right call here because the convention is enforced at import time (you get an error immediately if you forget the `product_type: Literal[...]` field). The Python side is great. The TypeScript side does **not** auto-discover, which is the next problem.

### 3.6 Benchmark suite with ground-truth fixtures

**Why it's good:** `tests/benchmark/expected/<slug>.json` holds the known-correct extraction for a fixture PDF. `./Quickstart bench` measures redundancy, speed, cost, and per-field precision/recall against ground truth. Cached LLM responses make offline runs free.

**Why a senior would keep it:** Most extraction projects of this scale have *no* objective quality measurement and are therefore defenseless against quality regressions. specodex has one. Don't lose it.

**File reference:** `cli/bench.py:1-675`, `tests/benchmark/`.

---

## 4. First-Principles Concerns

These are the things a fresh-eyes senior would flag. Not all of them are urgent. Several are tradeoffs the original author probably made consciously. The point is to surface them, not to "fix" them.

### 4.1 Polyglot stack without polyglot justification

**Observation:** The system is Python + TypeScript + Rust. The Rust portion is a 500-line Stripe Lambda that does test-mode metered billing. Test-mode. 500 lines.

**The argument for Rust here is "fast cold starts."** That's not wrong, but the actual cold-start delta (Rust ~10-50ms vs Python ~200-500ms on Lambda) is invisible to a Stripe webhook user. Stripe webhooks are async; nobody is waiting on them. A Python billing Lambda would be ~100 lines, share the existing DynamoDB client code, and remove an entire toolchain (cargo, clippy, the ARM64 cross-compile dance).

**The deeper question:** What is each language buying you that's worth its full carrying cost? Carrying cost = lint config + test runner + CI job + deploy path + cognitive switch + library duplication (you have AWS SDK clients in three languages now).

| Language | Bought | Cost | Worth it? |
|---|---|---|---|
| Python | Pipeline, ML libs, Pydantic, page-finder | Default | Yes |
| TypeScript | Frontend (mandatory), backend (chosen) | High — entire monorepo | Backend is debatable |
| Rust | Billing Lambda cold-start | High — extra runtime | **No** |

**A senior would ask:** *"Could the Node backend be a Python FastAPI service instead, sharing the Pydantic models directly?"* This is the single biggest leverage point in the codebase. See [§5](#5-greenfield-architecture-if-starting-today).

### 4.2 Six places to update for a new product type

**Observation:** CLAUDE.md spells this out as "Adding a new product type" — six files, three of them in TypeScript hand-syncing what Python already knows. This is the textbook symptom of a missing code-gen step.

The six files:
1. `specodex/models/<type>.py` — Pydantic model
2. `specodex/models/common.py` — `ProductType` literal
3. `app/backend/src/config/productTypes.ts` — `VALID_PRODUCT_TYPES`
4. `app/backend/src/types/models.ts` — TS interface + union
5. `app/backend/src/routes/search.ts` — Zod enum
6. `app/frontend/src/types/models.ts` — TS union

Steps 3, 4, 5, 6 should not exist. They are derivable from step 1.

**The fix in a greenfield design:** `pydantic2ts` (or `datamodel-code-generator` in the other direction) generates the TypeScript interfaces from the Pydantic models at build time. The Zod enum and `VALID_PRODUCT_TYPES` come from the same generated artifact. Adding a new type becomes: write the Pydantic model, run codegen, commit the generated files.

**Why this matters more than it looks:** Every hand-synced contract is a place where the "silently drops" bug lives. The bug is invisible until a user reports a missing product type. CLAUDE.md has a runbook for this — but the right answer is to make the runbook unnecessary.

### 4.3 Auth bolted on, not designed in

**Observation:** `APP_MODE=public|admin` is a deploy-time env var. There is no per-user role on `master`. The `feat-auth-phase1` worktree has Cognito scaffolding but it's not merged. The `subscription` middleware uses an unverified `x-user-id` header as a placeholder.

**Why a senior would flag this:** Auth is the single most expensive thing to retrofit in any web app. Every endpoint, every middleware, every test fixture, every UI component that conditionally renders based on role — they all need to know about the auth context. Doing it at the start costs days; doing it after launch costs months.

**The greenfield call:** Pick an auth provider on day 1 (Cognito, Clerk, Auth.js, Supabase Auth — any of them). Even if every user is "anonymous," you have a JWT and a user_id from the start. You wire `req.user` into every route. When you flip the switch from anonymous to real users, **nothing else changes**.

The current state is recoverable — Cognito on `feat-auth-phase1` is the right destination. But the lesson for *next time* is: never let "auth is a Phase 4 concern" be a sentence you say.

### 4.4 The `APP_MODE` global toggle

**Observation:** `APP_MODE=public` blocks all writes via `middleware/readonly.ts`. `APP_MODE=admin` opens everything. There is no middle ground — no "this user can edit motors but not drives," no "this user can review submissions but not delete." It's a global circuit breaker.

**Why this is a smell:** Global circuit breakers are correct exactly until the moment you need granularity. The day a contributor wants to edit-but-not-delete is the day this whole pattern collapses into a per-route `if (req.user.role === 'editor')` check and the global env var becomes vestigial scaffolding.

**The greenfield call:** Per-route authorization predicates from day 1. `requirePermission('product:write', { type: req.params.type })`. The function can return `true` for everyone today and refine later. Cost: 2 extra lines per route. Benefit: never have to do a 100-route refactor.

### 4.5 No type-safe contract between Python and TypeScript

**Observation:** The Pydantic models serialize to JSON via Pydantic's defaults. The TypeScript types are written by hand to match. **Nothing checks that they actually match.** A field renamed in Python without updating the TS interface ships and nobody notices until a user sees a missing column.

**The greenfield call:** Either
- (a) Generate the TS types from Pydantic at build time and fail CI if they're out of sync, OR
- (b) Use a single language end-to-end (see [§5](#5-greenfield-architecture-if-starting-today)), OR
- (c) Define schemas in a neutral language (JSON Schema, OpenAPI) and generate both Python and TS from it.

Option (a) is the cheapest retrofit. Option (b) is the cleanest greenfield. Option (c) is a thing other teams do and almost always regret because two layers of generation are worse than one.

### 4.6 No GSI on DynamoDB

**Observation:** `app/backend/src/db/dynamodb.ts` queries by `PK = PRODUCT#<type>` and filters in-memory. There is no GSI on manufacturer, no GSI on product family, no GSI for cross-type search.

**Why this is fine today:** With <10k rows and Lambda's 256MB+ memory, the full-table scan filter takes <100ms. Pay-per-request DynamoDB makes the cost trivial.

**Why a senior would flag it:** Cross-type search ("show me all products from Allen-Bradley" or "show me anything rated for 480V") is currently **N table scans where N = number of types**. As you grow types and rows, this hockey-sticks fast. A single GSI on `manufacturer` and another on a derived `voltage_class` field collapses these to single queries.

**Greenfield call:** Define GSIs in CDK from day 1, even if unused. Adding a GSI to a hot table later requires a write throughput burst that pay-per-request handles but provisioned capacity doesn't. Plan for it.

### 4.7 The `cli/` directory is doing two jobs

**Observation:** `cli/` has 31 modules. They fall into two categories:
- **Operational tools** (one-shot or scheduled): `bench`, `intake`, `processor`, `admin`, `agent`, `query`, `ingest_report`, `price_enrich`, `triage`, `godmode`.
- **One-time migrations**: `migrate_units_to_dict.py`, `migrate_electric_cylinders.py`, `audit_dedupes.py`, `audit_units.py`, `units_triage.py`, `batch_servo_*.py`.

The migrations should be **deletable after they run**. They're history, not API. Keeping them in `cli/` makes the directory feel busier than it is and risks someone running `migrate_units_to_dict.py` a second time (idempotency unclear).

**Greenfield call:** `cli/` for permanent tools, `scripts/migrations/<date>-<name>.py` for one-shots. Migrations get a header comment with the date they ran in prod and are deleted after a grace period. This isn't worth doing today (it's churn) but it's how you'd structure it from scratch.

### 4.8 Frontend state in one big AppContext

**Observation:** `app/frontend/src/context/AppContext.tsx` holds: product list, filter selections, UI toggles, pagination, sort state, theme, and the user's localStorage-persisted preferences. One context for everything.

**Why this is fine today:** It works, the renders are bounded, FRONTEND_TESTING.md has driven the setter contract into solid shape (Phases 1-5 shipped 2026-04-30).

**Why a senior would flag it:** "One context for everything" eventually becomes "every state change re-renders every consumer." React's escape hatch for this is `useMemo` on the context value, which is fragile (you have to remember). The cleaner pattern is **multiple narrow contexts** (`ProductsContext`, `FiltersContext`, `UIContext`) or a state library (Zustand is the lowest-overhead option, ~3kb).

The current pattern doesn't bite because the product list is small. If you ever ship per-product detail views with their own state, the splitting becomes mandatory.

### 4.9 `app/backend/src/routes/compat.ts` and `app/frontend/src/types/compat.ts`

**Observation:** There are "compat" routes and types. CLAUDE.md doesn't explain why. These exist to support a legacy response shape — they're a translation layer between the new schema and what an older client expected.

**Why this is a smell:** Compat layers are forever. Once you have one consumer of the compat shape, you can never delete it. They should be **time-boxed** — version 1 is supported until 2026-Q3, then it's removed.

**Greenfield call:** API versioning from day 1 (`/api/v1/products`, `/api/v2/products`), with a documented sunset policy. The current `/api/v1/search` route hints that this was started; finishing it would let you delete `compat.ts` on a schedule.

### 4.10 Tests are unevenly distributed

**Observation:** Python has 63 test files across unit/integration/staging/post_deploy/benchmark. Strong. The TypeScript backend has Jest tests but the coverage map isn't published. The frontend test coverage was zero until Phases 1-5 of FRONTEND_TESTING.md shipped this week, and Phase 6+ is still planned.

**Why a senior would flag it:** The richest test suite in the project is on the layer with the smallest blast radius (the Python pipeline runs offline; if it has a bug, you re-run it). The thinnest test suite is on the user-facing layer (frontend bugs ship to every visitor). The risk is inverted.

**Greenfield call:** Test budget in proportion to user-facing blast radius. A senior would put **more** effort on frontend regression tests than pipeline tests, not less. The pipeline has a benchmark suite; the frontend has Phase 5 of an unfinished plan.

---

## 5. Greenfield Architecture (If Starting Today)

> Reminder: this is a thought experiment. The current architecture works.

### 5.1 The constraint set I'd design for

If a senior architect sat down today knowing what specodex actually does, the constraints would be:

- **Single user-facing surface**: a web app that searches, filters, and shows industrial product specs
- **Async ingest pipeline**: PDFs come in, get extracted, stored
- **Low traffic**: hundreds of users, not millions; thousands of products, not millions
- **Solo or small team**: one engineer (Nick) maintaining; can't afford the carrying cost of three runtimes
- **AWS-native**: Lambda + DynamoDB + S3 is the deploy target by preference, not by accident
- **Cost-conscious**: pay-per-request DynamoDB, Gemini Flash (not Pro), no idle servers
- **LLM-quality-sensitive**: extraction accuracy is the product; benchmarks must stay green

### 5.2 The shape I'd reach for

```
┌────────────────────────────────────────────────────────────────┐
│                     ONE LANGUAGE: PYTHON                        │
│                                                                 │
│   ┌──────────────┐     ┌──────────────┐    ┌────────────────┐  │
│   │   Ingest     │     │  Web API     │    │  Frontend      │  │
│   │  (existing   │────►│  (FastAPI    │◄───│  (Vite + React │  │
│   │   pipeline)  │     │   on Lambda) │    │   thin shell,  │  │
│   │              │     │              │    │   types from   │  │
│   │  Gemini      │     │  Pydantic    │    │   Pydantic via │  │
│   │  page_finder │     │  models      │    │   pydantic2ts  │  │
│   │  Pydantic    │     │  → JSON      │    │   at build)    │  │
│   └──────┬───────┘     └──────┬───────┘    └────────┬───────┘  │
│          │                    │                     │          │
│          ▼                    ▼                     ▼          │
│   ┌────────────────────────────────────────────────────────┐  │
│   │             DynamoDB (single-table)                     │  │
│   │     PK=PRODUCT#<type>  SK=PRODUCT#<uuid>                │  │
│   │     GSI1=manufacturer  GSI2=voltage_class               │  │
│   └────────────────────────────────────────────────────────┘  │
│                                                                 │
│   Auth: Cognito JWT (or Clerk if Cognito is too much)          │
│   Billing: Stripe via Python Lambda (drop the Rust)            │
│   IaC: AWS CDK (TypeScript) — yes, one TS exception            │
└────────────────────────────────────────────────────────────────┘
```

### 5.3 Why Python end-to-end

The current Node backend (`app/backend/`) is **26,000 lines of TypeScript** that do CRUD, search, validation, and Stripe webhooks. None of it benefits from being TypeScript over Python. All of it pays the cost of maintaining a parallel type system.

**FastAPI** would let the same Pydantic models that drive the pipeline drive the API. The auto-generated OpenAPI spec would generate the TypeScript client for the frontend. The deploy story is the same Lambda + API Gateway shape (via Mangum or AWS Lambda Web Adapter). The TS line count drops to whatever the React frontend strictly needs (~14k → maybe 10k after deduping).

**What you lose:** the `serverless-http`/Express idioms, the shared TS toolchain between backend and frontend, the npm ecosystem for backend libraries.

**What you gain:** one type system, one test runner for the API+pipeline (pytest), one set of mocks (moto), one place to define a product schema. Adding a new product type becomes one file.

**Risk:** FastAPI cold-starts slower than Express on Lambda (~800ms vs ~200ms first request). Mitigation: Lambda SnapStart (works for Python now) or provisioned concurrency for the API path.

### 5.4 Why a thin React frontend (not full TypeScript backend)

You can't realistically build the SPA in Python. So the frontend is React. But it should be **as thin as possible** — ideally a "view layer" that calls a generated API client and renders. Filter logic, sort logic, computation (gear ratio, unit conversion) should live in the API where the Pydantic models are, not in `app/frontend/src/utils/filtering.ts:200+ lines`.

This is a controversial call. The current frontend does compute on the client (gear ratio derivation, unit conversion) which avoids API roundtrips. The tradeoff: do you optimize for **simple data flow** (compute on server, frontend is dumb) or **interactive responsiveness** (compute on client, no roundtrip)?

A senior would say: if the dataset is small (it is — hundreds to low-thousands of products), **compute on server, frontend is dumb**, eliminate the whole class of "frontend computed wrong because it's drifted from the server" bugs. If the dataset grows to where roundtrips matter, revisit.

### 5.5 Why drop the Rust Lambda

The Rust Stripe Lambda exists because cold-starts are fast. But Stripe webhooks are async — nobody's blocked on them. Stripe Checkout sessions don't need <50ms response either; the user is being redirected to Stripe. The Rust Lambda buys nothing measurable.

**Greenfield: Python Lambda.** It would be ~100 lines, use the existing `boto3` and `python-dotenv` already in the dependency tree, share the DynamoDB client code, and reduce the runtime count from 3 to 2.

**Caveat:** if you're learning Rust as a side-quest, that's a fine reason. Just don't pretend it's required.

### 5.6 Why keep CDK in TypeScript (the one exception)

CDK's Python bindings exist (`aws-cdk-lib` for Python) but are second-class. The TypeScript bindings are where new constructs land first, where the docs are richest, and where Stack Overflow answers are. CDK is also a small surface area (a few hundred lines for this project) that doesn't grow with the app.

A senior would accept this exception. One TS file in `infrastructure/` that nobody touches monthly is not the same cost as 26k lines of TS in the backend that you change weekly.

### 5.7 What the type-flow looks like

```
specodex/models/motor.py  (Pydantic — source of truth)
        │
        ├──► FastAPI /products endpoint (auto-uses Pydantic)
        │
        ├──► OpenAPI spec at /openapi.json (auto-generated)
        │
        └──► Build step: openapi-generator → app/frontend/src/api/generated.ts
                                                    │
                                                    └──► React components import typed client
```

**Adding a new product type:**
1. Write `specodex/models/<type>.py` with `product_type: Literal["<type>"] = "<type>"`.
2. Run `npm run gen:api` (regenerates the TS client).
3. Done.

Compare to today: 6 files, 5 of them by hand.

### 5.8 Auth from day 1

Pick **Cognito** (since AWS-native is the rest of the stack) or **Clerk** (if you want to ship faster and pay $25/mo to skip writing auth UI). Either way:

- Every API route reads `req.user` (or `request.state.user` in FastAPI).
- Anonymous users get a session-scoped JWT with `role: "anonymous"`.
- Middleware checks `requires_role("editor")` etc.
- The frontend sends the JWT in `Authorization: Bearer ...`.

The `APP_MODE=public|admin` toggle goes away. Roles replace it. The migration from "anonymous everyone" to "real users" is changing one Cognito attribute, not refactoring 30 routes.

### 5.9 What stays the same

- `specodex/` Python pipeline — keep as-is, this is the gem
- `cli/quickstart.py` dispatcher — single entry point pattern
- DynamoDB single-table design — fits Lambda
- Pydantic + ValueUnit/MinMaxUnit — keep, plus add GSI definitions
- Benchmark suite — keep, it's a moat
- `Quickstart` shell shim — keep
- React + Vite frontend — keep (just thinner)

---

## 6. Specific Design Choices, Justified

This section is for the reader who's saying "but why not X?" — let's preemptively answer the alternatives a senior would have to defend choices against.

### 6.1 Why not Postgres / RDS?

**Why a junior reaches for it:** SQL is familiar, joins work, you can do ad-hoc analytical queries.

**Why a senior says no here:**
- Postgres on AWS means RDS, which means a VPC, which means Lambda needs a VPC, which means cold-starts go from 200ms to 4 seconds.
- Connection pooling inside Lambda is a known nightmare (RDS Proxy mitigates but adds cost).
- The data model is *already* shaped for key-value access (look up products by type, filter in-memory).
- DynamoDB pay-per-request scales to zero. RDS charges 24/7.

**When you'd revisit:** if you needed full-text search across spec values (PG's `ts_vector` is great), or analytical queries (count products per manufacturer per voltage class). Until then, no.

### 6.2 Why Gemini, not Claude or GPT-4?

**Why a junior asks:** "isn't Claude better at structured output?"

**Why a senior keeps Gemini:**
- `response_schema=Model` with Pydantic gives **strict** structured output. Claude's tool-use is strict but more verbose; OpenAI's `response_format=json_schema` is comparable but pricier.
- Gemini 2.5 Flash is the cheapest competent option for spec extraction (~$0.075/1M input tokens at time of writing, 10× cheaper than Claude Sonnet).
- Single-provider simplicity: one SDK, one rate limit, one billing line.

**When you'd revisit:** if benchmark scores degrade, run a head-to-head with Claude Sonnet 4.7 on the fixtures. The infrastructure is in place (`./Quickstart bench --live`). Don't switch on vibes.

### 6.3 Why React, not HTMX or Svelte?

**Why a junior reaches for X:** Svelte is faster, HTMX is simpler.

**Why a senior keeps React:**
- React has the deepest ecosystem for component libraries (you'll want one when you build the admin dashboard).
- Vite makes the build fast enough (the original "React is slow to build" complaint is from CRA).
- The team knows it. Switching frontends is the most expensive thing you can do for the smallest visible benefit.

**When you'd revisit:** never, unless you're rewriting anyway and the team genuinely wants to.

### 6.4 Why CDK, not Terraform or raw CloudFormation?

**The CLAUDE.md drift:** the global `~/.claude/CLAUDE.md` lists "raw CloudFormation YAML, deployed via SAM CLI from shell scripts" as the IaC default. **The actual specodex codebase uses CDK in TypeScript** (see `app/infrastructure/lib/*.ts` and `Quickstart deploy` calling `cdk deploy`). This is a worth-flagging discrepancy: either the global rule needs an exception note for this project, or this project should consider migrating to SAM.

**Why CDK works here:** the stacks are typed, the cross-stack references are checked at synth, and the `HostedZone.fromLookup` / `fromLookup` patterns CDK enables make multi-environment deploys (dev/staging/prod) less copy-paste-heavy than raw YAML.

**Why a senior might still prefer SAM:** smaller surface area, no CDK version upgrades, raw CloudFormation is universally readable. For a project this size either works. The cost of switching is high; don't.

### 6.5 Why not microservices?

**Why a junior asks:** "shouldn't ingest, search, billing be separate services?"

**Why a senior says no:**
- Microservices solve organizational problems (team boundaries) that don't exist here. You have one engineer.
- Each service adds: deploy pipeline, monitoring, error budget, network calls instead of function calls.
- The current "monorepo with separate Lambdas" is already the right amount of separation. The pipeline runs in one Lambda, the API runs in another, the billing runs in a third. They share the DynamoDB layer. That's it.

The line between "separate Lambdas" and "microservices" is whether they have separate data stores and deploy schedules. Today they don't. Don't add the complexity.

### 6.6 Why not move CLI to Click / Typer?

**Why a junior asks:** `argparse` is verbose; Click/Typer would be cleaner.

**Why a senior accepts the current shape:** `cli/quickstart.py` is 1,088 lines of argparse + dispatcher. Refactoring to Typer would be ~3 days of work for ~0% feature improvement. The user-facing surface (`./Quickstart <cmd> [flags]`) wouldn't change. **Don't refactor what isn't blocking.**

If you were starting today: yes, use Typer. It generates `--help` from type hints, dispatches automatically, and reads cleaner. But the migration is not worth the churn.

---

## 7. Migration Sketch (Hypothetical, Don't Implement)

> **Reading this is not authorization to implement it.** This is here so the audit feels complete, not so it becomes a roadmap.

If the team ever decided to consolidate to one app-layer language, here's what a sane sequence would look like, in order of risk-adjusted value. Do **not** start at step 1 without a real plan and a real ADR.

**Phase 0: instrumentation (do this regardless).**
- Add the `pydantic2ts` codegen step. Generate `app/frontend/src/types/generated.ts`. Update `app/backend/src/types/models.ts` to re-export from the generated file. This is the low-risk, high-value win — it eliminates 4 of the 6 hand-synced files for new product types.
- Cost: 1-2 days. Risk: low. Reversible: yes.

**Phase 1: codegen the search Zod enum.**
- The `routes/search.ts` zod enum and `config/productTypes.ts` allowlist both come from `ProductType` in Python. Generate them at build time.
- Cost: 1 day. Risk: low. Reversible: yes.

**Phase 2: stand up FastAPI in parallel.**
- Build a FastAPI service mirroring `app/backend/`'s endpoints. Deploy it to a separate Lambda + API Gateway path (`/api/v2/...`).
- Frontend feature-flags its API base URL. Subset of users hit v2.
- Both services point at the same DynamoDB.
- Cost: 1-2 weeks. Risk: medium. Reversible: yes (just delete the v2 stack).

**Phase 3: cut over.**
- Compare error rates and latency between v1 (Express) and v2 (FastAPI) in CloudWatch.
- When v2 is stable, switch frontend to v2 by default.
- Wait one release cycle. Delete the Express backend.
- Cost: ongoing. Risk: medium-high (the cut itself). Reversible: yes (re-enable flag).

**Phase 4: drop the Rust billing Lambda.**
- Rewrite as Python Lambda using existing `stripe` Python SDK and `boto3`.
- Cost: 1-2 days. Risk: low. Reversible: yes.

**Phase 5: collapse `cli/` migrations into a `scripts/migrations/` archive directory.**
- Move one-time scripts. Delete after a 6-month grace.
- Cost: 0.5 days. Risk: zero. Reversible: trivially.

**What you would NOT do as part of this:**
- Rewrite the Pydantic models. They're correct.
- Rewrite the page-finder. It's correct.
- Rewrite the frontend in Svelte/HTMX. The cost-benefit isn't there.
- Move off DynamoDB. Single-table design is right.
- Add microservice boundaries. The blast radius is already right-sized.

**Total hypothetical effort:** ~6-8 weeks of focused work, spread across phases. Most of the value is in Phase 0 (codegen). Phases 2-4 are the big-ticket changes that you should only do if you have a stretch where the product roadmap is empty and you want to invest in foundations.

---

## 8. Things Junior Devs Should Know Before Touching This

If you're reading this as a junior trying to make a contribution, here's what a senior would whisper to you over coffee:

### 8.1 Read CLAUDE.md before doing anything

Both `~/.claude/CLAUDE.md` (global) and `./CLAUDE.md` (project). The project file especially has the "adding a new product type" runbook, the "two AWS auth principals" foot-gun, the "scraper.py:batch_create bug" warning. These are scars. They cost real time. Don't earn them again.

### 8.2 Run `./Quickstart verify` before pushing

It's the same lint+test+build as CI. Green here = green there. If you push without running it and CI fails, you owe the next dev who blocks on your branch a coffee.

### 8.3 Don't add a 7th file when adding a product type

Six files is the documented surface. If your new type needs a 7th file modified, you've found either a missing abstraction or a legitimate new feature. **Stop and ask.** Don't silently add it; the next person won't know it exists.

### 8.4 Never pass `--force` to ingestion

The `--force` flag re-runs ingestion and writes new rows even if a row exists. Combined with the pre-family-aware-ID era, this created the duplicate prefix-drift mess that `todo/DEDUPE.md` is solving. If you think you need `--force`, ask first.

### 8.5 The `outputs/` directory is regenerable

Don't commit anything from `outputs/`. It's git-ignored for a reason — it's where benchmarks, extraction outputs, and reports land. If a tool's output is interesting, it goes in `tests/benchmark/expected/` (ground truth) or in a PR description (one-off result), never in `outputs/`.

### 8.6 The PR you're about to open is probably already too big

Senior pattern: one logical change per PR. The instinct to "while I'm in here, also fix this other thing" is what produces 800-line diffs that nobody can review. If you find a second issue while fixing the first, write it down (a one-liner in `todo/` or a comment) and ship the first fix alone.

### 8.7 Tests come before "looks right"

"It looks right" is not done. "I ran `./Quickstart verify` and it passed" is done. The pipeline has a benchmark suite for a reason — if your change touches extraction quality, run `./Quickstart bench` and look at the per-field scores.

### 8.8 The frontend has a single global context, treat it carefully

`AppContext` holds everything. Adding a new piece of state to it is easy and tempting. Resist. If your state is local to a component, use `useState`. If your state is shared across two siblings, lift it to their parent. Only put it in `AppContext` if it's genuinely global (auth, theme, current product list).

### 8.9 The "type silently dropped" bug is real

When something doesn't show up on the site, before suspecting the LLM, check: is the type in `VALID_PRODUCT_TYPES`? In the Zod enum? In the TS union? CLAUDE.md has the runbook. Read it.

### 8.10 If you're stuck for more than 2 attempts, stop

This is Nick's rule (in the global CLAUDE.md) and it's correct. The third attempt is almost never the answer. The answer is usually a missing env var, a stale venv, a permission, a flag the docs didn't mention. **Asking costs 30 seconds; thrashing costs an hour.**

---

## 9. Open Questions a Senior Would Push Back On

These aren't answered in CLAUDE.md or the `todo/` docs. A senior reviewing the design would ask:

1. **Who is the primary user?** Engineers shopping for parts? Distributors building catalogs? Manufacturers auditing their own data? The current UI is "advanced search across products" — that targets engineers. But the data ingestion (PDF scraping, manual upload, agent-driven) implies distributor/admin use. Two audiences = two products. Are they really one?

2. **What is the SLA on data freshness?** When a manufacturer publishes a new datasheet, how long until it's in specodex? Today: never automatically (`./Quickstart process` runs by hand). Greenfield: scheduled crawls, RSS-of-PDFs subscriptions, manufacturer webhook pushes? This is a product question disguised as a tech question.

3. **What happens when two manufacturers publish the same part?** A Mitsubishi MR-J5 sold by an authorized distributor vs. by Mitsubishi direct — same product, different rows? Different price? Single canonical row + price-source variants? The current `compute_product_id` is deterministic per `manufacturer + product_name + variant`. That implies "one row per (mfr, name, variant)" — but not "one row per part across mfrs." This will matter when distributors come on board.

4. **How does the UI handle a new product type with no curated metadata?** `app/frontend/src/types/filters.ts:deriveAttributesFromRecords` auto-derives from records, but the labels are snake_case-to-Title-Case. For a new type, columns will look unpolished. Is that acceptable? Or does every new type need a curated metadata pass before it's user-visible?

5. **What's the failure mode for a quality-gate rejection?** Today, low-quality extractions are dropped silently (well, into `ingest_log`). The user uploaded a datasheet and got nothing. There's `./Quickstart ingest-report --email-template` for vendor outreach but no in-product path. Does a user see "we couldn't extract; here's why"?

6. **How does pricing actually work?** Is MSRP stable enough to store? Or is it stale the day it's written? `specodex/pricing/` has an LLM-last-resort cascade but no refresh schedule. A senior would ask: **what's the stale-price tolerance?**

7. **Is the benchmark suite representative?** Mitsubishi, Nidec, Omron, Oriental Motor are 4 fixtures. The page-finder has known holes on Nidec (1/14 spec pages found). Is "good enough on these 4" the right bar, or do you need per-vendor coverage thresholds before claiming a product type is shippable?

8. **What's the contractor model?** If a community contributor wants to add a product type, what's the path? Today the answer is "fork, edit 6 files, run `./Quickstart verify`, open a PR." A senior would note: that path is deeply CLAUDE.md-coupled, hard for a contributor without context. Does community contribution matter?

9. **Where does AI agent traffic come from?** `cli/agent.py` and `dsm-agent` exist. Who runs them? Is this an internal tool or a productized thing for partner agents? If the latter, it needs auth + rate limiting from day 1.

10. **What happens at the 10k product threshold?** Mentioned in [§4.6](#46-no-gsi-on-dynamodb). Is that a year away? A month? The DynamoDB scan-and-filter pattern has a cliff and you'll feel it before the metric dashboard tells you.

These aren't blockers. They're the questions whose answers shape the next twelve months of architecture decisions. Writing them down is half the work.

---

## Closing Note

This document was written by an audit-mode reviewer who walked into a working, shipping product and asked "what would I do differently?" The answer in nearly every case is: **less than you'd think, but more than zero.**

The core of specodex — the Pydantic-first pipeline, the page-finder optimization, the unit-aware data model, the single-table DynamoDB design, the `Quickstart` entry point, the benchmark suite — is correct. A senior architect would not touch it.

The seams of specodex — the polyglot stack, the hand-synced types, the bolt-on auth, the global admin toggle — are the typical scars of a project that grew past its prototype phase without a deliberate refactor pause. They are normal. They are also fixable, mostly with codegen, and mostly without rewriting.

If a future you (or future Nick) wants to act on any of this, **the highest-leverage move is the smallest one**: codegen the TypeScript types from Pydantic. That single change collapses 4 of the 6 hand-synced files, eliminates an entire bug class, and costs ~2 days. Everything else in this document is icing.

Don't implement this document. Use it the way you'd use a code review of a pull request you wrote a year ago: as a mirror for the patterns you reach for, and a list of bets you might make differently next time.

— *End of audit*
