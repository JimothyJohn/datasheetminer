# CLAUDE.md

## Project Overview

Datasheetminer is a tri-mode application for extracting technical data from PDF datasheets using Google's Gemini AI:

1. **CLI Tool**: Local command-line interface for direct document processing (`__main__.py`)
2. **AWS Lambda API**: REST API for serverless document analysis with API Gateway integration (`api/`)
3. **Remote MCP Server**: Model Context Protocol endpoint for integration with AI assistants (`mcp/`)

The service provides flexible PDF analysis capabilities with structured JSON output based on Pydantic schemas, supporting multiple deployment options.

## Architecture

### Core Components

```
datasheetminer/
├── datasheetminer/              # Source code
│   ├── __main__.py              # CLI entry point
│   ├── utils.py                 # Core analysis logic and utilities
│   ├── llm.py                   # LLM interface abstraction
│   ├── config.py                # Configuration management
│   ├── models/                  # Pydantic data models
│   │   ├── common.py            # Common/shared schemas
│   │   ├── motor.py             # Motor datasheet schema
│   │   └── drive.py             # Drive datasheet schema
│   ├── api/                     # AWS Lambda API endpoint
│   │   ├── app.py               # Lambda handler with streaming support
│   │   ├── template.yaml        # SAM deployment template
│   │   ├── samconfig.toml       # SAM CLI configuration
│   │   └── requirements.txt     # Lambda-specific dependencies
│   └── mcp/                     # Remote MCP server
│       ├── template.yaml        # MCP server SAM template
│       ├── samconfig.toml       # MCP SAM configuration
│       └── requirements.txt     # MCP-specific dependencies
├── schema/                      # JSON schema definitions
├── tests/                       # Test suite (currently minimal)
├── pyproject.toml               # Project config & dependencies
└── uv.lock                      # Locked dependencies
```

### Component Responsibilities

- **__main__.py**: CLI entry point with argument parsing, validation, and structured JSON output
- **utils.py**: Core document analysis logic, PDF processing, Gemini API integration with structured output
- **llm.py**: Abstract LLM interface for future provider extensibility
- **config.py**: Environment and configuration management
- **models/**: Pydantic models for structured JSON output (motor, drive, common schemas)
- **api/app.py**: Lambda function handler with streaming response support for API Gateway
- **mcp/**: Remote Model Context Protocol server for AI assistant integration

## Dependencies

### Runtime (All Modes)
```
google-genai>=1.29.0      # Gemini AI client with structured output
pydantic>=2.0.0           # Data validation and schemas
python-dotenv>=1.0.0      # Environment variables
```

### Development
```
pytest>=8.4.1             # Testing framework
ruff>=0.12.7              # Linter and formatter
uv                        # Fast Python package manager
```

## API Reference

### Lambda API Endpoint

**POST** `/hello` (API Gateway endpoint in `api/`)

#### Request Format
```json
{
  "prompt": "Extract all technical specifications",
  "url": "https://example.com/datasheet.pdf",
  "type": "motor",
  "pages": "1,3-5,7"
}
```

#### Headers
- `x-api-key`: Gemini API key (required)
- `Content-Type`: application/json

#### Response Format
Streaming response with structured JSON based on the specified type (motor/drive):
```json
[
  {
    "manufacturer": "Example Corp",
    "model_number": "ABC-123",
    "voltage": {"min": 200, "max": 240, "unit": "V"},
    ...
  }
]
```

#### Error Responses
```json
{
  "error": "Error message description",
  "statusCode": 400
}
```

Status codes: 400 (bad request), 401 (missing API key), 500 (server error)

### MCP Server Endpoint

**GET/POST/DELETE** `/mcp` (MCP endpoint in `mcp/`)

Remote Model Context Protocol server for AI assistant integration. See MCP documentation for protocol details.

## CLI Reference

### Installation
```bash
uv sync                   # Install all dependencies
```

### Basic Usage
```bash
# Using environment variable for API key
export GEMINI_API_KEY="your-api-key"
uv run datasheetminer \
  --type motor \
  --url "https://example.com/motor-datasheet.pdf" \
  --pages "1-5"

# Inline API key with specific pages
uv run datasheetminer \
  -t drive \
  -u "https://example.com/drive-spec.pdf" \
  --pages "1,3,5-7" \
  --x-api-key "your-api-key"

# Save to custom output file
uv run datasheetminer \
  -t motor \
  -u "https://example.com/motor.pdf" \
  --pages "1-10" \
  -o motor_specs.json
```

### CLI Options
| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--type` | `-t` | Yes | Schema type: motor or drive |
| `--url` | `-u` | Yes | PDF URL (must be publicly accessible) |
| `--pages` | | Yes | Page ranges (e.g., "1,3-5,7") |
| `--x-api-key` | | Conditional | API key (or use `GEMINI_API_KEY`) |
| `--output` | `-o` | No | Output file path (default: output.json) |
| `--help` | | No | Show help message |

## Commands

### Development Setup
```bash
uv sync                   # Install all dependencies
```

### Testing
```bash
pytest                    # Run all tests
pytest tests/unit/        # Unit tests only
pytest tests/integration/ # Integration tests only
pytest tests/test_cli.py  # CLI tests only
pytest -v                 # Verbose output
```

### Code Quality
```bash
ruff check .              # Lint code
ruff format .             # Format code
ruff check --fix .        # Auto-fix issues
```

### AWS SAM Deployment

#### Lambda API (api/)
```bash
cd datasheetminer/api

# Build Lambda package
sam build

# Deploy (first time - interactive setup)
sam deploy --guided

# Subsequent deploys
sam deploy

# Local testing
sam local start-api                           # Start local API
sam local start-api --warm-containers EAGER   # With warm containers
sam local invoke HelloWorldFunction           # Test function directly
```

#### MCP Server (mcp/)
```bash
cd datasheetminer/mcp

# Build MCP server
sam build

# Deploy
sam deploy --guided  # First time
sam deploy           # Subsequent deploys
```

### Local Development
```bash
# Run CLI locally
uv run datasheetminer --help

# Run with test document
uv run datasheetminer \
  -t motor \
  -u "https://example.com/test.pdf" \
  --pages "1-5"
```

## Development Standards

### Code Style
- **Python version**: 3.11+
- **Type hints**: Required for all function signatures
- **Docstrings**: Google-style for all public functions/classes
- **Formatting**: Use `ruff format` (enforced in CI/CD)
- **Linting**: Use `ruff check` (enforced in CI/CD)
- **Line length**: 100 characters (configured in pyproject.toml)

### Testing Requirements
- **Coverage target**: 90%+ for production code (currently minimal test coverage)
- **Test structure**: Arrange-Act-Assert pattern
- **Fixtures**: Use pytest fixtures for reusable test data
- **Mocking**: Mock external services (Gemini API, AWS services)
- **Integration tests**: Test full workflows for CLI, Lambda API, and MCP endpoints

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

#### Local Development (CLI)
```bash
# Required
export GEMINI_API_KEY="your-gemini-api-key"

# Optional
export LOG_LEVEL="INFO"           # DEBUG, INFO, WARNING, ERROR
```

#### Lambda Deployment
No environment variables needed - API key passed via `x-api-key` header in requests.

### AWS Lambda Settings

#### API Lambda (api/)
```yaml
Runtime: python3.11
Architecture: x86_64
Memory: 2048 MB
Timeout: 300 seconds
EphemeralStorage: 2048 MB
Environment: None (API key via headers)
Permissions:
  - AWSLambdaBasicExecutionRole (CloudWatch Logs)
  - lambda:InvokeFunctionUrl (for streaming)
FunctionUrlConfig:
  AuthType: AWS_IAM
  InvokeMode: RESPONSE_STREAM
Region: us-east-1 (configurable in samconfig.toml)
```

#### MCP Lambda (mcp/)
```yaml
Runtime: python3.11
Architecture: x86_64
Memory: 512 MB
Timeout: 30 seconds
Environment: Configurable (dev/staging/prod)
Region: us-east-1 (configurable in samconfig.toml)
```

### API Gateway Configuration
- **CORS**: Enabled (AllowOrigin: "*", AllowHeaders: "Content-Type,Authorization,x-api-key")
- **Authentication**: None (API endpoint is public)
- **Rate limiting**: Not configured (use AWS throttling if needed)
- **API key requirement**: Gemini key passed via `x-api-key` header

## Security Considerations

### API Key Management
- **Lambda**: Keys passed via headers (not stored in environment)
- **CLI**: Use environment variables, never hardcode keys
- **Version control**: Never commit API keys (check .gitignore)

### AWS Permissions
- Lambda execution role has minimal permissions (logs only)
- No access to S3, DynamoDB, or other AWS services by default
- Extend permissions in template.yaml if needed

### CORS Policy
- Currently allows all origins (`*`)
- Restrict in production by modifying template.yaml:
  ```yaml
  Cors:
    AllowOrigin: "'https://yourdomain.com'"
  ```

## Deployment Guide

### Prerequisites
- AWS CLI installed and configured (`aws configure`)
- AWS SAM CLI installed
- Gemini API key from [Google AI Studio](https://aistudio.google.com/)
- Python 3.11+
- uv package manager

### Lambda API Deployment (api/)
```bash
cd datasheetminer/api

# 1. Build the application
sam build

# 2. Deploy with guided setup
sam deploy --guided
# Follow prompts:
# - Stack name: datasheetminer-api
# - AWS region: us-east-1
# - Confirm changes: Y
# - Allow SAM CLI IAM role creation: Y
# - Disable rollback: N
# - Save arguments to config: Y

# 3. Note the API Gateway URL from outputs
# Example: https://abc123.execute-api.us-east-1.amazonaws.com/Prod/hello
```

### MCP Server Deployment (mcp/)
```bash
cd datasheetminer/mcp

sam build
sam deploy --guided
# Stack name: datasheetminer-mcp
# Choose environment: dev/staging/prod
```

### Testing Deployed API
```bash
# Replace URL with your API Gateway endpoint
curl -X POST https://your-api-id.execute-api.us-east-1.amazonaws.com/Prod/hello \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-gemini-api-key" \
  -d '{
    "url": "https://example.com/motor-datasheet.pdf",
    "type": "motor",
    "pages": "1-5"
  }'
```

## Monitoring & Debugging

### CloudWatch Logs
```bash
# View recent logs
sam logs -n HelloWorldFunction --tail

# View logs for specific time range
sam logs -n HelloWorldFunction \
  --start-time '10min ago' \
  --end-time '5min ago'
```

### Local Testing

#### CLI Testing
```bash
# Test with sample PDF
uv run datasheetminer \
  -t motor \
  -u "https://example.com/test.pdf" \
  --pages "1-5"
```

#### Lambda Local Testing (api/)
```bash
cd datasheetminer/api

# Start local API (with warm containers for faster testing)
sam local start-api --warm-containers EAGER

# Test with curl
curl -X POST http://localhost:3000/hello \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "url": "https://example.com/doc.pdf",
    "type": "motor",
    "pages": "1-5"
  }'
```

### Debugging Tips
1. **Check logs**: Review CloudWatch Logs for Lambda functions
2. **Validate API key**: Ensure Gemini API key is valid and has quota at [Google AI Studio](https://aistudio.google.com/)
3. **Check PDF URL**: Ensure URL is publicly accessible (no authentication required)
4. **Use sam local**: Test Lambda functions locally before deploying
5. **Validate page ranges**: Ensure page numbers exist in the PDF
6. **Schema validation**: Check that the response matches the Pydantic schema for the specified type

## MCP Integration

The project includes a Remote Model Context Protocol server (`mcp/`) that provides AI assistants with access to datasheet analysis capabilities. The MCP server is deployed as a separate Lambda function and can be used by tools like Claude Desktop, Cline, and other MCP-compatible clients.

### Using the MCP Server
Deploy the MCP endpoint to AWS Lambda and configure your MCP client to connect to the endpoint. The server provides tools for:
- Analyzing motor datasheets
- Analyzing drive datasheets
- Extracting structured data from PDFs

### Example CLI Integration
```python
from datasheetminer.utils import analyze_document

result = analyze_document(
    prompt="Extract specifications",
    url="https://example.com/doc.pdf",
    api_key="your-key",
    doc_type="motor",
    pages="1-5"
)

# Access structured data
for item in result.parsed:
    print(item.model_dump())
```

## Troubleshooting

### Common Issues

**Issue**: "API key is required" error
- **Solution**: Set `GEMINI_API_KEY` environment variable or use `--x-api-key`

**Issue**: "Invalid URL" error
- **Solution**: Ensure URL starts with `http://` or `https://` and is publicly accessible

**Issue**: Lambda timeout
- **Solution**: Increase timeout in `api/template.yaml` (currently 300s, max 900s)

**Issue**: PDF not accessible
- **Solution**: Ensure PDF URL is publicly accessible without authentication

**Issue**: Gemini API quota exceeded
- **Solution**: Check quota at [Google AI Studio](https://aistudio.google.com/), upgrade if needed

**Issue**: SAM deployment fails
- **Solution**: Ensure AWS CLI is configured (`aws configure`), check IAM permissions

**Issue**: Pydantic validation error
- **Solution**: Check that Gemini's response matches the schema in `models/motor.py` or `models/drive.py`

**Issue**: Page range parsing error
- **Solution**: Use valid format: "1,3-5,7" (comma-separated pages and ranges)

## Future Enhancements

### Planned Features
- [ ] Support for additional LLM providers (OpenAI, Anthropic, etc.)
- [ ] Additional datasheet schemas (pump, compressor, HVAC, etc.)
- [ ] Batch document processing endpoint
- [ ] Document caching to reduce API costs
- [ ] Rate limiting and quota management
- [ ] Multi-language document support
- [ ] Improved test coverage (currently minimal)
- [ ] WebSocket support for real-time progress updates

### Extensibility
The codebase is designed for extensibility:
- **llm.py**: Abstract interface for adding new LLM providers
- **models/**: Pydantic schemas make it easy to add new document types
- **utils.py**: Core logic is provider-agnostic and reusable
- **Tri-mode architecture**: CLI, Lambda API, and MCP server share the same core logic

## Support

- **Documentation**: See README.md, CLAUDE.md, schema/ directory
- **Issues**: Report bugs via GitHub Issues
- **Schemas**: JSON schemas available in `schema/` directory

## License

See LICENSE file for details.
