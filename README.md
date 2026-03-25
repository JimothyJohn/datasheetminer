# Datasheet Miner

Extract technical specifications from product datasheets using AI.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-github%20pages-blue.svg)](https://jimothyjohn.github.io/datasheetminer/)

## TODO

[] Add a field to ValueUnit that will set the default filter functinoality, ge, le, equal, not equal.
  - Exploring parsing by value type and/or unique values found.

## Quick Start

```bash
# Set API keys using .env.example
./Quickstart
```

## Use Cases

- **Product Comparison**: Extract specs from multiple datasheets for comparison
- **Database Population**: Automate extraction of technical data into databases

## Expected Performance

- Max products per prompt: ~256
- Processing time per product: ~2s

## License

MIT License - see LICENSE file for details
