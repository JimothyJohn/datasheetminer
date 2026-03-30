# Monetize DatasheetMiner: Auth + Freemium + API Tokens + Pay-as-you-go

## Context

DatasheetMiner is currently a single-user, unauthenticated product spec database. Public deployments are read-only (`APP_MODE=public`), admin is local-only. There are no users, no billing, no API keys. Stripe env vars exist in CDK but are empty/unused.

The goal: convert to an individual auth-driven, freemium, API-token pay-as-you-go data product deployable in nearly its current state. Minimal surgery — new files over editing existing ones.

---

## Architecture Overview

```
Browser (human)                CLI/Script (programmatic)
     |                                |
  Cognito hosted UI              X-API-Key: dsm_xxx
  → JWT in Authorization         → SHA-256 lookup in DynamoDB
     |                                |
     +---------- Express app ---------+
                     |
        auth.ts middleware → req.user = { userId, tier }
                     |
        tierGuard.ts (replaces readonlyGuard)
                     |
        usageMeter.ts (atomic DynamoDB counters)
                     |
        existing routes (unchanged)
```

---

## Phase 1: Auth Foundation (backend only, no billing, no limits)

**Branch**: `add-auth-foundation`

### New files

| File | Purpose |
|------|---------|
| `app/backend/src/types/auth.ts` | `AuthUser`, `Tier`, `ApiKeyRecord` types |
| `app/backend/src/middleware/auth.ts` | Resolves `req.user` from JWT or API key header. Falls back to `{ userId: 'anonymous', tier: 'free' }` |
| `app/backend/src/services/apikeys.ts` | Key generation (`dsm_live_<32hex>`), SHA-256 hashing, DynamoDB CRUD |
| `app/backend/src/routes/keys.ts` | `POST/GET/DELETE /api/keys` — create, list, revoke API keys (JWT-auth required) |
| `app/backend/src/routes/auth.ts` | `POST /api/auth/register`, `POST /api/auth/profile` — user profile CRUD |
| `app/infrastructure/lib/auth-stack.ts` | Cognito User Pool + Client (email signup, SRP auth, hosted UI domain) |
| `app/backend/tests/middleware/auth.test.ts` | Unit tests |
| `app/backend/tests/services/apikeys.test.ts` | Unit tests |

### Edits to existing files (minimal)

- **`app/backend/src/index.ts`** — Add 1 line: `app.use(authMiddleware)` after line 19, mount `keysRouter` and `authRouter`
- **`app/backend/package.json`** — Add `aws-jwt-verify` (AWS-maintained, <10KB, zero transitive deps)
- **`app/infrastructure/bin/app.ts`** — Instantiate `AuthStack`, pass `userPoolId` + `clientId` to `ApiStack`
- **`app/infrastructure/lib/api-stack.ts`** — Add `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID` env vars to Lambda
- **`app/backend/src/config/index.ts`** — Add `cognito.userPoolId`, `cognito.clientId` fields

### DynamoDB schema additions (same table, new PK/SK patterns)

```
PK: USER#{cognitoSub}       SK: PROFILE           → { email, tier, stripeCustomerId, createdAt }
PK: USER#{cognitoSub}       SK: APIKEY#{hash}      → { keyPrefix, name, createdAt, active }
PK: APIKEY#{sha256Hash}     SK: APIKEY#{sha256Hash} → { userId, tier, keyPrefix, name, active, lastUsedAt }
```

API key lookup is a single `GetItem` on `APIKEY#{hash}` — O(1), no scan. User's keys listed via `Query(PK=USER#{id}, SK begins_with APIKEY#)`.

### Auth middleware logic (`auth.ts`)

1. Check `Authorization: Bearer <jwt>` → verify with `aws-jwt-verify` (CPU-only, no network call)
2. Else check `X-API-Key: dsm_xxx` → SHA-256 hash → `GetItem` from DynamoDB (~5ms)
3. Else → `req.user = { userId: 'anonymous', tier: 'free', isAnonymous: true }`
4. Attach `req.user` and call `next()`

### Cognito User Pool (`auth-stack.ts`)

- Email-based signup, auto-verify email
- Password policy: 8+ chars, require digits
- SRP auth flow (no client secret for SPA)
- OAuth callbacks: `https://datasheets.advin.io/callback` + `http://localhost:3000/callback`
- Free tier: 50,000 MAUs included

---

## Phase 2: Frontend Auth

**Branch**: `add-frontend-auth`

### New files

| File | Purpose |
|------|---------|
| `app/frontend/src/context/AuthContext.tsx` | `user`, `isAuthenticated`, `login()`, `logout()`, `signup()`, JWT refresh |
| `app/frontend/src/pages/LoginPage.tsx` | Email + password login form |
| `app/frontend/src/pages/SignupPage.tsx` | Registration form |
| `app/frontend/src/pages/AccountPage.tsx` | Account overview, tier display |
| `app/frontend/src/pages/ApiKeysPage.tsx` | Create/list/revoke API keys |
| `app/frontend/src/components/AuthGuard.tsx` | Route wrapper that redirects to `/login` if unauthenticated |

### Edits to existing files

- **`app/frontend/src/App.tsx`** — Wrap with `<AuthProvider>`, add routes for `/login`, `/signup`, `/account`, `/account/keys`, add login button in header
- **`app/frontend/package.json`** — Add `amazon-cognito-identity-js` (~50KB, no Amplify)

### Auth state management

- JWT stored in memory (not localStorage — security)
- Auto-refresh before expiry via Cognito SDK
- `authClient` wrapper adds `Authorization: Bearer <jwt>` to existing `apiClient` calls
- Unauthenticated users see product data with anonymous limits

---

## Phase 3: Usage Metering & Tier Enforcement

**Branch**: `add-usage-tiers`

### Tier definitions

| Feature | Anonymous | Free (registered) | Pro | Enterprise |
|---------|-----------|-------------------|-----|------------|
| Reads/month | 100 | 1,000 | 50,000 | Unlimited |
| Uploads/month | 0 | 0 | 50 | 500 |
| API keys | 0 | 1 | 5 | 20 |
| Rate limit | 10 req/min | 60 req/min | 300 req/min | 1,000 req/min |

### DynamoDB usage records

```
PK: USAGE#{userId}    SK: 2026-03     → { reads: 847, uploads: 3, extractions: 2 }
PK: USAGE#{userId}    SK: 2026-03-28  → { reads: 42, uploads: 1, extractions: 0 }
```

Updated via `UpdateExpression: ADD reads :incr` (atomic, no race conditions). Monthly SK means each month starts fresh — no cleanup jobs.

### New files

| File | Purpose |
|------|---------|
| `app/backend/src/config/tiers.ts` | Tier limit definitions (reads, uploads, rate limits per tier) |
| `app/backend/src/services/usage.ts` | `increment()`, `getUsage()`, `getHistory()` — atomic DynamoDB counters with 60s in-memory cache |
| `app/backend/src/middleware/tierGuard.ts` | Replaces `readonlyGuard`. Checks `req.user.tier` + request type → allow/deny |
| `app/backend/src/middleware/usageLimiter.ts` | Checks monthly usage against tier limits → 429 if exceeded |
| `app/backend/src/middleware/rateLimiter.ts` | In-memory sliding window per userId (resets on Lambda cold start — acceptably lenient) |
| `app/backend/src/middleware/meter.ts` | Fire-and-forget usage increment on `res.finish` (no added latency) |

### Edit to existing files

- **`app/backend/src/index.ts`** — Replace `readonlyGuard` block (lines 28-31) with `tierGuard` + `usageLimiter` + `meter`

---

## Phase 4: Stripe Billing

**Branch**: `add-stripe-billing`

### Billing model

- **Metered billing**: Stripe tracks usage units, invoices monthly
- Read: $0.001/read (1,000 reads = $1)
- Upload: $0.10/upload
- Extraction: $0.50/extraction
- Free tier enforced application-side (first 1,000 reads free for registered users)

### New files

| File | Purpose |
|------|---------|
| `app/backend/src/services/stripe.ts` | `createCustomer()`, `createSubscription()`, `reportUsage()`, `getPortalUrl()` |
| `app/backend/src/routes/billing.ts` | `POST /api/billing/checkout` (Stripe Checkout), `POST /api/billing/portal`, `GET /api/billing/usage` |
| `app/backend/src/routes/webhooks.ts` | Stripe webhook handler (raw body parsing, signature verification) |
| `app/frontend/src/pages/BillingPage.tsx` | Current plan, upgrade button → Stripe Checkout, billing portal link |
| `app/frontend/src/pages/DashboardPage.tsx` | Usage stats, daily chart, tier badge |

### Webhook events handled

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Create user profile, set tier to 'pro' |
| `customer.subscription.updated` | Sync tier from Stripe plan |
| `customer.subscription.deleted` | Downgrade to 'free' |
| `invoice.payment_failed` | Flag account |

### Edits to existing files

- **`app/backend/src/index.ts`** — Mount `billingRouter`, `webhooksRouter` (raw body for Stripe signatures)
- **`app/backend/package.json`** — Add `stripe`
- **`app/infrastructure/lib/api-stack.ts`** — Add `STRIPE_WEBHOOK_SECRET` env var

---

## Phase 5: Polish

**Branch**: `add-monetization-polish`

- `app/frontend/src/components/UsageChart.tsx` — Daily usage bar chart
- `app/frontend/src/components/TierBadge.tsx` — Visual tier indicator in header
- `app/infrastructure/lib/usage-reporter-stack.ts` — Optional: daily cron Lambda reports usage to Stripe

---

## Files Modified Summary

### Files edited (minimal, additive changes only)

| File | Changes |
|------|---------|
| `app/backend/src/index.ts` | +auth middleware, +new route mounts, replace readonlyGuard → tierGuard |
| `app/backend/src/config/index.ts` | +cognito config fields |
| `app/backend/package.json` | +aws-jwt-verify, +stripe |
| `app/frontend/src/App.tsx` | +AuthProvider wrapper, +auth routes, +login button |
| `app/frontend/package.json` | +amazon-cognito-identity-js |
| `app/infrastructure/bin/app.ts` | +AuthStack instantiation |
| `app/infrastructure/lib/api-stack.ts` | +Cognito + Stripe env vars to Lambda |

### New files created (~25 files across all phases)

Backend: 15 new files (middleware, services, routes, types, tests)
Frontend: 8 new files (pages, context, components)
Infrastructure: 2 new files (auth-stack, usage-reporter-stack)

---

## Verification

### Phase 1 (Auth)
1. `./Quickstart dev` — server starts, all existing endpoints work with anonymous user
2. Create API key via `POST /api/keys` with JWT → get `dsm_live_xxx` key
3. Call `GET /api/products` with `X-API-Key: dsm_live_xxx` → 200 with `req.user` resolved
4. Call with invalid key → 401
5. Call with no auth → 200 as anonymous
6. Run `npm test` in backend

### Phase 2 (Frontend)
1. Navigate to `/login` → login form renders
2. Sign up via Cognito → redirected to `/account`
3. Create API key in `/account/keys` → key displayed once
4. Logout → anonymous browsing still works

### Phase 3 (Tiers)
1. Anonymous: 101st read in a month → 429
2. Free registered: uploads blocked → 403
3. Pro: uploads allowed, 50,001st read → 429
4. Rate limiter: burst 11 requests as anonymous → 429

### Phase 4 (Stripe)
1. Click upgrade → Stripe Checkout opens
2. Complete payment → webhook fires → tier updated to 'pro'
3. `GET /api/billing/usage` → current month's usage
4. Billing portal → manage payment method, view invoices
