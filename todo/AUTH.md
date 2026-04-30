# Auth plan: login + register for Specodex

Status: 📐 planned. No auth in the app today. The site is read-only in
public mode (`APP_MODE=public`) and fully open in admin mode
(`APP_MODE=admin`); there is no user concept on the frontend and only a
trust-the-header `x-user-id` placeholder on the backend's Stripe
middleware.

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

**Deliverable:** Stripe checkout uses the authed `sub`; `APP_MODE` env
variable is replaced (or made a fallback) by the Cognito `admin`
group.

Files:

- `app/backend/src/routes/subscription.ts:41` — drop the `user_id`
  field from the checkout request body. Pull from `req.user.sub`
  after stacking `requireAuth`. Frontend no longer sends a user_id;
  it just sends the auth header.
- `app/backend/src/services/stripe.ts` — same swap on the
  `reportUsage` call. The `user_id` parameter still exists on the
  Stripe Lambda's API; we keep passing the value, it just comes from
  the JWT now.
- `app/backend/src/middleware/adminOnly.ts` — drop the
  `config.appMode` check. Sole gate is `req.user.groups.includes(
  'admin')`. Update the docstring.
- `app/backend/src/config/index.ts` — `appMode` is no longer load-
  bearing for auth. Either remove it, or keep it as a feature flag
  for "show admin UI by default" on the local dev box (cheaper than
  promoting your dev account to the admin group every fresh deploy).
- `app/backend/src/index.ts` — the `readonlyGuard` mount on
  `/api` (line 39) becomes redundant once auth is in place: a write
  endpoint is gated by `requireAuth + requireAdmin`, which already
  rejects unauthenticated requests. Leave the guard in place during
  the soak — it's a belt for the suspenders — and remove in a
  followup branch once we're confident every write route has the
  middleware stack.

**CDK:** Add a `bootstrapAdmin` script (`scripts/promote-admin.sh`)
that takes an email and adds the user to the `admin` Cognito group
via `aws cognito-idp admin-add-user-to-group`. This is how Nick gets
admin powers on a fresh stack without `APP_MODE=admin` shortcuts.

**Verify:** Two browsers — one logged in as admin (sees AdminPanel,
can write), one as regular user (clean read-only UI). Same backend
URL, same `APP_MODE=public` env.

---

## Phase 5 — Production hardening

These are the items that turn the working system into a deployable
one. Defer until Phase 1–4 are green locally.

- **SES verified identity for verification emails.** Default Cognito
  email comes from `no-reply@verificationemail.com` and is
  sandbox-rate-limited. Move to a verified `noreply@specodex.com`
  identity (Route53 records + SES verification) and configure the
  user pool's `EmailConfiguration` to use it.
- **CSP headers** on the API Gateway response and on the CloudFront
  distribution serving the SPA. Reduces the blast radius of an XSS
  on a localStorage token. `script-src 'self'` is the load-bearing
  directive.
- **CORS tighten.** Drop `origin: '*'` once the SPA origin is known
  (`https://www.specodex.com`). Required if we ever switch to cookie
  auth.
- **Refresh-token revocation on logout.** `RevokeToken` API call so a
  stolen refresh token can't be reused.
- **Lockout policy.** Cognito has it built-in but it's off by default
  in the CDK construct — set `advancedSecurityMode` to ENFORCED for
  prod (incurs $0.05/MAU; off for dev/staging).
- **Audit logging.** Funnel `/api/auth/*` requests through CloudWatch
  with a structured logger so failed-login spikes show up in alarms.

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
  once per stage. The `scripts/promote-admin.sh` helper covers this.
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
