# Backlog

**This file is the entry point.** Reading this gets you the full picture
of what's left without opening each `todo/*.md`. Drill into the linked
docs only when you're about to act on that work.

> **Recently shipped (2026-04-28 / 2026-04-30).** REBRAND Stage 4 cutover
> ✅ `www.specodex.com` is live, `datasheets.advin.io` NXDOMAIN'd.
> All 5 CICD followups merged (`fromlookup`, `ci-hygiene`,
> `nightly-bench`, `staging-yml-cleanup`, `late-night-dedupe-audit`),
> plus `config.ts` apex-fallback fix, codeql.yml SHA pin (v3.35.2),
> and `HOSTED_ZONE_ID` secret deleted. CI/CD runbook + foot-gun list
> moved into the `/cicd` skill (`.claude/skills/cicd/SKILL.md`); only
> apex `specodex.com` DNS remains as outstanding follow-up.
> Frontend visual iteration ✅ (App.css palette, Welcome rework,
> ProductList refinements, FilterChip refactor + tests, sitemap.xml).
> UNITS ✅ (`ValueUnit` / `MinMaxUnit` end-to-end + data backfill).
> Mobile-friendly compaction pass ✅ shipped 2026-04-30 — header / filter
> sidebar / product grid / build tray / modal / pagination all trimmed,
> filter sidebar 500 → 380px and no longer orphaned 96px below the header
> (the chief "misalignment"); admin nav hides under 600px so phone
> headers don't clip the display toggles. Verified at 1440 / 1280 / 768
> / 414 / 375 with Playwright. CSS bundle flat (14.84 kB gzip).
> INTEGRATION ✅ — all planned phases shipped: pairwise checker, build
> tray, slot-aware filtering, plus the build-complete affordances (Copy
> BOM, "looks complete" badge, ChainReviewModal). Only the "Save build
> as preset" stretch and the explicit-future Phase D spec-first wizard
> remain. FRONTEND_TESTING ✅ — all 8 phases shipped: per-key
> persistence (caught L6 array bug in `isBuild`), AppContext setter
> contract, ProductList type-switch reset bundle (caught + fixed L1
> stale-modal bug), header toggles, FilterChip × unit system, BuildTray
> + compat junctions, ErrorBoundary, route smoke render. Suite is now
> 23 files / 373 tests.
>
> Historical plans for REBRAND, UNITS, INTEGRATION, and
> FRONTEND_TESTING were deleted from `todo/` after their scope
> shipped — see `git log --diff-filter=D --follow -- todo/REBRAND.md
> todo/UNITS.md todo/INTEGRATION.md todo/FRONTEND_TESTING.md` if you
> need the design rationale. A MOBILE.md plan proposing structural
> changes (bottom drawer, mobile cards) was drafted but never committed;
> the compaction pass above shipped in its place.

## How to use it

1. **Starting a session?** Skim **The bottleneck** and **Active work** to know what's hot, what's blocked.
2. **About to touch a file?** Scan **Trigger conditions** at the bottom — if anything matches, the linked doc is queued and worth reading first.
3. **Got an idle dev box overnight?** Pick from **Late Night** — curated tasks safe to run autonomously and easy to verify in the morning.
4. **Deferring new work?** Add a `todo/<AREA>.md` with a `## Triggers` section, then add a row to the table here.

---

## The bottleneck — operator queue

Drained as of 2026-04-30. No operator-only actions outstanding.

---

## Active work

Ordered by **dependency-and-rework risk**, not urgency or size.

| # | Doc | Status | Effort | One-line summary |
|---|-----|--------|--------|------------------|
| 1 | [SEO.md](SEO.md) | 🚧 Phase 0 ✅ shipped 2026-04-28 (robots.txt, static sitemap, OG/Twitter cards, JSON-LD); structural lifts queued | 🟡 medium | Public launch is now possible (`specodex.com` live). Next: SPA crawlability, per-product titles/meta, dynamic sitemap, category/manufacturer/comparison pages, OG image generator. The product *is* the SEO asset; every product row is a long-tail landing page waiting to be rendered. |
| 2 | [MARKETING.md](MARKETING.md) | 📐 planned | 🟡 medium | Engineer-to-engineer distribution — no paid spend, leans on field-manual aesthetic + open-source repo as proof of seriousness. Pairs with SEO (programmatic product pages serve both). |
| 3 | [DEDUPE.md](DEDUPE.md) | 🚧 Phase 1 audit ✅ shipped (`./Quickstart audit-dedupes`); Phase 2+3 pending | 🟡 medium (high blast radius) | Audit script identifies prefix-drift duplicates from `--force` re-ingests pre-family-aware-ID fix. Phase 2 auto-merge + Phase 3 human review queue follow. |
| 4 | [GODMODE.md](GODMODE.md) | 📐 planned | 🔴 large | One-page admin dashboard: Gemini + Claude usage, ingest health, DB health, repo activity, deploy state. Local + deployed split. |

CI/CD itself is healthy (full chain green; only outstanding bit is apex
`specodex.com` DNS) and now lives behind the `/cicd` skill rather than
a `todo/*.md` plan — invoke the skill or read
`.claude/skills/cicd/SKILL.md` for the runbook + foot-gun list.

Status legend: ✅ done · 🚧 in progress · ⏸ deferred · 🔴 urgent · 📐 planned
Effort legend: 🟢 ≤ 1 day, low risk · 🟡 multi-day, some unknowns · 🔴 multi-week or high blast radius

---

## Suggested chronological order

With UNITS, REBRAND, INTEGRATION, FRONTEND_TESTING, and CICD all
landed, the remaining order:

1. **SEO + MARKETING.** Public launch is now possible. SEO structural lifts pair with marketing distribution; product pages serve both.
2. **DEDUPE Phase 2+3.** Operates on post-UNITS uniform data. Audit script is shipped; auto-merge + human review queue follow.
3. **GODMODE last.** Large surface area; lands on stable substrate so panels don't get retouched.

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
- SEO structural lifts (per-product page rendering, dynamic sitemap) — needs build + manual crawl check.

---

## Trigger conditions — when to surface which doc

If your current task matches any "trigger" entry, the linked doc is queued and worth raising before you go further. When multiple match, mention all. Surfacing once is cheap; silently shipping work that conflicts with a deferred plan is expensive.

| Trigger (files / topics in your current task) | Surface |
|---|---|
| `app/frontend/index.html` head metadata, `app/frontend/public/{robots.txt,sitemap.xml}`, JSON-LD blocks, OG/Twitter card tags, per-product page rendering, dynamic sitemap, prerender/SSR, "SEO", "canonical", "search ranking", "OG image" | [SEO.md](SEO.md) |
| Landing-page copy, "marketing", "launch", "audience", "Reddit / HN / mailing list", outreach plans, paid spend (don't), Stripe pricing surface | [MARKETING.md](MARKETING.md) |
| `.github/workflows/`, `cli/quickstart.py`, push to master, deploy attempt, "CI red", `HOSTED_ZONE_ID`/`HOSTED_ZONE_NAME`/`DOMAIN_NAME`/`CERTIFICATE_ARN`, `gh-deploy-datasheetminer`, OIDC trust policy, apex/`www` domain support, `app/infrastructure/lib/config.ts:hostedZoneName` fallback | `/cicd` skill (`.claude/skills/cicd/SKILL.md`) |
| `cli/admin.py:purge`/`promote`, `specodex/ids.py:compute_product_id` or `_strip_family_prefix`, new vendor catalog with prefix-form drift; user mentions "duplicate", "dedupe", "merge rows", "same product twice", "two part numbers for one motor"; promotion to staging/prod | [DEDUPE.md](DEDUPE.md) |
| `app/backend/src/routes/admin.ts`, `AdminPanel.tsx`, `specodex/ingest_log.py`, `specodex/llm.py`, `cli/bench.py:PRICING`, "godmode/dashboard/observability/Gemini cost/Claude usage" | [GODMODE.md](GODMODE.md) |
