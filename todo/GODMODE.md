# GOD mode dashboard

A single page that answers "what the hell is going on with this project right
now?" without forcing context-switching between AWS Console, GitHub,
CloudWatch, the terminal, and three Quickstart commands.

## Goal

One URL — `/godmode` in the React app, gated by the existing `adminOnly`
middleware — that surfaces, at a glance:

1. **AI usage** — Gemini token spend / RPM / error rate (from ingest_log);
   Claude Code token spend (from local transcripts). Cost in dollars.
2. **Pipeline health** — recent ingest attempts, success vs quality_fail vs
   extract_fail, top failing manufacturers, p50/p95 wall-clock per attempt.
3. **Database health** — products by type, products written in last 24 h,
   "unhealthy" rows (nulls below the quality floor, missing prices, stale
   `createdAt`, orphaned `INGEST#` records with no matching product).
4. **Repo activity** — commits last 7/30 d, LOC by language, churn (lines
   added/removed), test pass rate from the last `./Quickstart test` run.
5. **Deploy state** — current stack version per stage (dev/staging/prod),
   `/health` response, last 10 CloudWatch errors.
6. **Backlog state** — `todo/*.md` count by status (🚧 / ⏸ / 🔴 / ✅),
   urgency surfaced.

Stupid simple on purpose: read existing data sources, no new agents, no new
metrics pipeline. Every panel must answer "where does the number come from?"
in one sentence.

## Non-goals

- **No new metrics infrastructure.** No CloudWatch custom metrics, no
  Prometheus, no Datadog. We already have ingest_log in DynamoDB and
  CloudWatch Logs — derive everything from there.
- **No real-time push.** Polling on an Refresh button is fine. SSE/WebSockets
  would be over-engineering for a one-user dashboard.
- **No historical timeseries store.** Last-N-days windows computed on
  demand. If we want trends later, that's a separate doc.
- **No ML/anomaly detection.** Threshold colors only (green/yellow/red).
- **No Claude org admin API integration.** Personal Claude usage comes from
  reading local `~/.claude/projects/` transcripts; we don't try to auth
  against console.anthropic.com.
- **No mobile responsiveness.** Desk-only tool.

## Architecture options

### Option A — extend the React admin surface (recommended)

Add `/godmode` route in the React app, backed by a new Express router at
`/api/admin/godmode/*`, gated by the existing `adminOnly` middleware. Each
panel = one endpoint that returns JSON shaped exactly for its widget.

Pros:
- Reuses existing auth, deployment, build pipeline.
- Backend already has DynamoDB, CloudWatch, and CloudFormation SDK clients.
- The frontend already has chart primitives (`DistributionChart`).

Cons:
- Backend (Lambda) can't read your local git repo or `~/.claude/`. Anything
  local needs a separate path (Option B).

### Option B — local-only HTML snapshot

`./Quickstart godmode` runs a Python script that pulls everything (DynamoDB,
git, Claude transcripts, last bench, last test result) into a single
self-contained HTML file at `outputs/godmode/latest.html`, then opens it.

Pros:
- Can read `~/.claude/`, local git, local test runs — all the things a
  Lambda can't see.
- Zero deploy required, zero auth question.

Cons:
- Stale the moment you regenerate. No "live" view.
- Duplicates panels we'd want in the deployed dashboard anyway.

### Recommended: A + B, split by data locality

- **Deployed (Option A) covers**: Gemini usage, ingest pipeline, DynamoDB
  health, deploy state, CloudWatch errors. All cloud-data, accessible from
  Lambda.
- **Local (Option B) covers**: Claude usage, git activity, LOC, last test
  run, backlog state. All local-data, would be expensive or impossible to
  ship to Lambda.

Both render with the same panel CSS so they feel like one tool. The local
script can write its JSON to a known path that the deployed dashboard
optionally embeds via file upload (later — not MVP).

## Data sources (where each number comes from)

| Panel | Source | Already exists? |
|---|---|---|
| Gemini tokens / cost | `INGEST#*` records — `gemini_input_tokens`, `gemini_output_tokens` fields | ✅ since ENRICH.md |
| Gemini RPM / error rate | Same records, group by minute, count `extract_fail` | ✅ |
| Gemini-non-ingest calls (schemagen, price LLM) | **gap** — not currently logged with tokens | ❌ requires a small change to `specodex/llm.py` to emit a structured log line with `{call_kind, input_tokens, output_tokens}` per call |
| Claude usage | `~/.claude/projects/*/conversations/*.jsonl` — each turn's `usage` field | ✅ files exist; need a parser |
| Ingest success rate | `INGEST#*` `status` field, last N days | ✅ |
| Top failing manufacturers | `cli/ingest_report.py` already does this — call its function | ✅ |
| Products by type | `categories` endpoint (already shipped) | ✅ |
| New products last 24 h | DynamoDB scan on `createdAt > now-24h` (need GSI or accept scan cost) | ⚠ need to confirm `createdAt` exists on every row |
| Unhealthy products | Scan + apply same logic as `quality.py` to live rows | ⚠ scan cost — limit to last 1000 rows or sample |
| Orphaned ingest records | `INGEST#*` with `status=success` but no matching product PK | ⚠ join on client side |
| Commits 7/30 d | `git log --since="7 days ago" --oneline \| wc -l` | ✅ |
| LOC by language | `cloc` (would need install) **or** `find ... -name "*.py" \| xargs wc -l` (zero-dep) | ✅ with shell only |
| Churn | `git log --since=... --shortstat` | ✅ |
| Last test result | Parse `pytest --json-report` output OR re-run quickly | ⚠ pytest needs `pytest-json-report` plugin OR write to a known path |
| Stack version per stage | `aws cloudformation describe-stacks --query 'Stacks[0].LastUpdatedTime'` | ✅ AWS CLI |
| `/health` per stage | `curl` each stage's URL | ✅ |
| Last 10 CloudWatch errors | `aws logs filter-log-events --filter-pattern ERROR` | ✅ |
| Backlog state | Parse `todo/README.md` table | ✅ |

## MVP slice — ship this first

The cheapest panels with the highest information density. Everything below
reuses data we already capture.

1. **Gemini panel (deployed)** — last 24 h / 7 d / 30 d:
   - Total input + output tokens.
   - Total cost (use the same `$/1M` constants from `cli/bench.py`).
   - Calls / hour sparkline.
   - Success / quality_fail / extract_fail counts.
   - **One endpoint:** `GET /api/admin/godmode/gemini?window=24h`.

2. **Ingest pipeline panel (deployed)** — last 24 h / 7 d:
   - Attempts processed.
   - Top 10 manufacturers by quality_fail count.
   - p50 / p95 `fields_filled_avg`.
   - "Most recent 20 attempts" table with status, manufacturer, URL, fields_filled.
   - **One endpoint:** `GET /api/admin/godmode/ingest?window=24h`.

3. **Database panel (deployed)**:
   - Count by `product_type` (already exists — reuse `categories`).
   - Count of products written last 24 h (needs `createdAt` audit first).
   - Count of products below quality floor (sample 1000 rows).
   - **One endpoint:** `GET /api/admin/godmode/db`.

4. **Repo panel (local, Option B)**:
   - Commits last 7 d / 30 d, top contributors.
   - LOC by extension (`.py`, `.ts`, `.tsx`).
   - Churn (added / removed) last 7 d.
   - Test result from last `./Quickstart test` run (write a JSON sidecar).
   - Backlog status counts from `todo/README.md`.
   - **One CLI:** `./Quickstart godmode` writes `outputs/godmode/latest.html`.

5. **Claude usage panel (local, Option B)**:
   - Parse `~/.claude/projects/-Users-nick-github-specodex/conversations/*.jsonl`.
   - Sum `usage.input_tokens`, `usage.output_tokens`,
     `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens`
     per day for the last 30 days.
   - Cost using current Sonnet 4.6 / Opus 4.7 pricing — pin in a constant.
   - **Same CLI as #4.**

Anything beyond MVP — orphan detection, deploy panel, CloudWatch errors —
goes in a follow-up. Each adds one endpoint + one widget.

## Per-panel design notes

### Gemini usage

The ingest_log already captures `gemini_input_tokens` / `gemini_output_tokens`
per call (see `specodex/ingest_log.py:build_record`). The deployed panel
queries `INGEST#*` records by SK timestamp range and aggregates client-side
(<1000 records per window in practice).

**Gap to close before this works:** schemagen and the price-LLM cascade also
call Gemini but don't emit ingest_log records. Two options:

- **(easier)** Have `specodex/llm.py` emit a CloudWatch log line per
  call — `{"event": "gemini_call", "kind": "schemagen|price|extract", "input_tokens": N, "output_tokens": N}` — and `metric filter` it into a count. Heavy.
- **(simpler)** Write a sibling row to ingest_log keyed under a different PK
  prefix — `LLM#<kind>#<sha256(prompt)[:16]>` — same shape, same query
  pattern. Then the dashboard queries both prefixes.

Recommend the second. Keeps everything in one table, one query pattern.

### Claude usage

Claude Code stores conversations as JSONL files. Each assistant turn has a
`usage` block:

    {"role": "assistant", "usage": {"input_tokens": 1234, "output_tokens": 567,
     "cache_read_input_tokens": 8000, "cache_creation_input_tokens": 200}}

Parser pseudocode:

    for jsonl in glob("~/.claude/projects/*/conversations/*.jsonl"):
        for line in jsonl:
            turn = json.loads(line)
            if turn.get("role") == "assistant" and "usage" in turn:
                day = turn["timestamp"][:10]
                model = turn.get("model", "unknown")
                bucket[(day, model)] += turn["usage"]

Then apply the per-model `$/1M` constants. Cache reads are 10% of the
non-cached price — important to count separately.

**Caveat:** the `~/.claude/projects/` path is project-specific (the project
directory is the path after `projects/`). The dashboard should default to
the current project but allow `--all-projects` to roll up across
everything.

### Database health

"Unhealthy" needs a definition. Three categories:

- **Quality floor breach**: products whose live `fields_filled` ratio
  (computed by walking model fields) is below the floor in `quality.py`.
  These shouldn't exist post-quality-gate but **historically have been
  written** (see CLAUDE.md note about `scraper.py:batch_create(parsed_models)`
  bug). Catch and surface.
- **Missing price**: `msrp` field is null after the price-enrich run.
- **Stale**: `createdAt` older than 6 months and never updated. Probably
  fine but worth seeing.

Implementation: scan the products table in pages of 100 with a `Limit`
cap (no full-table scan in the request path). If the table grows past
~5000 rows we'll need a precomputed health index — defer that doc.

### Repo activity

LOC without `cloc`:

    find . -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" \) \
      -not -path "./node_modules/*" -not -path "./.venv/*" \
      -not -path "./app/*/node_modules/*" -exec wc -l {} + | tail -1

Churn:

    git log --since="7 days ago" --shortstat --pretty=format: \
      | grep -E "files? changed" \
      | awk '{ins+=$4; del+=$6} END {print ins, del}'

Test result: `./Quickstart test` doesn't currently emit a machine-readable
sidecar. Two ways to fix:

- Add `pytest --json-report --json-report-file=outputs/test/last.json` to
  the test step. Requires `pytest-json-report` (one new dev dep).
- Or have the Quickstart wrapper capture the exit code + last 50 lines of
  output to `outputs/test/last.txt`. Zero deps, less rich.

Recommend the second — matches the project's "stupid simple" bent.

### Deploy state

Three calls, run in parallel:

    aws cloudformation describe-stacks --stack-name DatasheetMiner-Dev-Api \
      --query 'Stacks[0].{updated: LastUpdatedTime, status: StackStatus}'

Same for Staging and Prod. Plus a `curl /health` per stage. ~6 API calls
total per refresh — ~1 second.

### CloudWatch errors

    aws logs filter-log-events \
      --log-group-name /aws/lambda/DatasheetMiner-Prod-Api \
      --start-time $(($(date +%s) - 86400))000 \
      --filter-pattern ERROR \
      --max-items 10

Per stage. Render the message + timestamp; click expands to full event.

## Files touched (MVP)

| File | Change |
|---|---|
| `app/backend/src/routes/godmode.ts` | **new** — three endpoints (`/gemini`, `/ingest`, `/db`) |
| `app/backend/src/services/godmodeQueries.ts` | **new** — ingest_log aggregation + product health sampling |
| `app/backend/src/index.ts` | mount `godmode` router under `/api/admin/godmode` with `adminOnly` |
| `app/frontend/src/components/GodMode.tsx` | **new** — page + 3 panel components, fetches from above |
| `app/frontend/src/components/GodMode.css` | **new** — match `AdminPanel.css` styling |
| `app/frontend/src/App.tsx` | add `/godmode` route gated by admin auth |
| `cli/godmode.py` | **new** — local snapshot generator (Option B) |
| `cli/quickstart.py` | add `godmode` command dispatching to `cli/godmode.py` |
| `specodex/llm.py` | log non-ingest Gemini calls under `LLM#*` PK so they count |
| `specodex/ingest_log.py` | tiny extension — accept the new PK prefix |
| `Quickstart` | one-line passthrough (already a shim) |
| `CLAUDE.md` | add `./Quickstart godmode` to the entry-point list |

## Estimated effort

- Backend MVP (3 endpoints + service): **3 h**
- Frontend MVP (3 panels + page shell): **2 h**
- Local snapshot CLI (git + LOC + Claude transcripts + backlog): **2 h**
- Non-ingest Gemini call logging: **30 min**
- CSS + polish: **1 h**

About a day. Follow-ups (deploy panel, CloudWatch errors, orphan detection,
sparkline charts) are each a clean ~1-2 h add.

## Open questions

1. **Authentication.** The deployed dashboard reuses `adminOnly`. That
   middleware currently checks an `ADMIN_TOKEN` header. Confirm we want
   the same gate for /godmode, or whether it should be its own token (in
   case we ever expose limited godmode views to a teammate).
2. **Cost constants.** Gemini Flash and Claude (Sonnet 4.6 / Opus 4.7)
   pricing both pin in `cli/bench.py:PRICING` (or similar). Confirm we want
   one canonical pricing module both bench and godmode read from — that's
   probably the right factoring regardless of this doc.
3. **DynamoDB scan budget.** Worst case: prod table grows to 50k products
   × `Scan` per refresh = real money + real latency. MVP cap = 1000 rows
   sampled randomly. If that's not acceptable, we precompute a daily
   health snapshot row (`STATS#YYYY-MM-DD`) instead.
4. **Local snapshot output format.** HTML opened in browser, or JSON
   served by a one-shot `python -m http.server` Quickstart subcommand?
   HTML is simpler; JSON is more reusable. Recommend HTML for MVP.
5. **Claude usage scope.** Just this project's transcripts (matches repo
   focus), or all projects (better answer to "how much am I spending on
   Claude")? Easy to add a flag — confirm default.
6. **Refresh cadence.** Manual button, or auto-refresh every 60 s?
   Auto-refresh costs DynamoDB read units even when you're not looking.
   Recommend manual for MVP.

## Triggers

Surface this doc when the current task touches any of:

- "GOD mode", "godmode", "dashboard", "observability", "what's going on"
- `app/backend/src/routes/admin.ts`, `app/backend/src/middleware/adminOnly.ts`,
  `app/frontend/src/components/AdminPanel.tsx`
- `specodex/ingest_log.py` schema changes (the dashboard reads
  these fields — adding/renaming will break panels)
- `specodex/llm.py` (the place to add non-ingest call logging)
- `cli/ingest_report.py` (godmode's ingest panel reuses its grouping)
- "Gemini cost", "token usage", "Claude usage", "how much am I spending"
- `outputs/godmode/`
- `cli/bench.py:PRICING` — single source of truth for $/token; godmode
  reads it
