# Manual updates — things agents can't do for you

Prioritized checklist of manual actions that would de-risk agent work on
this repo. Ranked by ROI within each section. Derived from what broke or
required guessing during the 2026-04-18 prod migration session.

## GitHub Actions / CI

1. **Set repo secrets** (Settings → Secrets and variables → Actions).
   Without these, CI's deploy jobs fail at "Validate prod deploy-time
   secrets":
   - `AWS_ACCOUNT_ID`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - `DOMAIN_NAME`, `CERTIFICATE_ARN`, `HOSTED_ZONE_ID`, `HOSTED_ZONE_NAME`
   - `STRIPE_LAMBDA_URL` (optional)
2. **Delete the `GEMINI_API_KEY` secret** — now unused in CI, and leaving
   it there invites someone to re-wire it.
3. **Add a `production` GitHub Environment** with required reviewer
   approval. The `deploy-prod` job references it
   (`environment: name: production`), so prod deploys block until you
   click approve.
4. **Branch protection on `master`** — require PR + status checks
   (`test-backend`, `test-frontend`) before merge. Agents can push to
   `master` today.

## Local onboarding (any fresh clone)

5. **Create `app/.env.{dev,staging,prod}`** from `app/.env.example` and
   populate `AWS_ACCOUNT_ID`, `CDK_DEFAULT_ACCOUNT`, plus prod's domain
   block. These are gitignored, so every new machine (and every agent
   worktree) starts blind — this session I had to reconstruct them by
   re-reading CloudFormation.
6. **Add `.nvmrc`** at repo root with `18` so `nvm use` is automatic and
   CI's `NODE_VERSION` isn't drift-prone.

## Docker / bundling

7. **Decide on Docker policy.** Docker Desktop wasn't running this
   session, which broke CDK's `bundlingImage`. The bundling path was
   removed, but if you ever want Python-Lambda assets or bundled native
   deps, either install Colima (`brew install colima && colima start`)
   with `DOCKER_HOST` set, or note in `CLAUDE.md` that Docker-based CDK
   bundling is not supported.

## AWS-side invariants

8. **Add `DeletionProtection: true`** to the prod DynamoDB table via
   console or `aws dynamodb update-table --deletion-protection-enabled`.
   Its CloudFormation `removalPolicy: RETAIN` protects against stack
   deletion but not against an agent running `aws dynamodb delete-table`.
9. **Snapshot `products-prod`** on a schedule (DynamoDB → Backups → PITR).
   Right now a bad mutation is unrecoverable.
10. **Provision `/datasheetminer/prod/stripe-lambda-url`** (even as empty
    string) once manually, or accept the Lambda logging `SSM parameters
    not found` every cold start. Lean "provision empty" — noise in logs
    trains agents to ignore warnings.

## Project docs that would save agent time

11. **Add a `scripts/resurrect-orphan-table.sh`** that wraps the
    `cdk import` dance we did twice this session. It was written ad-hoc
    with throwaway `.import-*.json` files; next agent will re-derive it
    from scratch.
12. **Expand `CLAUDE.md`'s "Adding a new product type"** with "how to
    test it locally end-to-end" — currently it lists the 6 files to
    touch but not the smoke steps.
13. **Add a "post-deploy verification" section to `CLAUDE.md`** listing
    the exact URLs (`/health`, `/api/v1/categories`) and expected
    responses per stage. The right paths were rediscovered twice this
    session.

## Lower-stakes but quick wins

14. **Decide fate of `/api/datasheets/:id/scrape`.** It's mounted in
    public/prod mode but will always fail (no `GEMINI_API_KEY`). Either
    delete the route + `scraper.ts`/`gemini.ts` from the backend
    entirely (saves ~40MB of deps and removes an attack surface), or
    gate it behind `APP_MODE === 'admin'`. Right now it's a trap.

## Top-4 by ROI for agent sessions

1. Item **5** (env files) — unblocks every fresh clone.
2. Item **11** (resurrect script) — makes orphan recovery a one-liner.
3. Item **14** (dead route cleanup) — removes a silent-failure trap.
4. Item **3** (prod approval gate) — stops an agent from deploying
   straight to prod without human review.
