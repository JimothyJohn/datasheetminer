# Datasheet Miner

Extract technical specifications from product datasheets using AI. Dual deployment modes: AWS Lambda REST API or local CLI tool.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-github%20pages-blue.svg)](https://jimothyjohn.github.io/datasheetminer/)

## Expected Performance

- Max products per prompt: ~256
- Processing time per product: ~2s

## TODO

[x] Split products into product families with pages
  - Possibly resolved by fixing UUID Gemini bug and parsing properly
[] Add a field to ValueUnit that will set the default filter functinoality, ge, le, equal, not equal.
  - Exploring parsing by value type and/or unique values found.
[x] Add functionality to create the ProductModel as a template for the rest of the items using the JSON file input and the manufacturer and product fields.
  - Created a factory when initializing and applied automated values like UUID.
[ ] Don't highlight the value now that the column itself indicates if it's sorted or not.
[ ] Add a header that includes the filter spec when one is added.
[ ] Remove the Sort Fields at the top since Add Column is there
[ ] And Add Column to Add Spec
[ ] Fix the state management when choosing fields and values for the filters.

## Quick Start

### Option 1: CLI (Local)

```bash
# Install dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Set API key
export GEMINI_API_KEY="your-api-key"

# Analyze a document
uv run datasheetminer/scraper.py \
  --output device.json \
  --url http://example.com/my.pdf \
  --type drive \
  --pages 1,2,3
```

## Documentation

- **[Developer Guide](CLAUDE.md)**: Architecture, deployment, and development standards
- **[GitHub Pages](https://jimothyjohn.github.io/datasheetminer/)**: Interactive documentation site

## Use Cases

- **Product Comparison**: Extract specs from multiple datasheets for comparison
- **Database Population**: Automate extraction of technical data into databases
- **Documentation**: Generate summaries and technical briefs from source PDFs
- **Parts Selection**: Query datasheets with natural language to find suitable components
- **Engineering Automation**: Extract motor/drive specs for engineering tools

## Requirements

- Python 3.12+
- Gemini API key ([Get one free](https://aistudio.google.com/))

## License

MIT License - see LICENSE file for details
