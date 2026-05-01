# Specodex — what's next

A reading of `todo/*.md` as of 2026-04-29. Ordered to match the
chronological dependency chain in `todo/README.md`, not by urgency or
size. The goal is to avoid landing work that has to be redone after a
downstream refactor reshapes its substrate.

---

## Direction summary

The next ~6 months of the project, distilled:

- **Public launch.** `specodex.com` DNS cutover, then SEO foundation,
  then engineer-to-engineer marketing distribution. The product is
  ready; the URL and the indexability aren't.
- **Toolchain consolidation.** Python + TypeScript + small Rust crate
  → mono-Rust. Phases 0/1/3/5 of the port are already on the `rust`
  branch; cutover via CloudFront origin swap is the next physical
  step.
- **Data substrate cleanup.** UNITS shipped (the linchpin). DEDUPE is
  the post-UNITS sweep. After that, the catalog is clean enough to
  build features on top of without churn.
- **Builder-mode UX.** Motion-system builder phases A+B already ship.
  The rest is end-of-chain affordances (review modal, BOM copy,
  "looks complete" badge) plus a future spec-first sizing wizard
  (Phase D, separate decision).
- **Observability.** GODMODE dashboard collapses Gemini cost, ingest
  health, DB health, deploy state, repo activity, and Claude usage
  onto one page. Lands last so it doesn't have to be retouched as the
  substrate underneath changes.

---

## Active queue (chronological, dependency-ordered)

Status legend: ✅ done · 🚧 in progress · ⏸ deferred · 🔴 urgent · 📐 planned

| # | Doc | Status | Effort | One-line |
|---|---|---|---|---|
| 1 | [CICD](todo/CICD.md) | 🟢 healthy — full chain green 2026-04-29 | 🟢 small | ✅ shipped today: `fromLookup` (#1), nightly bench (#4), ci-hygiene 5a, staging.yml refresh (#7). Remaining: action version refresh (#2), integration tests in CI (#3), security scans. |
| 2 | [REBRAND](todo/REBRAND.md) | 🚧 Stage 4 DNS cutover pending | 🟡 medium | `specodex.com` ACM cert + CloudFront alt-domain + Route 53 records + 301 redirect. Waits on registrar NS propagation. |
| 3 | [UNITS](todo/UNITS.md) | ✅ shipped 2026-04-28 | 🟢 done | ~373 dev + 10 prod review entries pending manual triage (`±`, `;null`, `;unknown`). |
| 4 | [DEDUPE](todo/DEDUPE.md) | 🚧 Phase 1 script shipped 2026-04-29 | 🟡 medium | One-time sweep for prefix-drift duplicates from pre-family-aware-ID `--force` re-ingests. `cli/audit_dedupes.py` exists; running against dev is the next Late Night step. |
| 5 | [INTEGRATION](todo/INTEGRATION.md) | 🚧 phases A+B shipped | 🟢 small | Next slice: chain-review modal + BOM copy + "looks complete" tray state. UI-only, half-day. |
| 6 | [FRONTEND_TESTING](todo/FRONTEND_TESTING.md) | 📐 planned | 🟢 small | Lock down spillover bestiary (L1–L12) — persistence keys, AppContext setters, ProductList type-switch resets. 8 phases, half-day total. |
| 7 | [GODMODE](todo/GODMODE.md) | 📐 planned | 🔴 large | One-page admin dashboard: Gemini + Claude usage, ingest health, DB health, deploy state, backlog state. ~1 day for MVP. |
| 8 | [RUST](todo/RUST.md) | 🚧 Phase 0+1+3+5 shipped on `rust` branch | 🔴 multi-week | Full Python+TS → Rust port. Cutover via CloudFront origin swap; Phase 4 (frontend → Leptos) explicitly deferred. |
| 9 | [SEO](todo/SEO.md) | 🚧 Phase 0 metadata shipped 2026-04-28 | 🟡 medium | Phase 1 = SPA crawlability via build-time prerender, dynamic per-product sitemap, per-product Product JSON-LD, Lighthouse CI gate. |
| 10 | [MARKETING](todo/MARKETING.md) | 📐 planned | 🟡 medium | Show HN, r/PLC, awesome-* PRs, blog posts, trade press. Gated on REBRAND Stage 4 + SEO Phase 1. |

---

## 1. CICD — autonomous followups

The chain has been green end-to-end since 2026-04-29. Operator queue
is empty.

**Shipped 2026-04-29:** items 1, 4, the deploy-artifact + `/health`
slice of 5, plus a new item 7 (`staging.yml` repurpose). Remaining
work: actions version refresh (2), integration tests in CI (3), the
rest of CI hygiene (5), security scans.

1. ✅ **Eliminate `HOSTED_ZONE_ID` as a secret.** `frontend-stack.ts`
   now uses `HostedZone.fromLookup({ domainName })`; `cdk.context.json`
   is a committed artifact and the workflow no longer exports
   `HOSTED_ZONE_ID`.
2. **Refresh GitHub Actions versions.** Bump `actions/checkout`,
   `setup-node`, `astral-sh/setup-uv` (SHA-pinned). Resolves the Node
   20 deprecation warning emitting on every run.
3. **Wire `tests/integration/` into CI.** Eight files exist
   (`test_pipeline.py`, `test_db_integration.py`,
   `test_intake_guards_end_to_end.py`, `test_scraper_degraded_inputs.py`,
   etc.) and **none** run in CI. New integration tests rot silently.
   Add a `test-integration` job: `pytest tests/integration/ -m "not live"`
   with moto-mocked AWS. Gate `live`-marked tests behind a nightly
   trigger. Also: include `tests/test_cli.py` in the unit pass.
4. ✅ **Nightly `./Quickstart bench` workflow.** Live in
   `.github/workflows/bench.yml` with `cli/bench_compare.py` as the
   regression gate. Currently weekly (per-run cost ~$1-5); promote to
   nightly if the first month surfaces drift.
5. **CI hygiene.** ✅ Shipped: `cdk.out/` upload on deploy failure +
   unified `/health` poll between CI and `Quickstart smoke`.
   Remaining: JUnit XML + step summary, `paths-ignore` for doc-only
   changes, `cdk diff` PR comment.
6. **Security scans (warn-only first):** `pip-audit`, `npm audit
   --omit=dev`, CodeQL.
7. ✅ **`staging.yml` refresh.** Repurposed (not deleted) so the file
   serves a defined role under the new chain.

---

## 2. REBRAND Stage 4 — DNS cutover for `specodex.com`

Stages 1, 2, 3a–e all shipped. Stage 4 is mechanical AWS plumbing
that touches no Python/TS code, gated on registrar NS propagation:

- **4a. ACM cert** for `specodex.com` + `www.specodex.com`, DNS-validated
  in `us-east-1` (CloudFront requirement).
- **4b. CloudFront alt-domain.** Extend the prod `Distribution.domainNames`
  with both new aliases. Keep `datasheets.advin.io` active during the
  redirect window. CloudFront propagation is 15-30 min; cdk deploy
  returns before that completes.
- **4c. Route 53 A + AAAA records** for apex + www, ALIAS to the
  distribution.
- **4d. 301 redirect** via a CloudFront `viewer-request` function on
  the existing distribution. `datasheets.advin.io` → equivalent path on
  `specodex.com`. **Trigger only after 7+ days of `specodex.com`
  serving without issue.**
- **4e. Decommission** `datasheets.advin.io` 6 months after 4d ships
  (review at month 5).

**Pre-flight:** `dig NS specodex.com +short` from a non-AWS resolver
must return Route 53 NS records before 4a can validate.

**SEO ripple:** the canonical URL flips from `https://datasheets.advin.io/`
to `https://specodex.com/`. Affects `index.html` (canonical, og:url,
JSON-LD `url`/`@id`/`urlTemplate`), `public/robots.txt` sitemap line,
every `<loc>` in `public/sitemap.xml`. Treat as part of 4c.

---

## 3. UNITS — manual triage of legacy review entries

Code shipped. Data backfill applied to dev (273 rows fixed) and prod
(10 rows fixed). What remains is **human triage of the deliberately
deferred patterns** in `outputs/units_migration_review_<stage>_*.md`:

- **`±X;unit`** — semantically ambiguous. `pose_repeatability: ±0.02 mm`
  is one number (scalar tolerance); `working_range: ±360°` is -360..+360
  (bilateral range). The migration script can't tell field types at
  the dict-walk layer. Auto-fixing either way is wrong half the time.
- **`;null` / `;unknown`** — bad LLM emissions, not encoding artefacts.
  Rescuing them silently corrupts the catalog.

~373 dev rows + 10 prod rows. Pre-existing data quality, non-blocking.

---

## 4. DEDUPE — cross-vendor historical-duplicate cleanup

The `compute_product_id` family-aware fix (2026-04-26) prevents
**future** prefix-drift duplicates. It does **not** retroactively merge
existing rows. The Parker MPP cleanup surfaced 22 such groups in one
family; the same drift can hide in any catalog where the LLM sometimes
drops the marketing prefix or where `--force` re-ingests pre-fix
stamped fresh UUIDs.

Three phases:

- **Phase 1 — audit (read-only, Late Night-eligible).** ✅ Script
  shipped 2026-04-29. `cli/audit_dedupes.py` scans every product-type
  partition in dev DynamoDB; groups by family-aware normalized core;
  emits JSON of every group with ≥2 rows + side-by-side diff classified
  as `identical` / `complementary` / `conflicting`. No DB writes.
  Output: `outputs/dedupe_audit_<ts>.json` +
  `outputs/dedupe_review_<ts>.md`. **Next step:** run it against dev
  overnight.
- **Phase 2 — auto-merge safe cases.** `--apply --safe-only` writes
  the merged row under the canonical (family-aware) UUID, deletes
  orphans. Most-populated part-number form wins (e.g. `MPP-1152C` over
  `1152C`). `pages` becomes a union; `datasheet_url` keeps the
  most-populated row's URL.
- **Phase 3 — human review queue.** `outputs/dedupe_review_<ts>.md`
  has one section per `conflicting` group with a 3-column field table
  + direct PDF links. Reviewer fills in picks; `--apply --from-review`
  merges with the chosen values.

**Edge cases to respect:** `MPP` vs `MPJ` are different motors despite
sharing a normalized core — only strip when the *exact* `product_family`
token is the prefix, never a sibling family. Datasheet URL drift is
normal; group on `(manufacturer, normalized_part)` and ignore the URL.

**Estimated:** half a day code, ~1 hour human review on dev.
Promote-the-cleaned-set to staging/prod via existing `./Quickstart
admin promote` flow once approved. No prod writes from this CLI ever.

---

## 5. INTEGRATION — next slice (end-of-chain affordances)

Phases A (pairwise checker) and B (build tray + slot-aware filter)
shipped. The remaining slice is purely UI on top of the existing
engine:

1. **Whole-chain audit modal** — when the tray has ≥2 filled adjacent
   slots, a "Review chain" button opens a modal stacking every
   junction's `CompatibilityReport` (drive↔motor and motor↔gearhead).
   Reuses `CompatChecker`'s rendering primitives; calls
   `apiClient.checkCompat` once per adjacent pair.
2. **BOM copy.** "Copy BOM" button emits one block to clipboard:
   ```
   Drive:    Bardac — P2-74250-3HF4N-T
   Motor:    ABB — E2BA315SMB6
   Gearhead: <part>
   ```
   Plus a one-line junction summary per pair. Plain text first; CSV
   later if anyone asks. Pure clipboard-write from `useApp().build`.
3. **"Looks complete" badge.** When all three rotary slots are filled
   and every junction rolls up to `ok`, swap the tray's accent border
   to green and show a small ✓ marker. Pure visual.
4. **(Stretch) Save build as preset.** Named entries in localStorage,
   restore via dropdown next to Clear. Skip until someone asks.

**Files:** new `ChainReviewModal.tsx`; edits to `BuildTray.tsx` and
`App.css`. **No backend touch.** ~half-day, mostly CSS + clipboard.

**Phase D (spec-first wizard)** is named explicitly so the architecture
doesn't preclude it. User states load mass / stroke / duty cycle /
target speed; system proposes ranked candidate chains end-to-end.
Requires a sizing engine (RMS torque, gear-ratio sweep) +
application templates + probably ML re-ranking. Not in scope; not
near-term.

**Open questions worth recording:**
- Bidirectional voltage on drive↔motor: `_drive_ports` declares
  `motor_output.voltage = d.input_voltage` (drive reproduces input on
  output via PWM). False for some 24 VDC → 48 VDC bus-boost drives.
  Acceptable approximation; revisit on a false-pass report.
- `partial` vs `fail` policy in slot-aware filtering: strict mode
  hides too much when datasheets are incomplete; permissive is the
  right default but should be a user toggle.
- Where does `Contactor` sit in the chain? Has a `load_output` that
  fits a motor's `power_input` — could optionally precede the drive
  (line contactor) or replace it (across-the-line motor start).
  Doesn't fit the four-slot model. Park as optional fifth slot or
  hide.

---

## 6. FRONTEND_TESTING — close the spillover gaps

The frontend has 14 test files (~260 passing). What it doesn't cover
is the class of bug that has bitten this app most often: **state
spilling across product-type switches, persisted state surviving a
schema change in a broken shape, toggles that look like they work
but don't propagate**.

**Pre-req — fix 2 currently failing tests** in
`AttributeSelector.test.tsx`. Likely stale assertions against
pre-rebrand copy or pre-categorised attribute layout. CI red noise
hides anything new this plan introduces; fix first.

**The bestiary** (each test below maps to one of these):

| # | Failure mode |
|---|---|
| L1 | Selected product modal stays open after switching product type |
| L2 | Filter chips from `motor` carry into `drive` view |
| L3 | Sort state survives type switch and produces nonsense column refs |
| L4 | Pagination `currentPage=7` survives a type switch with only 2 pages |
| L5 | `productListHiddenColumns` from `motor` hides nonexistent columns on `drive` |
| L6 | `specodex.build` written by older schema crashes context init on next visit |
| L7 | `unitSystem='imperial'` doesn't propagate to a chip's slider min/max |
| L8 | `rowDensity='comfy'` written but `ProductList` reads from a stale prop |
| L9 | Build tray slot replacement leaves the old product visible for a frame |
| L10 | `compatibleOnly=true` on initial load filters to zero rows when build is empty |
| L11 | Theme toggle writes localStorage but DOM `data-theme` stays light next load |
| L12 | `safeLoad` accepts `{}` for a value typed as `string[]` (validator too loose) |

**Eight phases, each independently shippable, ~half-day total:**

1. **Persistence keys** (`localStorage.persistence.test.ts`) —
   table-driven, 4 cases per persisted key (default-when-absent,
   default-when-malformed, default-when-wrong-shape, valid-roundtrip).
   ~1 h. Cheapest, highest value.
2. **AppContext as a black box** — render `<AppProvider>` with a test
   consumer; exercise `setUnitSystem`, `setRowDensity`, `addToBuild`
   slot replacement, `clearBuild`, `setCompatibleOnly`, stale build
   shape recovery. ~2 h.
3. **ProductList type-switch reset** — *the single most important
   file in this plan.* L1–L4 live here. Mock `useApp()` to control
   `currentProductType`, render, assert `selectedProduct`/`filters`/
   `sorts` clear and `currentPage` resets to 1. ~2 h.
4. **Header toggles** — `UnitToggle`, `DensityToggle`, `GitHubLink`. ~1 h.
5. **FilterChip × unitSystem** — extend existing test file. L7. ~1 h.
6. **BuildTray** — hidden when empty, slot order, remove buttons,
   junction badges, Clear. ~1 h.
7. **ErrorBoundary** — child throws → fallback UI; healthy child → no
   fallback. 3 cases, ~30 lines.
8. **Smoke-render every page** — `<App />` in `MemoryRouter` for each
   route with `apiClient` mocked. Catches "I broke the imports"
   before CI does.

**Out of scope:** Playwright/visual-regression (separate effort, see
`webapp-testing` skill); backend route tests (owned by
`app/backend/`); coverage threshold enforcement.

---

## 7. GODMODE — one-page admin dashboard

Single URL — `/godmode` in the React app, gated by `adminOnly` — that
answers "what the hell is going on with this project right now?"
without context-switching across AWS Console, GitHub, CloudWatch,
terminal, and three Quickstart commands.

**Six panels:**

1. **AI usage** — Gemini token spend / RPM / error rate (from
   ingest_log); Claude Code token spend (from local
   `~/.claude/projects/*/conversations/*.jsonl`). Cost in dollars.
2. **Pipeline health** — recent ingest attempts, success vs
   quality_fail vs extract_fail, top failing manufacturers, p50/p95
   wall-clock per attempt.
3. **Database health** — products by type, products written last 24h,
   "unhealthy" rows (quality-floor breach, missing prices, stale
   `createdAt`, orphan `INGEST#` records).
4. **Repo activity** — commits last 7/30 d, LOC by language, churn
   (lines added/removed), test pass rate from last `./Quickstart test`.
5. **Deploy state** — current stack version per stage, `/health`
   response, last 10 CloudWatch errors.
6. **Backlog state** — `todo/*.md` count by status, urgency surfaced.

**Architecture: A + B, split by data locality.** Deployed (Option A,
React + Express endpoints) covers cloud data: Gemini usage, ingest
pipeline, DynamoDB health, deploy state, CloudWatch errors. Local
(Option B, `./Quickstart godmode` writes
`outputs/godmode/latest.html`) covers Claude transcripts, git, LOC,
last test run, backlog state — things a Lambda can't see. Both
render with the same panel CSS so they feel like one tool.

**MVP slice (~1 day):**

- 3 deployed endpoints under `/api/admin/godmode/*` + 3 React panels.
- 1 local CLI for git/LOC/Claude/backlog.
- Tiny extension to `specodex/llm.py` to log non-ingest Gemini calls
  (schemagen, price-LLM) under an `LLM#<kind>#<sha>` PK so the
  dashboard counts every call.

**Non-goals:** no new metrics infrastructure (no CloudWatch custom
metrics, no Prometheus, no Datadog); no real-time push (refresh
button); no historical timeseries store; no ML/anomaly detection; no
Claude org admin API integration (read local transcripts only); no
mobile responsiveness.

**Open questions:**
- Auth — reuse `adminOnly` `ADMIN_TOKEN`, or a separate godmode
  token in case of limited shares to teammates?
- Cost constants — single canonical `cli/bench.py:PRICING` module
  read by both bench and godmode? Probably yes.
- DynamoDB scan budget — MVP caps at 1000 rows sampled. If prod
  grows past 50k, precompute a daily `STATS#YYYY-MM-DD` row.
- Claude usage scope — current project only, or all projects with a
  `--all-projects` flag?
- Refresh cadence — manual button (recommended) vs auto-refresh.

---

## 8. RUST — pure-Rust port (the multi-week one)

The repo runs Python (~23.4k LOC), TypeScript (~13k LOC), and a small
Rust crate (Stripe). That's the maximally awkward shape. Going Rust
collapses three toolchains into one and aligns with the "one language
per project" preference in global CLAUDE.md.

**Already shipped on the `rust` branch (2026-04-28):**

- **Phase 0 — risk-burn spikes** (both green). Gemini structured-output
  spike: 84 motor variants from omron-g-series-servo-motors.pdf in
  12.5s, deserialized cleanly. PDF parity spike: 7/7 benchmark fixtures
  match Python exactly, including the j5.pdf 616-page monster (83 spec
  pages each side) and the Mitsubishi 410-page catalog (77 each side).
  **Caveat:** the spike used Poppler shell-out for text extraction.
  Production engine choice (`pdfium-render` vs `mupdf-rs`) is a
  separable Phase 1 decision.
- **Phase 1 — `specodex-core` + `specodex-db`.** All seven product
  models, units, quality scoring, blacklist, admin ops
  (diff/promote/demote). 170/170 tests pass. Live smoke against dev:
  1242 motors round-trip in 1.20s, 2106 rows across all types in 1.70s.
- **Phase 3 — `specodex-api`** (Axum). Drop-in compatible with the
  Express service for every route the frontend calls. Same response
  envelope, same spec-filter language, same summary projection. 28
  contract tests cover validation. `readonly_guard` and `admin_only`
  middleware via `route_layer` so unmatched paths still 404.
- **Phase 5 IaC** — `rust/infra/` standalone SAM template. Lambda
  (`provided.al2023`, arm64) + HTTP API + CORS, validates with `sam
  validate --lint`.

**Unblocked next step:** install `cargo-lambda`, run `sam build && sam
deploy --config-env default`, smoke against staging, A/B in CloudFront,
prod cutover. Express stack stays put until Rust API has baked.

**Deferred Phase 3 routes** (Express keeps these until they land):

- `/api/upload` — S3 presigned URL flow.
- `/api/v1/compat/check` — pairwise compat (needs the full compat
  engine port from `specodex/integration/`).
- `/api/subscription` — Stripe billing surface (already a Rust crate
  at `stripe/`, separate stack).
- `/api/docs` — OpenAPI spec (mechanical).

**Phase 1 polish items:**

- Family-filtering wrappers (Python `Voltage`/`Torque`/etc. that drop
  wrong-family units to `None`). Currently fields use plain
  `Option<ValueUnit>` / `Option<MinMaxUnit>` — wrong-family units
  keep their unit as-is rather than zeroing the field.
- Schema generation (`to_gemini_schema` Rust equivalent via `schemars`
  + Gemini adapter).
- `purge` admin operation — skeleton in `admin.rs`, not wired (needs
  paginated key-only delete).
- `testcontainers-rs` LocalStack integration for CI without live AWS
  creds.
- Forgiving `IpRating` coercion (Motor's `ip_rating` is currently
  plain `Option<i32>`; Python accepts `"IP54"`, `"54"`, `{"value": 54}`).

**Phase 4 — frontend → Leptos/WASM: explicitly deferred.** ~12.7k LOC
of plain React → ~12.7k LOC of Leptos = a multi-week rewrite for
**zero user-visible benefit**. WASM bundle is *bigger* than the
current Vite build for a UI this size. Recommendation in the doc is
to keep React indefinitely. Phase 4 should require a separate
decision once everything else has landed.

**Phases left after cutover (Phase 6 — cleanup):** delete
`pyproject.toml`, `uv.lock`, `.python-version`, all `package.json` /
lockfiles, `cdk.json`, `tsconfig.json`s, Vite config. Update
root CLAUDE.md to describe the Rust project shape. Single `cargo`
job replaces three CI stages. `./Quickstart verify` runs in <5 min.

**Honest tradeoffs called out in the doc:** no official Gemini Rust
SDK (hand-rolled HTTP client, pin to API version); no Pydantic
equivalent (~30% more boilerplate per model); PDF parsing fidelity
(`pdfium-render` adds a binary dep; bundle in Lambda layer); Playwright
in pricing enrichment (defer — keep as Python sidecar); test ecosystem
gap (LocalStack via `testcontainers-rs` instead of `moto`); CLI
ergonomics regress slightly (`clap` derive + `cargo-watch` mitigate).

---

## 9. SEO — make Specodex the answer when an engineer searches a part number

**Phase 0 (metadata foundation) shipped 2026-04-28:** `robots.txt`,
static homepage `sitemap.xml`, OG/Twitter cards, JSON-LD `WebSite` +
`Organization`, canonical URL, refined `<title>`/`<meta>`.

**Open follow-ups from Phase 0:**
- Generate `og-default.png` (1200×630). Until then link unfurls fall
  back to text.
- Flip canonical URL from `https://datasheets.advin.io/` to
  `https://specodex.com/` when REBRAND Phase 4c lands. Affects
  `index.html` (3 places), `public/robots.txt` (sitemap line),
  `public/sitemap.xml` (every `<loc>`).

**Phase 1 — technical foundation (must ship before any marketing push):**

- **1a. SPA crawlability.** Pick build-time prerender via
  `vite-plugin-prerender`. At `vite build`, hit `/api/products`,
  generate one static `.html` per product with the right `<title>`,
  `<meta>`, JSON-LD baked in, write to S3 with the SPA shell as
  fallback for unknown routes. Ship behind a `--prerender` flag in
  `./Quickstart deploy` first; default once green for a week on
  staging. Cost: build time grows with product count; mitigate via
  incremental rebuild.
- **1b. Dynamic per-product sitemap.** New `cli/sitemap.py` scans
  DynamoDB, emits one `<url>` per product at `/products/{type}/{slug}`
  + static routes. `<lastmod>` from `updated_at`. Switch to
  `sitemap-index.xml` past 50k URLs. Wire into `./Quickstart deploy`.
- **1d. Per-product `<title>`, `<meta>`, JSON-LD `Product`.**
  - Title: `{Manufacturer} {Part Number} — {Type} {one key spec} | Specodex`
    (60-char target, 70 hard cap; truncate spec, never the part number).
  - Meta description: `{Type} from {Manufacturer}, part {Part Number}.
    {2-3 key specs}. View full spec table, datasheet, and cross-vendor
    alternatives on Specodex.` (155-char target).
  - JSON-LD `schema.org/Product` with `additionalProperty[]` mapped
    from `ValueUnit`/`MinMaxUnit` shapes. **Use UN/CEFACT unit codes**
    (`KWT`, `MTR`, `HUR`, `NEW`) where they exist; fall back to
    custom `unitText`. Schema.org `unitCode` expects UN/CEFACT, not
    SI strings — this is the most common mistake.
- **1e. Canonical URLs.** Every product → exactly one canonical
  `/products/{type}/{slug}` where `slug = {manufacturer}-{part_number}`
  lowercased + hyphenated. Self-canonical on the canonical URL;
  `<link rel="canonical">` on aliases.
- **1f. Lighthouse CI in `verify`.** Gate at LCP < 2.5s, INP < 200ms,
  CLS < 0.1, SEO score > 95. Risk: JSON-LD payload bloat on product
  pages with hundreds of fields — measure before tuning.

**Phase 2 — content scaffolding (concurrent with Phase 1):**

- **2a. Category index pages** (`/products/motor`, etc.) — H1, filter
  snapshot, links to sub-categories + top 10 manufacturers. Highest-
  traffic SEO pages on this kind of site.
- **2b. Manufacturer index pages** (`/manufacturer/{slug}`) — vendor's
  products grouped by type, one-paragraph auto-generated intro,
  marked up with `Organization` schema.
- **2c. Comparison pages — programmatic.**
  `/compare/{type}/{mfr-a}-vs-{mfr-b}`. Cap to top vendor pairs per
  type (only generate if both have ≥ 5 products of that type) — Google
  penalizes thin content.
- **2d. Engineering blog at `docs/blog/`** (Jekyll, GitHub Pages
  already serves `docs/`). Three foundational posts:
  - Page-finder benchmark write-up (technical, links repo).
  - Cross-vendor servo motor benchmark (pure data, ranks 5-10 vendors).
  - Building a 3-axis motion stage (application walkthrough).
  Cross-link from blog into catalog and footer back into blog. The
  link graph is the second-biggest SEO lever after prerendering.
- **2e. OG image generator.** `cli/og-image.py` renders 1200×630 PNG
  per product at build time. Field-manual aesthetic — paper, OD-green
  header bar, part number in condensed sans, key specs in tabular
  monospace. Without these, Slack/LinkedIn previews look broken,
  undermining engineer-to-engineer sharing.

**Phase 3 — keyword strategy (layered by intent):**

- **Tier 1 — exact part numbers** (`{mfr} {part}`, `{part} datasheet`,
  `{part} specs`). Massive aggregate volume; prerendered product page
  with structured data wins on UX once indexed.
- **Tier 2 — manufacturer + family** (`mitsubishi mr-j5`, `yaskawa
  sigma-7`, `abb acs880`). Manufacturer + category index pages.
- **Tier 3 — spec-driven category searches** (`2kw servo motor 200v`,
  `gearhead ratio 100:1 backlash`). Filtered category pages where
  every filter combination is a canonical URL. **Cap to 200-500
  pre-curated filter pages chosen by search-volume data** — uncapped
  generates millions of thin URLs.
- **Tier 4 — broad informational** (`what is a servo drive`). Blog
  content; embedded interactive search.
- **Don't pursue:** generic head terms (Wikipedia outranks); brand
  keywords for distributors (trademark issues); geo-targeted variants
  (Specodex isn't a distributor).

**Phase 4 — backlinks.** Don't buy, earn. `awesome-*` PRs (slow-burn
but each merge ≈ 50-200 referrals/month forever); HN front page;
Eng-Tips/ControlBooth/r/PLC referral traffic; trade press placements;
occasional Wikipedia external-links sections.

**Phase 5 — measurement.** Google Search Console + Bing Webmaster
verified on `specodex.com`. **Plausible over GA4** to fit the
field-manual / no-marketing-fluff vibe (and so we can advertise "we
don't track you"). Lighthouse CI artifacts. Search Console weekly
export feeds the GODMODE panel.

**Risks specific to SEO:**
- Prerender + DynamoDB schema drift — every prerendered page becomes
  stale on a backfill. Solve: rebuild prerender as a deploy-time
  step that always pulls latest, never a checked-in artifact.
- Thin/duplicate content from over-generation. Cap aggressively.
- JSON-LD that doesn't validate — silently demotes the page. Use
  Google's Rich Results Test on 10 sample pages before shipping.
- Crawler budget. Past ~100k products, Googlebot may not crawl all.
  Solve via tight sitemap + good internal linking + `<priority>` hints.
- `noindex` on staging leaking to prod = entire site disappears from
  Google. Add an explicit assertion in `./Quickstart smoke` that prod
  HTML has no `X-Robots-Tag: noindex` and no
  `<meta name="robots" content="noindex">`.

---

## 10. MARKETING — engineer-to-engineer distribution

No paid spend, no ads, no agency. Engineer-to-engineer distribution,
leaning on the niche-signal of the field-manual aesthetic and the
open-source repo as proof of seriousness.

**The audience, sharply:** mechatronics design engineers, system
integrators / OEMs, robotics startup engineers, sourcing engineers,
university capstone teams, consulting firms. Unifying trait: *they
all know what `rotor_inertia=4.5e-5 kg·m²` means and resent UIs
that hide it behind "request a quote".*

**Anti-positioning:** not a marketplace (we don't sell, no referral
fees, no shadow-ranking). Not a CAD/PDM/PLM tool. **Not vendor-
affiliated** — the product shows ABB / Siemens / Rockwell / Yaskawa /
Mitsubishi / Schneider / Oriental Motor / Maxon / Nidec / Omron
without preferential ordering. *Neutrality is the product.* Re-read
this rule before any sponsorship conversation.

**Tagline (canonical, do not soften):**

> A product selection frontend that only an engineer could love.

**Channels ranked by ROI:**

- **Tier 1 (highest leverage, do first):**
  1. **Hacker News Show HN.** One-shot, 10k+ engineers in a single
     morning if it lands. Submit *after* `specodex.com` DNS cutover
     so the URL is stable. Title formula: `Show HN: Specodex —
     cross-vendor spec database for motors, drives, gearheads
     (datasheet-mined)`. Maintainer ready to answer comments live for
     the first 4 hours. Single attempt; if it flops, wait 90 days
     before resubmitting with substantially new material.
  2. **r/PLC, r/AskEngineers, r/Mechatronics, r/robotics,
     r/AutomationEng.** Five subs, ~600k combined. One thread per sub,
     spaced over 2-3 weeks (Reddit detects coordinated posting).
     Engage every comment in the first 48 hours.
  3. **Eng-Tips and ControlBooth forums.** Older, smaller, extremely
     high-trust. **Soft-introduce by answering questions with Specodex
     links before posting any standalone announcement.**
  4. **GitHub repo as a marketing asset.** Top-of-README screenshot
     + live-app one-liner. Submit to `awesome-industrial`,
     `awesome-robotics`, `awesome-mechatronics`, `awesome-engineering-resources`.
- **Tier 2 (sustained content):** engineering blog posts (Phase 2d
  of SEO); YouTube collabs (Tim Wilborne, Tim Hyland, RealPars —
  pitch 5-min "live search demo" segments); LinkedIn long-form
  posts every 10-14 days.
- **Tier 3 (slower-burn):** trade press (*Design World*, *Control
  Engineering*, *Machine Design*, *Motion Control & Sensors*,
  *Automation World* — short pitch + one image, no press release);
  conference attend (no booth pre-revenue — Automate / IMTS / Pack
  Expo / NI Week); CSIA cold outbound (only worth it once a second
  engineer can handle volume).
- **Don't bother:** Google/LinkedIn paid ads (CPM is brutal); generic
  SaaS review sites (audience doesn't use them); influencer marketing
  (not a thing in this niche).

**Conversion ladder:**
- (A) **Bulk / API tier** (paid via Stripe metered billing — already
  plumbed in `stripe/` Rust Lambda). Engineers wanting programmatic
  access, CSV export, BOM-import.
- (B) **Sponsored ingestion** (paid by manufacturers — *not yet, only
  with neutrality preserved*). Manufacturers get guaranteed coverage,
  no ranking changes. **Hold off until user base makes it matter to
  them.**
- (C) **Custom-type ingestion as a service** (paid by integrators).
  A consulting firm has a niche product type they want indexed; we
  run schemagen against their PDF pile. Low-volume, high-margin.

**Phasing:**

| Phase | Window | Gate to next |
|---|---|---|
| **0 — Pre-flight.** REBRAND Stage 4 + SEO Phase 1. | Until `specodex.com` resolves and Google has indexed > 50 product pages. | Both gates green. |
| **1 — Soft launch.** Show HN. r/PLC + r/AskEngineers thread. README screenshot. `awesome-*` PRs. | 30 days. | > 200 sessions/week sustained; > 50 GitHub stars; no critical UX bugs. |
| **2 — Content.** 3 blog posts. 2 YouTube collab pitches. 3 trade-press pitches. | 60 days. | At least one trade-press placement / YouTube mention / second HN appearance. |
| **3 — Outbound.** CSIA cold outreach, LinkedIn cadence, conference attend. Begin paid Stripe surface once free funnel produces > 1,000 sessions/week. | Indefinite. | Stripe MRR > $0. |
| **4 — Scale.** Re-evaluate paid ads, conference booths, partnerships. | TBD. | — |

**Risks:**
- **Looking like a vendor's affiliate.** If users perceive Specodex as
  ranking ABB above Siemens (or vice versa), trust collapses
  permanently. Search ordering must be deterministic and stable across
  vendors.
- **Datasheet copyright pushback.** Specs themselves are facts and not
  copyrightable; verbatim text and images are. Specodex *links* to the
  original datasheet rather than re-hosting — preserve that hard line.
  If a takedown notice arrives, comply on the specific item, document,
  continue. Don't capitulate site-wide.
- **Quality regressions visible to early users.** A high-profile post
  on HN/Reddit with a broken comparison is worse than no post. Run
  `./Quickstart bench --live` and `./Quickstart smoke` against prod
  immediately before any high-traffic announcement.
- **Email collection without a privacy story.** If we add `/subscribe`,
  it needs a one-paragraph privacy statement.

**Targets by month-3 of active marketing:** 1,000 sessions/week,
> 25% returning ratio, 250 GitHub stars, 5,000 weekly search
impressions, 30 real referring domains, 100 newsletter opt-ins,
first 5 Stripe conversions.

---

## Late Night queue

Curated tasks safe to run autonomously overnight on dev. Each meets
four criteria: bounded, dev-only writes, recoverable, morning-checkable.

**Tier 1 — read-only or local-only (zero cost):**

| Task | Command | Output |
|---|---|---|
| Bench (offline) | `./Quickstart bench` | `outputs/benchmarks/<ts>.json` — diff vs `latest.json` |
| Ingest-report | `./Quickstart ingest-report --email-template` | `outputs/ingest_report_*.md` |
| UNITS review triage | parse `outputs/units_migration_review_dev_*.md`, group by pattern | `outputs/units_triage_<ts>.md` |
| Integration test sweep | `./Quickstart verify --integration` | exit code; stale tests surface as failures |
| DEDUPE Phase 1 audit | run `uv run python -m cli.audit_dedupes` against dev | `outputs/dedupe_audit_<ts>.json` + `dedupe_review_<ts>.md` |

**Tier 2 — small Gemini cost, dev DB writes only:**

| Task | Cost | Output |
|---|---|---|
| Schemagen on stockpiled PDFs | ~$0.10–0.50/PDF | `<type>.py` + `<type>.md` ADR per cluster |
| Price-enrich (dev) | scraping + occasional Gemini | row counts before/after; spot-check 5–10 in UI |

**Tier 3 — bounded but expensive (run weekly):**

| Task | Cost | Output |
|---|---|---|
| Bench (live) | ~$1–5/run | precision/recall delta + cache delta |
| Process upload queue (dev) | unbounded — only with known queue size | products via `/api/v1/search` |

**Morning checklist before promoting to prod:**

1. `tail -100 .logs/*.log` — no unhandled exceptions, no rate-limit
   spirals.
2. `diff outputs/benchmarks/latest.json outputs/benchmarks/<ts>.json`.
   Drop > 5pp on any fixture is a stop signal.
3. Hit dev `/health`, `/api/products/categories`,
   `/api/v1/search?type=motor&limit=5`. All 200 with expected shape.
4. If schemagen ran: read each `<type>.md` ADR. Reject anything that
   hardcodes one vendor's quirks.
5. UI walkthrough on http://localhost:5173: pick the new type,
   confirm filter chips + table columns render.
6. **If green:** `./Quickstart admin promote --stage staging --since
   <ts>`, smoke staging, then `--stage prod`.
7. **If red:** damage is dev-only. `./Quickstart admin purge --stage
   dev --since <ts>` rolls back, then triage.

**Not Late Night material:** anything in `app/infrastructure/` (CDK)
or `.github/workflows/`; any prod write or `--stage prod` promotion;
REBRAND Stage 4 DNS cutover; INTEGRATION UI changes (visual review
required).

---

## Cross-cutting themes

**The substrate ordering matters more than urgency.** UNITS was the
linchpin everything else compiles against (Pydantic + DynamoDB +
frontend rendering). DEDUPE only makes sense on post-UNITS uniform
data. INTEGRATION UI lands on the cleaned-up rendering path.
FRONTEND_TESTING tests against canonical post-UNITS shape. GODMODE
panels read finalized substrates.

**Class-of-bug eliminations are queued, not just specific fixes.**
`HOSTED_ZONE_ID` secret → `fromLookup`. `??` vs `||` lifted into
global CLAUDE.md. The DEDUPE forward fix prevents new prefix-drift;
the audit cleans the historical mess. Same pattern for UNITS — fix
the parser **and** delete the compact-string layer so the next
exotic value can't regress.

**Operator queue stays empty.** Followups in CICD, REBRAND, UNITS
are explicitly partitioned into "operator action required" vs.
"autonomous followups." When the operator queue refills, it's named
(secret rotation, environment approval, IAM policy review) rather
than a vague "ask the human."

**Neutrality is non-negotiable.** Search ordering, vendor
visibility, sponsorship policy — every load-bearing surface defends
the rule that Specodex doesn't favor any manufacturer. Re-read the
MARKETING anti-positioning before any sponsorship conversation.

**The Rust port is the only multi-week item.** Everything else in the
queue is half-day to a few days. The port is the multi-week
commitment, sequenced behind the substrate cleanups (UNITS, DEDUPE)
so the Rust models port a stable shape.
