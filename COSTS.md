# DatasheetMiner — Annual Cost Analysis

**Assumption**: 1,000,000 requests/month (12M/year)

## Request Mix Estimate

Not all requests hit Gemini. Based on the endpoint structure:

| Request Type | % of Traffic | Monthly Volume | What It Does |
|---|---|---|---|
| Product reads (list, search, detail) | 85% | 850,000 | DynamoDB queries only |
| Static assets (frontend SPA) | 5% | 50,000 | CloudFront cached S3 |
| Datasheet scrapes (Gemini) | 5% | 50,000 | PDF/HTML → Gemini → DynamoDB write |
| Uploads (presigned URL) | 3% | 30,000 | S3 PUT + DynamoDB write |
| Other writes (CRUD, dedup) | 2% | 20,000 | DynamoDB read/write |

---

## AWS Infrastructure Costs

### Lambda (512 MB, 30s timeout)

| Metric | Value | Monthly Cost |
|---|---|---|
| Invocations | 1,000,000 | $0.20 |
| Duration (avg 500ms reads, 10s scrapes) | ~7,750 GB-s | $0.13 |
| **Free tier** (400K GB-s, 1M requests) | covers most | — |
| **Lambda Total** | | **~$0.33/mo** |

Calculation: (950K reads × 0.5s × 0.5GB) + (50K scrapes × 10s × 0.5GB) = 237,500 + 250,000 = 487,500 GB-s.
After free tier (400K GB-s): 87,500 × $0.0000166667 = $1.46. Requests free up to 1M.

**Revised Lambda Total: ~$1.50/mo**

### API Gateway (REST API)

| Metric | Value | Monthly Cost |
|---|---|---|
| API calls | 1,000,000 | $3.50 |
| **API Gateway Total** | | **$3.50/mo** |

### DynamoDB (On-Demand)

| Operation | Volume | Monthly Cost |
|---|---|---|
| Reads (1 RRU per query page) | ~1,000,000 RRUs | $0.25 |
| Writes (scrape results + uploads + CRUD) | ~200,000 WRUs | $1.25 |
| Storage (estimated 5 GB) | 5 GB | $1.25 |
| **DynamoDB Total** | | **~$2.75/mo** |

Note: Each scrape produces ~5-20 product items (batch write). 50K scrapes × 10 avg items = 500K write operations, but BatchWriteItem groups into 25-item batches, so ~200K WRUs.

### S3 (Upload Bucket)

| Operation | Volume | Monthly Cost |
|---|---|---|
| PUT requests (uploads) | 30,000 | $0.15 |
| GET requests (Lambda reads for scraping) | 50,000 | $0.02 |
| Storage (30K PDFs × 2 MB avg, 90-day lifecycle) | ~180 GB peak | $4.14 |
| **S3 Total** | | **~$4.31/mo** |

### CloudFront

| Metric | Value | Monthly Cost |
|---|---|---|
| HTTPS requests (all traffic) | 1,000,000 | $0.75 |
| Data transfer out (avg 20 KB/response) | ~20 GB | $1.70 |
| Free tier (1 TB transfer, 10M requests) | covers all | — |
| **CloudFront Total** | | **$0.00/mo** (free tier) |

CloudFront free tier is permanent (not 12-month limited) and covers this volume.

### CloudWatch Logs

| Metric | Value | Monthly Cost |
|---|---|---|
| Log ingestion (~2 KB per invocation) | ~2 GB | $1.00 |
| Storage (1-week retention) | ~0.5 GB | $0.02 |
| **CloudWatch Total** | | **~$1.02/mo** |

### Route 53

| Metric | Value | Monthly Cost |
|---|---|---|
| Hosted zone | 1 | $0.50 |
| DNS queries | ~2,000,000 | $0.80 |
| **Route 53 Total** | | **~$1.30/mo** |

### ACM (SSL Certificate)

Free for certificates used with CloudFront.

---

## AWS Subtotal

| Service | Monthly | Annual |
|---|---|---|
| Lambda | $1.50 | $18.00 |
| API Gateway | $3.50 | $42.00 |
| DynamoDB | $2.75 | $33.00 |
| S3 | $4.31 | $51.72 |
| CloudFront | $0.00 | $0.00 |
| CloudWatch | $1.02 | $12.24 |
| Route 53 | $1.30 | $15.60 |
| **AWS Total** | **$14.38** | **$172.56** |

---

## Gemini API Costs (Primary Cost Driver)

Two Gemini models are in use:

### Web App Scraping — `gemini-2.0-flash-exp`

Used by the Node.js backend for on-demand datasheet extraction via `/api/datasheets/:id/scrape`.

| Metric | Value |
|---|---|
| Scrape requests/month | 50,000 |
| Avg input tokens per call (PDF pages + prompt) | ~8,000 |
| Avg output tokens per call (structured JSON) | ~2,000 |
| Fallback retries (text analysis after PDF rejection) | ~10% of calls |

Gemini 2.0 Flash pricing:
- Input: $0.10 / 1M tokens
- Output: $0.40 / 1M tokens

| Component | Tokens/mo | Monthly Cost |
|---|---|---|
| Input (55K calls × 8K tokens) | 440M | $44.00 |
| Output (55K calls × 2K tokens) | 110M | $44.00 |
| **Web Scraping Total** | | **$88.00/mo** |

### CLI Batch Pipeline — `gemini-3-flash-preview`

Used by the Python CLI (`dsm-agent`) for batch intake and extraction.

| Metric | Value |
|---|---|
| Batch extractions/month (estimate) | 5,000 |
| Avg input tokens (full PDF + prompt) | ~15,000 |
| Avg output tokens (max 65,536 configured) | ~4,000 |

Gemini 2.5 Flash pricing (closest available for 3-flash-preview):
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens
- Thinking: $0.70 / 1M tokens (if thinking enabled)

| Component | Tokens/mo | Monthly Cost |
|---|---|---|
| Input (5K calls × 15K tokens) | 75M | $11.25 |
| Output (5K calls × 4K tokens) | 20M | $12.00 |
| **CLI Pipeline Total** | | **$23.25/mo** |

### Triage Pipeline — `gemini-2.5-flash`

Used by `cli/intake.py` for lightweight PDF triage (TOC/spec detection).

| Component | Tokens/mo | Monthly Cost |
|---|---|---|
| Input (5K calls × 10K tokens) | 50M | $7.50 |
| Output (5K calls × 500 tokens) | 2.5M | $1.50 |
| **Triage Total** | | **$9.00/mo** |

### Gemini Subtotal

| Pipeline | Monthly | Annual |
|---|---|---|
| Web scraping (2.0 Flash) | $88.00 | $1,056.00 |
| CLI extraction (2.5 Flash) | $23.25 | $279.00 |
| Triage (2.5 Flash) | $9.00 | $108.00 |
| **Gemini Total** | **$120.25** | **$1,443.00** |

---

## Cognito (Planned — Phase 1 of Monetization)

| Metric | Value | Monthly Cost |
|---|---|---|
| MAUs (first 50K free) | <50,000 | $0.00 |

Free unless exceeding 50K monthly active users.

---

## Total Cost Summary

| Category | Monthly | Annual | % of Total |
|---|---|---|---|
| **AWS Infrastructure** | $14.38 | $172.56 | 10.7% |
| **Gemini API** | $120.25 | $1,443.00 | 89.3% |
| **Grand Total** | **$134.63** | **$1,615.56** | 100% |

---

## Cost Per Request

| Metric | Value |
|---|---|
| Overall cost per request | $0.000135 |
| Cost per read request | ~$0.000003 (DynamoDB + Lambda only) |
| Cost per scrape request | ~$0.002 (Gemini dominates) |

---

## Sensitivity Analysis

Gemini token usage is the biggest variable. Here's how total annual cost shifts:

| Scenario | Scrapes/mo | Gemini Annual | AWS Annual | Total Annual |
|---|---|---|---|---|
| Light (2% scrapes) | 20,000 | $577 | $160 | **$737** |
| **Base (5% scrapes)** | **50,000** | **$1,443** | **$173** | **$1,616** |
| Heavy (10% scrapes) | 100,000 | $2,886 | $195 | **$3,081** |
| Extreme (20% scrapes) | 200,000 | $5,772 | $240 | **$6,012** |

---

## Cost Optimization Opportunities

1. **Cache Gemini results** — If datasheets are re-scraped, store results in DynamoDB. A 30-day cache could cut Gemini calls 10-30%.
2. **Switch to provisioned DynamoDB** — At predictable load, provisioned capacity + auto-scaling is ~5x cheaper than on-demand.
3. **API Gateway → Lambda Function URLs** — Eliminates the $3.50/mo API Gateway cost entirely. CloudFront can front a Function URL directly.
4. **Reduce Gemini input tokens** — Pre-extract text from PDFs (client-side or Lambda) and send text instead of binary PDF. Text is ~5x fewer tokens than image-based PDF analysis.
5. **Batch Gemini calls** — Group multiple small datasheets into a single Gemini call where possible.
6. **CloudFront caching for reads** — Cache `/api/products` responses at CloudFront edge for 60s. At 850K reads/mo, even a 50% cache hit rate halves Lambda invocations.
