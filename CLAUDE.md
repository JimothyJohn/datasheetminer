# CLAUDE.md

## Project Overview

Datasheetminer is a dual-mode application for extracting technical data from PDF datasheets using Google's Gemini AI:

1. **AWS Lambda Service**: REST API for serverless document analysis with API Gateway integration
2. **CLI Tool**: Local command-line interface for direct document processing

The service provides flexible PDF analysis capabilities, supporting multiple output formats and deployment options.

## Architecture

### Core Components

```
datasheetminer/
├── datasheetminer/              # Source code
│   ├── app.py                   # Lambda handler (lambda_handler)
│   ├── __main__.py              # CLI entry point
│   ├── miner.py                 # Core analysis logic
│   ├── llm.py                   # LLM interface abstraction
│   ├── gemini.py                # Gemini AI client
│   ├── config.py                # Configuration management
│   ├── async_handler.py         # Async request handling
│   ├── models/                  # Data models
│   │   ├── request.py           # Request schemas
│   │   └── response.py          # Response schemas
│   └── requirements.txt         # Lambda dependencies
├── tests/                       # Test suite
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── test_cli.py              # CLI tests
├── examples/                    # Usage examples
│   └── mcp_integration.py       # MCP backend example
├── template.yaml                # AWS SAM deployment
├── pyproject.toml               # Project config
└── samconfig.toml               # SAM CLI settings
```

### Component Responsibilities

- **app.py**: Lambda function handler, API Gateway event processing, authentication
- **miner.py**: Document analysis orchestration, result formatting
- **llm.py**: Abstract LLM interface for future provider extensibility
- **gemini.py**: Gemini-specific implementation (file upload, analysis)
- **config.py**: Environment and configuration management
- **async_handler.py**: Async request handling for concurrent operations
- **models/**: Pydantic models for request/response validation

## Dependencies

### Runtime (Lambda & CLI)
```
google-genai>=1.29.0      # Gemini AI client
boto3>=1.40.8             # AWS SDK
python-dotenv>=1.1.1      # Environment variables
requests>=2.32.4          # HTTP client (fallback)
httpx>=0.27.0             # Async HTTP client
awslambdaric>=0.2.1       # Lambda runtime (container mode)
click>=8.1.7              # CLI framework
```

### Development
```
pytest>=8.4.1             # Testing framework
ruff>=0.12.7              # Linter and formatter
```

## API Reference

### Lambda Endpoint

**POST** `/hello`

### Request Format
```json
{
  "prompt": "Extract all technical specifications including voltage, current, power ratings",
  "url": "https://example.com/datasheet.pdf"
}
```

### Headers
- `x-api-key`: Gemini API key (required)
- `Content-Type`: application/json

### Response Format
```json
{
  "message": "AI-generated analysis response with extracted specifications"
}
```

### Error Responses
```json
{
  "error": "Error message description",
  "statusCode": 400
}
```

Status codes: 400 (bad request), 401 (missing API key), 500 (server error)

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
  --prompt "Extract specifications" \
  --url "https://example.com/datasheet.pdf"

# Inline API key
uv run datasheetminer \
  --prompt "Summarize key features" \
  --url "https://example.com/doc.pdf" \
  --x-api-key "your-api-key"
```

### Output Options
```bash
# Save to file
uv run datasheetminer \
  -p "Extract specs" \
  -u "https://example.com/doc.pdf" \
  -o results.txt

# JSON format
uv run datasheetminer \
  -p "Analyze document" \
  -u "https://example.com/doc.pdf" \
  --format json

# Markdown format
uv run datasheetminer \
  -p "Create summary" \
  -u "https://example.com/doc.pdf" \
  --format markdown
```

### CLI Options
| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--prompt` | `-p` | Yes | Analysis instructions |
| `--url` | `-u` | Yes | PDF URL |
| `--x-api-key` | | Conditional | API key (or use `GEMINI_API_KEY`) |
| `--output` | `-o` | No | Output file path |
| `--format` | `-f` | No | Format: text, json, markdown |
| `--verbose` | `-v` | No | Enable verbose logging |
| `--version` | | No | Show version |
| `--help` | | No | Show help |

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
```bash
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

### Local Development
```bash
# Run CLI locally
uv run datasheetminer --help

# Run with test document
uv run datasheetminer \
  --prompt "Test analysis" \
  --url "https://example.com/test.pdf" \
  --verbose
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
- **Coverage target**: 90%+ for production code
- **Test structure**: Arrange-Act-Assert pattern
- **Fixtures**: Use pytest fixtures for reusable test data
- **Mocking**: Mock external services (Gemini API, AWS services)
- **Integration tests**: Test full API Gateway → Lambda flow

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
```yaml
Runtime: python3.11
Architecture: x86_64
Memory: 1024 MB
Timeout: 30 seconds
Environment: None (API key via headers)
Permissions:
  - AWSLambdaBasicExecutionRole (CloudWatch Logs)
Region: us-east-1 (configurable in samconfig.toml)
```

### API Gateway Configuration
- **CORS**: Enabled (AllowOrigin: "*", AllowHeaders: "*")
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

### First-Time Deployment
```bash
# 1. Build the application
sam build

# 2. Deploy with guided setup
sam deploy --guided
# Follow prompts:
# - Stack name: datasheetminer
# - AWS region: us-east-1
# - Confirm changes: Y
# - Allow SAM CLI IAM role creation: Y
# - Disable rollback: N
# - Save arguments to config: Y

# 3. Note the API Gateway URL from outputs
# Example: https://abc123.execute-api.us-east-1.amazonaws.com/Prod/
```

### Subsequent Deployments
```bash
sam build && sam deploy
```

### Testing Deployed API
```bash
# Replace URL with your API Gateway endpoint
curl -X POST https://your-api-id.execute-api.us-east-1.amazonaws.com/Prod/hello \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-gemini-api-key" \
  -d '{
    "prompt": "Extract the rated voltage, current, and power",
    "url": "https://example.com/motor-datasheet.pdf"
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
```bash
# Start local API (with warm containers for faster testing)
sam local start-api --warm-containers EAGER

# Test with curl
curl -X POST http://localhost:3000/hello \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{"prompt": "test", "url": "https://example.com/doc.pdf"}'
```

### Debugging Tips
1. **Enable verbose logging**: Add `--verbose` to CLI commands
2. **Check CloudWatch Logs**: All Lambda execution logs go to CloudWatch
3. **Use sam local**: Test locally before deploying
4. **Validate API key**: Ensure Gemini API key is valid and has quota
5. **Check PDF URL**: Ensure URL is publicly accessible (no authentication)

## MCP Integration

The CLI is designed for easy integration with Model Context Protocol backends. See `examples/mcp_integration.py` for a complete example showing:

- Batch document processing
- Database storage (SQLite, PostgreSQL, etc.)
- Result querying and export
- Error handling and retry logic

### Example MCP Usage
```python
from datasheetminer.miner import analyze_document

result = analyze_document(
    prompt="Extract specifications",
    url="https://example.com/doc.pdf",
    api_key="your-key"
)
```

## Troubleshooting

### Common Issues

**Issue**: "API key is required" error
- **Solution**: Set `GEMINI_API_KEY` environment variable or use `--x-api-key`

**Issue**: "Invalid URL" error
- **Solution**: Ensure URL starts with `http://` or `https://`

**Issue**: Lambda timeout
- **Solution**: Increase timeout in template.yaml (max 900 seconds)

**Issue**: PDF not accessible
- **Solution**: Ensure PDF URL is publicly accessible, no authentication required

**Issue**: Gemini API quota exceeded
- **Solution**: Check quota at [Google AI Studio](https://aistudio.google.com/), upgrade if needed

**Issue**: SAM deployment fails
- **Solution**: Ensure AWS CLI is configured, check IAM permissions

## Future Enhancements

### Planned Features
- [ ] Support for additional LLM providers (OpenAI, Anthropic, etc.)
- [ ] Batch document processing endpoint
- [ ] Async webhook notifications for long-running analyses
- [ ] Structured output schemas (JSON Schema validation)
- [ ] Document caching to reduce API costs
- [ ] Rate limiting and quota management
- [ ] WebSocket support for real-time progress updates
- [ ] Multi-language document support

### Extensibility
The codebase is designed for extensibility:
- **llm.py**: Abstract interface for adding new LLM providers
- **models/**: Pydantic schemas make it easy to add new request/response formats
- **miner.py**: Core logic is provider-agnostic
- **async_handler.py**: Ready for concurrent operations

## Support

- **Documentation**: See README.md, CLI_README.md, SCHEMA.md
- **Issues**: Report bugs via GitHub Issues
- **Examples**: Check `examples/` directory for code samples

## License

See LICENSE file for details.
