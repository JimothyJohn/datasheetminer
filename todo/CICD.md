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

Two actions, both one-shot. Once done, followup #1 (`fromLookup` on
branch `cicd-followup-fromlookup`) can merge and the chain stays green.

### 1. Add Route53 read perms to deploy role (gates the merge)

`HostedZone.fromLookup` makes a Route53 SDK call at synth time. The
deploy role doesn't have `route53:ListHostedZonesByName` or
`route53:GetHostedZone` yet, so the next prod deploy on the new branch
would fail at synth.

```bash
aws iam get-role-policy --role-name gh-deploy-datasheetminer \
  --policy-name CdkDeploy --query 'PolicyDocument' --output json \
  > /tmp/cdk-deploy.json

# Add a Route53Lookup statement to /tmp/cdk-deploy.json:
#   { "Sid": "Route53Lookup",
#     "Effect": "Allow",
#     "Action": ["route53:ListHostedZonesByName", "route53:GetHostedZone"],
#     "Resource": "*" }

aws iam put-role-policy --role-name gh-deploy-datasheetminer \
  --policy-name CdkDeploy --policy-document file:///tmp/cdk-deploy.json
```

Both actions are read-only on Route53 — low risk.

### 2. Delete the HOSTED_ZONE_ID secret (after one prod deploy proves it)

The followup #1 PR drops every code reference to `HOSTED_ZONE_ID`. Once
one CI prod deploy on master proves fromLookup works end-to-end, the
secret is dead weight:

```bash
gh secret delete HOSTED_ZONE_ID
```

(`gh secret set/delete` is correctly rejected by session permission
rules — deploy-time secret changes are shared production state and
require explicit operator authorization. Don't relax the rule; the
friction is doing its job.)

---

## What I'll do after (autonomous followups)

Ordered by impact. Each is bounded, branch-isolated, no shared-state
side effects beyond a normal PR.

### 1. Eliminate `HOSTED_ZONE_ID` as a secret entirely ✅ code-ready

Branch `cicd-followup-fromlookup`, gated on operator action #1 above.
Drops `hostedZoneId` from `DomainConfig`, switches `frontend-stack.ts`
to `HostedZone.fromLookup({ domainName: hostedZoneName })`, removes
`HOSTED_ZONE_ID` from `quickstart.py` required keys + CI validation +
prod-deploy env, un-gitignores `app/infrastructure/cdk.context.json`
(now a committed artifact caching the lookup result).

Local `cdk diff DatasheetMiner-Prod-Frontend` confirms zero change to
the live `SiteAliasRecord` — fromLookup produces the same Route53 zone
reference as the manual `Z039212425BG1MHVPYWDN` secret did. Deploy is
a no-op for that resource.

### 2. Refresh GitHub Actions versions ✅ shipped

Landed in `9346c66` ("CICD followup: bump action versions to current
majors"). actions/checkout@v6.0.2, setup-uv@v8.1.0, etc.

### 3. Wire `tests/integration/` into CI ✅ shipped

Landed in `e834acc` ("CICD followup #3: wire tests/integration/ into
CI"), preceded by `186347c` (drop dead tests, add `live` marker), then
the triage commits `cd33052` (`test_deploy_readiness.py`) and `02efea7`
(`test_pipeline.py` + `test_scraper_degraded_inputs.py`) fixing 7
stale test bugs so the new gate goes green. New `test-integration` job
runs `pytest tests/integration/ -m "not live"`; `live`-marked tests
stay deferred to a separate nightly trigger.

### 4. Nightly `./Quickstart bench` workflow

Catches LLM-pipeline regressions before users see them. Schedule
weekly first (Gemini cost ~$1-5/run); promote to nightly if the weekly
catches anything in the first month. Compare against
`outputs/benchmarks/latest.json`; post to a tracking issue if
precision/recall drops > 5pp on any fixture.

### 5. CI hygiene (one PR, low-risk)

- **JUnit XML + step summary.** ✅ shipped in `b32a63f` (CICD followup:
  JUnit XML + step summary on Python tests). Backend/frontend test jobs
  still don't emit JUnit XML — backlog candidate, low priority.
- **`paths-ignore` filters.** Doc-only changes (`*.md`, `todo/**`,
  `outputs/**`) skip the deploy chain. **Caveat:** interacts with
  branch protection's required-status-checks list — confirm what's
  required before merging.
- **Unify `/health` poll.** CI waits 60s, `Quickstart smoke` waits 5s.
  Single helper in `cli/quickstart.py:159`, parameterized; both
  callsites converge.
- **Upload `cdk.out/` on deploy failure.** Post-mortem doesn't require
  re-running.
- **`cdk diff` PR comment.** New job runs `npx cdk diff --all` against
  staging, posts the diff. Reviewers see infra delta before approval.

### 6. Security scans (warn-only first)

- **`pip-audit` + `npm audit --omit=dev`** as non-blocking jobs.
  Promote to blocking after one cleanup cycle.
- **CodeQL workflow** (Python + JavaScript). Standard GitHub starter,
  ~5-min job per language.

### 7. Operational tidying

- **Delete `staging.yml`** — duplicates `smoke-staging`. Confirm via
  `gh workflow list` first; if anything triggers it on
  `workflow_dispatch` for ad-hoc cross-env smoke, repurpose with a
  `URL` input parameter instead of deleting.

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
