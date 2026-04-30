# Auth plan: login + register for Specodex

Status: 🔨 **Phases 1–4 in flight on the `feat-auth-phase1` worktree
(`/Users/nick/github/specodex-auth`).** Cognito stack scaffolded and
wired into `bin/app.ts`; backend middleware + Cognito proxy routes
shipped (414 tests pass); frontend `AuthContext` + `AuthModal` +
`AccountMenu` shipped (280 tests pass); Stripe routes + admin gating
swapped to Cognito-group with `scripts/promote-admin.sh` bootstrap.
**Not deployed, not merged to `master`.** On `master`, the site is
still read-only in public mode (`APP_MODE=public`) and fully open in
admin mode (`APP_MODE=admin`); the unverified `x-user-id` placeholder
still lives in `middleware/subscription.ts:11`.

**Next up:** Deploy ordering — see [Phase 4 deploy ordering](#deploy-ordering--read-this-before-pushing)
below. Phases 5+ (production hardening, stretch) follow once the
cutover is soaked.

This doc is the **how** for adding email/password login, registration,
and session management. It does not cover OAuth providers (deferred —
see Phase 6 stretch).

## Why now

Three things in the codebase are pointing at the same gap:

1. `app/backend/src/middleware/subscription.ts:11` reads
   `x-user-id` from the request header without verifying anything. Any
   client can claim to be any user. This is fine while billing is off
   (the middleware is unused in routes today) but blocks turning Stripe
   on.
2. `routes/subscription.ts` accepts `user_id` in the request body for
   `POST /checkout`. Same trust problem — a logged-out browser can
   create a checkout session under someone else's identity.
3. `APP_MODE` is a deploy-time global. There's no way to give one user
   admin powers on the public deployment without flipping the whole
   stack into admin mode and exposing every admin endpoint to the
   internet. Role-based auth removes that all-or-nothing toggle.

## The thesis

**Use Cognito.** Reasoning:

- Already on AWS, CDK-deployed, SDK clients in the bag. Adding a user
  pool is one stack file.
- Email verification, password reset, lockout, password policy, MFA
  scaffolding are all built in. Hand-rolling these is the bulk of the
  work and the bulk of the foot-guns.
- Free tier covers 50K MAUs — well past anything Specodex needs for
  the foreseeable future.
- JWT verification on the API side is a ~30-line middleware
  (`aws-jwt-verify`), no shared session store needed — fits the
  Lambda-stateless model.

The alternative (bcrypt + JWT + DynamoDB user table + reset-token
emails via SES) is doable but adds three weeks of surface area for no
upside on a solo project. Pick Cognito; revisit only if a concrete
limitation hits.

**JWT in `Authorization: Bearer` header**, not cookies. Reasoning:

- Backend currently runs `cors({ origin: '*' })`. Cookie auth needs
  `credentials: true` + an explicit origin allowlist + `SameSite`
  decisions per environment. Bearer tokens sidestep all of that.
- Lambda + API Gateway is the deploy target; cookie-based session
  refresh doesn't compose well with a stateless function.
- Tradeoff acknowledged: localStorage tokens are XSS-readable. CSP
  headers (Phase 5) close most of that gap; the rest is acceptable
  risk for a B2B engineering tool.

**Read endpoints stay public.** SEO depends on them being crawlable.
Auth gates writes (uploads, build saves) and per-user endpoints
(subscription, account). The line is: if logging out should hide it,
gate it; otherwise leave it open.

---

## Phase 1 — Cognito user pool (CDK)

**Status:** ✅ shipped on `feat-auth-phase1` (commits `0a8298d`,
`4d7004e`). `app/infrastructure/lib/auth/auth-stack.ts` defines the
pool, web client, `admin` group, SSM params (`${ssmPrefix}/cognito/*`),
and outputs. Wired in `bin/app.ts` as a dependency of `ApiStack`. Synth
clean; not yet deployed to any stage.

**Deliverable:** a deployed user pool + app client, IDs surfaced via
SSM parameters and stack outputs.

Files:

- `app/infrastructure/lib/auth-stack.ts` — new file. `UserPool` with:
  - `signInAliases: { email: true }` (email as username)
  - `selfSignUpEnabled: true`
  - `autoVerify: { email: true }` (Cognito sends the verification
    code via its default SES sandbox; switch to a verified SES
    identity in Phase 5 to lift the sandbox cap)
  - Password policy: 12 chars min, mixed case + number, no symbol
    requirement (engineers paste-from-vault more than they type)
  - `accountRecovery: AccountRecovery.EMAIL_ONLY`
  - `removalPolicy: RETAIN` for prod, `DESTROY` for dev/staging
    (mirrors the existing `database-stack.ts` pattern)
  - User group: `admin` — replaces the binary `APP_MODE` gate
    (Phase 4)
- `app/infrastructure/lib/auth-stack.ts` — `UserPoolClient`:
  - No client secret (SPA / public client)
  - OAuth flows: `authorizationCodeGrant` + `implicit` off; we use
    USER_PASSWORD_AUTH (SRP optional, can layer in later)
  - Token validity: ID/access 1h, refresh 30d
- `app/infrastructure/bin/*.ts` — instantiate `AuthStack` alongside
  database/api/frontend stacks. Wire as a dependency of `ApiStack` so
  the API Lambda gets the pool ID at deploy time.
- `app/infrastructure/lib/api-stack.ts` — extend Lambda env with
  `COGNITO_USER_POOL_ID` and `COGNITO_CLIENT_ID`. Or, to match the
  existing pattern, write them to SSM under `${ssmPrefix}/cognito-*`
  and read in `loadSsmSecrets()`.
- `app/infrastructure/lib/frontend-stack.ts` — emit the same two IDs
  as build-time vars on the frontend bundle (`VITE_COGNITO_*`).

**Verify:** `aws cognito-idp describe-user-pool --user-pool-id <id>`
returns the pool with the right policies. `aws cognito-idp list-users`
is empty.

**Cost note:** zero until users sign up. Cognito charges from the
50,001st MAU.

---

## Phase 2 — Backend auth middleware

**Status:** ✅ shipped on `feat-auth-phase1` (commit `6a494d6`).
`aws-jwt-verify`-backed `requireAuth` / `optionalAuth` / `requireGroup`
in `middleware/auth.ts`. Cognito proxy routes for register / confirm /
resend / login / refresh / forgot / reset / me in `routes/auth.ts`.
`requireSubscription` reads `req.user.sub`. `readonlyGuard` exempts
`/auth/*` so login POSTs work in public mode. 408 backend tests pass.
Note: `adminOnly` middleware still env-gated — that retirement is
Phase 4.

**Deliverable:** verified JWT on every protected endpoint; unverified
header trust removed from `requireSubscription`.

Files:

- `app/backend/package.json` — add `aws-jwt-verify` (~30 KB,
  zero-dep, maintained by AWS).
- `app/backend/src/middleware/auth.ts` — new. Two exports:
  - `requireAuth(req, res, next)` — verifies the bearer token,
    attaches `req.user = { sub, email, groups }`. 401 on missing /
    invalid token.
  - `optionalAuth(req, res, next)` — same verify, but missing token
    is fine; `req.user` is undefined. Used on read endpoints that
    can personalize when logged in but don't require it.
- `app/backend/src/middleware/subscription.ts` — replace
  `req.headers['x-user-id']` with `req.user.sub`. Stack `requireAuth`
  before `requireSubscription` in any route that uses it.
- `app/backend/src/middleware/adminOnly.ts` — replace the
  `config.appMode !== 'admin'` gate with
  `req.user?.groups?.includes('admin')`. Keep the env gate as a
  belt-and-braces check for now (`APP_MODE !== 'admin'` *or* user
  not in admin group → 403); drop it in Phase 4 once the cutover is
  proven.
- `app/backend/src/routes/auth.ts` — new. Three endpoints:
  - `POST /api/auth/register` — proxies to Cognito `SignUp`
  - `POST /api/auth/login` — proxies to Cognito
    `InitiateAuth` (USER_PASSWORD_AUTH), returns id/access/refresh
    tokens
  - `POST /api/auth/refresh` — exchanges refresh token for new
    access/id tokens
  - `POST /api/auth/confirm` — confirms signup with the emailed code
  - `POST /api/auth/forgot` + `POST /api/auth/reset` — password
    reset flow
  - `GET /api/auth/me` — returns the authed user's profile;
    `requireAuth`-gated
- `app/backend/src/index.ts` — `app.use('/api/auth', authRouter)`.

**Why proxy through our backend instead of calling Cognito directly
from the SPA:** keeps the client SDK out of the bundle, lets us add
rate-limiting and audit logging in one place, and means the frontend
only ever talks to one origin. Tradeoff: extra network hop on login.
Acceptable; login is rare.

**Tests** (`app/backend/src/__tests__/`): jest + supertest, no live
Cognito. Mock the SDK at module boundary. Cover:

- 401 on missing/invalid/expired token
- 403 on valid token but missing required group
- `req.user.sub` plumbed through to downstream handlers
- Refresh-token rotation works on second call

**Verify locally:**

```bash
# After Phase 1 deploy:
curl -X POST localhost:3001/api/auth/register \
  -H 'content-type: application/json' \
  -d '{"email":"test@example.com","password":"correct horse battery staple"}'

# Confirm via the code emailed to test@example.com, then:
curl -X POST localhost:3001/api/auth/login -d '...'
# → returns tokens
curl localhost:3001/api/auth/me -H "authorization: Bearer <id_token>"
# → 200 with profile
```

---

## Phase 3 — Frontend auth UI

**Status:** ✅ shipped on `feat-auth-phase1` (commit `f45ae0b`).
`AuthContext` provides login / register / confirm / forgot / reset
with token persistence under `specodex.auth.tokens` and an auto-refresh
scheduled ~60s before id-token `exp`. `AuthModal` hosts all five flows
in a single modal with carry-over email between steps; Esc and
click-outside both close. `AccountMenu` swaps "Sign in" for the user's
email + an `ADMIN` pill when the Cognito group is present. The admin
nav is OR-gated: env-mode admin OR Cognito admin group → admin powers
(env retirement is Phase 4). 280 frontend tests pass.

**Tradeoff taken:** modal-with-step-state instead of router. Cheaper to
land, matches the rest of the SPA's single-page state pattern; we lose
deep-linkable `/login` URLs, which is fine because we don't link to
auth pages from anywhere external.

**Deliverable:** Login / Register / Forgot Password pages, persistent
session, "Sign in" → "Account" header swap.

Files:

- `app/frontend/src/context/AuthContext.tsx` — new, parallel to
  `AppContext`. Provides:
  - `user: { sub, email, groups[] } | null`
  - `login(email, password)`, `register(...)`, `logout()`,
    `confirmSignup(code)`, `forgotPassword(email)`,
    `resetPassword(email, code, newPassword)`
  - Token state: `idToken`, `accessToken`, `refreshToken` —
    persisted in `localStorage` under `specodex.auth.*` (existing
    persistence convention; see `safeLoad` in
    `utils/localStorage.ts`)
  - Auto-refresh: a `useEffect` that schedules a refresh at
    `exp - 60s`. On refresh failure → `logout()` and surface a
    re-auth prompt.
- `app/frontend/src/api/client.ts` — extend the request layer to
  attach `Authorization: Bearer ${idToken}` when a token is in
  context. On 401 responses, attempt one refresh; on second 401, log
  out.
- `app/frontend/src/components/Auth/`:
  - `LoginForm.tsx` — email + password + submit
  - `RegisterForm.tsx` — email + password + confirm-password
  - `ConfirmEmail.tsx` — code input shown after register
  - `ForgotPassword.tsx` — email → "we sent a code"
  - `ResetPassword.tsx` — code + new password
  - `AccountMenu.tsx` — header dropdown (logged in: email + Logout;
    logged out: "Sign in" button)
- `app/frontend/src/App.tsx` — wrap with `<AuthProvider>` inside
  `<AppProvider>`. Add a lightweight router (or modal-based
  navigation — the rest of the app uses single-page state, so a
  modal flow is the path of least resistance) for the auth pages.
- `app/frontend/src/components/Welcome.tsx` — add a "Sign in to save
  builds" CTA in the empty state. Logged-in users see their saved
  builds (Phase 6).
- Existing components that already gate on admin (`AdminPanel`,
  `BuildTray`, `ProductManagement`) — switch from "rendered when
  `APP_MODE=admin`" to "rendered when `user.groups.includes('admin')`".

**Tests** (`app/frontend/src/test/`):

- AuthContext: token persistence across reload, refresh-on-401, logout
  clears state
- LoginForm: error display on bad creds, loading state, success
  redirects
- AccountMenu: correct labels logged-in vs logged-out

**Verify:** `./Quickstart dev`, register a test account, confirm via
the email code, log in, hit a protected endpoint from the browser
network tab — Authorization header present, 200 OK.

---

## Phase 4 — Wire Stripe and admin to the authed user

**Status:** ✅ shipped on `feat-auth-phase1` (commits `c94fb5e`,
`c3ed0d9`, `75054cd`). Backend: subscription routes auth-gated,
identity from `req.user.sub`; `adminOnly` is pure Cognito group;
`/health` reports group membership. Frontend: env-OR arm dropped from
admin nav, lazy admin chunks ship in every build (~38KB on disk,
code-split, fetched only for admins); client-side `requireAdmin`
preflight removed. `scripts/promote-admin.sh` lands the SSM-based
bootstrap. 414 backend + 280 frontend tests pass; verify gate green.
**Deploy ordering still applies — read it before merging.**

**One deviation from the original plan:** the doc said to wire
`scripts/promote-admin.sh` into `./Quickstart admin promote <stage>
<email>`. The existing `cli/admin.py` already has a `promote`
subcommand for dev→prod data movement, so reusing the word would
conflate two operations. The script is invoked directly instead;
the deploy-ordering steps below reference it that way.

**Deliverable:** Stripe checkout uses the authed `sub`; `APP_MODE` env
variable is replaced (or made a fallback) by the Cognito `admin`
group.

### Backend changes

- `app/backend/src/routes/subscription.ts:41` — drop the `user_id`
  field from the checkout request body schema. Pull from `req.user.sub`
  after stacking `requireAuth`. Same for `GET /status/:userId` at
  line 16 — drop the path param and read `req.user.sub`.
- `app/backend/src/services/stripe.ts` — `createCheckoutSession`,
  `getSubscriptionStatus`, `isSubscriptionActive`, and `reportUsage`
  all take a `userId` argument today (lines 38, 52, 69, 91). They keep
  the parameter — the Stripe Lambda's wire format still uses
  `user_id` — but every caller now passes `req.user.sub` from the
  middleware.
- `app/backend/src/middleware/adminOnly.ts:14` — drop the
  `config.appMode !== 'admin'` check. Sole gate is
  `req.user?.groups?.includes('admin')`. Stack `requireAuth` before
  it on every admin route. Update the file-top docstring (currently
  says "403 unless APP_MODE === 'admin'").
- `app/backend/src/config/index.ts` — `appMode` is no longer
  load-bearing for auth. Keep it as a *local-dev convenience flag*:
  when `APP_MODE=admin` on `localhost`, auto-render the AdminPanel
  without requiring a real Cognito session. Remove the production
  code paths that read it.
- `app/backend/src/index.ts:33,38,49,138` — the four `config.appMode`
  references. Logging line at 33 stays (still useful as a debug
  string). The `readonlyGuard` mount at line 38–46 stays through the
  soak — it's redundant once every write route has
  `requireAuth + requireAdmin`, but it's a belt for the suspenders.
  Drop in a follow-up branch once we've audited every `POST`/`PUT`/
  `DELETE` and confirmed the middleware stack. Health-check `mode`
  field at line 49 should report Cognito group membership when an
  authed call hits it, otherwise `"public"`.
- `app/backend/tests/subscription.test.ts` — refresh fixtures to send
  `Authorization: Bearer <mock-jwt>` instead of body `user_id`.

### Frontend changes

- `app/frontend/src/api/client.ts:483,496` — `getSubscriptionStatus`
  and `createCheckoutSession` currently take `userId: string` and
  embed it in the URL / body. Drop the parameter; the
  `Authorization: Bearer` header (set via `apiClient.setAuthToken`
  in Phase 3) supplies identity server-side. **No callers exist
  today** — these methods are defined but unused, so the swap is
  zero-risk. The Subscribe button that will eventually call them
  ships post-Phase 4.
- Components currently OR-gated on `APP_MODE` (touched in Phase 3:
  `App.tsx`, `AdminPanel`, `BuildTray`, `ProductManagement`, etc.) —
  drop the env arm of the OR. Sole condition becomes
  `user?.groups.includes('admin')`. Grep for the OR pattern; Phase 3
  introduced it in a known set of files.

### Bootstrap script

`scripts/promote-admin.sh` — new, run once per fresh stack to give
Nick admin powers on a public deployment:

```bash
#!/usr/bin/env bash
# Usage: ./scripts/promote-admin.sh <stage> <email>
# Adds the Cognito user identified by <email> to the 'admin' group on the
# user pool for <stage>. Prereq: user must already be registered + confirmed.
set -euo pipefail
STAGE="${1:?stage required (Dev|Staging|Prod)}"
EMAIL="${2:?email required}"

POOL_ID=$(aws ssm get-parameter \
  --name "/datasheetminer/${STAGE,,}/cognito/user-pool-id" \
  --query 'Parameter.Value' --output text)

aws cognito-idp admin-add-user-to-group \
  --user-pool-id "$POOL_ID" \
  --username "$EMAIL" \
  --group-name admin

aws cognito-idp admin-list-groups-for-user \
  --user-pool-id "$POOL_ID" \
  --username "$EMAIL" \
  --query 'Groups[].GroupName'
```

Wire the script as `./Quickstart admin promote <stage> <email>` —
fits the existing `cli/admin.py` pattern alongside `blacklist`,
`movement`, `purge`.

### Deploy ordering — read this before pushing

The cutover is **not** atomic. There's a window where the env arm is
gone but no one is in the admin group yet, and admin endpoints will
403 until you bootstrap. Order:

1. Merge Phases 1–3 to `master`. Deploy. AuthStack creates the user
   pool; backend routes accept tokens; frontend modal works. **Admin
   gating is still on `APP_MODE=admin` env arm — nothing breaks.**
2. Register `nick@advin.io` via the production modal. Confirm via
   email.
3. Run `./scripts/promote-admin.sh prod nick@advin.io`. The script
   verifies group membership at the end via
   `aws cognito-idp admin-list-groups-for-user`.
4. Log in, confirm the `ADMIN` pill renders and AdminPanel is visible
   (this works through the OR-gate Phase 3 introduced).
5. *Now* merge Phase 4 (drops the env arm). Deploy. Admin gating is
   pure Cognito group; AdminPanel still renders for me, vanishes for
   everyone else.
6. Stage env vars: keep `APP_MODE=admin` on local dev only; remove
   from `app/.env.dev`, `app/.env.prod` deploy configs. The variable
   becomes a localhost convenience.

Doing 5 before 3 strands you out of the AdminPanel on prod. Doing 5
before 1 is a deploy of code that imports a `req.user` that doesn't
exist yet — backend tests catch this, but don't rely on luck.

### Verify

- **Two browsers test.** Logged in as admin → sees AdminPanel, can
  POST to a write endpoint. Logged out / regular user → clean
  read-only UI, write endpoints 401. Same backend URL, same
  `APP_MODE=public` env.
- **Stripe smoke** (when the Subscribe button ships): hit
  `POST /api/subscription/checkout` with no body, just the auth
  header → 200 with a checkout URL whose `client_reference_id` is the
  authed `sub`.
- **Negative test:** old-style `POST /api/subscription/checkout`
  with `{"user_id": "abc"}` and no auth header → 401, not 200. (The
  zod schema should reject the body field outright; double-check.)

---

## Phase 5 — Production hardening

**Status:** 📐 planned. Defer until Phase 1–4 are green and soaked.
These are independent items; ship as small follow-up branches rather
than one mega-PR.

### SES verified identity for verification emails

Default Cognito email comes from `no-reply@verificationemail.com` and
is hard-capped at **50 emails/day** in the AWS sandbox. That cap is
hit by ~10 real users hitting "forgot password" twice each, so this is
not optional past beta.

Concrete steps:

1. `aws ses verify-domain-identity --domain specodex.com` and add the
   returned DKIM CNAMEs to Route53. Wait for verification.
2. `aws ses verify-email-identity --email-address noreply@specodex.com`
   (or use the domain identity directly).
3. Move out of SES sandbox via support ticket — required to email
   non-verified addresses.
4. In `auth-stack.ts`, set
   `email: cognito.UserPoolEmail.withSES({ fromEmail: 'noreply@specodex.com', ... })`.
5. Customize the verification message templates (currently default
   Cognito copy) — set `userVerification.emailSubject` and
   `emailBody` on the `UserPool` props.

### CSP headers

Currently no `responseHeadersPolicy` on either the SPA or `/api/*`
behaviors in `app/infrastructure/lib/frontend-stack.ts`. Add a
CloudFront `ResponseHeadersPolicy` and attach to both behaviors.

Minimum directives for a localStorage-token SPA:

```typescript
const securityHeaders = new cloudfront.ResponseHeadersPolicy(this, 'SecHeaders', {
  securityHeadersBehavior: {
    contentSecurityPolicy: {
      contentSecurityPolicy: [
        "default-src 'self'",
        "script-src 'self'",                   // load-bearing — blocks injected scripts
        "style-src 'self' 'unsafe-inline'",    // Vite + inline component styles
        "img-src 'self' data: https:",
        "connect-src 'self' https://cognito-idp.us-east-1.amazonaws.com",
        "frame-ancestors 'none'",
        "base-uri 'self'",
      ].join('; '),
      override: true,
    },
    strictTransportSecurity: { accessControlMaxAge: Duration.days(365), includeSubdomains: true, override: true },
    contentTypeOptions: { override: true },
    frameOptions: { frameOption: cloudfront.HeadersFrameOption.DENY, override: true },
    referrerPolicy: { referrerPolicy: cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN, override: true },
  },
});
```

`unsafe-inline` for styles is required because of inline component
styles in the React tree; tightening that needs a refactor pass
elsewhere. Keep in scope for a later "CSP tighten" follow-up, not
this phase.

### CORS tighten

`app/backend/src/index.ts:27` mounts `cors(config.cors)`. Today
`config.cors` is `{ origin: '*' }` (verify in
`app/backend/src/config/index.ts`). Replace with stage-aware allowlist:

- `prod` → `['https://datasheets.advin.io', 'https://www.specodex.com']`
- `staging` → CloudFront URL from
  `aws cloudformation describe-stacks --stack-name DatasheetMiner-Staging-Frontend ...`
- `dev` / local → `['http://localhost:5173', 'http://localhost:3001']`

Wire via env (`CORS_ORIGINS=...,...`) read in
`config/index.ts`. Required before any switch to cookie auth, and
table-stakes hardening regardless.

### Refresh-token revocation on logout

Phase 3 `AuthContext.logout()` clears localStorage but doesn't tell
Cognito. Steal the refresh token now, you can mint id-tokens for 30d.

Add:

- `POST /api/auth/logout` in `routes/auth.ts` — calls
  `RevokeToken` on the SDK with the refresh token from the request
  body. `requireAuth`-gated so only the rightful owner can revoke.
- `AuthContext.logout()` — `await apiClient.authLogout(refreshToken)`
  before clearing local state. Best-effort: if the call fails (e.g.
  token already expired), proceed with local clear anyway.

### Lockout / threat detection

Note: `advancedSecurityMode` is **deprecated** as of late 2025 in
favor of "Cognito user pool feature plans" (`Essentials` / `Plus`).
The Plus plan ($0.05/MAU) gets you adaptive auth, compromised-creds
detection, and configurable lockout. CDK `aws-cdk-lib@2.173.4`
(current pin) still uses the old `advancedSecurityMode` enum; check
whether the version we're on at hardening time has migrated to
`featurePlan`.

For now: enable basic lockout via a custom Lambda trigger
(`PreAuthentication`) that counts failed attempts in DynamoDB —
overkill for our scale, so this item probably resolves to "wait until
CDK exposes feature plans, then flip the prod pool to Plus."

### Audit logging

Failed-login spikes are the canary for credential stuffing. Plumb:

- Structured logger in `routes/auth.ts` — emit
  `{ event, email, sub, ip, userAgent, success, errorCode }` on every
  auth attempt. Use the existing logger pattern; don't introduce
  Winston/pino just for this.
- CloudWatch metric filter on log group: count of
  `event=login success=false` per minute, alarm on >20/min for 5min.
- Never log the password or the JWT itself. The `email` field is fine
  (it's the username); hash for higher sensitivity if we ever go B2C.

---

## Phase 6 — Stretch (deferred)

Order roughly by user value, not effort:

- **Saved builds tied to user.** The `build` state in `AppContext`
  currently lives in localStorage only. Add a `POST /api/builds` +
  `GET /api/builds` pair, gate behind `requireAuth`, store under
  DynamoDB `PK=USER#<sub>, SK=BUILD#<id>`. Ties auth to a concrete
  feature instead of being plumbing.
- **Saved searches / alerts.** Same shape as builds; a user can save a
  filter set and (later) get an email when a new product matches.
- **Google / GitHub OAuth.** Add identity providers to the user pool;
  expose on the login page. Cognito hosted UI is the cheapest path
  but breaks the "all UI in our SPA" pattern. Worth it iff sign-up
  conversion is a measurable problem.
- **API keys for programmatic access.** A logged-in user mints a
  long-lived token (separate from the Cognito access token) for
  scripting. Stored hashed in DynamoDB. Necessary if the public
  API gets a developer audience.

---

## Risks and decisions still open

- **Token storage tradeoff.** localStorage chosen over httpOnly
  cookie for CORS simplicity. Revisit if/when XSS becomes a
  realistic threat (i.e. if we ever render user-generated HTML).
- **Email deliverability.** Cognito's default email caps will bite
  if registration is even modestly active. Phase 5 SES move is not
  optional — schedule it before any public sign-up announcement.
- **Migrating existing test users.** None today (zero auth means
  zero accounts). Whenever you test admin-only endpoints in
  staging post-Phase 4, you'll need to register + promote yourself
  once per stage. Run `./scripts/promote-admin.sh <stage> <email>`
  after registering through the AuthModal.
- **Lock-in.** Cognito tokens are JWTs and the user attributes are
  trivially exportable, so a migration to Auth0 / Supabase / WorkOS
  later is bounded effort. Not worth optimizing for now.
- **Apex domain + cookies.** If we ever flip to cookie auth, the
  cookie domain must be `.specodex.com` to span apex + www.
  Recorded here so it's not a surprise.

---

## What this unblocks

- Real Stripe billing — the existing middleware becomes safe to
  enable on routes (search, upload).
- Per-user features (saved builds, alerts, history).
- One deployed environment serving both admin and public UI based on
  role, removing the `APP_MODE` foot-gun.
- Credible "API access" story for a future developer-targeted plan.

## Triggers

Read this doc before:

- Adding any route that needs to know "who is calling."
- Enabling Stripe enforcement on a real route — the
  `requireSubscription` middleware is unsafe without auth landed
  first.
- Touching `APP_MODE` env handling or `adminOnly`/`readonlyGuard`
  middleware — the long-term plan is to retire both.
- Wiring user-generated content (saved builds, comments, uploads
  attributed to a user) — needs `req.user.sub` available.
