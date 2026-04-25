# Log Feedback — Areas for Improvement

Pulled from local `.logs/`, `outputs/ingest_logs/`, and CloudWatch (`/aws/lambda/DatasheetMiner-*`) on 2026-04-25.

## Sources surveyed

- `.logs/agent_cli.log` — 262 KB, 2,416 lines (most recent: 2026-04-04)
- `.logs/backend.log` — 187 KB, 125 lines (most recent: 2026-04-25)
- `.logs/quickstart.log` — 30 KB, 720 lines (most recent: 2026-04-25)
- `outputs/ingest_logs/contactor-reingest.log` — 127 KB, 905 lines (2026-04-21)
- CloudWatch: `DatasheetMiner-{Dev,Staging,Prod}-Api`, `*-Frontend` (Lambda)

## Top findings (ranked by leverage)

### 1. Gemini free-tier 429 storms wipe out batch ingests
- `outputs/ingest_logs/contactor-reingest.log`: **55 of 905 lines are `429 Too Many Requests`**, every Gemini call in the run failed, **0 products extracted** at the end (`No products extracted`). This was a real attempt to ingest a 410-page Mitsubishi contactor catalog after page_finder had already trimmed it to 25 pages — the entire LLM cost was wasted on retries that all hit the same daily quota wall.
- `.logs/agent_cli.log`: **67 hits** for `RESOURCE_EXHAUSTED`. Every entry says `quotaValue: '20'`, `metric: generate_content_free_tier_requests` — the **20-req/day free tier**.
- The Gemini error payload includes `retryDelay: 32s` (or similar), but the Tenacity wrapper in `datasheetminer/scraper.py` retries every ~4 seconds. We never read the `retryDelay` field; we just burn budget faster.
- **Action:** (a) move off the free tier (or set `GEMINI_API_KEY` to a billed project — pricing is in `cli/bench.py`); (b) parse `retryDelay` from the 429 body and honor it in the retry policy; (c) add an upstream daily-quota guard so `cli.agent` aborts the run after the first 429 instead of grinding through the queue and logging 100 identical errors.

### 2. `RetryError[...ClientError]` swallows the actual status code
- All scraper failures surface as `Failed to extract page(s) [18, 28, 32]: RetryError[<Future at 0x10ee451c0 state=finished raised ClientError>]` — useless without the underlying message.
- The wrapping happens in the Tenacity decorator on `datasheetminer/llm.py`. Reraise with the original exception (`reraise=True`) or capture `last_attempt.exception()` in the log line.
- **Action:** log the inner status + retry-after on the final failure so a future investigator can see "this was a 429, not a model error."

### 3. CloudWatch retention is 7 days — gone before we can look
- All Lambda log groups: `retentionInDays: 7`. Today is 2026-04-25; the last log streams from 2026-04-18 (prod + staging API) report `storedBytes: 0` and `get-log-events` returns `[]`. **Neither prod nor staging has any retrievable API request history right now.**
- Only the CDK frontend-deploy Lambda (no retention set, defaults to never expire) has readable history — and that's just S3 sync output.
- **Action:** bump API/Auth Lambda retention to 30 days in `app/infra/api-stack.ts`. Cost is negligible at current traffic and it lets us actually do this kind of analysis.

### 4. `httpcore`/`httpx` DEBUG noise drowns useful signal
- `outputs/ingest_logs/contactor-reingest.log`: **720 of 905 lines are `DEBUG`** — TLS handshake start/complete, request body send/receive, response close events. Every Gemini call produces ~14 lines of TLS chatter we never read.
- The 429 retry storm produced 127 KB of log for a run that should have been ~5 KB of meaningful output.
- **Action:** in whatever sets up logging for `cli/agent.py` and `cli/intake.py`, add `logging.getLogger("httpcore").setLevel(logging.WARNING)` and the same for `httpx` and `google_genai.models.AFC`.

### 5. Backend logs every DynamoDB query twice per request
- `.logs/backend.log` lines 33–47 vs 41–47: the same 7 category queries (`motor`, `drive`, `gearhead`, ...) are logged twice for a single `GET /api/products/categories`. Same for the result lines (`Page 1 returned ... items`).
- Either the route handler is calling `getCategories()` twice, or the logger is wired up twice. Both are fixable; one wastes DynamoDB read units.
- **Action:** check `app/backend/src/routes/products.ts` (or wherever `getCategories` lives) for a duplicated `await` or middleware that runs the handler twice. Confirm with one curl + a clean log.

### 6. Categories endpoint scans known-empty types every call
- Even though `contactor` and `linear_actuator` reliably return 0 items, `/api/products/categories` issues a full DynamoDB query for them on every request. Seven sequential queries before responding.
- **Action:** parallelize the queries (`Promise.all`) and/or cache the category counts for ~60s. The list of valid types is bounded and slow-changing.

### 7. Gemini JSON truncation still hitting at ~124K chars
- `.logs/agent_cli.log`: `Failed to parse JSON from response text: Unterminated string starting at: line 4262 column 19 (char 124122)`.
- This is the same issue `CLAUDE.md` already notes ("scraper's bundled path tops out around 30 pages before Gemini truncates JSON mid-string"), but it's still firing in the agent path. The auto-switch to per-page extraction in `scraper.process_datasheet` may not be reaching the agent code path.
- **Action:** detect the truncation explicitly (catch `json.JSONDecodeError` near the response cap and split-retry with smaller page batches) instead of returning a `ClientError` that bubbles up as a generic failure.

### 8. Pydantic `value_error` patterns are recurring failure modes
From `agent_cli.log`, repeated across many records:
- `'Stator: 0.077 kg, Rotor: 0.027 kg'` → field is single `value;unit`, model gets a multi-component string. Looks like `weight` collecting both stator and rotor masses on frameless motors.
- `'One-year limited warranty'` → text where the model expects `value;unit`. Probably a `warranty` field mis-typed as numeric.
- The validator `must be in "value;unit" format` rejects the entire record on these — silent data loss, not a single field drop.
- **Action:** in `datasheetminer/models/common.py`, either (a) add a BeforeValidator that detects "comma-separated component:value pairs" and picks one canonical component, or (b) return `None` for unparseable fields rather than failing the whole `Motor` instance. The CLAUDE.md `ambient_temp` `{"unit":"V"}` bug is the same shape — Gemini sometimes returns dicts where strings are expected.

### 9. Silent data loss on missing identifier
- `.logs/agent_cli.log`: `WARNING Cannot generate ID for  — skipping` appears repeatedly when `manufacturer` or `product_name` came back blank.
- The Gemini call succeeded (`Successfully created 1 full model instances`), then we threw the row away because we couldn't build a key.
- **Action:** log the file path and a snippet of the extracted data when this happens, so we know whether to fix the prompt, the model, or the source PDF list.

### 10. `Quickstart` error messages are stripped of context
- `quickstart.log` is full of lines like `ERROR: Command failed (exit 1): npx cdk deploy --all ...` with no stderr captured. Whoever's debugging has to re-run by hand to see the actual CDK error.
- **Action:** in `cli/quickstart.py`, on a failed subprocess, append the last ~20 lines of stderr to the log line (or to `.logs/quickstart-errors.log`).

### 11. Clean Ctrl-C shutdowns logged as `[1;33m Process exited with code 143/15`
- SIGTERM (143) and SIGINT (15) are normal for `./Quickstart dev`, but they show up yellow-flagged like a real failure. Trains the eye to ignore the warning color.
- **Action:** in the dev-server wrapper, treat 143/130/15 as expected exit codes and just log "shut down" at info level.

### 12. Same-record validation logged twice in a row
- `agent_cli.log`: `'BG 45x15 SI'` validation failure appears on consecutive lines with the same timestamp. Most BG-series records are double-logged.
- Either the per-page extraction is processing the same model twice (overlapping page slices) or the merge step re-validates after a failed merge. Worth tracing.
- **Action:** find the dedup key — if the same `manufacturer + product_name` shows up twice in the parsed list, the merge step should drop the duplicate before validation, not after.

### 13. CDK custom-resource Lambdas have unbounded retention
- The `LogRetentionaae0aa3c5b4d4f-*` log groups have `retentionInDays: 1`, but the `CustomCDKBucketDeploymen-*` and `CustomS3AutoDeleteObject-*` groups have `None` (= never expire). They're tiny but they accumulate forever.
- Frontend deploy Lambda invocations take **73 seconds each** because `WaitForDistributionInvalidation: true`. Multiply by every deploy and that's a chunk of CDK custom-resource time we're paying for serially.
- **Action:** set retention on these in the CDK stack (30 days is fine), and consider `WaitForDistributionInvalidation: false` if we don't actually block on the invalidation completing.

### 14. Stale debug artifact at outputs root
- `outputs/output.json` — 130 KB, last modified 2025-11-03 (>5 months ago). Not produced by any current pipeline; gitignored but cluttering.
- **Action:** delete, or move to `outputs/archive/` if it's reference data.

## What we couldn't see (and want)

- **Live API request volume / 4xx rates from prod.** 7-day Lambda retention has expired the only window we had. Fix #3 unlocks this.
- **`/api/v1/search` query patterns.** No structured access logs. Even a `console.log({ type, page, filterCount })` per request would tell us which product types and filters get used.
- **Per-fixture extraction outcome.** The contactor reingest run wrote no summary of "X products extracted, Y failed validation, Z hit 429" — we only know it failed because the tail says `No products extracted`. A run-completion summary line would let us spot regressions in CI.

## Triggers

Surface this doc when the current task touches any of:

- `datasheetminer/llm.py` (Tenacity retry policy — items #1, #2, #7)
- `datasheetminer/scraper.py` retry / per-page split logic (items #1, #7, #12)
- `datasheetminer/models/common.py` BeforeValidators or quality filtering (item #8)
- `cli/agent.py`, `cli/intake.py`, `cli/quickstart.py` logging setup (items #4, #10, #11)
- `app/backend/src/routes/products.ts` `getCategories` (items #5, #6)
- Any CDK infra log-group config — `app/infrastructure/lib/*-stack.ts` (items #3, #13)
- Gemini 429 / `RESOURCE_EXHAUSTED` / quota errors in any session
- User asks "why are logs so noisy" or "why did this batch ingest fail silently"
- Each numbered finding here is independently fixable — pick one when an adjacent edit makes it cheap.
