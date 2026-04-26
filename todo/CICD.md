# CI/CD: tighten the dev loop, make it agent-friendly

## Current state — the headline problem

CI has been **red on every push to master since 2026-03-30** (9+ consecutive failures, last green deploy unknown).

**P0 root causes fixed 2026-04-26** (CI not yet re-run as of this edit):

1. **`tests/unit/test_admin.py` failed to import `specodex.admin`.** Surface error was the obvious `ModuleNotFoundError`, but the underlying cause was `.gitignore` line 280: a bare `admin/` pattern that silently nuked both `specodex/admin/` (the Python module — `Blacklist`, `promote`, `demote`, `purge`) and `admin/blacklist.json` (the data file the docstring claims is "checked into git for code review"). Pattern was too broad — gitignore matches `admin/` anywhere in the tree, not just at repo root. Fix: dropped the pattern (top-level `admin/` only contains the data file, and we want it tracked). Now `git ls-tree HEAD specodex/admin/` shows the module; pytest collects it cleanly. Originally the doc framed this as "delete or repoint test imports to `cli.admin`" — that would have been wrong, since `specodex.admin` is the real implementation and `cli.admin` is just the argparse wrapper.

2. **Frontend Vitest "passed" but exit-1'd on 3 unhandled rejections** in `client.edge.test.ts` (added in commit `04bbf39`, lines up with the 2026-03-30 CI-red start date). Pattern was `const p = call(); await runAllTimersAsync(); await expect(p).rejects.toThrow(...)` — the rejection fires during timer drain *before* `expect().rejects` registers a handler. Fix: attach the handler synchronously via `.catch(e => e)` on the same line as the call. Same diagnosis applies to all three retry tests (5xx, network, timeout). 7/7 edge tests pass and 243/243 vitest pass with zero unhandled errors.

`./Quickstart test` now exits 0 locally. Next push will tell whether CI agrees.

Consequences (still open):
- Production has not been deployed by CI in three+ weeks. Whatever is in prod got there by hand or is stale.
- The `deploy-staging` → `smoke-staging` → `deploy-prod` chain has not been exercised end-to-end on master since the breakage. The OIDC migration in commit `9f054a4` (Phase P4) hasn't been validated yet either.
- `./Quickstart test` and CI run *almost* the same commands but not exactly the same — agents who run Quickstart locally and see green still get a red CI surprise. (CI lints, Quickstart doesn't. CI builds backend/frontend, Quickstart doesn't.) → addressed in P1 below.

## What's in place today

| Stage | Where | Notes |
|-------|-------|-------|
| Unit (Python) | `.github/workflows/ci.yml:16` | `pytest tests/unit/ -m "not slow"` |
| Unit (backend) | `ci.yml:34` | lint + jest + tsc |
| Unit (frontend) | `ci.yml:62` | lint + vitest + tsc + vite build |
| Deploy staging | `ci.yml:93` | `./Quickstart deploy --stage staging` (delegates to single source of truth — good) |
| Smoke staging | `ci.yml:172` | `tests/staging/` + `tests/post_deploy/` |
| Deploy prod | `ci.yml:215` | gated on staging smoke + `environment: production` approval |
| Smoke prod | `ci.yml:317` | `tests/post_deploy/` |
| `staging.yml` | manual `workflow_dispatch` | Duplicates what `smoke-staging` already does. Probably dead. |

`./Quickstart test` (`cli/quickstart.py:260`) runs only Python unit + backend jest + frontend vitest. **No lint, no tsc, no integration tests, no build.**

`tests/integration/` (8 files including new `test_intake_guards_end_to_end.py`, `test_scraper_degraded_inputs.py`) is **not wired into CI or Quickstart anywhere**. It might as well not exist.

## Pain points, grouped by who feels them

### The agent / dev loop (highest leverage)

1. **Drift between `./Quickstart test` and CI.** Local green ≠ CI green because Quickstart skips lint and build. Agents push, CI fails on lint, agents iterate from a red gate.
2. **No pre-push verification command.** There is no `./Quickstart verify` (or `./Quickstart ci`) that runs *exactly* what CI runs. Each agent rediscovers the gap.
3. **No path filtering.** A README edit triggers Python tests, backend tests, frontend tests, and a staging deploy. Slow feedback + wasted deploys.
4. **No concurrency cancellation.** Two pushes in quick succession deploy concurrently → CDK race + CloudFront double-invalidation.
5. **Brittle JSON parsing in YAML.** `ci.yml:142-157` and `:283-300` inline `python3 -c '…json.load…'` to read `cdk-outputs.json`. Silently prints empty string if the key shape changes (e.g., `SiteUrl` vs `CloudFrontUrl` precedence varies between staging/prod). Belongs in `Quickstart`.
6. **Pytest output is the only failure signal.** No JUnit XML, no test-report summary in the PR. Agents have to re-run `gh run view --log-failed` and grep.
7. **Long-lived AWS access keys.** `ci.yml:118` uses `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`. OIDC + role assumption is the modern norm, removes secret rotation, and scopes per-stage.
8. **No deploy dry-run / `cdk diff` step.** PRs don't surface the infra delta, so reviewers (human or agent) approve blind.
9. **No deps caching.** Every job re-installs `uv` deps and `npm` deps from scratch (~30-60s each, 3 jobs = wasted ~2 min/run).
10. **Health-check polling is divergent.** CI waits 60s (`ci.yml:191`), `Quickstart smoke` waits 5s (`cli/quickstart.py:488`). Same code path, different verdicts.

### Coverage gaps

11. **Integration tests don't run anywhere.** `tests/integration/test_pipeline.py`, `test_db_integration.py`, `test_intake_guards_end_to_end.py`, `test_scraper_degraded_inputs.py` — none of these are in CI or Quickstart. New files added in this branch will rot the same way.
12. **`tests/test_cli.py` (top-level) isn't picked up by `tests/unit/` glob.** `pytest tests/unit/` excludes it.
13. **No regression guardrail on the LLM pipeline.** `./Quickstart bench` runs only on demand. A keyword-matcher refactor in `page_finder.py` could silently cut recall in half and we'd find out by user complaint.
14. **No dependency audit.** No `uv pip audit` / `npm audit` / `pip-audit` step. CVEs land silently.
15. **No security scan.** A `/security-review` skill exists but is human-triggered. CodeQL or Semgrep would catch obvious stuff per-PR.
16. **Smoke tests don't verify CloudFormation stack status.** `/health` 200 doesn't mean the stack converged cleanly — a partial UPDATE_ROLLBACK_COMPLETE can still serve traffic from old Lambda code.

### Operational

17. **`staging.yml` is duplicative legacy.** Same checkout + `pytest tests/staging/` as `smoke-staging`. Either repurpose for cross-environment ad-hoc testing or delete.
18. **No nightly bench.** Quality regressions surface late.
19. **No artifact upload on failure.** When `cdk deploy` fails, the CDK template, `cdk.out/`, and `cdk-outputs.json` are gone with the runner.
20. **Node.js 20 actions deprecation warning** in CI logs. Action versions need a refresh pass before June 2026.

## Plan

Ordered by leverage. Steps 1–3 are blocking (everything else is moot while CI is red).

### P0 — unblock the gate

- [x] **Fix `tests/unit/test_admin.py`** (2026-04-26). Real cause was the `.gitignore admin/` pattern; module is now tracked. 26/26 tests pass.
- [x] **Fix Frontend Vitest unhandled rejections** (2026-04-26). Async-handler race in 3 retry tests; rewrote to attach the rejection handler synchronously. 243/243 vitest pass with 0 unhandled errors. (Not in the original P0 plan — surfaced once Test Python was unblocked.)
- [ ] **Add a CI sanity test that `Quickstart test` exits 0 on a clean checkout.** Trivial job, but it forces local/CI parity for the test command. *(Folds into the P1 `./Quickstart verify` work — handle there.)*
- [ ] **Confirm prod is in the state we think it is.** `aws cloudformation describe-stacks --stack-name DatasheetMiner-Prod-*` for each stack, sanity-check `LastUpdatedTime`. If prod has drifted, decide whether to redeploy from `master` HEAD once CI is green.

### P1 — close the local↔CI loop ✅ shipped 2026-04-26

- [x] **`./Quickstart verify` (alias: `./Quickstart ci`)** lands in `cli/quickstart.py:cmd_verify`. Stages: ruff check + ruff format --check + pytest tests/unit/ for Python; `npm run lint && npm test && npm run build` for backend and frontend. `--only python|backend|frontend` runs a single stage; `--integration` adds `tests/integration/` to the Python stage. Skips `npm install` and `uv sync` — assumes those ran upstream (CI's `npm ci` / `uv sync --quiet` steps; locally the user's existing dev env). Fails fast with a hint if `app/node_modules` is missing.
- [x] **CI calls verify.** Each `test-*` job in `.github/workflows/ci.yml` is now `./Quickstart verify --only <stage>` instead of inline run blocks. Single source of truth for what "tested" means. Note: CI keeps its own `actions/setup-uv` + `uv sync` and `actions/setup-node` + `npm ci` setup steps — verify doesn't reinvent those.
- [x] **Pre-existing 22 ruff errors cleaned up** so the new `verify` gate doesn't false-red on day one. 17 autofix (unused imports, f-strings without placeholders), 5 manual (one `once_flag` deadcode in `quickstart.py`, one `__all__` in `specodex/models/__init__.py`, one `l → line` rename in `page_finder.py`, two unused locals in tests). 1050 unit tests still green.
- [x] **`./Quickstart test` kept lean** (just tests, no lint/build) for fast dev-loop feedback; help text now explicitly directs pre-push users to `verify`. Folding `test` into `verify` would have lost the fast inner loop.
- [x] **CLAUDE.md updated.** Entry-point section advertises both `test` (fast) and `verify` (gate). Smoke-testing-a-new-type checklist now says "step 1: `./Quickstart verify`" instead of the old `(cd app/{backend,frontend} && npx tsc --noEmit)` pair, since verify covers tsc via the build stage.

### P2 — make CI faster, more honest, and more diagnosable

- [ ] **`paths-ignore` and `paths` filters** on workflow triggers. Doc-only changes (`*.md`, `todo/**`, `outputs/**`) skip the deploy chain. Per-job filters: backend changes don't trigger frontend tests.
- [ ] **`concurrency:` block** on each workflow keyed by ref + workflow, `cancel-in-progress: true` for non-deploy stages, `cancel-in-progress: false` for `deploy-prod`.
- [ ] **Cache `uv` and `npm` deps** via `actions/setup-node`'s built-in `cache: npm` and `astral-sh/setup-uv`'s `enable-cache: true`. Shaves ~2 min/run.
- [ ] **Move JSON-parsing logic out of YAML.** Add `./Quickstart cdk-outputs --key SiteUrl --fallback CloudFrontUrl` and `--key DistributionId` so CI is `URL=$(./Quickstart cdk-outputs --key SiteUrl)`. Tested in Python, not embedded in shell heredoc.
- [ ] **Unify the `/health` poll.** One helper in `quickstart.py` (already exists at `:159`), parameterized by retries, called from both `cmd_smoke` and CI. CI invokes `./Quickstart smoke "$URL" --wait 60`.
- [ ] **`--junitxml` on every pytest run + `actions/upload-artifact@v4`** for the XML and `cdk-outputs.json`. Add a job summary step (`echo "..." >> $GITHUB_STEP_SUMMARY`) listing pass/fail counts.
- [ ] **Refresh action versions.** `actions/checkout@v5`, `actions/setup-node@v5`, `astral-sh/setup-uv@v6` (whatever's current at ship time). Keeps SHA-pinning convention. Resolves the Node 20 deprecation warning.

### P3 — wire up the missing test surface

- [ ] **Run `tests/integration/` on PR.** Needs a job with mocked AWS (moto is already a dev dep). Skip the ones that need real LLM credentials, or gate them behind a `live` marker that runs nightly only.
- [ ] **Include `tests/test_cli.py`** in the unit pass — change CI to `pytest tests/unit/ tests/test_cli.py` or move the file under `tests/unit/`.
- [ ] **Nightly `./Quickstart bench` workflow** with `--update-cache` disabled, comparing against `outputs/benchmarks/latest.json`. Post a comment to a tracking issue if precision/recall drops > 5pp on any fixture. Costs real money — make it weekly first, see what it catches.
- [ ] **Stack-status smoke check.** Add a step after `deploy-staging` / `deploy-prod` that calls `aws cloudformation describe-stacks` and asserts `StackStatus` ends in `_COMPLETE` (not `_ROLLBACK_*` or `_IN_PROGRESS`).

### P4 — secret hygiene & supply chain

- [x] **Migrate to GitHub OIDC for AWS** (2026-04-26, commit `9f054a4`). Workflow now has `permissions: id-token: write` and both staging + prod deploy jobs use `role-to-assume: arn:aws:iam::403059190476:role/gh-deploy-datasheetminer`. Single role for now (not per-stage); the role name still uses the legacy `datasheetminer` slug — Phase 3c of REBRAND will rename it. **Not yet validated end-to-end** because the deploy jobs were skipped while Test Python was red; first real exercise is the next CI run after the P0 fixes ship.
- [ ] **`pip-audit` and `npm audit --omit=dev`** in CI as a non-blocking job (warn, don't fail). Promote to blocking after one cycle of cleanup.
- [ ] **CodeQL workflow** (Python + JavaScript). GitHub provides a starter; ~5-min job. Catches obvious injection / unsafe patterns.

### P5 — operational tidying

- [ ] **Delete `staging.yml`** unless it's used by something I missed. `gh workflow list` shows it's active but it duplicates `smoke-staging`. If kept, repurpose for "smoke an arbitrary URL" with `workflow_dispatch`.
- [ ] **Add a `cdk-diff` job on PR** that runs `npx cdk diff --all` against the staging account and posts the diff as a PR comment. Reviewers see infra delta before approval.
- [ ] **Upload `cdk.out/` on deploy failure** so post-mortem doesn't require re-running.

## Success criteria

The loop is "agent-friendly" when, for an agent making a code change, the following sequence holds:

1. Agent runs `./Quickstart verify` locally → green.
2. Agent pushes → CI green within ~5 min for the unit jobs, ~15 min for the full deploy chain.
3. If CI fails, the failure is in `$GITHUB_STEP_SUMMARY` (not buried in `--log-failed`), and reproduces locally with one command.
4. A green merge to `master` deploys to staging, smoke-tests, deploys to prod (with environment approval), and posts the prod URL — all without human intervention beyond the approval click.
5. New product types, new CLI subcommands, and new integration tests all run by default — no separate registration step that someone might forget.

## Notes / open questions

- Is the staging account separate from prod, or same account different stacks? OIDC role design depends on this.
- Does anyone read `outputs/benchmarks/latest.json`? If not, the nightly bench needs an actual notification path (email? GH issue comment?) or it's just more noise.
- `tests/integration/test_intake_guards_end_to_end.py` is uncommitted on this branch — confirm whether it's meant to ship before wiring the integration job to it.

## Triggers

Surface this doc when the current task touches any of:

- Any file under `.github/workflows/`
- `tests/unit/test_admin.py` (the import bug blocking CI today)
- `cli/quickstart.py` (especially `cmd_test`, `cmd_deploy`, `cmd_smoke`, or adding new subcommands)
- Pushing to `master`, opening a PR, or any deploy attempt
- User mentions "CI red", "deploy stuck", "broken pipeline", "branch protection", or asks "is this in prod?"
- AWS credentials / OIDC / GitHub Actions secrets
- Once Quickstart `verify`/`ci` lands, also closes part of [MANUAL_UPDATES.md](MANUAL_UPDATES.md) item 4.
