# Backlog

**This file is the entry point.** Reading this gets you the full picture
without opening each `todo/*.md`. Drill into the linked docs only when
you're about to act on that work.

## How to use it

1. **Starting a session?** Skim **Active and deferred work** and **Suggested chronological order** below to know what's hot, what's blocked, and what's done.
2. **About to touch a file?** Scan **Trigger conditions** at the bottom — if anything matches, the linked doc is queued and worth reading first.
3. **Got an idle dev box overnight?** Pick from **Late Night** — curated tasks safe to run autonomously and easy to verify in the morning.
4. **Deferring new work?** Add a `todo/<AREA>.md` with a `## Triggers` section, then add a row to the table here.

---

## Active and deferred work

Ordered by **dependency-and-rework risk**, not urgency or size — the goal
is to avoid landing work that has to be redone after a downstream refactor
reshapes its substrate.

| # | Doc | Status | Effort | One-line summary |
|---|-----|--------|--------|------------------|
| 1 | [CICD.md](CICD.md) | 🟢 healthy — full chain green 2026-04-29 | 🟢 small | Test → Deploy Staging → Smoke Staging → Deploy Prod → Smoke Prod all clean. Action refresh, integration tests in CI, JUnit XML all shipped. Followup #1 (`fromLookup`) code-ready on branch `cicd-followup-fromlookup` — gated on operator adding `route53:ListHostedZonesByName`/`route53:GetHostedZone` to the deploy role. Remaining followups (nightly bench, `paths-ignore`, security scans, `staging.yml` cleanup) are mine to land. |
| 2 | [REBRAND.md](REBRAND.md) | 🚧 Phase 3a–e ✅ shipped + deployed; Stage 4 (DNS cutover) pending | 🟡 medium | Datasheetminer → Specodex. Stages 1+2 chrome ✅, 3a (Python pkg) ✅, 3b (Node workspaces) ✅, 3c (CDK rename) ✅ deployed 2026-04-28, 3d (GH repo rename) ✅, 3e (docs sweep) ✅. Stage 4 (`specodex.com` DNS cutover + ACM cert + CloudFront alt-domain) waits on zone NS propagation. |
| 3 | [UNITS.md](UNITS.md) | ✅ shipped 2026-04-28 — code `a8f6162` + `aac7050`, data backfill applied to dev (273 rows) + prod (10 rows) | 🟢 done | **Linchpin.** `ValueUnit`/`MinMaxUnit` carry `{value, unit}` end-to-end. `cli/migrate_units_to_dict.py` rescued `~`/`,`/`≤`/`≥` quirks; `±` and `;null`/`;unknown` left in review. Manual triage of ~373 dev + 10 prod review entries pending — pre-existing data quality, non-blocking. |
| 4 | [DEDUPE.md](DEDUPE.md) | ⏸ deferred | 🟡 medium (high blast radius) | One-time cross-vendor sweep for prefix-drift duplicates left by `--force` re-ingests pre-family-aware-ID fix. Audit + safe-merge + human review. **Phase 1 audit is a Late Night candidate** — read-only on DB, output is JSON. |
| 5 | [INTEGRATION.md](INTEGRATION.md) | 🚧 phases A+B shipped 2026-04-26 | 🟢 small | Motion-system builder — drive → motor → gearhead. Next slice: chain-review modal + BOM copy + "looks complete" tray state. UI-only. |
| 6 | [FRONTEND_TESTING.md](FRONTEND_TESTING.md) | 📐 planned | 🟢 small (half-day, 8 phases) | Lock down "simple but crucial" frontend state — persistence keys, AppContext setters, ProductList type-switch resets, header toggles, FilterChip unit propagation. Catches L1–L12 spillover bestiary. |
| 7 | [GODMODE.md](GODMODE.md) | 📐 planned | 🔴 large | One-page admin dashboard: Gemini + Claude usage, ingest health, DB health, repo activity, deploy state. Local + deployed split. |

Status legend: ✅ done · 🚧 in progress · ⏸ deferred · 🔴 urgent · 📐 planned
Effort legend: 🟢 ≤ 1 day, low risk · 🟡 multi-day, some unknowns · 🔴 multi-week or high blast radius

---

## Suggested chronological order

UNITS was the linchpin (Pydantic + DynamoDB + frontend rendering substrate). Now done.
With UNITS landed and CICD green, the remaining order:

1. **CICD followups.** `fromLookup` code-ready on `cicd-followup-fromlookup` (gated on operator adding Route53 read perms to deploy role). Then nightly bench, `paths-ignore`, security scans, `staging.yml` cleanup. Each is a separate small PR.
2. **REBRAND Stage 4.** DNS cutover for `specodex.com` once registrar NS records propagate. Mechanical AWS plumbing — touches no Python/TS code, can interleave with anything else.
3. **DEDUPE.** Operates on post-UNITS uniform data. Phase 1 audit is a Late Night candidate (read-only). Phase 2 auto-merge + Phase 3 human review queue follow.
4. **INTEGRATION next slice.** UI-only, lands on cleaned-up rendering path.
5. **FRONTEND_TESTING.** Tests against canonical post-UNITS shape.
6. **GODMODE last.** Large surface area; lands on stable substrate so panels don't get retouched.

**Out-of-band exceptions.** Urgent bugs, security issues, or user-visible breakage jump the queue.

---

## Late Night

Curated tasks safe to run autonomously overnight on dev. Each one meets four criteria:

- **Bounded** — known finish line (queue size, fixture list, model count)
- **Dev-only writes** — no infrastructure touch, no shared-state mutation, no prod
- **Recoverable** — failure leaves dev DB consistent or rolls back cleanly
- **Morning-checkable** — clear go/no-go signal in artifacts; if green, ship to prod via existing `./Quickstart admin promote` flow

### Tier 1 — read-only or local-only (zero cost)

| Task | Command | Output to check |
|---|---|---|
| Bench (offline) | `./Quickstart bench` | `outputs/benchmarks/<ts>.json` — diff precision/recall vs `latest.json` |
| Ingest-report | `./Quickstart ingest-report --email-template` | `outputs/ingest_report_*.md` — quality fails grouped by manufacturer |
| UNITS review triage | parse `outputs/units_migration_review_dev_*.md`, group by pattern (pre-existing rescue groups: `±`, `;null`, `;unknown`, `IP##;<wrong>`), emit triage list with row counts | `outputs/units_triage_<ts>.md` |
| Integration test sweep | `./Quickstart verify --integration` | exit code; stale tests surface as failures |
| DEDUPE Phase 1 audit | write `cli/audit_dedupes.py` (no DB writes), then run against dev | `outputs/dedupe_audit_<ts>.json` + `outputs/dedupe_review_<ts>.md` |

### Tier 2 — small Gemini cost, dev DB writes only

| Task | Command | Cost | Output to check |
|---|---|---|---|
| Schemagen on stockpiled PDFs | `./Quickstart schemagen <pdf>... --type <name>` | ~$0.10–0.50/PDF | `<type>.py` + `<type>.md` (ADR) per cluster |
| Price-enrich (dev) | `./Quickstart price-enrich --stage dev` | scraping + occasional Gemini | DynamoDB row counts before/after; spot-check 5–10 enriched rows in UI |

### Tier 3 — bounded but expensive (run weekly, not nightly)

| Task | Command | Cost | Output to check |
|---|---|---|---|
| Bench (live) | `./Quickstart bench --live --update-cache` | ~$1–5/run | precision/recall delta + cache delta — catches LLM-pipeline drift offline-bench can't see |
| Process upload queue | `./Quickstart process --stage dev` | unbounded — only run if queue size is known | products created in dev; smoke-check via `/api/v1/search` |

### Morning checklist (before promoting)

1. **Logs.** `tail -100 .logs/*.log` — no unhandled exceptions, no rate-limit spirals.
2. **Bench delta.** `diff outputs/benchmarks/latest.json outputs/benchmarks/<ts>.json` (or `jq` the precision/recall fields). Drop > 5pp on any fixture is a stop signal.
3. **Endpoint shape.** Hit dev `/health`, `/api/products/categories`, `/api/v1/search?type=motor&limit=5`. All should 200 with expected shape per CLAUDE.md "canonical endpoints".
4. **Newly-proposed types.** If schemagen ran: read each `<type>.md` ADR. Reject anything that hardcodes one vendor's quirks.
5. **DB sample.** UI walkthrough on http://localhost:5173: pick the new type, confirm filter chips + table columns render. Spot-check 5–10 newly-written / enriched rows.
6. **If green:** `./Quickstart admin promote --stage staging --since <ts>`, smoke staging, then `--stage prod`.
7. **If red or surprising:** damage is dev-only. `./Quickstart admin purge --stage dev --since <ts>` rolls back, then triage.

### Not Late Night material

- Anything touching `app/infrastructure/` (CDK) or `.github/workflows/` — needs human review.
- Any prod write or `./Quickstart admin promote --stage prod` — gated on morning checklist.
- REBRAND Stage 4 DNS cutover — needs zone NS propagation + manual smoke.
- INTEGRATION UI changes — visual review required.

---

## Trigger conditions — when to surface which doc

If your current task matches any "trigger" entry, the linked doc is queued and worth raising before you go further. When multiple match, mention all. Surfacing once is cheap; silently shipping work that conflicts with a deferred plan is expensive.

| Trigger (files / topics in your current task) | Surface |
|---|---|
| `.github/workflows/`, `tests/unit/test_admin.py`, `cli/quickstart.py`, push to master, deploy attempt, "CI red", `HOSTED_ZONE_ID`, `gh-deploy-datasheetminer` | [CICD.md](CICD.md) |
| `cli/admin.py:purge`/`promote`, `specodex/ids.py:compute_product_id` or `_strip_family_prefix`, new vendor catalog with prefix-form drift; user mentions "duplicate", "dedupe", "merge rows", "same product twice", "two part numbers for one motor"; promotion to staging/prod | [DEDUPE.md](DEDUPE.md) |
| `app/backend/src/routes/admin.ts`, `AdminPanel.tsx`, `specodex/ingest_log.py`, `specodex/llm.py`, `cli/bench.py:PRICING`, "godmode/dashboard/observability/Gemini cost/Claude usage" | [GODMODE.md](GODMODE.md) |
| `specodex/integration/{ports,adapters,compat}.py`, `app/backend/src/services/compat.ts`, `BuildTray.tsx`, `CompatChecker.tsx`; user mentions "compat", "pairing", "BOM", "system", "chain" | [INTEGRATION.md](INTEGRATION.md) |
| `app/frontend/src/` styling/theme/palette/fonts; landing or `App.tsx` routes; "datasheetminer" in user-facing copy; ACM cert / Route 53 / CloudFront alt-domain for `specodex.com`; CDK Frontend stack viewer cert; repo rename | [REBRAND.md](REBRAND.md) |
| `app/frontend/src/utils/localStorage.ts`; `AppContext.tsx` (new persisted key); `ProductList.tsx` type-switch effect; `FilterChip.tsx` × `unitSystem`; `*.test.{ts,tsx}` under `app/frontend/`; user mentions "spillover", "state leak", "stale filter", "wrong unit", "frontend tests", "vitest" | [FRONTEND_TESTING.md](FRONTEND_TESTING.md) |
| `specodex/models/common.py` (`ValueUnit`/`MinMaxUnit`), product model field annotations; `specodex/units.py`; `specodex/db/dynamo.py`; `app/backend/src/db/dynamodb.ts`; `specodex/models/llm_schema.py:to_gemini_schema`; `specodex/schemagen/renderer.py`; user mentions "semicolon in UI", "value;unit", "rotor inertia displayed wrong", "compact string", "scientific notation in specs" | [UNITS.md](UNITS.md) |
