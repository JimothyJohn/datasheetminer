# CLAUDE.md

## Project Overview

Datasheetminer is an AWS Lambda service for extracting technical data from PDF datasheets using Google's Gemini AI. The service provides a REST API that accepts PDF URLs and analysis prompts, returning AI-generated insights.

## Architecture

### Core Components

- `datasheetminer/app.py`: Lambda function handler with API key authentication
- `datasheetminer/gemini.py`: Gemini AI integration for PDF document analysis
- `datasheetminer/requirements.txt`: Lambda deployment dependencies
- `template.yaml`: AWS SAM deployment configuration
- `pyproject.toml`: Project metadata and development dependencies
- `samconfig.toml`: SAM CLI configuration

### Project Structure

```
datasheetminer/
├── datasheetminer/          # Lambda source code
│   ├── app.py              # Main handler (lambda_handler function)
│   ├── gemini.py           # Gemini AI client integration
│   └── requirements.txt    # Lambda runtime dependencies
├── tests/                  # Test suite
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
├── template.yaml           # SAM deployment template
├── pyproject.toml          # Project config & dev dependencies
└── samconfig.toml          # SAM CLI settings
```

### Dependencies

**Runtime (Lambda):**
- `google-genai>=1.26.0`: Gemini AI client
- `boto3>=1.39.10`: AWS SDK
- `python-dotenv>=1.1.1`: Environment variables
- `requests>=2.32.4`: HTTP client

**Development:**
- `pytest>=8.4.1`: Testing framework
- `ruff>=0.12.4`: Linter and formatter

## API Reference

### Endpoint
- **POST** `/hello`: Document analysis endpoint

### Request Format
```json
{
  "prompt": "Analysis instructions for the AI",
  "url": "https://example.com/datasheet.pdf"
}
```

### Headers
- `x-api-key`: Gemini API key (required)
- `Content-Type`: application/json

### Response Format
```json
{
  "message": "AI analysis response"
}
```

## Commands

```bash
# Development setup
uv sync                   # Install all dependencies

# Testing
pytest                    # Run all tests
pytest tests/unit/        # Unit tests only
pytest tests/integration/ # Integration tests only

# Code quality (run before commits)
ruff check .              # Lint code
ruff format .             # Format code

# AWS SAM deployment
sam build                 # Build Lambda package
sam deploy                # Deploy to AWS (uses samconfig.toml)
sam local start-api       # Test API locally
sam local invoke HelloWorldFunction  # Test function directly

# Local development
sam local start-api --warm-containers EAGER
```

## Development Notes

### Code Standards
- Python 3.11+ required
- Type annotations mandatory
- Google-style docstrings for all functions/classes
- Use `ruff` for consistent formatting/linting
- Unit tests required (aim for 90%+ coverage)

### Environment Setup
- **Local development**: No environment needed (API key passed via headers)
- **Lambda deployment**: Uses runtime environment, no `.env` file needed

### AWS Configuration
- **Runtime**: Python 3.11 on x86_64
- **Memory**: 1024MB
- **Timeout**: 30 seconds
- **Permissions**: Basic execution role + SecretsManager access
- **Region**: us-east-1 (configurable in samconfig.toml)

### Authentication
- API uses `x-api-key` header for Gemini API key authentication
- No AWS API Gateway authentication configured (open endpoint)
- CORS enabled for web applications

### Testing Strategy
- Unit tests: Test individual functions in isolation
- Integration tests: Test full API Gateway → Lambda flow
- Use pytest fixtures for consistent test data