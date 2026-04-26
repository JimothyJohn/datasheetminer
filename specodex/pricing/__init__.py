"""MSRP price scraping pipeline.

Given (manufacturer, part_number), resolve a set of candidate URLs through
a tiered cascade (OEM → distributor → aggregator → SERP fallback), fetch
each page, and extract a single USD price using a JSON-LD → microdata →
regex → LLM extraction cascade.

See `plans/devise-a-webscraper-to-linked-riddle.md` for the full design.
"""

from __future__ import annotations

from specodex.pricing.extract import PriceResult, extract_price
from specodex.pricing.fetch import PriceFetcher
from specodex.pricing.resolver import Candidate, resolve_candidates

__all__ = [
    "Candidate",
    "PriceFetcher",
    "PriceResult",
    "extract_price",
    "resolve_candidates",
]
