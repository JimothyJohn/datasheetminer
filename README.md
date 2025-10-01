![datasheetminer.jpg](docs/datasheetminer.jpg)
# Datasheet Miner

Extract technical specifications from product datasheets using AI. Dual deployment modes: AWS Lambda REST API or local CLI tool.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Features

- **AI-Powered Analysis**: Extract specs, summarize documents, and answer questions using Google Gemini AI
- **Dual Deployment**: Run as AWS Lambda API or local CLI tool
- **Multiple Formats**: Output as JSON, Markdown, or plain text
- **Easy Integration**: MCP-ready for database and workflow integration
- **Production Ready**: Serverless architecture with auto-scaling

## Quick Start

### Option 1: CLI (Local)

```bash
# Install dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Set API key
export GEMINI_API_KEY="your-api-key"

# Analyze a document
uv run datasheetminer \
  --prompt "Extract voltage, current, and power specifications" \
  --url "https://example.com/datasheet.pdf"
```

### Option 2: AWS Lambda

```bash
# Install AWS SAM CLI
brew install aws-sam-cli

# Build and deploy
sam build
sam deploy --guided
```

## Usage Examples

### CLI Examples

```bash
# Extract specifications to JSON
uv run datasheetminer \
  --prompt "Extract all electrical specifications" \
  --url "https://example.com/motor.pdf" \
  --format json \
  --output specs.json

# Create summary in markdown
uv run datasheetminer \
  --prompt "Summarize key features and applications" \
  --url "https://example.com/product.pdf" \
  --format markdown \
  --output summary.md

# Verbose output for debugging
uv run datasheetminer \
  --prompt "Analyze document" \
  --url "https://example.com/doc.pdf" \
  --verbose
```

### API Examples

```bash
# Test deployed Lambda API
curl -X POST https://your-api-id.execute-api.us-east-1.amazonaws.com/Prod/hello \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-gemini-api-key" \
  -d '{
    "prompt": "Extract voltage, current, and power ratings",
    "url": "https://example.com/datasheet.pdf"
  }'
```

## Documentation

- **[CLI Guide](CLI_README.md)**: Complete CLI documentation with all options and examples
- **[Developer Guide](CLAUDE.md)**: Architecture, deployment, and development standards
- **[Schema Examples](SCHEMA.md)**: Example data schemas for motors, drives, and components
- **[GitHub Pages](https://yourusername.github.io/datasheetminer/)**: Interactive documentation site

## Development

### Setup
```bash
# Install dependencies
uv sync

# Run tests
pytest

# Code quality
ruff format .      # Format code
ruff check .       # Lint code
```

### Testing
```bash
pytest                    # All tests
pytest tests/unit/        # Unit tests
pytest tests/integration/ # Integration tests
pytest -v                 # Verbose output
```

### Local API Testing
```bash
# Start local API server
sam local start-api --warm-containers EAGER

# Test locally
curl -X POST http://localhost:3000/hello \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-key" \
  -d '{"prompt": "test", "url": "https://example.com/doc.pdf"}'
```

## Architecture

- **app.py**: Lambda handler with API Gateway integration
- **miner.py**: Core document analysis logic
- **gemini.py**: Google Gemini AI client
- **__main__.py**: CLI entry point
- **models/**: Request/response schemas (Pydantic)

## Use Cases

- **Product Comparison**: Extract specs from multiple datasheets for comparison
- **Database Population**: Automate extraction of technical data into databases
- **Documentation**: Generate summaries and technical briefs from source PDFs
- **Parts Selection**: Query datasheets with natural language to find suitable components
- **Engineering Automation**: Extract motor/drive specs for engineering tools

## Requirements

- Python 3.11+
- Gemini API key ([Get one free](https://aistudio.google.com/))
- AWS account (for Lambda deployment only)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/datasheetminer/issues)
- **Documentation**: See [CLAUDE.md](CLAUDE.md) for detailed developer guide
- **Examples**: Check `examples/` directory for integration samples
