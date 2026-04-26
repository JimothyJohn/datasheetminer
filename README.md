# Datasheet Miner

Extract technical specifications from product datasheets and webpages using AI.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-github%20pages-blue.svg)](https://jimothyjohn.github.io/datasheetminer/)

## What It Does

Datasheet Miner reads PDF datasheets and product webpages, extracts structured specifications using Gemini AI, validates them against strict Pydantic schemas, and stores them in DynamoDB. A full-stack web app lets you search, filter, and compare products across manufacturers.

## Data Sources

| Source | Tool | How It Works |
|--------|------|-------------|
| PDF datasheets | `specodex` CLI | Downloads PDF, optionally extracts specific pages, sends to Gemini |
| Product webpages | `web-scraper` CLI | Renders JS-heavy pages via Playwright, extracts HTML + JSON-LD, sends to Gemini |
| Manual entry | Web app (admin mode) | Direct CRUD via the product management UI |

Both CLI tools share the same extraction pipeline: Gemini AI outputs CSV with unit-in-header columns, which is parsed locally into `value;unit` compact strings, validated by Pydantic models and unit-family rules, quality-scored, and pushed to DynamoDB with deterministic UUIDs.

## Product Types

| Type | Key Specs |
|------|-----------|
| Motor | voltage, current, power, torque, speed, encoder, inertia |
| Drive | input/output voltage, power, I/O counts, fieldbus, safety |
| Gearhead | ratio, backlash, continuous/peak torque, input speed, rigidity |
| Electric Cylinder | stroke, push/pull force, linear speed, repeatability, lead pitch |
| Robot Arm | payload, reach, repeatability, TCP speed, axes, IP rating |
| Factory | general industrial equipment specs |

New product types are auto-discovered: create a Pydantic model in `specodex/models/` that inherits from `ProductBase` and it appears in all CLIs and the web app automatically.

## Architecture

```
specodex/                Python core: LLM extraction, validation, DynamoDB, models
webscraper/              Browser-based page scraper (Playwright + same LLM pipeline)
cli/                     CLI tools: agent, query, intake, batch processing
app/
  backend/               Express.js REST API (TypeScript)
  frontend/              React + Vite UI (TypeScript)
  infrastructure/        AWS CDK stacks (DynamoDB, API Gateway, CloudFront)
stripe/                  Rust Lambda for metered billing via Stripe
```

## Quick Start

```bash
# Install Python dependencies
uv sync

# Set API keys (copy .env.example to .env and fill in)
cp .env.example .env

# Extract specs from a PDF datasheet
uv run specodex \
  --url "https://example.com/motor-catalog.pdf" \
  --type motor \
  --manufacturer "Acme" \
  --product-name "X100" \
  --pages "3,4,5"

# Scrape a product webpage
uv run web-scraper \
  --url "https://shop.example.com/products/X100" \
  --type motor \
  --manufacturer "Acme" \
  --product-name "X100"

# Query the database
uv run dsm find --type motor \
  --where "rated_power>=1000" \
  --sort "rated_torque:desc" -n 10

# Start the web app (backend + frontend)
cd app && npm install && npm run dev
```

## CLI Tools

| Command | Description |
|---------|-------------|
| `specodex` | Extract specs from a PDF or webpage URL |
| `web-scraper` | Scrape JS-rendered product pages via headless browser |
| `page-finder` | Identify which PDF pages contain spec tables |
| `dsm-agent` | Agent-facing CLI for batch datasheet-to-database workflows |
| `dsm` | Query products in DynamoDB with filters and sorting |

## Gear-Aware Filtering

When filtering motors by torque or speed, the system computes the optimal gear ratio each motor needs to meet the criteria. A motor producing 5 Nm at 3000 rpm becomes a valid match for a 50 Nm filter at 10:1 ratio (at 300 rpm output). Every motor is evaluated at its best ratio, and only those that can satisfy both torque and speed constraints at some ratio are shown.

## Web App

The web app runs in two modes:

- **Admin** (local dev): full CRUD, datasheet management, product upload pipeline
- **Public** (deployed): read-only with search, filtering, comparison, and datasheet links

Features: multi-attribute filtering with IS/NOT modes, range sliders, multi-column sort, gear ratio computation, distribution charts, dark/light theme, mobile responsive.

See [app/README.md](app/README.md) for setup, API reference, and deployment.

## Testing

```bash
# Python unit tests
uv run pytest tests/unit/ -v

# Web app tests
cd app && npm test
```

See [tests/COVERAGE.md](tests/COVERAGE.md) for full coverage breakdown.

## License

MIT License - see LICENSE file for details.
