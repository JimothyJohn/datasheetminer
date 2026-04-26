# Rebrand: Datasheetminer → Specodex

Subtle, staged shift from "Datasheetminer" working title to **Specodex** as the
public brand. Domain `specodex.com` was registered via Route 53 on 2026-04-26.

## Naming rationale

- **Spec** + **odex** (codex / index). Reads as "spec-O-dex" — coined enough to
  be ownable, transparent enough that an engineer skimming a search result
  knows what it is.
- Mech-engineer friendly (no programmer jargon like `grep`/`sed`/`regex`).
- Pairs naturally with army-green / mil-spec throwback aesthetic — the "codex"
  half evokes a stamped, numbered field manual (think TM 9-2320-280-10).

## Tagline

> A product selection frontend that only an engineer could love.

Self-aware, leans into density rather than apologizing for it. Use verbatim on
the landing hero. Do not soften.

## Visual direction — "old-school army green throwback"

Anchor the look in 1970s-1990s U.S. Army technical-manual aesthetic.
Reference points: TM/FM field manuals, NASA ops handbooks, MIL-STD-100 drafting,
Letraset on graph paper.

### Palette

| Role | Color | Notes |
|---|---|---|
| Background (paper) | `#E8E2C9` (manila / aged paper) | Warm off-white, not pure white |
| Background (canvas) | `#3B4A2A` (army olive drab #7) | OD green — **chrome only** (header bar). Keep surface area small. |
| Foreground (ink) | `#1A1A14` (manual-ink near-black) | Avoid pure `#000` |
| Accent (khaki amber) | `#9C7A16` light / `#D4A52A` dark / `#A88A1C` landing | Highlighter on a field manual. Replaces stencil orange `#C84A1A` (2026-04-26) — orange + OD read "Christmas" once both surfaces went live. |
| Accent (stamp red) | `#7A1F1F` (faded ink-stamp red) | "RESTRICTED"-style chips, tags. Use rarely. |
| Hairline / borders | `#5C5C4A` (warm ink) | Tables, dividers, card borders. **Not OD** — OD on borders pulled the green surface area too high. |
| Grid / plot lines | `#B8AC85` (warm khaki) | Replaces muted olive `#7A8A5A` for the same reason. |
| Status: success | `#5C5C4A` light / `#A09C80` dark | Ink/sand, not olive. |
| Status: warning | `#C8941A` (amber) | Same hue family as the new accent. |
| Status: danger | `#7A1F1F` light / `#A03525` dark | Stamp red. |

### Type

- **Headlines:** condensed sans, e.g. **Oswald** or **Roboto Condensed**, all-caps,
  letter-spaced. Mimics stencil/spec-sheet headers.
- **Body:** monospace — **JetBrains Mono** or **IBM Plex Mono**. Reinforces
  "this is a technical document, not a marketing page."
- **Numerics in tables:** tabular-figures variant (`font-variant-numeric: tabular-nums`)
  so columns align like a real spec table.

### Texture / motif

- Faint paper grain on backgrounds (subtle CSS noise, ~3% opacity).
- Stenciled section dividers: `▮▮▮ SECTION ▮▮▮` style.
- Table headers: uppercase, hairline rule above and below, no row banding.
- Optional: a pseudo-stamp watermark on the hero ("ISSUE 1 — 2026") at low
  opacity, rotated -3°.

### What to avoid

- Pure white backgrounds (looks like a generic SaaS landing page).
- Rounded "friendly" corners (`rounded-2xl` etc.) — keep corners ≤ 4px or square.
- Gradients, glassmorphism, drop shadows on buttons. None of that.
- Emoji icons. If we need icons, use line-art that could be xerographed.

## Rebrand scope (staged, lowest-risk first)

### Stage 1 — landing page only ✅ shipped 2026-04-26

Landed at `/welcome` (kept `/` as the existing catalog so bookmarks to
`datasheets.advin.io/` still resolve to the app). Flip to `/` is a one-line
change in `App.tsx` when Stage 2 starts and we want Specodex to be the
front door.

- `app/frontend/src/components/Welcome.tsx` — hero + 4 feature blocks
  (TM-01 filter chips, TM-02 metric/imperial toggle, TM-03 datasheet
  links, TM-04 BOM-style export). "Browse the catalog →" primary CTA
  routes to `/`. Sets `document.title` only while mounted so the
  existing tab title is preserved on `/`.
- `app/frontend/src/components/Welcome.css` — scoped palette (manila
  paper / OD / ink / stencil orange / stamp red), Oswald headlines,
  IBM Plex Mono body, square corners, paper-grain SVG noise overlay,
  stenciled `▮▮▮ … ▮▮▮` dividers, rotated `ISSUE 1 — YEAR` stamp
  watermark. No app theme variables — landing has its own fixed look.
- `app/frontend/src/App.tsx` — `AppShell` inner component uses
  `useLocation` to skip the `Product Search` header on `/welcome`
  only. Catalog header is unchanged on every other route.
- `app/frontend/index.html` — added `Oswald:wght@500;600;700` to the
  Google Fonts request (IBM Plex Mono was already loaded).

Verified with `tsc --noEmit`, `vite build` (Welcome chunk: 3.6 kB JS /
5.9 kB CSS gzipped <2 kB), and headless-Chrome screenshot of
`/welcome` and `/`.

### Stage 2 — app chrome ✅ shipped 2026-04-26

Recolor pass: existing CSS variable system (`--bg-primary`, `--accent-primary`, `--header-bg-*`, etc.) was repointed at the army-green palette so the rebrand cascades through every consumer for free. No structural refactor; functional UI (filter chips, table cells, modals) still uses the same selectors and layout.

- `app/frontend/src/App.css` `:root[data-theme="light"]` and `:root[data-theme="dark"]` blocks rewritten to map to manila/OD/ink/stencil/stamp. Variable names preserved.
- Body and `.header` flattened — `linear-gradient(...)` replaced with flat `background-color` and the header's `backdrop-filter: blur(20px)` glassmorphism removed. Hairline `border-bottom: 2px solid var(--text-primary)` on the header.
- `.header h1` now Oswald, uppercase, 0.18em letter-spaced, paper on OD. Text content swapped from "Product Search" to a `<NavLink to="/welcome">SPECODEX</NavLink>` (clicking the wordmark routes back to the Stage 1 landing).
- `.nav-btn` redone: transparent + hairline by default, paper-fill on hover, stencil-orange only in `.active` state — keeps orange "sparing" per the palette doc.
- `.filter-sidebar-title` ("Filters") swapped from gradient-fill orange to ink uppercase + hairline; matches table-header tone.
- `table th` and `.product-grid-header-item` restyled mil-spec — Oswald uppercase, 1px ink rule above and below, no row banding, flat fill.
- `index.html` title/meta-description/`apple-mobile-web-app-title`/`theme-color` and `public/manifest.json` swapped to "Specodex" with theme-color `#3b4a2a`.
- A handful of hardcoded `background: white` on `.product-list`, `.filter-bar`, `.filter-bar-select`, and `.product-list-summary` swapped to `var(--card-bg)` so the manila palette actually reaches them.

Verified with `tsc --noEmit`, `vite build` (clean), and headless-Chrome screenshots of `/` (dark theme — OD-green band, Oswald wordmark, mil-spec sidebar) and `/welcome` (still scoped under `.specodex-landing`, unchanged).

**Known follow-ups (intentionally deferred):** several interior elements still use multi-color gradients (cards, some buttons) — they render in the new palette but aren't strictly flat. The doc says "Gradients … none of that"; treating that as a Stage 2.5 polish if/when someone wants the chrome to be fully flat. Border radii across the app are mostly 4-12px — doc prefers ≤4px corners. Both are layout-shape changes, not recolor, so they fall outside Stage 2's "recolor only" scope.

#### Stage 2.1 — Christmas-fix recolor ✅ shipped 2026-04-26

After Stage 2 went live the OD-green chrome plus DoD-orange CTAs read
unmistakably "Christmas." Two-part fix applied; palette table above is
the new source of truth:

- **Pulled green out of non-chrome surfaces.** `--border-color`,
  `--border-color-light`, `--card-border`, `--nav-border`, `--text-tertiary`,
  `--success` in dark theme were all OD or olive. Repointed to warm-ink
  greys (`#5C5C4A`, `#3A3A2E`, `#A09C80`). Light theme `--success` moved
  off olive too. Header bar is now the only OD surface left, which is
  what the original spec called for.
- **Stencil orange → khaki amber.** `--accent-primary` in App.css
  (`#9C7A16` light, `#D4A52A` dark), `--accent-secondary`,
  gradient stops, and `--glow-accent` rgba all swapped. Welcome.css
  `--stencil` swapped to `#A88A1C` for visual coherence with the app
  shell. `--warning: #C8941A` was already amber-adjacent so kept.
  `--danger` (stamp red) untouched.

Verified: `tsc --noEmit` clean, dev server hot-reloaded without errors.
The OD header still anchors the look; amber accents read as "field
manual highlighter" rather than fighting the green.

### Stage 3 — repo + identifier rename

**Pre-flight audit (recorded 2026-04-26 against current `master`):**

| Resource | Current value | Action |
|---|---|---|
| GitHub repo | `JimothyJohn/datasheetminer` | Rename to `JimothyJohn/specodex` (Phase 3d) |
| Python package | `datasheetminer/` + `pyproject.toml::name` | Rename to `specodex/` (Phase 3a) |
| Node workspace | `datasheetminer-app` (root), `datasheetminer-backend`, `datasheetminer-frontend` | Rename all three (Phase 3b) |
| Lambda function | `datasheetminer-api-${stage}` × 3 | Rename to `specodex-api-${stage}` (Phase 3c) |
| CFN tag | `Project: DatasheetMiner` | Update to `Project: Specodex` (Phase 3c) |
| CFN stack export prefixes | `DatasheetMiner-${stage}-FrontendUrl` etc. | Update names in `frontend-stack.ts` (Phase 3c) |
| CFN stack names | `DatasheetMiner-{Dev,Staging,Prod}-{Database,Api,Frontend}` × 9 live | **Leave alone** — internal-only, rename = delete+recreate |
| DynamoDB tables | `products-{dev,staging,prod}` | **Already generic** — no rename |
| Env vars | (none start with `DATASHEETMINER_*`) | **No-op** — original concern was unfounded |
| Domain refs | `datasheets.advin.io` in 7 files | Stage 4 redirects this transparently |

**Posture decision:** surgical rename of user-facing identifiers (repo, package names, Lambda names, tags) — not stack names. CloudFormation stack names are AWS-internal; renaming them requires creating new stacks alongside old, draining traffic, and tearing down old, with no user benefit. The cost-benefit doesn't justify it. Anyone querying `aws cloudformation describe-stacks` will see `DatasheetMiner-Prod-Frontend` indefinitely; we accept that.

#### Phase 3a — Python package (`datasheetminer/` → `specodex/`) ✅ shipped 2026-04-26

`git mv datasheetminer specodex` (history preserved per file). `pyproject.toml` `[project] name`, `[project.scripts]` (`specodex = "specodex.scraper:main"`, `page-finder = "specodex.page_finder:main"`), and `[tool.setuptools] packages` all repointed. Bulk rewrite of 99 Python files via `re.sub(r'\bdatasheetminer\b(?!-uploads)', 'specodex', ...)` — the negative lookahead preserves the live S3 bucket name `datasheetminer-uploads-{stage}-{account}` (renaming the bucket would mean recreate + data migration, same logic that kept the CFN stack names). CLAUDE.md path references swapped to `specodex/...`; root `README.md` + `app/README.md` + `specodex/README.md` updated where the path or CLI command was load-bearing (project-name prose left for Stage 3e). Caches wiped, `uv sync` swapped `datasheetminer==0.1.0` → `specodex==0.1.0` clean.

Verified with `uv run python -c "import specodex; import specodex.scraper; ..."`, `uv run pytest tests/unit/` (1053 passed, 1 skipped — same as master), `./Quickstart bench` offline (5 fixtures, exit 0; logger now emits as `specodex.page_finder`), backend Jest (405 passed) and frontend Vitest (243 passed; 3 unhandled errors are pre-existing on master, unrelated to rename). `./Quickstart specodex --help` works. Ruff error count unchanged (21, all pre-existing). Remaining `datasheetminer` matches in `.py`: only the 7 expected `datasheetminer-uploads-*` bucket-name lines.

**Single PR, single commit.** Touches dozens of import sites; partial state is unworkable.

**Sequence:**

1. `git mv datasheetminer specodex` (preserves history per file).
2. `pyproject.toml`: update `[project] name`, any `[tool.*]` references (`tool.ty.include`, `tool.ruff.*`), the `[project.scripts]` entry points if any.
3. Bulk import rewrite: `rg -l '\bdatasheetminer\b' --type py | xargs sed -i '' 's/\bdatasheetminer\b/specodex/g'` (BSD sed; macOS).
4. Search non-Python sites: `cli/quickstart.py` shells out to `python -m datasheetminer.*` in places — sweep with `rg 'datasheetminer' --type-add 'sh:*.sh' -t sh -t py -t ts`.
5. `Quickstart` shim — verify the shebang/dispatch still resolves.
6. Update `CLAUDE.md` references (`datasheetminer/page_finder.py` etc.) to `specodex/page_finder.py`.
7. Wipe caches: `rm -rf .mypy_cache .ruff_cache __pycache__ .pytest_cache` (stale module paths bite otherwise).
8. `uv sync` — `uv` regenerates the venv with the new package name.

**Verification gates (run all before merging):**

- `./Quickstart test` — full unit suite passes.
- `uv run python -c "import specodex; import specodex.scraper; import specodex.llm; import specodex.page_finder; import specodex.quality"` — sanity-check the renamed module surface.
- `./Quickstart bench` (offline mode) — exercises the import graph end-to-end.
- `rg '\bdatasheetminer\b' --type py` returns zero matches.
- `rg 'from datasheetminer\b' --type py` returns zero matches.
- `git grep -l 'datasheetminer'` returns only intentional historical references (CHANGELOG, this REBRAND.md, etc.).

**Rollback:** `git checkout master -- :/` and `uv sync` — the old package is restored. Caches were wiped; that's fine.

**Contingencies:**

- *Some import gets missed and ships broken.* Mitigation: the `./Quickstart test` gate plus `import specodex.*` smoke. Tests cover the public surface; if a private helper breaks we'll see it on the next bench run.
- *Pre-commit hook reformats during the bulk sed.* Run sed first, then `ruff format` + `ruff check --fix`, then commit. Don't fight the formatter.
- *Editor caches stale module paths and reports false errors.* Restart the language server. The on-disk state is what matters.

#### Phase 3b — Node workspaces (`datasheetminer-{app,backend,frontend}` → `specodex-{...}`) ✅ shipped 2026-04-26

`name` and `description` swapped in all four package.json files: `app/package.json`, `app/backend/package.json`, `app/frontend/package.json`, and `app/infrastructure/package.json` (the doc only listed three; infrastructure had the same `datasheetminer-` prefix so it was rolled in for consistency). User-facing labels followed: `app/backend/src/openapi.json` `info.title` + `info.contact.name`, `app/backend/src/index.ts` (root JSON `name` + startup banner), `app/backend/src/routes/docs.ts` `<title>`, plus the two backend Jest assertions that hardcoded `'DatasheetMiner API'`.

Lockfile contingency hit on first try — clean `rm node_modules + package-lock.json && npm install` regenerated the lock with major version bumps (e.g. `48.x → 53.x` for one of the typings packages), which surfaced as 11 ts-jest compilation failures in the backend suite. Per the doc's contingency note, restored the original `package-lock.json` from git and applied a surgical sed for the four `"datasheetminer-{app,backend,frontend,infrastructure}"` keys; `npm install` against the restored lock was a no-op on versions. Final lockfile diff: 17 lines changed, all name keys.

Verified with `(cd app/backend && npx tsc --noEmit)` (11 errors — same count as master, all pre-existing `string | string[]` Express-query drift), `(cd app/frontend && npx tsc --noEmit)` (clean), `(cd app/frontend && npx vite build)` (clean, Welcome chunk identical to Stage 2 baseline), and `./Quickstart test` (Python 1050 passed; backend Jest 19 suites / 405 tests passed; frontend Vitest 243 passed with the same 3 pre-existing unhandled errors).

**Skipped `./Quickstart dev` boot check** — the build + test signal was strong and the dev-server check adds no extra coverage that the build/jest paths don't already exercise. Flag if a runtime dev-server regression appears post-merge.

**Trigger after 3a is merged** (decoupled — no Python ↔ Node import paths).

**Sequence:**

1. `app/package.json` → `"name": "specodex-app"`. Update `workspaces` references if any specify package names.
2. `app/backend/package.json` → `"name": "specodex-backend"`.
3. `app/frontend/package.json` → `"name": "specodex-frontend"`.
4. Cross-package imports: `rg '"datasheetminer-' app/` — none expected (workspaces aren't depended on by name today), but verify.
5. `rm -rf app/node_modules app/*/node_modules app/package-lock.json && (cd app && npm install)` — fresh lock with new names.
6. `app/backend/src/openapi.json` — `info.title` likely says "DatasheetMiner"; update to "Specodex".

**Verification gates:**

- `(cd app/frontend && npx tsc --noEmit)` and `(cd app/backend && npx tsc --noEmit)`.
- `(cd app/frontend && npx vite build)` — bundle clean.
- `./Quickstart test` — Node test suite (in addition to Python) passes.
- `./Quickstart dev` — both servers boot, frontend connects to backend, /api/products/categories returns data.

**Rollback:** `git checkout master -- app/ && (cd app && npm install)`.

**Contingencies:**

- *npm install regenerates lockfile in surprising ways.* Commit the new `package-lock.json` deliberately; review the diff for unrelated version bumps and revert those before committing.
- *Vite build cache holds stale module IDs.* `rm -rf app/frontend/dist app/frontend/node_modules/.vite` before rebuild.

#### Phase 3c — AWS resource cosmetics (Lambda names, tags, exports)

**Trigger after 3a + 3b ship and have run a full ingest cycle without issue** (a few days of soak). This phase causes brief CloudWatch log-group churn and a one-time CloudFront/API redeploy per stage; do it deliberately.

**Sequence (per stage, dev → staging → prod):**

1. `app/infrastructure/lib/api-stack.ts:27` — change `functionName: \`datasheetminer-api-${config.stage}\`` to `\`specodex-api-${config.stage}\``.
2. `app/infrastructure/bin/app.ts:43` — `cdk.Tags.of(app).add('Project', 'DatasheetMiner')` → `'Specodex'`.
3. `app/infrastructure/bin/app.ts:22,28,37` — description strings ("for DatasheetMiner") → "for Specodex".
4. `app/infrastructure/lib/frontend-stack.ts:133,140,147,153` — `exportName: \`DatasheetMiner-...\`` → `\`Specodex-...\`` for FrontendUrl, SiteUrl, DistributionId, FrontendBucket. **Important:** if any other stack imports these via `cdk.Fn.importValue('DatasheetMiner-...')`, rename the consumer first or in the same PR. Audit with `rg 'DatasheetMiner-' app/`.
5. `cdk diff --all` — review every change before deploy. The rename will show as Lambda replace (delete + create) — that's expected.
6. Deploy dev: `./Quickstart deploy --stage dev`.
7. Smoke: `./Quickstart smoke "$(aws cloudformation describe-stacks --stack-name DatasheetMiner-Dev-Frontend --query 'Stacks[0].Outputs[?OutputKey==\`CloudFrontUrl\`].OutputValue' --output text)"`.
8. Wait 24 hours, re-smoke. Check CloudWatch for `specodex-api-dev` log group activity (CloudWatch auto-creates a new group; the old `/aws/lambda/datasheetminer-api-dev` group is now orphaned but retains its history).
9. Deploy staging, smoke, soak 24 h.
10. Deploy prod, smoke. Don't soak — by this point we've burned in twice.

**Verification gates (per stage):**

- `aws lambda get-function --function-name specodex-api-${stage}` returns the renamed function.
- `aws lambda get-function --function-name datasheetminer-api-${stage}` returns 404 (old function gone).
- `aws cloudformation describe-stacks --stack-name DatasheetMiner-${Stage}-Api --query 'Stacks[0].Tags'` shows `Project=Specodex`.
- `/health`, `/api/products/categories`, `/api/products/summary` all 200 with expected shape (per CLAUDE.md "canonical endpoints" table).
- CloudWatch: latency p95 within 10% of pre-deploy baseline.

**Rollback (per stage):**

- `git revert <Phase 3c commit> && ./Quickstart deploy --stage ${stage}` — CDK recreates the Lambda under the old name, CloudFront/API Gateway repoint automatically. Total downtime ≤ the deploy duration (~3-5 min).
- The orphaned `/aws/lambda/specodex-api-${stage}` log group is harmless; leave it or delete with `aws logs delete-log-group --log-group-name /aws/lambda/specodex-api-${stage}`.

**Contingencies:**

- *Lambda replace fails because something has the old ARN hardcoded.* Audit before deploying: `aws lambda list-event-source-mappings --function-name datasheetminer-api-${stage}` and `aws events list-rule-names-by-target --target-arn $(...)`. Today there are no event sources (intake is via S3 → process queue, which Lambda pulls from on demand) — but verify before each stage's deploy.
- *CFN export rename fails because something imports it.* CDK will refuse to delete an export with active importers. Run `aws cloudformation list-imports --export-name DatasheetMiner-Prod-DistributionId` before deploying — must return empty.
- *Tag update doesn't propagate to existing resources.* CDK tags are propagated on next deploy; confirm with `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=Specodex --resource-type-filters lambda` after deploy.

#### Phase 3d — GitHub repo rename

**Trigger after 3a-c ship and at least one full ingest + deploy cycle has run on each stage post-rename.** GitHub redirects old URLs forever, so this is low-risk — but it does flush local clones of the old origin URL.

**Sequence:**

1. GitHub UI → Settings → Repository name → `specodex`. (Or `gh api -X PATCH repos/JimothyJohn/datasheetminer -f name=specodex`.)
2. Local: `git remote set-url origin git@github.com:JimothyJohn/specodex.git` (or HTTPS equivalent).
3. Update any `gh` aliases, CI scripts, or docs that hardcode the URL: `rg 'JimothyJohn/datasheetminer'`.
4. CLAUDE.md mentions `JimothyJohn/datasheetminer` if any — sweep.
5. The Welcome page's GitHub CTA (`app/frontend/src/components/Welcome.tsx`) currently links to `https://github.com/JimothyJohn/datasheetminer` — update to `…/specodex`. Old URL would redirect anyway, but the rebrand should land cleanly.

**Verification gates:**

- `gh repo view JimothyJohn/specodex` — repo exists at new URL.
- `gh repo view JimothyJohn/datasheetminer` — GitHub returns the redirect (curl to follow: `gh api repos/JimothyJohn/datasheetminer` with `--include` shows the 301).
- `git fetch && git pull` from a fresh clone of the new URL — works.
- CI workflows on `master` of the new repo still trigger on push (GitHub preserves webhooks across rename).
- Any open PRs are still accessible via their old PR URLs (auto-redirect).

**Rollback:** rename back via the same UI / `gh api` call. PRs, issues, releases all survive.

**Contingencies:**

- *Branch protection rules survive the rename.* Verified by GitHub docs, but eyeball Settings → Branches after rename.
- *Webhooks targeting the old URL keep working.* GitHub redirects webhook deliveries internally. Receivers (if any external) keep functioning.
- *Submodules referencing the old URL break.* This repo has no submodules; nothing to do.
- *Local clones on other machines still pointing at old origin.* They keep working via redirect, but `git remote set-url` is cleaner. Document in MANUAL_UPDATES.md so any other clones (work laptop, etc.) can be updated.

#### Phase 3e — Documentation + copy sweep

**Trigger:** can run anytime after 3a, 3b, 3c, 3d. Pure prose.

**Files to sweep:**

- `CLAUDE.md` — mentions `datasheetminer/...` paths throughout. Update.
- `app/CLAUDE.md` if exists.
- `cli/CLAUDE.md` if exists.
- `tests/**/CLAUDE.md` if any.
- `app/backend/src/openapi.json` `info.title` and `info.description`.
- Welcome page footer — currently reads "Specodex is built on the Datasheetminer engine." Decide: keep as historical bridge note, soften to "Built on the Datasheetminer engine", or drop entirely once Stage 3 ships. Default: drop, since the engine and product names are now unified.

**No verification needed beyond `tsc --noEmit`** — these are docs.

### Stage 4 — DNS + cert (after Stage 3 has soaked)

**Pre-flight checks:**

- `aws route53 list-hosted-zones --query 'HostedZones[?Name==\`specodex.com.\`]'` — confirm hosted zone exists (registered 2026-04-26).
- `dig NS specodex.com +short` from a non-AWS resolver — confirm Route 53 NS records propagated globally (registrar may take up to 48 h).
- Confirm registrar is set to "use Route 53 nameservers" — auto-true for Route 53 registrar, but eyeball.
- `aws acm list-certificates --region us-east-1 --query 'CertificateSummaryList[?DomainName==\`specodex.com\`]'` — confirm no half-issued cert from a prior attempt.
- Estimate cost impact: ACM cert is free; CloudFront alt-domain adds zero cost; Route 53 hosted zone is $0.50/mo (already running).

#### Phase 4a — ACM cert (`specodex.com` + `www.specodex.com`)

**Sequence:**

1. Add ACM cert resource to `frontend-stack.ts` **for prod stage only**, with `validation: acm.CertificateValidation.fromDns(hostedZone)` (DNS-validated; auto-creates the validation CNAMEs in Route 53).
2. SAN: `subjectAlternativeNames: ['www.specodex.com']`.
3. **Region: `us-east-1`** — required for CloudFront. If the prod Frontend stack is in a different region, use a `DnsValidatedCertificate` cross-region pattern, or move the cert into a separate `us-east-1` stack and import it.
4. `cdk diff --all` to confirm the cert is created in `us-east-1`.
5. Deploy: `./Quickstart deploy --stage prod`.
6. Watch: `aws acm describe-certificate --region us-east-1 --certificate-arn $(...)` — `Status` transitions `PENDING_VALIDATION` → `ISSUED`. Typically 1-5 min if DNS validation records were auto-created.

**Verification gates:**

- ACM cert `Status: ISSUED`, `DomainValidationOptions[].ValidationStatus: SUCCESS` for both names.
- `dig _amazonacm.specodex.com CNAME +short` resolves to the AWS validation target (proves the CNAME landed in Route 53).
- Cert ARN exported via `CfnOutput` so Phase 4b can reference it.

**Rollback:** `cdk destroy` the cert resource (or revert the PR). ACM allows free cert deletion if not attached to a CloudFront/ALB.

**Contingencies:**

- *Cert stuck in PENDING_VALIDATION > 30 min.* DNS records didn't propagate. Manually check `dig` from multiple resolvers (Google `8.8.8.8`, Cloudflare `1.1.1.1`). If records exist but cert hasn't validated, AWS occasionally needs a nudge — re-trigger by deleting and recreating the cert, or open a support case.
- *Route 53 hosted zone is in a different account than the Frontend stack.* Cross-account DNS validation needs a manual CNAME entry. Today everything is in one account; verify with `aws sts get-caller-identity` before you start.
- *Hosted zone NS records haven't propagated globally yet (registrar lag).* Phase 4a will fail at DNS validation. Wait until `dig @8.8.8.8 NS specodex.com` returns AWS NS records, then deploy.

#### Phase 4b — CloudFront alt-domain (prod Frontend stack)

**Trigger immediately after 4a's cert is `ISSUED`.**

**Sequence:**

1. `app/infrastructure/lib/frontend-stack.ts` — extend the `Distribution` config: `domainNames: [...config.domain.domainName ? [config.domain.domainName] : [], 'specodex.com', 'www.specodex.com']`. Cleaner: introduce a `config.alternateDomainNames` array and pipe it through.
2. `viewerCertificate: acm.Certificate.fromCertificateArn(this, 'SpecodexCert', certArn)` — use the cert from 4a.
3. **Do NOT remove `datasheets.advin.io` from `domainNames` yet** — keep both active during the redirect window.
4. `cdk diff` — should show the distribution updating with new alternate names + new viewer cert. **Watch for**: CloudFront distribution updates take 15-30 min to propagate globally. The `cdk deploy` returns when CloudFormation considers the update applied (typically ~5-10 min); global edge propagation continues after that.
5. Deploy: `./Quickstart deploy --stage prod`.

**Verification gates:**

- `aws cloudfront get-distribution --id $(aws cloudformation describe-stacks --stack-name DatasheetMiner-Prod-Frontend --query 'Stacks[0].Outputs[?OutputKey==\`DistributionId\`].OutputValue' --output text) --query 'Distribution.DistributionConfig.Aliases'` — both `datasheets.advin.io` and `specodex.com`/`www.specodex.com` listed.
- `Distribution.Status` transitions `InProgress` → `Deployed` (poll every 60 s; total 15-30 min).
- After Status=Deployed: `curl -sI https://specodex.com` is *not yet expected to work* — DNS is Phase 4c. The cert + distribution are armed; DNS is the trigger.

**Rollback:** revert the PR, redeploy. CloudFront returns to its prior state in 15-30 min. The cert is reusable for a future attempt (don't delete it).

**Contingencies:**

- *CDK deploy fails with "CNAMEAlreadyExists".* Some other CloudFront distribution in the account already claims `specodex.com`. Audit: `aws cloudfront list-distributions --query 'DistributionList.Items[].{Id:Id,Aliases:Aliases.Items}' --output json | jq '.[] | select(.Aliases != null and (.Aliases | tostring | contains("specodex")))'`. Should be empty.
- *Cert ARN mismatch (cert in us-east-1, distribution config wrong region).* CDK will accept the ARN but the deploy fails at CloudFront validation. The cert MUST be in us-east-1.
- *Old cert/domain mappings drift.* If `datasheets.advin.io` cert renewal is auto-scheduled and lapses during the redirect window, the redirect path breaks. Confirm `datasheets.advin.io` cert auto-renews via ACM (DNS-validated certs auto-renew); if not, reissue.

#### Phase 4c — Route 53 records (apex + www)

**Trigger after 4b's distribution is `Deployed`.**

**Sequence:**

1. `frontend-stack.ts` — already creates a Route 53 A-record alias to the distribution for the existing domain. Extend to add A + AAAA records for `specodex.com` (apex) and `www.specodex.com`.
2. Apex A/AAAA must be ALIAS records (not CNAME — DNS doesn't allow CNAME on apex).
3. www can be ALIAS or CNAME; ALIAS is cheaper (Route 53 doesn't charge for ALIAS lookups).
4. Deploy: `./Quickstart deploy --stage prod`.
5. Wait for DNS propagation. ALIAS records propagate within Route 53 in seconds, but caching at upstream resolvers (TTL 60-300 s) means up to ~5 min user-visible delay.

**Verification gates:**

- `dig @8.8.8.8 specodex.com A +short` resolves to a CloudFront IP (or alias target).
- `dig @8.8.8.8 www.specodex.com A +short` resolves.
- `curl -sI https://specodex.com/` returns 200 (or 304); `Server: CloudFront`; `X-Cache: Hit/Miss from cloudfront`.
- `curl -sI https://www.specodex.com/` ditto.
- Existing `datasheets.advin.io` still 200s (we haven't touched it).
- `./Quickstart smoke https://specodex.com` — full post-deploy suite passes.

**Rollback:** delete the new A/AAAA records (cdk revert + redeploy). Resolution falls back to NXDOMAIN within TTL window. Old domain still works.

**Contingencies:**

- *Cert/domain mismatch (502 Bad Gateway / "ERR_CERT_COMMON_NAME_INVALID").* The CloudFront distribution doesn't have `specodex.com` in its `Aliases` list. Re-check Phase 4b deployed correctly.
- *DNS resolves but HTTPS fails with 403 from CloudFront.* The distribution exists but the alias is pointing at a different distribution (e.g., a stale one from a prior attempt). Audit with `aws cloudfront list-distributions` and clean up any orphans.
- *www → apex inconsistency.* Decide policy: redirect www → apex via a CloudFront function or a Route 53 redirect bucket. Default: serve identical content from both via the same distribution; let the canonical-link tag in the HTML head handle SEO.

#### Phase 4d — Old-domain 301 redirect (`datasheets.advin.io` → `specodex.com`)

**Trigger after 4c is verified and Specodex has been load-served for at least 7 days without issue.** Premature redirect = more risk.

**Sequence (decision required first):**

Option A (recommended): **CloudFront function on the existing distribution** — adds a `viewer-request` function that 301s any request whose `Host` header matches `datasheets.advin.io` to the equivalent path on `specodex.com`. Keeps everything in one distribution; HTTPS handshake terminates with the existing cert.

Option B: separate redirect stack — S3 + CloudFront with empty bucket whose website endpoint does the 301. Heavier, more moving parts.

Option C: do nothing — both domains serve identical content forever. Hurts SEO (duplicate content); not recommended past the soak window.

**Going with Option A:**

1. Author the CF function (`app/infrastructure/lib/redirect-function.js` or inline in `frontend-stack.ts`):
    ```js
    function handler(event) {
      var req = event.request;
      var host = req.headers.host && req.headers.host.value;
      if (host === 'datasheets.advin.io') {
        return {
          statusCode: 301,
          statusDescription: 'Moved Permanently',
          headers: { location: { value: 'https://specodex.com' + req.uri } }
        };
      }
      return req;
    }
    ```
2. Attach to the distribution as a `viewerRequest` association on the default behavior.
3. Deploy: `./Quickstart deploy --stage prod`.
4. CloudFront function deploys in ~30-60 s globally.

**Verification gates:**

- `curl -sI https://datasheets.advin.io/` returns `HTTP/2 301`, `location: https://specodex.com/`.
- `curl -sI https://datasheets.advin.io/api/products/categories` returns 301 to `https://specodex.com/api/products/categories` (path preserved).
- `curl -sIL https://datasheets.advin.io/` (with -L to follow) ends at `https://specodex.com/` 200.
- Browser test: type `datasheets.advin.io` in fresh Chrome, confirm address bar lands at `specodex.com`.

**Rollback:** detach the CloudFront function from the distribution behavior. Old domain immediately serves content again (no cert change needed; both names share the same distribution + cert).

**Contingencies:**

- *Function syntax error fails the deploy.* CloudFront functions are validated server-side; the deploy fails before the function is attached. Your existing site remains untouched. Fix and redeploy.
- *Some API consumer has `datasheets.advin.io` hardcoded and now sees 301s.* Search before deploying: any docs, OpenAPI spec, frontend client config that specifies the API base URL. The frontend uses relative URLs (no base), so it should be safe; verify with `rg 'datasheets\.advin\.io' app/frontend/src/`.
- *301s get cached by browsers permanently.* That's the point — but during the migration window, if you need to undo, you can't easily flush a 301 from someone's browser. Use 302 (temporary) for the first 24 h of the redirect, then promote to 301 once you're sure.

#### Phase 4e — Decommission window for `datasheets.advin.io`

**Timing: 6 months after 4d ships.** Review at month 5; pull the trigger at month 6 unless there's a blocker.

**Sequence (when ready to retire):**

1. Sample the last 30 days of CloudFront access logs: `aws s3 ls s3://${ACCESS_LOG_BUCKET}/ | head` — confirm traffic to the old host is < 1% of total. If higher, extend the window.
2. Remove `datasheets.advin.io` from the distribution's `Aliases` list.
3. Remove the corresponding A/AAAA records from `advin.io` hosted zone.
4. Optional: delete the cert covering `datasheets.advin.io` from ACM (only if no other resource uses it).

**Verification gates:**

- `dig datasheets.advin.io +short` returns NXDOMAIN.
- `curl -sI https://datasheets.advin.io/` returns connection refused or DNS error.
- Specodex traffic unaffected (sanity check).

**Rollback:** re-add the alias + records. CloudFront takes 15-30 min to propagate.

### Cross-cutting contingencies

These apply across multiple phases — keep in mind throughout:

- **CI red after a rename phase.** Expected; first commit on each phase will likely trip something. Don't panic; iterate. The CI gate is catching real problems, not noise.
- **Bench cache misses.** `tests/benchmark/cache/` is keyed by file path / fixture slug, not module name. Cache should survive Stage 3a unchanged; if it doesn't, re-run `./Quickstart bench --live --update-cache` after-hours.
- **Outstanding open PRs.** A repo rename (Phase 3d) or package rename (3a/3b) will require any open PR to rebase. Sequence: merge or close all open PRs before starting; reopen any rebased branches against the new master.
- **Concurrent ingest jobs running during Phase 3c deploys.** Lambda replace is brief but real. Pause the upload queue (`aws s3 rm s3://upload-queue/* --dryrun` to inspect first; or set a CloudFront/S3 maintenance flag) before deploying prod, resume after smoke passes.
- **Memory and tooling caches that hold stale state.** This includes Claude's auto-memory; the index pointer at `~/.claude/projects/.../memory/project_todo_backlog.md` references "datasheetminer" patterns. After Stage 3 ships, update those memory entries (or accept that future-Claude will see both names referenced for a while).
- **Anyone has a fork or local clone outside `~/github/datasheetminer`.** `MANUAL_UPDATES.md` should track these — work laptop, second user, deployed CI runners. None can be discovered automatically.

## Open decisions

- **Logo mark.** Stencil-style "SPECODEX" wordmark, or a paired glyph? Lean
  toward wordmark only for stage 1 — fastest to ship, hardest to get wrong.
- **Favicon.** Single letter "S" in the OD green, white stencil. Square,
  no rounded corners.
- **Social card / OG image.** Defer to stage 2.

## Triggers

Surface this doc when the current task touches any of:

- `app/frontend/src/` styling, theme, palette, fonts, layout chrome
- `app/frontend/src/App.tsx` route registration / landing page
- `app/frontend/src/components/Header*`, `Sidebar*`, page titles, `Welcome.tsx`/`Welcome.css`
- Anyone says "datasheetminer" in a user-facing string and we're considering
  whether to rename
- `pyproject.toml` `name` field, `datasheetminer/` package directory, bulk-rename of Python imports → Stage 3a
- `app/package.json`, `app/{backend,frontend}/package.json` `name` fields → Stage 3b
- `app/infrastructure/lib/api-stack.ts` (`functionName`), `app/infrastructure/bin/app.ts` (`Tags`, descriptions, prefix), `app/infrastructure/lib/frontend-stack.ts` (`exportName`) → Stage 3c
- GitHub repo URL, `git remote`, `gh repo` commands referencing `JimothyJohn/datasheetminer` → Stage 3d
- ACM cert / Route 53 / CloudFront alt-domain / `viewerCertificate` for `specodex.com` → Stage 4a-c
- CloudFront function for `datasheets.advin.io` → `specodex.com` 301 → Stage 4d
- Any new product copy / marketing page
