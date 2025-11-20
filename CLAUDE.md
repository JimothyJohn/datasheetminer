# CLAUDE.md

## Project Overview

Datasheetminer is a comprehensive solution for extracting and managing technical data from PDF datasheets and product web pages using Google's Gemini AI.

**Components:**
1. **CLI Tool (Python)**: Extract technical data from PDFs and web pages using AI
2. **Web Application (TypeScript)**: View and manage product data via web interface
3. **AWS Infrastructure (CDK)**: Deploy serverless backend to AWS

The tool provides AI-powered document analysis capabilities with structured JSON output based on Pydantic schemas, along with a web interface for viewing and managing the extracted data. It intelligently detects whether the input is a PDF or webpage and handles each appropriately.

## Architecture

### Core Components

```
datasheetminer/
├── datasheetminer/              # Python CLI source code
│   ├── scraper.py               # CLI entry point for extraction
│   ├── searcher.py              # Automated product URL discovery
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
│       ├── pusher.py            # Data pusher utility
│       └── deleter.py           # Flexible deletion utility
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
- **scraper.py**: CLI entry point with automatic content type detection (PDF vs webpage), validation, and structured JSON output
- **searcher.py**: Automated product discovery using free search APIs (DuckDuckGo, Brave) - generates urls.json for scraper.py
- **llm.py**: Gemini AI integration with structured output using Pydantic schemas - supports both PDF and HTML content
- **config.py**: Environment and configuration management
- **models/**: Pydantic models for structured JSON output (motor, drive, gearhead, robot_arm, common schemas)
- **db/**: Database utilities for querying, pushing, and deleting data from DynamoDB
  - **dynamo.py**: Core DynamoDB CRUD operations
  - **query.py**: Query and inspect table contents
  - **pusher.py**: Batch push JSON data to DynamoDB
  - **deleter.py**: Flexible deletion with complex filtering (manufacturer, product_type, product_name, product_family)
- **utils.py**: Content fetching utilities (PDFs and web pages), validation, and parsing helpers

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

The tool automatically detects whether the URL is a PDF or web page and handles each appropriately.

```bash
# Set API key
export GEMINI_API_KEY="your-api-key"

# Analyze a motor datasheet (PDF - automatically detected)
uv run datasheetminer/scraper.py \
  --type motor \
  --from-json urls.json \
  --json-index 0 \
  --output motor_specs.json

# Analyze a product web page (HTML - automatically detected)
uv run datasheetminer/scraper.py \
  --type drive \
  --from-json urls.json \
  --json-index 1 \
  --output drive_specs.json

# The tool uses the url.json file format:
# {
#   "motor": [
#     {
#       "url": "https://example.com/motor.pdf",
#       "pages": "1-5",
#       "manufacturer": "ACME",
#       "product_name": "AC-2300"
#     }
#   ],
#   "drive": [
#     {
#       "url": "https://example.com/product-page",
#       "manufacturer": "TechCorp",
#       "product_name": "VFD-500"
#     }
#   ]
# }
```

### CLI Options
| Option | Required | Description |
|--------|----------|-------------|
| `--type` | Yes | Schema type: `motor`, `drive`, `gearhead`, `robot_arm`, etc. |
| `--from-json` | Yes | Path to JSON file containing product information |
| `--json-index` | Yes | Index of the product in the JSON file array |
| `--output` | No | Output file path (default: output.json) |
| `--x-api-key` | No | Gemini API key (can also use GEMINI_API_KEY env var) |

**Note:**
- For PDFs: Specify page ranges in the JSON file (e.g., "1,3-5,7")
- For web pages: The entire page is analyzed automatically (pages parameter ignored)

## Automated Discovery (NEW)

The `searcher.py` tool automates the process of finding product specifications using free search APIs:

### Quick Start

```bash
# Step 1: Search for product URLs
python datasheetminer/searcher.py \
  --type robot_arm \
  --query "Universal Robots specifications" \
  --output robot_urls.json

# Step 2: Extract data from discovered URLs
export GEMINI_API_KEY="your-api-key"
python datasheetminer/scraper.py \
  --type robot_arm \
  --from-json robot_urls.json \
  --json-index 0
```

### Features

- **Free APIs**: Uses DuckDuckGo (no key) or Brave Search (free tier)
- **Smart Filtering**: Identifies PDFs and specification pages automatically
- **Metadata Extraction**: Extracts manufacturer and product names
- **Direct Integration**: Output format feeds directly into scraper.py

### Complete Workflow

```bash
# 1. Discover products
python datasheetminer/searcher.py \
  --type motor \
  --query "servo motor datasheet" "stepper motor specifications" \
  --output urls.json

# 2. Review discovered URLs
cat urls.json

# 3. Process each URL automatically
python datasheetminer/scraper.py \
  --type motor \
  --from-json urls.json \
  --json-index 0 \
  --output motor_data.json

# 4. Data automatically pushed to DynamoDB!
```

See [SEARCHER.md](SEARCHER.md) for complete documentation.

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
# Process a motor datasheet (PDF)
uv run datasheetminer/scraper.py \
  --type motor \
  --from-json urls.json \
  --json-index 0 \
  --output motor_data.json

# Process a product web page (HTML)
uv run datasheetminer/scraper.py \
  --type drive \
  --from-json urls.json \
  --json-index 1 \
  --output drive_data.json

# The tool automatically detects content type (PDF vs webpage)
# based on URL and Content-Type header
```

### Database Management

The project includes utilities for managing data in DynamoDB:

#### Query Data
```bash
# Show table summary
uv run datasheetminer/db/query.py --summary

# List all items (first 10)
uv run datasheetminer/db/query.py --list

# List motors with details
uv run datasheetminer/db/query.py --list --type motor --limit 20 --details

# Get specific item by ID
uv run datasheetminer/db/query.py --get <product-id> --type motor
```

#### Push Data
```bash
# Push JSON data to DynamoDB
uv run datasheetminer/db/pusher.py --file output.json

# Push to custom table
uv run datasheetminer/db/pusher.py --file output.json --table my-table
```

#### Delete Data (NEW)

The deletion utility supports flexible filtering with any combination of:
- `--manufacturer`: Filter by manufacturer name
- `--product-type`: Filter by product type (motor, drive, gearhead, robot_arm)
- `--product-name`: Filter by product name
- `--product-family`: Filter by product family

```bash
# Dry run - see what would be deleted
uv run datasheetminer/db/deleter.py --manufacturer "ABB" --dry-run

# Delete all products from a manufacturer
uv run datasheetminer/db/deleter.py --manufacturer "ABB" --confirm

# Delete specific product type from manufacturer
uv run datasheetminer/db/deleter.py \
  --manufacturer "Siemens" \
  --product-type motor \
  --confirm

# Delete by manufacturer + product family
uv run datasheetminer/db/deleter.py \
  --manufacturer "ABB" \
  --product-family "ACS880" \
  --confirm

# Complex query - multiple filters
uv run datasheetminer/db/deleter.py \
  --manufacturer "Siemens" \
  --product-type drive \
  --product-family "SINAMICS" \
  --confirm

# Delete specific product
uv run datasheetminer/db/deleter.py \
  --manufacturer "Baldor" \
  --product-name "M3615T" \
  --confirm
```

Safety features:
- Requires `--confirm` flag to actually delete (or `--dry-run` for testing)
- Shows preview of items to be deleted with sample data
- Requires typed confirmation ("DELETE")
- At least one filter must be specified
- Uses efficient queries when product_type is specified

## Development Standards

### Code Style
- **Python version**: 3.12+
- **Type annotations**: MANDATORY for ALL code
  - **Function signatures**: All function parameters and return types MUST be annotated
  - **Class attributes**: All class instance variables MUST be annotated
  - **Local variables**: All local variables SHOULD be annotated, especially in complex functions
  - **Collections**: Use `List[T]`, `Dict[K, V]`, `Set[T]`, `Optional[T]`, etc. from `typing`
  - **Any type**: Use `Any` when type is truly dynamic or comes from external libraries
  - **Example**:
    ```python
    from typing import List, Dict, Optional, Any

    def process_data(items: List[Dict[str, Any]], limit: Optional[int] = None) -> Dict[str, int]:
        result: Dict[str, int] = {}
        count: int = 0
        for item in items:
            # Process item...
            count += 1
        return result
    ```
- **Docstrings**: Google-style for all public functions/classes
- **Formatting**: Use `ruff format`
- **Linting**: Use `ruff check`
- **Line length**: 100 characters (configured in pyproject.toml)

**IMPORTANT**: Code without proper type annotations is unacceptable and will not be merged. Type annotations are not optional - they are required for code quality, maintainability, and IDE support.

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

**Issue**: Web page content extraction fails
- **Solution**: Ensure the webpage is publicly accessible and doesn't require JavaScript rendering. The tool fetches raw HTML content.

**Issue**: Gemini API quota exceeded
- **Solution**: Check quota at [Google AI Studio](https://aistudio.google.com/), upgrade if needed

**Issue**: Pydantic validation error
- **Solution**: Check that Gemini's response matches the schema in `models/motor.py` or `models/drive.py`

**Issue**: Page range parsing error
- **Solution**: Use valid format: "1,2,3" or "1-5" or "1,3-5,7" (comma-separated pages and ranges)

### Debugging Tips

1. **Validate API key**: Ensure Gemini API key is valid and has quota at [Google AI Studio](https://aistudio.google.com/)
2. **Check content URL**: Ensure URL is publicly accessible (no authentication required) for both PDFs and web pages
3. **Content type detection**: The tool automatically detects PDF vs web page. Check logs for "Content type detected" message
4. **Validate page ranges**: For PDFs, ensure page numbers exist in the PDF (pages parameter ignored for web pages)
5. **Schema validation**: Check that the response matches the Pydantic schema for the specified type
6. **Check output**: Review generated JSON file for completeness and accuracy
7. **Web page content**: For web pages, raw HTML is sent to Gemini. If JavaScript is required to render content, consider using a headless browser solution


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

- **Product Comparison**: Extract specs from multiple PDFs and web pages for side-by-side comparison
- **Database Population**: Automate extraction of technical data from PDFs and manufacturer websites into databases
- **Web Interface**: View and manage products via intuitive web application
- **Documentation Generation**: Generate summaries and technical briefs from source PDFs and web pages
- **Parts Selection**: Query both datasheets and online product pages to find suitable components for projects
- **Engineering Automation**: Extract motor/drive specs from any source (PDF or web) for integration into engineering tools
- **E-commerce Integration**: Populate product pages with specifications from manufacturer datasheets and product pages
- **Multi-Source Data**: Combine data from PDF datasheets and online spec sheets into unified product records

## Support

- **Documentation**: See README.md, CLAUDE.md, app/README.md, and [GitHub Pages](https://jimothyjohn.github.io/datasheetminer/)
- **Issues**: Report bugs via [GitHub Issues](https://github.com/jimothyjohn/datasheetminer/issues)
- **API Key**: Get your Gemini API key from [Google AI Studio](https://aistudio.google.com/)

## License

MIT License - See LICENSE file for details.
