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

1. **Starting a session?** Open the [Specodex Orchestration board](https://github.com/users/JimothyJohn/projects/1) — it's the source of truth for what's active, blocked, or queued. Skim **The bottleneck** here for any operator-only actions.
2. **About to touch a file?** Scan **Trigger conditions** at the bottom — if anything matches, the linked doc is queued and worth reading first.
3. **Got an idle dev box overnight?** Pick from **Late Night** — curated tasks safe to run autonomously and easy to verify in the morning.
4. **Deferring new work?** Add a `todo/<AREA>.md` with a `## Triggers` section, then create a card on the board referencing it. Add a row to **Trigger conditions** below if the doc has file-level triggers.

> **Board access (CLI).** `gh project item-list 1 --owner JimothyJohn --format json`. Requires the `project` scope on the gh token. Full access pattern + field IDs in the auto-memory `reference_orchestration_board.md`.

---

## The bottleneck — operator queue

Drained as of 2026-04-30. No operator-only actions outstanding.

---

## ⚠ Current chaos — what's in the working tree right now

Snapshot 2026-05-02. **Stale within hours; re-run `git status` and
`git worktree list` for ground truth.** This section exists because
multiple agents have been working concurrently and the diff is non-trivial
to read cold.

### Concurrent in-flight streams

| Stream | What it is | Files | State |
|---|---|---|---|
| **Codegen toolchain** | `pydantic2ts` → `generated.ts`, Quickstart cmd, CI drift gate | `scripts/gen_types.py`, `app/frontend/src/types/generated.ts`, `cli/quickstart.py`, `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml`, header comment in `app/frontend/src/types/models.ts` | ✅ committing 2026-05-02. Follow-up = [MODELGEN.md](MODELGEN.md). |
| **Projects feature (Step 3)** | Per-user project collections — list page, delete action, /projects route | `app/backend/src/{db,routes,tests}/projects*`, `app/frontend/src/components/{ProjectsPage,AddToProjectMenu}*`, `app/frontend/src/context/ProjectsContext.tsx`, `app/frontend/src/types/projects.ts`, edits in `App.tsx`/`App.css`/`api/client.ts` | Step 3 locally complete; gated on the `filters.test.ts` `gearhead` decision (see "Cross-stream conflicts" below). |
| **Auth Phase 5 recovery** | Re-apply 5a/5c/5d/5e/5f to master | `todo/PHASE5_RECOVERY.md`, the 5 `specodex-{ses,revoke,csp,audit,alarms}` worktrees, `app/backend/src/{index,middleware/readonly}.ts`, edits in `app/backend/src/types/models.ts` | 🔴 blocking. Plan = one stacked cherry-pick PR. |
| **Stripe Python** | Drop the Rust billing Lambda for ~100 lines of Python | `todo/PYTHON_STRIPE.md` | 📐 drafted, not yet started. Likely lives under PYTHON_BACKEND.md Phase 4 and may merge into that doc. |
| **CLI archive cleanup** | Move one-shot migrations to `scripts/migrations/<date>-<name>.py` | `scripts/migrations/2026-04-26-batch_process.py` (staged), `cli/batch_process.py` deleted, `cli/README.md` modified | Phase 5 of PYTHON_BACKEND.md, mid-execution. |
| **Column / filter UI iteration** | `manufacturer` added to `gearhead` `COLUMN_ORDER`; filter chip refactor | `app/frontend/src/types/{columnOrder,filters,filters.test}.ts`, `app/frontend/src/components/{ColumnHeader,FilterChip,ProductDetailModal,ProductList}.tsx`, `app/frontend/src/App.css` | 🔴 `filters.test.ts` red — see below. |
| **Pipeline edits** | `lead_time` field added to `ProductBase`; quality changes | `specodex/models/product.py`, `specodex/quality.py`, edits in `app/{frontend,backend}/src/types/models.ts` | Likely related to MODELGEN consumers; commit ownership unclear. |
| **`todo/RUST_ONE.md` deletion** | An old Rust-era plan deleted (227 lines) | `todo/RUST_ONE.md` (D) | Looks intentional — leftover from the rust-era refactor that landed at `c076fd0`. Confirm before committing. |
| **STYLE plan + CLAUDE.md rule** | Plan to eliminate native browser/OS chrome (tooltips, confirms, alerts, toasts, validation bubbles, scrollbars, external links). Docs-only, no code yet. | `todo/STYLE.md` (new), `CLAUDE.md` (new "No native browser/OS chrome" subsection), `todo/README.md` (this row + active-work row + trigger row) | ✅ ready to commit 2026-05-02. Docs-only — zero merge friction with any other stream. |

### Cross-stream conflicts

- **`filters.test.ts` red.** Test asserts `COLUMN_ORDER.gearhead === []`
  but `columnOrder.ts` now has `['manufacturer']`. **One-line decision:**
  either revert the `manufacturer` addition, or update `toEqual([])` →
  `toEqual(['manufacturer'])`. Source of the addition isn't clear (not
  the codegen stream; not the Projects stream). Mid-session edit
  attributed by the Projects agent to "the Pydantic→TS work" but
  actually unrelated. **Whoever owns the `manufacturer` column policy
  must answer this.**
- **`app/{frontend,backend}/src/types/models.ts` is touched by three
  streams:** codegen (header comment), pipeline (`lead_time`), Auth/Projects
  (probably). Expect merge friction; keep edits to this file small until
  MODELGEN-0a-ii lands.
- **`scripts/migrations/2026-04-26-batch_process.py` is staged but not
  by the codegen agent.** Whoever owns CLI archive cleanup should commit
  it themselves so blame stays accurate.

### Active worktrees

```
/Users/nick/github/specodex         master                              ← this one
/Users/nick/github/specodex-alarms  feat-auth-phase5f-alarms
/Users/nick/github/specodex-audit   feat-auth-phase5e-audit
/Users/nick/github/specodex-csp     feat-auth-phase5d-csp
/Users/nick/github/specodex-revoke  feat-auth-phase5c-revoke
/Users/nick/github/specodex-ses     feat-auth-phase5a-ses
```

The five Phase 5 worktrees are stranded (their PRs show MERGED on GitHub
but the SHAs aren't on `origin/master`). PHASE5_RECOVERY.md owns the
recovery plan.

### Suggested whittle order

To get back to a clean working tree:

1. **Land the codegen commit (this PR).** Already isolated; no merge friction.
2. **Resolve the `filters.test.ts` `gearhead` question** — owner needed.
3. **Ship Projects Step 3** (it's locally complete, just gated on #2).
4. **Stage + commit the cli/migrations move** (whoever owns Phase 5 cleanup).
5. **Decide on `lead_time` + `quality.py` edits** — review and commit, or revert.
6. **Confirm `RUST_ONE.md` deletion is intentional**, then drop it.
7. **PHASE5_RECOVERY.md** is the heaviest remaining lift; it deserves its own clean tree before starting.

---

## Active work

**Tracked on the [Specodex Orchestration board](https://github.com/users/JimothyJohn/projects/1).** Status, Priority, and Size live there now — this section is no longer the source of truth.

Each card body links back to its `todo/<AREA>.md` doc. To add new work, create a card on the board referencing the doc; if the work has file-level triggers, also add a row to **Trigger conditions** below.

Initial card load (2026-05-02): PHASE5_RECOVERY (P0), MODELGEN, SEO, MARKETING, DEDUPE, GODMODE, PYTHON_BACKEND, STYLE.

CI/CD itself is healthy (full chain green; only outstanding bit is apex
`specodex.com` DNS) and now lives behind the `/cicd` skill rather than
a `todo/*.md` plan — invoke the skill or read
`.claude/skills/cicd/SKILL.md` for the runbook + foot-gun list.

---

## Suggested chronological order

With UNITS, REBRAND, INTEGRATION, FRONTEND_TESTING, and CICD all
landed, the remaining order:

1. **PHASE5_RECOVERY first.** It blocks PYTHON_BACKEND Phase 1 (FastAPI auth would mirror the wrong Cognito surface) and it's the highest-risk of the queue.
2. **MODELGEN consumer rewire + Zod collapse.** Small, isolated, captures the value of the Phase 0 toolchain that's already shipped.
3. **SEO + MARKETING.** Public launch is now possible. SEO structural lifts pair with marketing distribution; product pages serve both.
4. **DEDUPE Phase 2+3.** Operates on post-UNITS uniform data. Audit script is shipped; auto-merge + human review queue follow.
5. **PYTHON_BACKEND Phase 1+** once everything above stops shifting. Don't start the FastAPI parallel-deploy on a moving target.
6. **GODMODE last.** Large surface area; lands on stable substrate so panels don't get retouched.
7. **STYLE** runs alongside in any spare slot. Phases 1 (Tooltip), 5 (scrollbars), 6 (ExternalLink) are pure-additive and can ship anytime — they don't compete with the queue above. Phases 2-4 (ConfirmDialog, Toast, FormField) touch shared state, so single-stream them, but they don't block PYTHON_BACKEND or anything else.

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
| `app/infrastructure/lib/auth/auth-stack.ts`, `frontend-stack.ts`, `app/backend/src/routes/auth.ts` (audit), Cognito SES sender, refresh-token revocation, CSP/HSTS response headers, WAF CloudWatch alarms; `gh pr list` showing PR #3/#5/#6/#7/#8 as merged; the `specodex-{ses,revoke,csp,audit,alarms}` worktrees | [PHASE5_RECOVERY.md](PHASE5_RECOVERY.md) |
| `specodex/models/*.py`, `specodex/models/common.py:ProductType`, `app/frontend/src/types/{models,generated}.ts`, `app/backend/src/routes/search.ts` zod enum, `app/backend/src/config/productTypes.ts`, `scripts/gen_types.py`, `./Quickstart gen-types`, "pydantic2ts", "generated.ts", "drift", "add product type" | [MODELGEN.md](MODELGEN.md) |
| `app/backend/src/` beyond a bug fix, new endpoint, new middleware, "FastAPI", "Mangum", "rewrite Express in Python", `stripe/` (Rust) | [PYTHON_BACKEND.md](PYTHON_BACKEND.md) |
| New JSX with `title=`, `window.confirm`, `alert(`, `<form>` without `noValidate`, bare `target="_blank"`, `<input type="checkbox">` without `appearance: none`, raw `overflow: auto/scroll` in CSS; any user-triggered `console.error` without a paired toast; reaching for `<select>`/`<input type="file">`/`<dialog>`/`<details>` | [STYLE.md](STYLE.md) |
