# Backlog

**This file is the entry point.** Reading this gets you the full picture
of what's left without opening each `todo/*.md`. Drill into the linked
docs only when you're about to act on that work.

> **Recently shipped (2026-04-28 / 2026-04-29).** REBRAND Stage 4 cutover
> ✅ `www.specodex.com` is live, `datasheets.advin.io` NXDOMAIN'd.
> All 5 CICD followups merged (`fromlookup`, `ci-hygiene`,
> `nightly-bench`, `staging-yml-cleanup`, `late-night-dedupe-audit`).
> Frontend visual iteration ✅ (App.css palette, Welcome rework,
> ProductList refinements, FilterChip refactor + tests, sitemap.xml).
> UNITS ✅ (`ValueUnit` / `MinMaxUnit` end-to-end + data backfill).
>
> Historical plans for REBRAND and UNITS were deleted from `todo/` on
> 2026-04-29 — see `git log --diff-filter=D --follow -- todo/REBRAND.md
> todo/UNITS.md` if you need the design rationale.

## How to use it

1. **Starting a session?** Skim **The bottleneck** and **Active work** to know what's hot, what's blocked.
2. **About to touch a file?** Scan **Trigger conditions** at the bottom — if anything matches, the linked doc is queued and worth reading first.
3. **Got an idle dev box overnight?** Pick from **Late Night** — curated tasks safe to run autonomously and easy to verify in the morning.
4. **Deferring new work?** Add a `todo/<AREA>.md` with a `## Triggers` section, then add a row to the table here.

---

## The bottleneck — operator queue

Drained as of 2026-04-30. Only manual action remaining is
`gh secret delete HOSTED_ZONE_ID` (operator-only) — see CICD row below.

---

## Active work

Ordered by **dependency-and-rework risk**, not urgency or size.

| # | Doc | Status | Effort | One-line summary |
|---|-----|--------|--------|------------------|
| 1 | [SEO.md](SEO.md) | 🚧 Phase 0 ✅ shipped 2026-04-28 (robots.txt, static sitemap, OG/Twitter cards, JSON-LD); structural lifts queued | 🟡 medium | Public launch is now possible (`specodex.com` live). Next: SPA crawlability, per-product titles/meta, dynamic sitemap, category/manufacturer/comparison pages, OG image generator. The product *is* the SEO asset; every product row is a long-tail landing page waiting to be rendered. |
| 2 | [MARKETING.md](MARKETING.md) | 📐 planned | 🟡 medium | Engineer-to-engineer distribution — no paid spend, leans on field-manual aesthetic + open-source repo as proof of seriousness. Pairs with SEO (programmatic product pages serve both). |
| 3 | [DEDUPE.md](DEDUPE.md) | 🚧 Phase 1 audit ✅ shipped (`./Quickstart audit-dedupes`); Phase 2+3 pending | 🟡 medium (high blast radius) | Audit script identifies prefix-drift duplicates from `--force` re-ingests pre-family-aware-ID fix. Phase 2 auto-merge + Phase 3 human review queue follow. |
| 4 | [INTEGRATION.md](INTEGRATION.md) | 🚧 phases A+B ✅ shipped 2026-04-26 | 🟢 small | Motion-system builder — drive → motor → gearhead. Next slice: chain-review modal + BOM copy + "looks complete" tray state. UI-only. |
| 5 | [CICD.md](CICD.md) | 🟢 healthy — full chain green; 2 small followups remain | 🟢 small | Test → Deploy Staging → Smoke Staging → Deploy Prod → Smoke Prod all clean. **Remaining followups:** delete dead `HOSTED_ZONE_ID` secret + remove its workflow validation (operator-only); apex `specodex.com` support (only `www` resolves today). `config.ts` apex-domain fallback ✅ shipped 2026-04-30 (`HOSTED_ZONE_NAME` now optional for 2-part domains); codeql.yml SHA pin ✅ shipped 2026-04-30 (v3.35.2, `ce64ddc`). |
| 6 | [FRONTEND_TESTING.md](FRONTEND_TESTING.md) | 🚧 Phase 1 ✅ shipped 2026-04-30 (per-key persistence + caught L6 array-shape bug); Phases 2–8 pending | 🟢 small (half-day, 8 phases) | Lock down "simple but crucial" frontend state — persistence keys, AppContext setters, ProductList type-switch resets, header toggles, FilterChip unit propagation. Catches L1–L12 spillover bestiary. |
| 7 | [GODMODE.md](GODMODE.md) | 📐 planned | 🔴 large | One-page admin dashboard: Gemini + Claude usage, ingest health, DB health, repo activity, deploy state. Local + deployed split. |

Status legend: ✅ done · 🚧 in progress · ⏸ deferred · 🔴 urgent · 📐 planned
Effort legend: 🟢 ≤ 1 day, low risk · 🟡 multi-day, some unknowns · 🔴 multi-week or high blast radius

---

## Suggested chronological order

With UNITS, REBRAND, and CICD all landed, the remaining order:

1. **SEO + MARKETING.** Public launch is now possible. SEO structural lifts pair with marketing distribution; product pages serve both.
2. **DEDUPE Phase 2+3.** Operates on post-UNITS uniform data. Audit script is shipped; auto-merge + human review queue follow.
3. **INTEGRATION next slice.** UI-only, lands on cleaned-up rendering path.
4. **FRONTEND_TESTING.** Tests against canonical post-UNITS shape.
5. **CICD remaining followups.** Small loose ends — `HOSTED_ZONE_ID` cleanup, apex domain support. Each can interleave with anything else.
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
| UNITS review triage | `./Quickstart units-triage outputs/units_migration_review_dev_*.md` (script lives on branch `late-night-units-triage`) | `outputs/units_triage_<stage>_<source-ts>_triaged_<run-ts>.md` — pattern groups + suggested action per group |
| Integration test sweep | `./Quickstart verify --integration` | exit code; stale tests surface as failures |
| DEDUPE Phase 1 audit | `./Quickstart audit-dedupes --stage dev` (script lives on branch `late-night-dedupe-audit` — read-only on dev DB) | `outputs/dedupe_audit_dev_<ts>.json` + `outputs/dedupe_review_dev_<ts>.md` |

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
- INTEGRATION UI changes — visual review required.
- SEO structural lifts (per-product page rendering, dynamic sitemap) — needs build + manual crawl check.

---

## Trigger conditions — when to surface which doc

If your current task matches any "trigger" entry, the linked doc is queued and worth raising before you go further. When multiple match, mention all. Surfacing once is cheap; silently shipping work that conflicts with a deferred plan is expensive.

| Trigger (files / topics in your current task) | Surface |
|---|---|
| `app/frontend/index.html` head metadata, `app/frontend/public/{robots.txt,sitemap.xml}`, JSON-LD blocks, OG/Twitter card tags, per-product page rendering, dynamic sitemap, prerender/SSR, "SEO", "canonical", "search ranking", "OG image" | [SEO.md](SEO.md) |
| Landing-page copy, "marketing", "launch", "audience", "Reddit / HN / mailing list", outreach plans, paid spend (don't), Stripe pricing surface | [MARKETING.md](MARKETING.md) |
| `.github/workflows/`, `tests/unit/test_admin.py`, `cli/quickstart.py`, push to master, deploy attempt, "CI red", `HOSTED_ZONE_ID`, `gh-deploy-datasheetminer`, apex/`www` domain support, `app/infrastructure/lib/config.ts:hostedZoneName` fallback | [CICD.md](CICD.md) |
| `cli/admin.py:purge`/`promote`, `specodex/ids.py:compute_product_id` or `_strip_family_prefix`, new vendor catalog with prefix-form drift; user mentions "duplicate", "dedupe", "merge rows", "same product twice", "two part numbers for one motor"; promotion to staging/prod | [DEDUPE.md](DEDUPE.md) |
| `app/backend/src/routes/admin.ts`, `AdminPanel.tsx`, `specodex/ingest_log.py`, `specodex/llm.py`, `cli/bench.py:PRICING`, "godmode/dashboard/observability/Gemini cost/Claude usage" | [GODMODE.md](GODMODE.md) |
| `specodex/integration/{ports,adapters,compat}.py`, `app/backend/src/services/compat.ts`, `BuildTray.tsx`, `CompatChecker.tsx`; user mentions "compat", "pairing", "BOM", "system", "chain" | [INTEGRATION.md](INTEGRATION.md) |
| `app/frontend/src/utils/localStorage.ts`; `AppContext.tsx` (new persisted key); `ProductList.tsx` type-switch effect; `FilterChip.tsx` × `unitSystem`; `*.test.{ts,tsx}` under `app/frontend/`; user mentions "spillover", "state leak", "stale filter", "wrong unit", "frontend tests", "vitest" | [FRONTEND_TESTING.md](FRONTEND_TESTING.md) |
