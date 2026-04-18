# Edge-Case Hardening Plan

Goal: push the whole stack — Python core, Node backend, React frontend — toward "hard
to break from the outside, fast to recover when it does break." Targets functionality,
robustness, and performance in that order.

Baseline (from coverage survey, 2026-04-17):

- Python core: **60% line coverage** (671 tests). Biggest holes: `db/dynamo.py` 31%,
  `scraper.py` 41%, `page_finder.py` 0%.
- Node backend: **46% line coverage** (194 tests). Biggest holes: `db/dynamodb.ts`
  1.9%, `services/gemini.ts` 12%, `services/scraper.ts` 5%, `services/stripe.ts` 8%.
- Frontend: 127 tests, no line-coverage tracked. No schema validation on
  `localStorage` reads. Only one XSS-targeted file (`utils/sanitize.test.ts`).

## Design rules

- **One failure class per test.** No test should verify both "parses correctly" and
  "rejects garbage" — split them. Easier to read a failure at 2am.
- **Property tests where the input space is large.** Hypothesis (Python) and
  fast-check (Node) beat hand-rolled parametrize lists for parsers, validators,
  and string normalizers.
- **Real DynamoDB for DB tests.** No mocks. Prior project rule — mock-DB tests passed
  before a migration that broke prod. Use a scoped `dsm-test-*` table in the bench
  account; nuke between runs.
- **No network in unit tests.** Gemini, Stripe, S3 stay mocked at the unit layer.
  Integration tests hit a throwaway stack; staging tests hit dev.
- **Timed budgets.** Every perf test asserts a wall-clock ceiling (liberal on CI,
  tighter locally). A regression that doubles latency should fail loud, not silently.

---

## Phase 1 — Python core: parser + validator hardening

Targets `datasheetminer/models/common.py`, `datasheetminer/units.py`,
`datasheetminer/db/dynamo.py::_parse_compact_units`, and every `BeforeValidator` used
by product models.

### 1a. `tests/unit/test_value_unit_property.py` (new)

Hypothesis-driven property tests for `handle_value_unit_input` and the `"value;unit"`
canonical form. At minimum:

- **Round-trip**: any `(value, unit)` pair that the validator accepts must survive
  `serialize → _parse_compact_units → reassemble` without drift.
- **Idempotence**: `normalize(normalize(x)) == normalize(x)` for every accepted input.
- **Min-max invariant**: `min-max;unit` with `min > max` is either rejected or
  canonicalized — never silently accepted.
- **Rogue inputs**: `""`, `None`, `";"`, `"1;"`, `";V"`, `"1;2;3"`, `"nan"`, `"inf"`,
  `"-0"`, leading/trailing whitespace, unicode digits (U+FF11 `１`), scientific
  notation (`1e3`), negative zero, floats that overflow Decimal.
- **Dict input**: `{"value": ..., "unit": ...}` with missing keys, extra keys,
  nested dicts, wrong types (list, bool, None) — all must either coerce deterministically
  or raise a `ValidationError`, never pass through silently.

### 1b. `tests/unit/test_compact_units_regex.py` (new)

The regex in `db/dynamo.py:92` is the lone boundary between DynamoDB strings and
typed values. Hit it directly:

- Every known unit from `datasheetminer/units.py` as a case.
- Unicode lookalikes: em-dash vs hyphen in ranges, non-breaking space, ohm sign.
- Values bigger than Python float precision → assert Decimal path doesn't lose digits.
- Pathological: `"1;2;3"` (too many separators), `"abc;V"` (non-numeric), `"--5;V"`
  (double-negative), `"1-;V"` (missing max), `";V"` (missing value).

### 1c. `tests/unit/test_quality_boundary.py` (new)

`datasheetminer/quality.py` rejects products below a threshold. Today covered only at
the happy path. Add:

- Exactly-at-threshold records (boundary condition) — must not flap.
- Records where every field is `None` but schema has no required fields.
- Records where `part_number` equals the string `"None"`, `"N/A"`, `"-"`, `"TBD"`.
- Unicode collisions (product_name with zero-width joiner or combining accents).

### 1d. `tests/unit/test_models_per_type.py` (extend)

One parametrized test per model in `datasheetminer/models/`:

- Minimal valid instance.
- Instance with every field populated (full-fat).
- Instance with one required field missing → `ValidationError`.
- Instance with one extra/unknown field → assert behavior matches `model_config`
  (either pass through or reject; document which).
- `model_dump()` → `model_validate(dump)` round-trip equivalence.

**Verification:** `./Quickstart test` green; `uv run pytest --cov=datasheetminer
--cov-report=term-missing` shows `db/dynamo.py` above 60% and `common.py` above 90%.

---

## Phase 2 — Python core: pipeline + scraper integration

Targets `datasheetminer/scraper.py`, `datasheetminer/page_finder.py`, and the
`cli/intake.py → cli/intake_guards.py → scraper` chain.

### 2a. `tests/integration/test_scraper_degraded_inputs.py` (new)

Feeds scraper the failure modes we've actually hit:

- 162-byte HTML-disguised-as-PDF (from `bad_examples/`) — must hit guard-block,
  not explode.
- Truncated PDF (first 10KB of a valid PDF) — parse error surfaced clearly.
- Password-protected PDF — detected and skipped, not hung.
- 616-page J5 catalog fed raw → scraper must auto-switch to per-page mode per
  `MAX_PER_PAGE_CALLS` and finish without JSON-truncation errors.
- PDF where `page_finder` returns 0 pages → fallback path runs, doesn't crash.
- PDF where `page_finder` returns all N pages (cap didn't engage) → test asserts
  the cap works.

### 2b. `tests/unit/test_page_finder_edge.py` (new — `page_finder.py` is 0% covered)

- Empty PDF (1 blank page).
- PDF with text layer but zero spec keywords anywhere.
- PDF with spec keywords on every page (all pages tie on score).
- PDF where text extraction returns bytes instead of str (old `pypdf2` quirk).
- Density scoring: assert `find_spec_pages_scored` returns pages ordered by density
  DESC, not by page index.
- `SPEC_KEYWORDS` groups (all 18) — property test: any page containing ≥ 3 keywords
  from any one group is scored > 0.

### 2c. `tests/integration/test_intake_guards_end_to_end.py` (new)

Guards exist and are unit-tested (`test_intake_guards.py`) but not exercised through
`intake_single`. Add:

- Real `bad_examples/` PDFs → `intake_single` returns `status: rejected` with the
  right `guard` field.
- A valid PDF → passes all guards, returns `status: promoted`.
- DynamoDB mock returns a content-hash collision → dedup path returns `duplicate`.

### 2d. `tests/integration/test_db_roundtrip.py` (expand)

Hit `datasheetminer/db/dynamo.py` against a real test table:

- Concurrent writes of the same `product_id` (10 threads, `ConditionExpression`
  should serialize them).
- `batch_delete` of 100+ items (crosses the 25-item BatchWriteItem limit).
- `list_all` pagination across 2000 items (validates cursor handling).
- An item stored via `create`, mutated in DynamoDB directly, then read — assert
  decimals deserialize back to Decimal not float (no silent precision loss).

**Verification:** `./Quickstart test` green; new integration dir passes against a
dedicated `dsm-test-<timestamp>` table that's torn down after.

---

## Phase 3 — Node backend: route-level contract + fuzz tests

Targets every route under `app/backend/src/routes/`. Framework: Jest + supertest.

### 3a. `app/backend/tests/routes/search.contract.test.ts` (new)

`/api/v1/search` already has Zod validation; test the boundary:

- `limit=0`, `limit=-1`, `limit=101`, `limit=1e10`, `limit=abc` → all 400.
- `type` not in enum → 400.
- `where` with 50+ entries → behaviour is documented and enforced (cap or 400).
- `sort` pointing at a non-existent column → either empty result or 400, not 500.
- `q` with SQL-ish content (`'; DROP TABLE products --`) → treated as literal text,
  no server error. We don't use SQL but this is the canonical abuse input.
- `q` at 10KB → 400 (length cap) rather than pushed to DynamoDB.
- Duplicated query-string keys (`?type=motor&type=drive`) → deterministic behavior
  (take first or array), not undefined.
- Null bytes (`\x00`) in every string param — rejected or stripped.
- Unicode normalization: `caf\u00e9` vs `cafe\u0301` — both should match the same
  record if search is normalized, or both should NOT match if we've decided not to.
  Pick one; test it.

### 3b. `app/backend/tests/routes/products.contract.test.ts` (new, expand existing)

- POST with body exceeding Express `json` size limit → 413, not crash.
- POST with `Content-Type: application/json` but body is HTML → 400.
- POST with extra unknown fields → assert policy (strip? reject? store?).
- PUT with `id` mismatched between URL and body → 400.
- DELETE non-existent `id` → 404 (idempotent) not 500.
- Path params with URL-encoded slashes (`/api/products/a%2Fb`) → handled deterministically.
- Batch endpoints (`/deduplicate`, by `partNumber`): empty input array → 400; 10k-item
  input → capped.

### 3c. `app/backend/tests/routes/upload.contract.test.ts` (new)

Presigned-URL endpoint is the one user-writable path in public mode:

- Filename without `.pdf` → 400.
- Filename with path traversal (`../etc/passwd.pdf`) → sanitized or 400.
- Filename with null bytes, CRLF, emoji → either sanitized or 400.
- `product_type` not in `VALID_PRODUCT_TYPES` → 400.
- Missing `manufacturer` → 400.
- Rapid repeat calls from same client → presigned URLs are distinct (no reuse).

### 3d. `app/backend/tests/middleware/readonly.edge.test.ts` (new)

`readonly.ts` exempts `/upload`. Verify:

- POST `/api/upload` allowed in public mode.
- POST `/api/upload/something-else` NOT allowed (exact-path match, not prefix).
- All verbs on `/api/admin/*` blocked regardless of `/upload` exemption.
- Case-sensitivity: `/API/UPLOAD` — document behavior (Express is case-insensitive
  by default; test that this either matches the exemption or doesn't, consistently).

### 3e. `app/backend/tests/db/dynamodb.integration.test.ts` (new)

Biggest coverage hole. Against a real test table:

- `getProduct` returns undefined (not null, not throw) for missing id.
- `listProducts` pagination across > 1MB of data (DynamoDB's per-page limit).
- `putProduct` with a Decimal field at DynamoDB's max precision.
- `batchDelete` across the 25-item BatchWriteItem boundary.
- Network-timeout simulation → client retries per config, not infinitely.

**Verification:** `cd app/backend && npm test`; coverage report shows
`db/dynamodb.ts` above 70% and every route file above 80%.

---

## Phase 4 — Frontend: input, state, and rendering edges

Targets `ProductList.tsx`, `FilterBar.tsx`, `AppContext.tsx`, `api/client.ts`, and
the `localStorage` hooks.

### 4a. `app/frontend/src/utils/localStorage.test.ts` (new)

Today, `ProductList.tsx` reads hidden-column JSON from `localStorage` without a
schema. Add a `safeLoad<T>(key, schema)` helper + tests:

- Missing key → returns default.
- Malformed JSON (`"{"`) → returns default, logs once.
- Valid JSON but wrong shape (e.g. hidden columns is `{}` instead of `[]`) → returns
  default.
- Value is `null`, `"null"`, `""`, `"undefined"` → returns default.
- Value exceeds quota on write → doesn't throw, falls back to in-memory.
- Concurrent tab write (storage event) → updates state without stale closure.

Then migrate every `localStorage.getItem` in the frontend to go through this helper.

### 4b. `app/frontend/src/components/ProductList.edge.test.tsx` (new)

- Empty product list (zero records) — renders "No products" rather than empty grid.
- One product with every field `null` — no column crash, all cells render "—".
- 10,000 products — virtualization kicks in, initial render under 200ms.
- `productListMaxVisibleColumns = 0` → at least one column still shown (the cap has
  a floor).
- Hidden columns list contains a column that no longer exists in data → silently
  ignored, not a render loop.
- Sort on a column where half the rows have `null` — nulls sort last consistently.
- Row-density toggle while sorted — selection + scroll position preserved.

### 4c. `app/frontend/src/components/FilterBar.edge.test.tsx` (extend existing)

- Filter where value is empty string → no-op (not "match everything").
- Filter on numeric field with string input (`"abc"`) → validation hint, not
  pushed to API.
- Combined filters where one filter zeroes the result set → empty state renders
  without race against the spinner.
- Rapid filter toggling (10 changes in 500ms) → only last request wins
  (abort-controller or debounce).

### 4d. `app/frontend/src/api/client.edge.test.ts` (extend)

- Server returns 500 → retries per config, surfaces final error to caller.
- Server returns 200 with malformed JSON → caught, doesn't crash the UI.
- Request times out at 30s → abort fires, UI shows timeout state.
- `VITE_APP_MODE=public` + admin call → throws *before* network (test exists;
  assert error shape is stable).

### 4e. `app/frontend/src/utils/sanitize.edge.test.ts` (extend)

Existing tests cover `javascript:`, `data:`, `ftp:`. Add:

- `vbscript:`, `file:`, `blob:` — all blocked.
- URL with embedded newline (`http://x.com/\nbad`) — rejected.
- URL at 10KB — handled without ReDoS.
- International domain: `http://münchen.de` — allowed (or policy-documented).

**Verification:** `cd app/frontend && npm test`; add `--coverage` to the Vitest
script and check the new tests raise branch coverage in each target file above 80%.

---

## Phase 5 — Performance + load budgets

Performance tests run via `./Quickstart bench` and a new `./Quickstart loadtest`
subcommand.

### 5a. `tests/benchmark/budgets.json` (new)

A JSON map of wall-clock ceilings by fixture slug:

```
{
  "j5-filtered":         { "page_find_ms": 500,  "llm_extract_ms": 30000 },
  "nidec-d-series":      { "page_find_ms": 200,  "llm_extract_ms": 15000 },
  ...
}
```

The bench harness reads this and fails the run when a fixture exceeds budget by
> 25%. Regressions become visible immediately, not at release.

### 5b. `app/backend/tests/load/search.load.test.ts` (new)

Using `autocannon` or similar:

- 100 concurrent `/api/v1/search?q=motor` for 30s → p95 under 500ms.
- 10 concurrent `/api/v1/search` with different `where` clauses → no 5xx.
- Single hot key: 1000 sequential `GET /api/products/:id` → per-request p50 under
  50ms.

### 5c. `cli/loadtest.py` (new, wired into `./Quickstart loadtest`)

Small Python script that replays a canned set of requests against a target URL and
asserts the budgets above. Deploy-gated: run against dev post-deploy, skip against
prod by default.

**Verification:** `./Quickstart loadtest https://api.dev.datasheetminer.com` prints
a pass/fail table; fail triggers non-zero exit.

---

## Phase 6 — Chaos + failure injection

Lightweight, optional. Run locally, not in CI.

- `tests/chaos/test_dynamo_throttling.py` — mock DynamoDB client raises
  `ProvisionedThroughputExceededException` on every 3rd call; assert backoff +
  eventual success.
- `tests/chaos/test_gemini_partial_response.py` — Gemini returns a JSON string
  truncated mid-value; assert `parse_gemini_response` surfaces a clean error rather
  than a silent drop.
- `tests/chaos/test_s3_eventual_consistency.py` — simulate `HEAD` returning 404
  immediately after `PUT`; assert retry-with-backoff rather than treating upload
  as lost.

These aren't run on `./Quickstart test` by default. Add a `./Quickstart chaos`
subcommand that runs them on demand.

---

## Phase 7 — Security edges (narrow scope)

Not a full security review — just the edges most likely to bite.

- Every route that accepts a DynamoDB attribute name from the user (search `where`,
  `sort`) must refuse reserved words and dotted paths. Add
  `app/backend/tests/routes/search.attribute-safety.test.ts`.
- Upload filename sanitization (Phase 3c) is the main user-writable surface.
- Admin endpoints should 403 when `APP_MODE=public` even with a forged JWT header
  (the guard should not inspect auth). Test in `middleware/adminOnly.edge.test.ts`.
- All outbound `fetch` calls in the backend validate URL scheme is https (blocks
  SSRF via a crafted datasheet URL). Add `services/scraper.url-policy.test.ts`.

---

## Files to create/modify

| File | Action | Phase |
|---|---|---|
| `tests/unit/test_value_unit_property.py` | **Create** | 1a |
| `tests/unit/test_compact_units_regex.py` | **Create** | 1b |
| `tests/unit/test_quality_boundary.py` | **Create** | 1c |
| `tests/unit/test_models_per_type.py` | **Extend** | 1d |
| `tests/integration/test_scraper_degraded_inputs.py` | **Create** | 2a |
| `tests/unit/test_page_finder_edge.py` | **Create** | 2b |
| `tests/integration/test_intake_guards_end_to_end.py` | **Create** | 2c |
| `tests/integration/test_db_roundtrip.py` | **Extend** | 2d |
| `app/backend/tests/routes/search.contract.test.ts` | **Create** | 3a |
| `app/backend/tests/routes/products.contract.test.ts` | **Create** | 3b |
| `app/backend/tests/routes/upload.contract.test.ts` | **Create** | 3c |
| `app/backend/tests/middleware/readonly.edge.test.ts` | **Create** | 3d |
| `app/backend/tests/db/dynamodb.integration.test.ts` | **Create** | 3e |
| `app/frontend/src/utils/localStorage.ts` + `.test.ts` | **Create** | 4a |
| `app/frontend/src/components/ProductList.tsx` | **Edit** (use safeLoad) | 4a |
| `app/frontend/src/components/ProductList.edge.test.tsx` | **Create** | 4b |
| `app/frontend/src/components/FilterBar.edge.test.tsx` | **Extend** | 4c |
| `app/frontend/src/api/client.edge.test.ts` | **Extend** | 4d |
| `app/frontend/src/utils/sanitize.edge.test.ts` | **Extend** | 4e |
| `tests/benchmark/budgets.json` | **Create** | 5a |
| `cli/bench.py` | **Edit** (enforce budgets) | 5a |
| `app/backend/tests/load/search.load.test.ts` | **Create** | 5b |
| `cli/loadtest.py` | **Create** | 5c |
| `cli/quickstart.py` | **Edit** (add `loadtest` + `chaos` subcommands) | 5c, 6 |
| `tests/chaos/*.py` | **Create** | 6 |
| `app/backend/tests/routes/search.attribute-safety.test.ts` | **Create** | 7 |
| `app/backend/tests/middleware/adminOnly.edge.test.ts` | **Create** | 7 |
| `app/backend/tests/services/scraper.url-policy.test.ts` | **Create** | 7 |

## Implementation order

1. **Phase 1** (pure Python, no infra). Property tests on validators catch the most
   bugs per hour of effort. Ship first.
2. **Phase 3a + 3b + 3c + 3d** (backend route contracts, in-memory). No DynamoDB
   needed; zod/supertest covers most of this.
3. **Phase 4a** (localStorage safeLoad) — one helper, big robustness win, unblocks
   4b.
4. **Phase 2a + 2b + 2c** (scraper + page_finder + guards end-to-end). Need real
   PDFs from `bad_examples/` but no AWS.
5. **Phase 4b + 4c + 4d + 4e** (frontend edges).
6. **Phase 2d + 3e** (DB integration against throwaway table). Needs AWS.
7. **Phase 5** (performance budgets). Only useful once functional tests are solid.
8. **Phase 6 + 7** (chaos + security edges). Last — most work per bug caught.

## Stop conditions (don't over-invest)

- Python core above 80% line coverage and 100% branch coverage on
  `models/common.py`, `db/dynamo.py`, `quality.py`.
- Backend above 75% line coverage with every route file at ≥ 80%.
- Frontend: coverage on file-by-file basis, target 80% on touched files only.
- No perf regression exceeds its budget by > 25% on `./Quickstart bench`.
- Every fixture in `bad_examples/` has a matching integration test that exercises
  the guard + rejection path.

When all four are green, stop. Further testing has diminishing returns; pour the
leftover effort into monitoring + alerting instead.
