# PHASE 5 RECOVERY — get the stranded auth-hardening work onto master

## Status

`gh pr list` says PRs #3, #5, #6, #7, #8 (Phases 5a, 5c, 5d, 5e, 5f) are MERGED.
`origin/master` says only Phases 1–4 + 5b are actually shipped. The other five
were merged into the **`feat-auth-phase1` PR branch** instead of into master,
or merged to master and rolled back, depending on the phase. Net effect:
**~1.4k lines of auth-hardening code are not on production.**

Phase work that's still missing from master:

| Phase | Commit | Footprint | Where it currently lives |
|-------|--------|-----------|--------------------------|
| 5a SES email sender | `a14613a` | 5 files, +202/-17 | local `feat-auth-phase5a-ses`; also on `origin/feat-auth-phase1` |
| 5c refresh-token revocation | `a679fdf` | 5 files, +135/-1 | local `feat-auth-phase5c-revoke`; also on `origin/feat-auth-phase1` |
| 5d CSP + HSTS headers | `3ef96a7` | 4 files, +296 | local `feat-auth-phase5d-csp` only — gh says merged with SHA `c63df04` but that SHA is not in `origin/master` (suspected revert/force-push) |
| 5e auth audit logging | `28d6fdc` | 3 files, +400/-6 | local `feat-auth-phase5e-audit`; also on `origin/feat-auth-phase1` |
| 5f WAF CloudWatch alarms | `ae1144c` | 5 files, +365 | local `feat-auth-phase5f-alarms` only — base was `feat-auth-phase5b-waf` (already merged + deleted) |

## Open question to resolve before proceeding

**Why isn't Phase 5d on master?** GitHub PR #6 reports MERGED with merge commit
`c63df04…d54b29d`, base = `master`. That SHA does not exist in `origin/master`'s
history. Either someone reverted the merge off-band, or the PR was retargeted,
or `origin/master` was force-reset. Until we know, re-applying 5d blindly may
re-introduce something that was deliberately rolled back.

Action: check the GitHub UI for PR #6 to see if there's a follow-up revert
commit, a "merged then closed" history note, or a comment explaining why it
came out. If 5d was reverted for cause, we should NOT cherry-pick it; reopen
the conversation with whoever did the revert.

## Recovery plan (recommended)

One stacked PR rather than five small ones — the phases were originally
sequenced to land together, the test surface is small, and reviewers would
rather look at the auth-hardening bundle once than five times.

### Step 1 — fresh branch off current master

```sh
git checkout master
git pull --ff-only
git checkout -b feat-auth-phase5-tail
```

### Step 2 — cherry-pick the phase commits in order

Order matters: 5a / 5c / 5e all touch the auth backend; 5d / 5f touch
infrastructure. Pick auth first, infra second, so any rebase conflict is
isolated to the auth file cluster.

```sh
git cherry-pick a14613a   # 5a SES
git cherry-pick a679fdf   # 5c revoke
git cherry-pick 28d6fdc   # 5e audit
git cherry-pick 3ef96a7   # 5d CSP   (only if the open question above is resolved)
git cherry-pick ae1144c   # 5f alarms
```

Expected conflict surface, by file:

- `app/backend/src/routes/auth.ts` — 5c and 5e both edit. 5e adds audit logging
  lines; 5c adds revocation lines. Order is 5c then 5e, so 5e's hunk should
  apply on top cleanly. If not, hand-resolve and re-run `npm test`.
- `app/infrastructure/lib/config.ts` — 5a adds SES env reads. Should not
  collide with current master.
- `app/infrastructure/lib/auth/auth-stack.ts` — 5a wires SES into the user
  pool. If `auth-stack.ts` was edited on master since the phase was authored,
  re-thread the wiring.
- `app/infrastructure/lib/frontend-stack.ts` — 5d attaches the response-
  headers policy to the CloudFront distribution. Single insertion point.
- `app/infrastructure/lib/waf/site-web-acl.ts` — 5f reads metric names off
  the existing WAF stack. Read the current shape before assuming the field
  layout 5f expected is still there.

### Step 3 — local verification

```sh
./Quickstart verify
```

Mirrors CI exactly. Red here = red on the PR. Specifically watch for:

- `app/backend` tests — `auth-audit.test.ts` (5e) and `AuthContext.test.tsx`
  (5c) are the two largest additions; both have to pass.
- `app/infrastructure` tests — `auth-stack.test.ts` (5a),
  `site-response-headers-policy.test.ts` (5d), `waf-alarms.test.ts` (5f).
- CDK synth (`cdk synth` via `verify`) — the response-headers-policy and
  WAF-alarms additions both register new constructs at synth time. Any drift
  from the current stack shape will surface here.

### Step 4 — push and open one PR

```sh
git push -u origin feat-auth-phase5-tail
gh pr create --base master --head feat-auth-phase5-tail \
  --title "auth Phase 5 tail: 5a SES + 5c revoke + 5d CSP + 5e audit + 5f alarms" \
  --body "$(cat <<'EOF'
## Summary
- Recovers Phase 5a/5c/5d/5e/5f from stranded PR branches that were merged
  into the Phase 1 PR branch (or rolled back) instead of master.
- Each commit is the original phase commit cherry-picked verbatim;
  conflicts (if any) are noted in the per-commit messages.

## Why this PR exists
PRs #3/#5/#7 were merged into `feat-auth-phase1`, not master. PR #8 was
based on `feat-auth-phase5b-waf` which had already been merged and deleted.
PR #6 (5d) shows MERGED on GitHub but its merge commit doesn't appear in
master — suspected off-band revert; re-applying here unless that revert
had a reason.

## Test plan
- [ ] `./Quickstart verify` green locally before push
- [ ] CI green
- [ ] `cdk diff` against the current prod stack shows ONLY: SES domain
      identity (5a), CSP/HSTS response-headers policy (5d), WAF alarms (5f)
- [ ] After deploy, `curl -I https://datasheets.advin.io` shows the new
      `Content-Security-Policy` and `Strict-Transport-Security` headers
- [ ] After deploy, `aws cognito-idp list-user-pool-clients` shows the
      refresh-token revocation flag enabled (5c)
- [ ] After deploy, trigger a sign-in and grep CloudWatch for the audit log
      record format added by 5e
EOF
)"
```

### Step 5 — clean up after merge

Once the PR lands on master:

```sh
git checkout master && git pull --ff-only

# Tear down the five stranded worktrees
git worktree remove /Users/nick/github/specodex-ses
git worktree remove /Users/nick/github/specodex-revoke
git worktree remove /Users/nick/github/specodex-csp
git worktree remove /Users/nick/github/specodex-audit
git worktree remove /Users/nick/github/specodex-alarms

# Delete the stranded local branches (force-delete; they aren't strictly
# merged because the cherry-picks have new SHAs)
git branch -D feat-auth-phase5a-ses feat-auth-phase5c-revoke \
  feat-auth-phase5d-csp feat-auth-phase5e-audit feat-auth-phase5f-alarms

# And the now-redundant origin tracking branch
git push origin --delete feat-auth-phase1
```

## Fallback option

If verify is red and the conflicts go beyond a few lines, **back out** —
abort the cherry-pick chain (`git cherry-pick --abort`), open one PR per
phase, and let reviewers stage them. The bundle is an ergonomic preference,
not a correctness requirement.

## Why not just merge `origin/feat-auth-phase1` into master?

Tempting — it already has 5a/5c/5e merged into it. But:

1. It does **not** have 5d (only on local `feat-auth-phase5d-csp`).
2. It does **not** have 5f (only on local `feat-auth-phase5f-alarms`,
   based on the deleted `feat-auth-phase5b-waf`).
3. It's also missing the rust-era frontend cleanup that just landed on
   master, so a back-merge would create a noisy reconciliation commit.

Cherry-picking the five focused commits is cleaner.
