# Local dev visibility: testing the auth feature on laptops + phones

Status: 📐 plan / how-to. The current config already supports LAN access
out of the box; this doc captures what works, the gotchas, and how to
get real-time visibility on both layers while you're testing on a
device that isn't the one running the servers.

## Why this doc

Auth is harder to gut-check on the laptop than the catalog UI. You
want to:

1. Register / confirm / login from a phone browser to make sure the
   modal flow doesn't break on iOS Safari or Chrome Android.
2. Watch backend logs in real time so when something 401s, you see
   the verifier message before the phone screen has even reloaded.
3. Catch regressions in non-auth code while the app is on the
   network — touch panels, mobile layout, unit toggle behavior.

The Phase 4 PR (#2) is the first feature where "works on localhost"
genuinely doesn't cover the surface area. Hence this doc.

## Pre-deploy safety: read this first

Auth deploy ordering lives in [`todo/AUTH.md`](AUTH.md) under
"Deploy ordering — read this before pushing". Don't merge PR #2
without walking those six steps. The summary:

1. Merge → CI deploys AuthStack (Cognito pool created).
2. Register `nick@advin.io` via the production AuthModal.
3. `./scripts/promote-admin.sh prod nick@advin.io`.
4. Log out + back in (group claim only appears on token refresh).
5. Verify ADMIN pill renders + AdminPanel works.
6. `./Quickstart smoke <prod-url>` to confirm canonical endpoints.

The "test it locally first" sections below are how you de-risk
steps 2–5 before doing them on the production user pool.

---

## Tier 1 — LAN access (zero setup, works today)

**TL;DR:** start `./Quickstart dev`, find your laptop's LAN IP, point
the phone browser at `http://<lan-ip>:3000`. That's it.

### Why it just works

`app/frontend/vite.config.ts` already has:

```ts
server: {
  host: '0.0.0.0',         // bind all interfaces, not just loopback
  port: 3000,
  allowedHosts: true,      // accept any Host header (so 192.168.x.x:3000 works)
  proxy: {
    '/api': { target: 'http://localhost:3001', changeOrigin: true },
  },
}
```

The proxy is the unsung hero: the SPA makes relative `/api/*` calls,
Vite proxies them to the backend **server-side** (not browser-side),
so there's no CORS dance and no `VITE_API_URL` to set per network.
Your phone hits `http://192.168.1.42:3000/api/products` and Vite
forwards to `http://localhost:3001/api/products` invisibly.

The backend (`app/backend/src/index.ts:129` — `app.listen(config.port)`)
binds `0.0.0.0` by Express default. No backend config needed.

### Getting on the LAN

```bash
# Find your laptop's LAN IP
ipconfig getifaddr en0          # macOS Wi-Fi
ipconfig getifaddr en1          # macOS Ethernet
# Or just look at System Settings → Wi-Fi → Details

# Start dev servers
./Quickstart dev

# On the phone (same Wi-Fi)
http://<that-ip>:3000
```

If you're on a coffee-shop network with client isolation, this won't
work — you'll need Tier 2.

### Auth-specific: what works on the LAN over plain HTTP

- ✅ Register / confirm / login / logout flows (Cognito proxy through
  the backend; phone never talks to Cognito directly)
- ✅ JWT in `localStorage` (no `Secure` cookie hangups)
- ✅ Auto-refresh ~60s before id-token expiry
- ✅ Admin gating (assuming the admin user is promoted in your dev pool)
- ⚠️ Verification emails — Cognito's default sender hits the SES
  sandbox cap fast on a fresh dev pool; if a confirm email never
  arrives, check the pool config or use the bypass (Tier 3 below)

### Auth-specific: what *won't* work on plain HTTP

- ❌ "Add to Home Screen" PWA install (HTTPS-required on iOS/Android)
- ❌ `crypto.subtle` (HTTPS-only) — not currently used by AuthContext
  but worth knowing
- ❌ Service workers — not used today, would need HTTPS later

---

## Tier 1.5 — Real-time visibility while you test

`./Quickstart dev` writes backend and frontend output to log files
**instead of stdout** (see `cli/quickstart.py:cmd_dev` — they're
piped to `LOG_DIR/{backend,frontend}.log`). That's annoying when
you're debugging interactively but it's exactly right for "tail in
another terminal while the phone drives the UI."

### Backend log tail

```bash
# In a second terminal, while ./Quickstart dev runs:
tail -f .logs/backend.log

# Filter for auth events specifically:
tail -f .logs/backend.log | grep -E '\[auth\]|/api/auth/|401|403'

# Watch for slow requests:
tail -f .logs/backend.log | grep -E 'ms\)$' | awk '$NF > 500'
```

`.logs/` is repo-root-relative and gitignored. Source of truth is
`cli/quickstart.py` (`LOG_DIR = ROOT / ".logs"`).

### Frontend / Vite log tail

```bash
tail -f .logs/frontend.log
```

Vite logs HMR updates and proxy errors here. If a `/api/*` call
401s, you see the proxy line *before* the phone screen has finished
re-rendering.

### Phone browser inspector

Plain stdout doesn't show you the phone's `console.log` or network
tab. Two options, both free:

- **iOS Safari:** Settings → Safari → Advanced → Web Inspector ON,
  plug into laptop, open Safari on Mac → Develop menu → your phone
  → the page tab. Full DevTools. Best path for iOS.
- **Android Chrome:** Enable USB debugging on phone, plug in,
  desktop Chrome → `chrome://inspect/#devices`. Full DevTools.
- **Both, no-cable option:** add a `<DebugOverlay />` component
  rendered behind `import.meta.env.DEV` that surfaces the last 20
  console messages and the last 20 fetch calls in a fixed-position
  panel. Not built today; one afternoon's work if pure log-tailing
  is too clumsy.

### Combined "watch everything" pane

If you live in tmux:

```bash
# Pane 1: ./Quickstart dev
# Pane 2: tail -f .logs/backend.log
# Pane 3: tail -f .logs/frontend.log
# Pane 4: aws logs tail --follow --filter-pattern '[auth]' /aws/lambda/...
#         (when you're testing against a deployed dev stage, not local)
```

---

## Tier 2 — Public HTTPS via tunnel (when LAN won't do)

Reach for this when:

- You're on a network with client isolation (coffee shop, conference)
- You need real HTTPS (PWA install, OAuth callback testing if/when
  that ships in Phase 6, sharing a working URL with a non-coworker)
- You want a stable URL that survives switching networks

### Cloudflared tunnel (recommended over ngrok)

Free, no account required for ad-hoc tunnels, no session limit:

```bash
brew install cloudflared
./Quickstart dev                          # in one terminal
cloudflared tunnel --url http://localhost:3000   # in another
# → prints https://random-words-12345.trycloudflare.com
```

The Vite `allowedHosts: true` config already accepts the random
hostname — no per-tunnel config update.

### ngrok (if you already have a paid account)

`ngrok http 3000` works the same way. Free tier puts a banner page
on first load and rotates the URL each session, which is fine for
spot-checks but annoying for repeated test cycles.

### CORS gotcha (won't bite you today, will later)

The backend currently runs `cors({ origin: '*' })`
(`app/backend/src/index.ts:27`), so tunnel access works without
config. **The Phase 5 hardening item will tighten this to a stage
allowlist.** When that lands, add `http://192.168.*` and your
preferred tunnel domain to the dev-stage allowlist or you'll get
opaque CORS rejections on the phone.

---

## Tier 3 — Real Cognito flow against a deployed dev stage

Plain LAN access lets you exercise the *backend's* auth code, but
the user pool it talks to is whatever's in `app/.env`'s
`COGNITO_USER_POOL_ID` (probably empty on a fresh checkout, in
which case `requireAuth` returns 503 "Auth not configured"). To
exercise the real Cognito flow end-to-end before touching prod:

1. **Deploy AuthStack to the dev stage:**
   ```bash
   ./Quickstart deploy --stage dev
   ```
   Creates a dev-only user pool. SSM params land at
   `/datasheetminer/dev/cognito/{user-pool-id,user-pool-client-id}`.

2. **Pull the IDs into your local `.env`:**
   ```bash
   POOL_ID=$(aws ssm get-parameter --name /datasheetminer/dev/cognito/user-pool-id --query Parameter.Value --output text)
   CLIENT_ID=$(aws ssm get-parameter --name /datasheetminer/dev/cognito/user-pool-client-id --query Parameter.Value --output text)
   echo "COGNITO_USER_POOL_ID=$POOL_ID" >> app/.env
   echo "COGNITO_USER_POOL_CLIENT_ID=$CLIENT_ID" >> app/.env
   ```
   (Env-var names per `app/backend/src/config/index.ts`:
   `COGNITO_USER_POOL_ID` and `COGNITO_USER_POOL_CLIENT_ID`. Don't
   abbreviate the second one — the verifier silently 503s if it's
   empty.)

3. **Restart `./Quickstart dev`** so the backend picks up the new
   env vars.

4. **Register yourself + bootstrap admin:**
   ```bash
   # In the SPA on phone or laptop: register nick@advin.io,
   # confirm via the email code Cognito sends.
   ./scripts/promote-admin.sh dev nick@advin.io
   # Log out + back in to refresh the token's group claim.
   ```

5. **Now everything you do locally hits a real Cognito pool.** This
   is the highest-fidelity test before hitting prod — same
   verifier code path, real JWT signatures, real refresh flow.

### Tearing down the dev pool

If you're going to land destructive schema changes on the user
pool:

```bash
aws cloudformation delete-stack --stack-name DatasheetMiner-Dev-Auth
```

The `removalPolicy: DESTROY` is set for non-prod stages
(`auth-stack.ts`), so this nukes the pool and all its users
cleanly. You'll need to re-register and re-promote next time.

---

## Risks and gotchas

- **Phone-cached frontend bundles.** Vite HMR updates desktop
  immediately; phone Safari sometimes serves a cached SPA on
  reconnect. If a deployed change isn't showing up on phone, hard
  reload (long-press the refresh icon → "Reload Without Cache").
- **Backend restart kills tokens? No.** Tokens in `localStorage`
  survive backend restarts; the backend is stateless. The verifier
  rebuilds on first request after restart.
- **Email deliverability on dev pool.** Cognito's default sender
  hits the SES sandbox and is rate-limited. If a confirm email
  doesn't arrive after 60s, check the pool's CloudWatch logs and
  consider whether to land Phase 5 SES verified-identity work
  before doing extensive dev testing.
- **Admin promotion needs token refresh.** You'll log in, run the
  promote script, and not see the ADMIN pill until you log out and
  back in. This bites every fresh dev pool.
- **HTTPS-only browser features will silently fail on plain HTTP
  LAN.** If a feature you test "doesn't work on phone but works on
  laptop," check whether it requires a secure context before
  blaming the code.

## What this unblocks

- Phase 4 PR (#2) acceptance testing without merging — load the
  branch on phone via LAN, register against a dev Cognito pool,
  exercise the modal on a small viewport.
- Future mobile / PWA work — the Tier 2 tunnel is what you'll use
  for "Add to Home Screen" testing.
- Confidence in deploy step 2 (register + confirm) on prod — if it
  works against the dev pool from a phone, it'll work against prod.

## Triggers

Read this doc before:

- Doing any responsive / touch / mobile-layout work.
- Testing the auth modal flow on a real device (registration,
  password reset, MFA if Phase 5 lockout adds it).
- Investigating a "works on my machine" report from anyone using
  the deployed staging.
- Deciding whether to spend time on a PWA/install story —
  Tier 2 unblocks that without committing to it.
