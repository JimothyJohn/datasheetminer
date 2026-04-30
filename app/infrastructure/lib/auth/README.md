# Auth — Phase 1 scaffold

This directory holds the Cognito user pool stack for Specodex. It is
**not yet wired into the CDK app** — `bin/app.ts` does not import
`AuthStack`, so a `cdk synth` from master synthesizes the existing
three stacks unchanged.

This is intentional. Landing the construct on its own branch keeps
the merge surface zero and lets sibling work (e.g. CICD followups)
ship without conflicts.

## What's here

- `auth-stack.ts` — `AuthStack`: UserPool, web client, `admin` group,
  SSM parameters, outputs. See file header for the rationale per
  decision.
- `index.ts` — re-export.

## Wiring (Phase 2)

When the rest of Phase 1 is reviewed and the backend middleware is
ready to consume the IDs, wire as follows in `bin/app.ts`:

```ts
import { AuthStack } from '../lib/auth';

const authStack = new AuthStack(app, `${prefix}-Auth`, config, {
  env: config.env,
  description: `Cognito user pool for Specodex (${stage})`,
});

// Make sure ApiStack is deployed after Auth so the SSM params exist
// when the Lambda starts up.
apiStack.addDependency(authStack);
```

The API Lambda already has SSM read access scoped to
`${config.ssmPrefix}/*` (see `api-stack.ts:50`), so adding parameters
under `${ssmPrefix}/cognito/*` requires no IAM change.

The backend's `loadSsmSecrets()` (`backend/src/config/index.ts:54`)
will need two new parameter names appended:

```ts
const paramNames = [
  `${ssmPrefix}/stripe-lambda-url`,
  `${ssmPrefix}/cognito/user-pool-id`,
  `${ssmPrefix}/cognito/user-pool-client-id`,
];
```

## Local synth check

From the worktree root:

```bash
cd app/infrastructure
npm install
npx cdk synth --app "node -e \"\
  const cdk = require('aws-cdk-lib');\
  const { AuthStack } = require('./lib/auth');\
  const { getConfig } = require('./lib/config');\
  const app = new cdk.App();\
  new AuthStack(app, 'SmokeAuth', getConfig());\
  app.synth();\
\""
```

Or just `npx tsc --noEmit` from `app/infrastructure/` to confirm the
file type-checks against the existing CDK lib version.

## What this does NOT do (yet)

- No Lambda wiring — Phase 2.
- No SES verified-identity sender — Phase 5.
- No advanced security mode (lockout) — Phase 5; off by default
  because it bills per MAU.
- No identity providers (Google / GitHub) — Phase 6 stretch.
