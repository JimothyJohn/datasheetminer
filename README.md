# Datasheet Miner

Extract technical specifications from product datasheets using AI.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-github%20pages-blue.svg)](https://jimothyjohn.github.io/datasheetminer/)

## Core Tenets

### Gear-Aware Filtering

Mechanical specs like torque and speed are not fixed — they can be traded off through gearing. When filtering motors by torque or speed, the system automatically computes the minimum gear ratio each motor needs to meet the filter criteria, rather than requiring the user to manually set a global ratio. A motor that produces 5 Nm at 3000 rpm becomes a valid match for a 50 Nm filter at a 10:1 ratio (at the cost of 300 rpm output speed). This means:

- **Every motor is evaluated at its optimal gear ratio** for the given filter constraints
- **Torque and speed filters constrain the ratio range**: torque sets the floor, speed sets the ceiling
- **Motors that cannot satisfy both constraints at any ratio are excluded**
- **The computed ratio is displayed per-motor** so the user sees exactly what gearing is needed

This is fundamental to how the tool provides value — raw motor specs alone are misleading without considering the gearhead that will be paired with them.

## Expected Performance

- Max products per prompt: ~256
- Processing time per product: ~2s

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
