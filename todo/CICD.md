# CI/CD

**Status (2026-04-29):** Healthy. Full chain green Test → Deploy Staging
→ Smoke Staging → Deploy Prod → Smoke Prod for the first time since
2026-03-30. Phase 3c rebrand is in prod (`specodex-api-prod` Lambda,
`Project=Specodex` tag, `Specodex-prod-*` exports).
`https://datasheets.advin.io/health` returns 200 with `mode: "public"`.

The chain crossed three latent bugs to get here: OIDC trust policy
(REBRAND Phase 3d ripple), `??`-vs-`||` env-var fallback, wrong
`HOSTED_ZONE_ID` zone, and one new bug (secret-derived job outputs
stripped between jobs). All resolved. See **Postmortem archive** for
the chronology.

---

## What you need to do next (manual)

**Six branches off master, code-ready, awaiting review/merge.** All
are bounded, branch-isolated, and pass local lint + unit suite (1119
passing). Suggested merge order — the first one is gated on an IAM
update; the rest can land in any order.

| # | Branch | What it does | Gate |
|---|---|---|---|
| 1 | `cicd-followup-fromlookup` | Eliminate `HOSTED_ZONE_ID` secret via `HostedZone.fromLookup` | Add `route53:ListHostedZonesByName` + `route53:GetHostedZone` to `gh-deploy-datasheetminer`'s `CdkDeploy` inline policy first. |
| 2 | `cicd-followup-ci-hygiene` | `cdk.out/` artifact on deploy fail + unify `/health` poll via `./Quickstart wait-health` | None |
| 3 | `cicd-followup-nightly-bench` | Weekly `./Quickstart bench --live` workflow + `cli.bench_compare` regression gate (>5pp drop fails the run) | `GEMINI_API_KEY` secret needs to exist (already does) |
| 4 | `cicd-followup-security-scans` | pip-audit + npm audit + CodeQL, all warn-only first | Pin CodeQL action SHA before merging — see TODO comment in `codeql.yml` (declined to fabricate one). |
| 5 | `cicd-followup-staging-yml-cleanup` | Refresh `staging.yml` action versions, clarify it's *not* a duplicate of `smoke-staging` | None |
| 6 | `late-night-dedupe-audit` | DEDUPE Phase 1 read-only audit script (`./Quickstart audit-dedupes --stage dev`) | None — read-only on dev DB |

After branch 1 lands and one prod deploy proves fromLookup works in
CI: `gh secret delete HOSTED_ZONE_ID`. The workflow no longer
references it; the value is dead weight.

`gh secret set/delete` is correctly rejected by session permission
rules — deploy-time secret changes are shared production state and
require explicit operator authorization. Don't relax the rule; the
friction is doing its job.

---

## What I'll do after (autonomous followups)

Ordered by impact. Each is bounded, branch-isolated, no shared-state
side effects beyond a normal PR.

### 1. Eliminate `HOSTED_ZONE_ID` as a secret entirely ✅ code-ready

Branch `cicd-followup-fromlookup`. Drops `hostedZoneId` from
`DomainConfig`, switches `frontend-stack.ts` to
`HostedZone.fromLookup({ domainName: hostedZoneName })`, removes
HOSTED_ZONE_ID from `quickstart.py` required keys + CI prod env,
un-gitignores `app/infrastructure/cdk.context.json` (now a committed
artifact caching the lookup result → `Z039212425BG1MHVPYWDN`).

Local `cdk diff DatasheetMiner-Prod-Frontend` confirms zero change to
the live `SiteAliasRecord` — fromLookup produces the same Route53
zone reference as the manual hostedZoneId did, so the deploy is a
no-op for that resource.

### 2. Refresh GitHub Actions versions ✅ shipped

Landed in `9346c66` ("CICD followup: bump action versions to current
majors"). actions/checkout@v6.0.2, setup-uv@v8.1.0, etc.

### 3. Wire `tests/integration/` into CI ✅ shipped

Landed in `e834acc` ("CICD followup #3: wire tests/integration/ into
CI"), preceded by `186347c` (drop dead tests, add `live` marker), then
the triage commits `cd33052` and `02efea7` fixing 7 stale test bugs so
the new gate goes green. New `test-integration` job runs
`pytest tests/integration/ -m "not live"`; `live`-marked tests stay
deferred to a separate nightly trigger.

### 4. Nightly `./Quickstart bench` workflow ✅ code-ready

Branch `cicd-followup-nightly-bench`. New `.github/workflows/bench.yml`
schedules the live bench weekly (Sundays 12:00 UTC) +
workflow_dispatch. Snapshots `outputs/benchmarks/latest.json` to
`/tmp/baseline.json`, runs the bench, then runs `cli.bench_compare`
(new, 14 tests) which fails the run on any fixture's precision or
recall dropping > 5pp. Bench cache + JSON uploaded as a 30-day
artifact for postmortem.

### 5. CI hygiene (one PR, low-risk)

- **JUnit XML + step summary.** ✅ shipped in `b32a63f`. Backend +
  frontend test jobs still don't emit JUnit XML — backlog candidate,
  low priority.
- **Upload `cdk.out/` on deploy failure.** ✅ code-ready on branch
  `cicd-followup-ci-hygiene`. `if: failure()` gate on both deploy
  jobs; 7-day retention.
- **Unify `/health` poll.** ✅ code-ready on the same branch. New
  `./Quickstart wait-health <url> --retries N --label <stage>`
  subcommand replaces the inline bash loops in `smoke-staging` and
  `smoke-prod`. CI and local pre-deploy gate now share one definition
  of "healthy".
- **`paths-ignore` filters.** Deferred — interacts with branch
  protection's required-status-checks list, needs a confirm-before-
  merging step.
- **`cdk diff` PR comment.** Deferred — needs `pull-requests: write`
  permission and PR number resolution; cleaner as a separate PR.

### 6. Security scans (warn-only first) ✅ code-ready

Branch `cicd-followup-security-scans`. Two new workflows:

- `.github/workflows/security.yml` — pip-audit (uv-export →
  pip-audit on the locked dep set) + npm audit (matrix over
  backend/frontend/infrastructure workspaces). Both
  `continue-on-error: true` (warn-only). Triggers: schedule (Mondays
  13:00 UTC), workflow_dispatch, and PRs that touch dep manifests.
- `.github/workflows/codeql.yml` — Python + JavaScript-TypeScript,
  security-and-quality query suite. SHA-pinning TODO in the workflow
  for the operator (declined to fabricate the SHA).

### 7. Operational tidying ✅ code-ready

Branch `cicd-followup-staging-yml-cleanup`. `staging.yml` has the
URL input parameter the doc was asking for, so it's not a duplicate
of `smoke-staging` — it's the manual-trigger ad-hoc smoke for
arbitrary URLs. Refreshed action versions to match `ci.yml` + added
a header comment spelling out the distinction.

---

## Success criteria (unchanged from prior plan)

The loop is "agent-friendly" when, for an agent making a code change:

1. `./Quickstart verify` locally → green.
2. Push → CI green within ~5 min for unit jobs, ~15 min for full deploy chain.
3. CI failure surfaces in `$GITHUB_STEP_SUMMARY`, reproduces locally with one command.
4. Green merge to `master` → staging → smoke → prod (with environment approval) → prod URL posted, no human intervention beyond approval.
5. New product types, CLI subcommands, integration tests all run by default — no separate registration step.

Items 1, 2, 4 (unit + full chain), and 5 (auto-discovery) are done.
The followups above close items 3 and the "no separate registration"
half of 5.

---

## Postmortem archive

Read-only history. Don't act on these — the issue is resolved. Kept for
future tripwire diagnosis.

### 2026-04-28 PM: Smoke Prod red — secret-derived job output stripped

After `HOSTED_ZONE_ID` was rotated and the rerun went green through
Deploy Prod, Smoke Prod failed at `Wait for /health to go 200` with
`URL rejected: No host part in the URL` and `Production /health
returned 000`.

Root cause: `Extract stack outputs` ran `./Quickstart cdk-outputs --key
SiteUrl --key CloudFrontUrl`. Prod has the `SiteUrl` output
(`https://${DOMAIN_NAME}` ≈ `https://datasheets.advin.io`) — string
contains the `DOMAIN_NAME` secret value. **GitHub Actions strips
secret-derived values from job outputs**, so the consuming `smoke-prod`
job saw `needs.deploy-prod.outputs.url` as empty. In the deploy job's
own log it shows up as `Production URL: https://***`. Staging was
unaffected — staging only emits `CloudFrontUrl` (`*.cloudfront.net`,
not secret-derived).

**Fix:** swap priority so `CloudFrontUrl` always wins for prod. The
CloudFront URL serves identical content (custom domain is a Route53
alias to that same distribution), passes between jobs cleanly, and was
already what staging used. Loss: smoke-prod no longer exercises the
custom-domain path — but `SiteAliasRecord` CFN resource + stack-status
verify already prove DNS is wired correctly. Trade is fine.

This was the **first time Smoke Prod ever ran**. Every prior CI prod-
deploy attempt failed at Deploy Prod (OIDC, then `??` vs `||`, then
wrong-zone secret), so smoke was always skipped. Three layers deep,
only the green deploy let us see this one.

**Lesson lifted into `~/.claude/CLAUDE.md`:** `secrets.*` flowing
through job outputs is a silent data-loss pattern. Audit other
workflow paths if you add cross-job output passing.

### 2026-04-28: Prod deploy red — `HOSTED_ZONE_ID` points at wrong zone

Run `25031648467` failed at `Deploy Prod / Frontend / SiteAliasRecord`
with `RRSet with DNS name ***. is not permitted in zone
bigcanyonboys.com.`. Stack rolled back cleanly to
`UPDATE_ROLLBACK_COMPLETE`.

Diagnosis: secret held `Z02805013L9EPXCI8U7ZD` (zone
`bigcanyonboys.com.`, an unrelated personal domain in the same AWS
account) instead of `Z039212425BG1MHVPYWDN` (zone `advin.io.`). Prior
manual prod deploys (2026-04-06, -18, -24) succeeded because the
operator's local shell exported the correct value. CI's secret had
been wrong since OIDC migration unlocked CI prod-deploys (P4).

**Resolved by:** operator running `gh secret set HOSTED_ZONE_ID --body
"Z039212425BG1MHVPYWDN"` and rerunning the failed job.

**Permanently eliminated by:** followup #1 above (`fromLookup`).

### 2026-04-27: Prod deploy red — `??` vs `||` in `config.ts`

First post-OIDC prod CI deploy failed with `DomainLabelEmpty` from
Route53. `HOSTED_ZONE_NAME` secret unset → workflow exports empty
string → `process.env.HOSTED_ZONE_NAME ?? "advin.io"` kept `""`
because `??` only triggers on `null`/`undefined`. CDK rendered
`Name: datasheets.advin.io..` (double dot). Fixed in `c3a89fb`:
`??` → `||`.

**Lesson lifted into `~/.claude/CLAUDE.md`:** in TS env-var reads with
a fallback, prefer `||` over `??`. Bash-set vars are always strings;
missing ones surface as `""`, not `undefined`.

### 2026-04-26 PM: OIDC trust policy fixed after REBRAND Phase 3d

`Deploy Staging` failed with `Could not assume role with OIDC: Not
authorized to perform sts:AssumeRoleWithWebIdentity` after the GitHub
repo rename. Trust policy hardcoded `repo:JimothyJohn/datasheetminer:*`
patterns; renamed to `JimothyJohn/specodex:*` via `aws iam
update-assume-role-policy`. Also expanded the inline `CdkDeploy` policy
with `ProvisionStageSsmParams` and `InvalidateCloudFront` Sids
(needed for SSM put + CloudFront invalidation steps that run outside
CDK).

The role *name* (`gh-deploy-datasheetminer`) still uses the legacy
slug — role name doesn't appear in OIDC claims; only `sub` does, and
that's been rewritten.

**Lesson lifted into REBRAND.md Phase 3d contingency list:** repo
rename silently breaks IAM trust policies whose `sub` claims hardcode
the old name.

### Done milestones (P0–P4 full list)

P0 ✅ — `tests/unit/test_admin.py` import (`.gitignore admin/` pattern);
Frontend Vitest unhandled rejections (async-handler race in 3 retry
tests).

P1 ✅ — `./Quickstart verify` (alias `ci`); CI calls `verify --only
<stage>`; 22 ruff errors cleaned; CLAUDE.md entry-point section
advertises both `test` (fast) and `verify` (gate); smoke-testing-a-new-
type checklist points at `verify`.

P2 ✅ (most) — concurrency block (`cancel-in-progress: false` on
master); deps caching (`uv` + `npm`); prod SSM-put empty-string guard;
JSON parsing moved to `./Quickstart cdk-outputs --key`. Deferred:
paths-ignore (branch protection interaction), unified /health poll,
JUnit XML, action refresh.

P3 ✅ — Stack-status smoke check (each deploy job verifies
`StackStatus ∈ {CREATE_COMPLETE, UPDATE_COMPLETE}`). Deferred:
integration tests in CI, nightly bench, `tests/test_cli.py` inclusion.

P4 ✅ — OIDC migration (`9f054a4`); `permissions: id-token: write`;
`role-to-assume` on staging + prod jobs. Deferred: pip-audit, CodeQL.

P5 deferred — `staging.yml` cleanup, `cdk diff` PR comment, `cdk.out/`
artifact upload on failure.

---

## Triggers

Surface this doc when the current task touches any of:

- Any file under `.github/workflows/`
- `cli/quickstart.py` (especially `cmd_test`, `cmd_deploy`, `cmd_smoke`,
  `cmd_verify`, `cmd_cdk_outputs`, or adding new subcommands)
- `app/infrastructure/lib/{api,frontend,database}-stack.ts` or
  `bin/app.ts` — they all interact with the deploy chain
- Pushing to `master`, opening a PR, any deploy attempt
- User mentions "CI red", "deploy stuck", "broken pipeline", "branch
  protection", or asks "is this in prod?"
- AWS credentials / OIDC / GitHub Actions secrets
- `HOSTED_ZONE_ID`, `HOSTED_ZONE_NAME`, `DOMAIN_NAME`, `CERTIFICATE_ARN`
- IAM trust policy or `gh-deploy-datasheetminer` mentions
- Cross-job output passing (`steps.foo.outputs.x` → `needs.<job>.outputs.x`)
  with values that might be secret-derived
