# CLAUDE.md

## Project Overview

Datasheetminer is an AWS Lambda service for extracting technical data from datasheets using Google's Gemini AI.

## Architecture

### Core Components

- `datasheetminer/app.py`: Lambda function handler
- `datasheetminer/gemini.py`: Gemini AI integration
- `main.py`: Local testing script (uv inline dependencies)
- `template.yaml`: AWS SAM deployment configuration

### Dependencies

- `google-genai`, `boto3`, `httpx`, `python-dotenv`

## Commands

```bash
# Local development (requires GEMINI_API_KEY in .env)
./main.py

# Testing
pytest                    # All tests
pytest tests/unit/        # Unit tests only
pytest tests/integration/ # Integration tests only

# Code quality
ruff check .
ruff format .

# AWS SAM
sam build                 # Build application
sam deploy                # Deploy to AWS
sam local start-api       # Local API Gateway
sam local invoke HelloWorldFunction

# Dependencies
uv sync
```

## Development Notes

- Python 3.11+, type annotations required
- Google-style docstrings for all functions/classes
- Use `ruff` for formatting/linting
- Unit tests required (aim for 90%+ coverage)
- Environment: `GEMINI_API_KEY` required
- AWS deployment: Python 3.11, 1024MB memory, 30s timeout
- Endpoints: `/hello` (GET), `/v1/completions` (POST)