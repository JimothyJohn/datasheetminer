# CLAUDE.md

## Project Overview

Datasheetminer is a comprehensive solution for extracting and managing technical data from PDF datasheets using Google's Gemini AI.

**Components:**
1. **CLI Tool (Python)**: Extract technical data from PDFs using AI
2. **Web Application (TypeScript)**: View and manage product data via web interface
3. **AWS Infrastructure (CDK)**: Deploy serverless backend to AWS

The tool provides AI-powered PDF analysis capabilities with structured JSON output based on Pydantic schemas, along with a web interface for viewing and managing the extracted data.

## Architecture

### Core Components

```
datasheetminer/
├── datasheetminer/              # Python CLI source code
│   ├── scraper.py               # CLI entry point
│   ├── llm.py                   # LLM interface (Gemini AI)
│   ├── config.py                # Configuration management
│   ├── models/                  # Pydantic data models
│   │   ├── common.py            # Common/shared schemas
│   │   ├── product.py           # Base product schema
│   │   ├── motor.py             # Motor datasheet schema
│   │   └── drive.py             # Drive datasheet schema
│   └── db/                      # Database utilities
│       ├── dynamo.py            # DynamoDB client
│       ├── query.py             # Query utility
│       └── pusher.py            # Data pusher utility
├── app/                         # Web application (ISOLATED)
│   ├── backend/                 # Express + TypeScript API
│   │   ├── src/
│   │   │   ├── index.ts         # Express app entry point
│   │   │   ├── config/          # Configuration
│   │   │   ├── db/              # DynamoDB service
│   │   │   ├── routes/          # API routes
│   │   │   └── types/           # TypeScript types
│   │   ├── tests/               # Backend tests
│   │   └── package.json         # Backend dependencies
│   ├── frontend/                # React + TypeScript UI
│   │   ├── src/
│   │   │   ├── App.tsx          # Main React app
│   │   │   ├── components/      # React components
│   │   │   ├── api/             # API client
│   │   │   └── types/           # TypeScript types
│   │   ├── public/              # Static assets
│   │   └── package.json         # Frontend dependencies
│   ├── infrastructure/          # AWS CDK (TypeScript)
│   │   ├── lib/
│   │   │   ├── database-stack.ts  # DynamoDB table
│   │   │   ├── api-stack.ts       # API Gateway + Lambda
│   │   │   └── config.ts          # CDK configuration
│   │   ├── bin/
│   │   │   └── app.ts           # CDK app entry point
│   │   └── package.json         # CDK dependencies
│   ├── .github/                 # CI/CD workflows
│   │   └── workflows/
│   │       └── ci.yml           # GitHub Actions workflow
│   ├── package.json             # Root package.json (workspaces)
│   └── README.md                # App documentation
├── docs/                        # Documentation website
│   └── index.html               # GitHub Pages site
├── tests/                       # Python test suite
├── pyproject.toml               # Python project config
└── uv.lock                      # Python locked dependencies
```

### Component Responsibilities

**Python CLI:**
- **scraper.py**: CLI entry point with argument parsing, validation, and structured JSON output
- **llm.py**: Gemini AI integration with structured output using Pydantic schemas
- **config.py**: Environment and configuration management
- **models/**: Pydantic models for structured JSON output (motor, drive, common schemas)
- **db/**: Database utilities for querying and pushing data to DynamoDB

**Web Application (app/):**
- **backend/**: Express.js REST API with TypeScript
  - DynamoDB service for CRUD operations
  - REST endpoints matching Python utilities (query.py, pusher.py)
  - Type-safe operations with TypeScript types mirroring Pydantic models
- **frontend/**: React single-page application
  - Dashboard showing product summary statistics
  - Product list with filtering (motors, drives, all)
  - Responsive, minimalistic UI design
- **infrastructure/**: AWS CDK for infrastructure as code
  - DynamoDB table with single-table design
  - API Gateway + Lambda for serverless backend
  - Optional custom domain with HTTPS support
  - Configurable via environment variables

## Dependencies

### Python CLI Runtime
```
google-genai>=1.29.0      # Gemini AI client with structured output
pydantic>=2.0.0           # Data validation and schemas
boto3>=1.40.45            # AWS SDK for Python
```

### Python Development
```
pytest>=8.4.1             # Testing framework
ruff>=0.12.7              # Linter and formatter
uv                        # Fast Python package manager
```

### Web Application (TypeScript/Node.js)
```
# Backend
express>=4.21.2           # Web framework
@aws-sdk/client-dynamodb>=3.700.0  # AWS SDK for DynamoDB
zod>=3.24.1               # Runtime type validation

# Frontend
react>=18.3.1             # UI framework
react-router-dom>=7.1.1   # Routing
vite>=6.0.5               # Build tool

# Infrastructure
aws-cdk-lib>=2.173.4      # AWS CDK framework
constructs>=10.4.2        # CDK constructs
```

## CLI Reference

### Installation
```bash
uv sync                   # Install all dependencies
```

### Basic Usage
```bash
# Set API key
export GEMINI_API_KEY="your-api-key"

# Analyze a motor datasheet
uv run datasheetminer/scraper.py \
  --type motor \
  --url "https://example.com/motor-datasheet.pdf" \
  --pages "1-5" \
  --output motor_specs.json

# Analyze a drive datasheet with specific pages
uv run datasheetminer/scraper.py \
  --type drive \
  --url "https://example.com/drive-spec.pdf" \
  --pages "1,3,5-7" \
  --output drive_specs.json
```

### CLI Options
| Option | Required | Description |
|--------|----------|-------------|
| `--type` | Yes | Schema type: `motor` or `drive` |
| `--url` | Yes | PDF URL (must be publicly accessible) |
| `--pages` | Yes | Page ranges (e.g., "1,2,3" or "1-5" or "1,3-5,7") |
| `--output` | No | Output file path (default: output.json) |

## Commands

### Development Setup
```bash
uv sync                   # Install all dependencies
```

### Testing
```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest tests/             # Run specific test directory
```

### Code Quality
```bash
ruff check .              # Lint code
ruff format .             # Format code
ruff check --fix .        # Auto-fix issues
```

### Running the CLI
```bash
# Process a motor datasheet
uv run datasheetminer/scraper.py \
  --type motor \
  --url "https://example.com/motor.pdf" \
  --pages "1-5" \
  --output motor_data.json

# Process a drive datasheet
uv run datasheetminer/scraper.py \
  --type drive \
  --url "https://example.com/drive.pdf" \
  --pages "1,3-5,7" \
  --output drive_data.json
```

## Development Standards

### Code Style
- **Python version**: 3.12+
- **Type hints**: Required for all function signatures
- **Docstrings**: Google-style for all public functions/classes
- **Formatting**: Use `ruff format`
- **Linting**: Use `ruff check`
- **Line length**: 100 characters (configured in pyproject.toml)

### Testing Requirements
- **Coverage target**: 90%+ for production code (currently minimal test coverage)
- **Test structure**: Arrange-Act-Assert pattern
- **Fixtures**: Use pytest fixtures for reusable test data
- **Mocking**: Mock external services (Gemini API)
- **Integration tests**: Test full CLI workflows

### Git Workflow
```bash
# Before committing
ruff format .             # Format code
ruff check .              # Check for issues
pytest                    # Run tests

# Commit
git add .
git commit -m "feat: descriptive message"
git push
```

## Configuration

### Environment Variables

```bash
# Required
export GEMINI_API_KEY="your-gemini-api-key"
```

Get your API key from [Google AI Studio](https://aistudio.google.com/)

## Setup Guide

### Prerequisites
- Python 3.12+
- uv package manager
- Gemini API key from [Google AI Studio](https://aistudio.google.com/)

### Installation

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/jimothyjohn/datasheetminer.git
cd datasheetminer

# Install dependencies
uv sync

# Set API key
export GEMINI_API_KEY="your-api-key"
```

### Quick Start

```bash
# Analyze a datasheet
uv run datasheetminer/scraper.py \
  --type motor \
  --url "https://example.com/motor-datasheet.pdf" \
  --pages "1-5" \
  --output motor_specs.json
```

## Debugging & Troubleshooting

### Common Issues

**Issue**: "API key is required" error
- **Solution**: Set `GEMINI_API_KEY` environment variable: `export GEMINI_API_KEY="your-key"`

**Issue**: "Invalid URL" error
- **Solution**: Ensure URL starts with `http://` or `https://` and is publicly accessible

**Issue**: PDF not accessible
- **Solution**: Ensure PDF URL is publicly accessible without authentication

**Issue**: Gemini API quota exceeded
- **Solution**: Check quota at [Google AI Studio](https://aistudio.google.com/), upgrade if needed

**Issue**: Pydantic validation error
- **Solution**: Check that Gemini's response matches the schema in `models/motor.py` or `models/drive.py`

**Issue**: Page range parsing error
- **Solution**: Use valid format: "1,2,3" or "1-5" or "1,3-5,7" (comma-separated pages and ranges)

### Debugging Tips

1. **Validate API key**: Ensure Gemini API key is valid and has quota at [Google AI Studio](https://aistudio.google.com/)
2. **Check PDF URL**: Ensure URL is publicly accessible (no authentication required)
3. **Validate page ranges**: Ensure page numbers exist in the PDF
4. **Schema validation**: Check that the response matches the Pydantic schema for the specified type
5. **Check output**: Review generated JSON file for completeness and accuracy


## Output Format

The tool outputs structured JSON based on the specified schema type:

### Motor Schema
```json
[
  {
    "manufacturer": "ACME Motors",
    "model_number": "AC-2300-5HP",
    "voltage": {
      "min": 200,
      "max": 240,
      "unit": "V"
    },
    "power": {
      "value": 5,
      "unit": "HP"
    },
    "current": {
      "rated": 6.8,
      "unit": "A"
    },
    "weight": {
      "value": 45,
      "unit": "lbs"
    }
  }
]
```

### Drive Schema
Similar structured output for drive specifications. See `models/drive.py` for complete schema definition.

## Future Enhancements

### Planned Features
- [ ] Support for additional LLM providers (OpenAI, Anthropic, etc.)
- [ ] Additional datasheet schemas (pump, compressor, HVAC, etc.)
- [ ] Batch document processing
- [ ] Document caching to reduce API costs
- [ ] Multi-language document support
- [ ] Improved test coverage (currently minimal)
- [ ] Progress indicators for long-running operations

### Extensibility
The codebase is designed for extensibility:
- **llm.py**: Interface for adding new LLM providers
- **models/**: Pydantic schemas make it easy to add new document types
- **Modular design**: Easy to extend with new features and capabilities

## Web Application

The web application (`app/`) is a complete TypeScript-based solution for viewing and managing products extracted by the CLI tool. It's completely isolated from the Python CLI and can be developed, tested, and deployed independently.

### Quick Start

```bash
cd app

# Install all dependencies
npm install

# Development (runs backend + frontend concurrently)
npm run dev

# Backend will run on http://localhost:3001
# Frontend will run on http://localhost:3000
```

### Architecture

**Backend (Express + TypeScript):**
- REST API with endpoints matching Python utilities
- DynamoDB integration for data storage
- Type-safe with TypeScript types mirroring Pydantic models
- Comprehensive test coverage with Jest

**Frontend (React + TypeScript):**
- Modern React with functional components and hooks
- Responsive, minimalistic UI design
- Dashboard with summary statistics
- Product list with filtering capabilities

**Infrastructure (AWS CDK):**
- DynamoDB table with single-table design (PK/SK pattern)
- API Gateway + Lambda for serverless deployment
- Optional custom domain with HTTPS certificate
- Infrastructure as code with TypeScript

### API Endpoints

```
GET  /health                    # Health check
GET  /api/products/summary      # Get product counts
GET  /api/products              # List products (with filtering)
GET  /api/products/:id          # Get product by ID
POST /api/products              # Create product(s)
DELETE /api/products/:id        # Delete product
```

### Deployment

```bash
cd app

# Build everything
npm run build

# Deploy to AWS (requires AWS credentials)
cd infrastructure
npm run deploy

# Or use GitHub Actions for CI/CD (see .github/workflows/ci.yml)
```

### Configuration

Environment variables for deployment:
```bash
# Required
AWS_ACCOUNT_ID=your-account-id
AWS_REGION=us-east-1
DYNAMODB_TABLE_NAME=products

# Optional: HTTPS with custom domain
DOMAIN_NAME=api.example.com
CERTIFICATE_ARN=arn:aws:acm:...
HOSTED_ZONE_ID=Z1234567890ABC
```

### Testing

```bash
# Run all tests
npm test

# Backend tests
cd backend && npm test

# Frontend tests
cd frontend && npm test
```

## Use Cases

- **Product Comparison**: Extract specs from multiple datasheets for side-by-side comparison
- **Database Population**: Automate extraction of technical data into databases
- **Web Interface**: View and manage products via intuitive web application
- **Documentation Generation**: Generate summaries and technical briefs from source PDFs
- **Parts Selection**: Query datasheets to find suitable components for projects
- **Engineering Automation**: Extract motor/drive specs for integration into engineering tools
- **E-commerce Integration**: Populate product pages with specifications from manufacturer datasheets

## Support

- **Documentation**: See README.md, CLAUDE.md, app/README.md, and [GitHub Pages](https://jimothyjohn.github.io/datasheetminer/)
- **Issues**: Report bugs via [GitHub Issues](https://github.com/jimothyjohn/datasheetminer/issues)
- **API Key**: Get your Gemini API key from [Google AI Studio](https://aistudio.google.com/)

## License

MIT License - See LICENSE file for details.
