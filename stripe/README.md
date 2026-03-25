# DatasheetMiner Payments (Stripe + Lambda)

Rust Lambda function that handles metered token-based billing via Stripe.
Users subscribe, make CLI API calls that query the DB, and get billed per-token at the end of each billing cycle.

**Currently hardcoded to TEST MODE only** — the Lambda refuses to start if `STRIPE_SECRET_KEY` is not a `sk_test_` key.

## Architecture

```
CLI → API Gateway → your backend (app/backend)
                        ↓
                   [records tokens used]
                        ↓
              API Gateway → this Lambda (/usage)
                        ↓
                   Stripe Usage Records
                        ↓
              Stripe invoices at period end
```

### Billing Model

- **Metered subscription**: user pays $0/mo base + per-1K-token usage
- One Stripe Product with one metered Price (configured in Stripe Dashboard)
- Usage records posted after each API call with `input_tokens + output_tokens`
- Stripe aggregates and bills at the end of each billing period

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/checkout` | Create Stripe Checkout session → returns URL |
| `POST` | `/webhook` | Stripe webhook receiver |
| `POST` | `/usage` | Report token usage (called by your backend) |
| `GET` | `/status/{user_id}` | Check subscription status |
| `GET` | `/health` | Health check |

### DynamoDB Table

Table: `datasheetminer-users` (separate from your products table)

| Field | Type | Description |
|-------|------|-------------|
| `user_id` (PK) | String | Your app's user identifier |
| `stripe_customer_id` | String | Stripe customer ID |
| `subscription_id` | String | Stripe subscription ID |
| `subscription_status` | String | active, past_due, canceled, none |
| `created_at` | String | ISO 8601 timestamp |

## Setup

### 1. Stripe Dashboard (Test Mode)

1. Go to https://dashboard.stripe.com/test/products
2. Create a product: "DatasheetMiner API Access"
3. Add a price:
   - **Recurring**
   - **Usage-based** (metered)
   - Price per unit: e.g. `$0.001` per token (or `$0.01` per 1K tokens — your call)
   - Billing period: Monthly
   - Usage aggregation: **Sum during period**
4. Copy the Price ID (`price_...`)

### 2. Webhook

1. Go to https://dashboard.stripe.com/test/webhooks
2. Add endpoint: `https://your-api-gateway-url/webhook`
3. Events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. Copy the Webhook Signing Secret (`whsec_...`)

### 3. Environment Variables

Copy `.env.example` → `.env` and fill in:

```sh
STRIPE_SECRET_KEY=sk_test_...      # From Stripe Dashboard → API Keys
STRIPE_WEBHOOK_SECRET=whsec_...    # From step 2
STRIPE_PRICE_ID=price_...          # From step 1
AWS_REGION=us-east-1
USERS_TABLE_NAME=datasheetminer-users
FRONTEND_URL=http://localhost:3000
```

### 4. DynamoDB Table

Create the table (CLI or Console):

```sh
aws dynamodb create-table \
  --table-name datasheetminer-users \
  --attribute-definitions AttributeName=user_id,AttributeType=S \
  --key-schema AttributeName=user_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 5. Build & Deploy

```sh
# Install cargo-lambda (one time)
cargo install cargo-lambda

# Build for Lambda (ARM64 = cheapest)
cargo lambda build --release --arm64

# Deploy
cargo lambda deploy datasheetminer-payments \
  --region us-east-1 \
  --env-file .env

# Create a function URL (or use API Gateway)
aws lambda create-function-url-config \
  --function-name datasheetminer-payments \
  --auth-type NONE
```

For production you'd put API Gateway in front, but for test mode a Lambda Function URL works fine.

## Integration with app/backend

Your existing Express backend (`app/backend`) should call `/usage` after each CLI API request completes. Minimal integration:

```typescript
// In app/backend/src/routes/ — after processing a CLI request:

const PAYMENTS_URL = process.env.PAYMENTS_LAMBDA_URL; // e.g. https://xxx.lambda-url.us-east-1.on.aws

async function reportTokenUsage(userId: string, inputTokens: number, outputTokens: number) {
  if (!PAYMENTS_URL) return; // Skip if payments not configured
  await fetch(`${PAYMENTS_URL}/usage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, input_tokens: inputTokens, output_tokens: outputTokens }),
  });
}

// Before returning a response that used tokens:
async function handleCliQuery(req, res) {
  const result = await queryFromDb(req.body.query);  // your existing logic
  await reportTokenUsage(req.userId, result.inputTokens, result.outputTokens);
  res.json(result);
}
```

Add a subscription check before allowing API access:

```typescript
async function requireActiveSubscription(req, res, next) {
  const resp = await fetch(`${PAYMENTS_URL}/status/${req.userId}`);
  const data = await resp.json();
  if (data.subscription_status !== 'active') {
    return res.status(402).json({ error: 'Active subscription required' });
  }
  next();
}
```

## Local Testing

```sh
# Run locally (emulates Lambda)
cargo lambda watch

# Test checkout
curl -X POST http://localhost:9000/checkout \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "test-user-1", "email": "test@example.com"}'

# Test usage reporting
curl -X POST http://localhost:9000/usage \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "test-user-1", "input_tokens": 500, "output_tokens": 200}'

# Test status
curl http://localhost:9000/status/test-user-1
```

For webhook testing locally, use the [Stripe CLI](https://stripe.com/docs/stripe-cli):

```sh
stripe listen --forward-to localhost:9000/webhook
```

## Cost Optimization Notes

- **ARM64 Lambda**: ~20% cheaper than x86
- **PAY_PER_REQUEST DynamoDB**: no idle cost, perfect for low/variable traffic
- **Metered billing**: no upfront pricing decisions, charge what you spend on LLM tokens
- **Single Lambda**: one function handles all routes, minimal cold start surface
- **Rust**: fastest cold starts of any Lambda runtime (~10-50ms), lowest memory usage
