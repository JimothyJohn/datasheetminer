# Operator queue (things only Nick can do)

This file is the punch list of one-shot manual actions blocking the
work currently sitting on local branches. Each item is bounded; nothing
needs design input. The column "Why me" tells you which permission rule
or session policy is keeping it out of the agent's hands.

Read top-down: the order minimizes rework. After each item lands, the
listed branches in the **Unblocks** column are safe to merge.

---

## 1. Add Route53 read perms to the deploy role

**Why me:** `aws iam put-role-policy` modifies shared production IAM —
session policy requires explicit operator authorization for IAM writes.

**Unblocks:** `cicd-followup-fromlookup` (branch 1).

**Time:** ~30 s + AWS-side propagation (immediate).

```bash
# Snapshot for rollback.
aws iam get-role-policy \
  --role-name gh-deploy-datasheetminer \
  --policy-name CdkDeploy \
  --query 'PolicyDocument' --output json \
  > /tmp/cdk-deploy.before.json

# Append the Route53Lookup statement.
jq '.Statement += [{
  "Sid": "Route53Lookup",
  "Effect": "Allow",
  "Action": ["route53:ListHostedZonesByName", "route53:GetHostedZone"],
  "Resource": "*"
}]' /tmp/cdk-deploy.before.json > /tmp/cdk-deploy.after.json

# Sanity-diff before applying.
diff /tmp/cdk-deploy.before.json /tmp/cdk-deploy.after.json

# Apply.
aws iam put-role-policy \
  --role-name gh-deploy-datasheetminer \
  --policy-name CdkDeploy \
  --policy-document file:///tmp/cdk-deploy.after.json

# Verify it stuck.
aws iam get-role-policy \
  --role-name gh-deploy-datasheetminer \
  --policy-name CdkDeploy \
  --query 'PolicyDocument.Statement[?Sid==`Route53Lookup`]'
```

Both actions are read-only on Route 53. Rollback if needed:

```bash
aws iam put-role-policy \
  --role-name gh-deploy-datasheetminer \
  --policy-name CdkDeploy \
  --policy-document file:///tmp/cdk-deploy.before.json
```

---

## 2. Merge the 5 CICD followup branches + DEDUPE Phase 1 branch

**Why me:** PR creation/merge against master is your call.

**Order matters only for `cicd-followup-fromlookup`** — that one needs
step 1 above to land first. The other branches are independent of each
other and of the fromLookup change.

| Branch | Tip commit | After merge |
|---|---|---|
| `cicd-followup-fromlookup` | `90a8826` | First prod deploy proves fromLookup → step 3 |
| `cicd-followup-ci-hygiene` | `f7aaba0` | `cdk.out/` artifact + unified `/health` poll live in CI |
| `cicd-followup-nightly-bench` | `f1e675d` | Sunday 12:00 UTC bench + regression gate active |
| `cicd-followup-security-scans` | `22f9054` | Pin CodeQL action SHA before merging — see TODO comment in `.github/workflows/codeql.yml` |
| `cicd-followup-staging-yml-cleanup` | `67cd228` | Manual smoke workflow uses current action versions |
| `late-night-dedupe-audit` | `faf20d5` | `./Quickstart audit-dedupes --stage dev` available |
| `late-night-units-triage` | `18976b6` | `./Quickstart units-triage <md>` available |
| `todo-doc-refresh` | `8593547` | `todo/CICD.md` + `todo/README.md` reflect the merge queue |

For `cicd-followup-security-scans` specifically, before you merge:

```bash
# Look up the current v3 SHA for github/codeql-action and replace
# the three `@v3` tags in .github/workflows/codeql.yml with the
# pinned SHA (matches the SHA-pinning convention everywhere else).
gh api repos/github/codeql-action/git/refs/tags/v3 --jq '.object.sha'
```

---

## 3. Delete the now-unused `HOSTED_ZONE_ID` secret

**Why me:** `gh secret delete` is operator-only. Do this **after** one
prod deploy proves fromLookup works end-to-end on master.

**Unblocks:** nothing — pure cleanup. The workflow no longer references
the secret; the value is dead weight.

```bash
gh secret delete HOSTED_ZONE_ID
gh secret list | grep -i hosted   # confirm it's gone
```

---

## 4. REBRAND Stage 4 — `specodex.com` cutover

This is the change you mentioned — switching the live URL from
`https://datasheets.advin.io` to `https://specodex.com`. Independent
of step 1 (the fromLookup branch is domain-agnostic; it'll resolve
whichever zone `DOMAIN_NAME`'s parent points to).

**State of the world (verified via aws CLI 2026-04-29):**

- `specodex.com.` hosted zone: `Z03197838G9A003R9OC1`, NS records
  propagated globally (8.8.8.8 matches whois).
- ACM cert: ✅ **ISSUED 2026-04-29 by the agent** for
  `specodex.com` + `www.specodex.com` (DNS-validated).
  ARN: `arn:aws:acm:us-east-1:403059190476:certificate/e885768d-a52b-4e42-a5e8-6d47bcbc2e70`
  Valid until 2026-11-13. Validation CNAMEs are now in the zone (UPSERTed
  via `change-resource-record-sets`); ACM will auto-renew while they
  remain.
- Existing `*.advin.io` cert is `ISSUED` and still in use — no
  collision; both certs can coexist on the same distribution during
  the soak.

### 4a. Rotate the GitHub secrets

**Why me:** `gh secret set` is operator-only.

```bash
gh secret set DOMAIN_NAME --body "specodex.com"
gh secret set CERTIFICATE_ARN \
  --body "arn:aws:acm:us-east-1:403059190476:certificate/e885768d-a52b-4e42-a5e8-6d47bcbc2e70"
# REQUIRED for the apex case — fromLookup defaults to the parent of
# DOMAIN_NAME, which is "com" for an apex (wrong). Set the zone name
# explicitly:
gh secret set HOSTED_ZONE_NAME --body "specodex.com"
```

**Apex caveat:** because the new `DOMAIN_NAME` is the apex
(`specodex.com`), the parent-of-domain default in
`config.ts:hostedZoneName = domainName.split('.').slice(1).join('.')`
becomes `"com"` — wrong. The `HOSTED_ZONE_NAME=specodex.com` setting
above is required, not optional, for the apex form. (If you'd picked
`www.specodex.com` instead, the default would have produced
`specodex.com` correctly and HOSTED_ZONE_NAME would be unnecessary.)

### 4b. Deploy + verify

```bash
# Push to master (ensures the fromLookup branch is in) and the CI chain
# runs deploy-staging → smoke-staging → deploy-prod → smoke-prod with
# the new domain. Or, for a manual one-off:
./Quickstart deploy --stage prod
./Quickstart smoke "https://specodex.com"
```

After a clean deploy, both URLs serve the same content for the soak
window: `datasheets.advin.io` (still aliased on the CloudFront
distribution because the cert + SAN haven't been removed yet) and
`specodex.com`. To finalize, drop `datasheets.advin.io` from the
CloudFront distribution's alt-domain list — that's a Stage 5 cleanup,
not blocking.

---

## What's blocking you (today, in priority order)

1. **Step 1** — Route53 IAM perms. Unblocks `cicd-followup-fromlookup`.
2. **Step 2** — merge the 7 branches. The doc-refresh branch in
   particular keeps `todo/README.md` honest about what's outstanding,
   so it's worth landing early in the queue.
3. **Step 3** — delete `HOSTED_ZONE_ID` secret (after step 2's
   fromLookup branch deploys clean to prod).
4. **Step 4** — `specodex.com` cutover whenever you want; doesn't
   block anything else.

---

## What the agent has already done for you

- Issued the ACM cert for `specodex.com` + `www.specodex.com` (Stage 4
  pre-flight). Validation CNAMEs in zone, cert `ISSUED`, ARN noted in
  section 4 above.

## What the agent still cannot do

- IAM writes (section 1) — needs your "go ahead" if you want it run
  for you; otherwise just paste the snippet.
- `gh secret set/delete` (sections 3, 4a) — operator-only by design.
- Branch merges (section 2) — your call.
- Any prod deploy (section 4b) — gated on environment approval anyway.
