#!/usr/bin/env python3
"""
Automated product search tool for discovering robot/product specifications.

This module uses free search APIs to find product datasheets and specification pages,
then outputs them in the format expected by the main scraper (urls.json).

Features:
- Multiple search API support (DuckDuckGo, Brave, SerpApi)
- Smart URL filtering (PDFs, product pages, spec sheets)
- Manufacturer and product name extraction
- Output compatible with scraper.py
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import html

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger: logging.Logger = logging.getLogger(__name__)


class SearchResult:
    """Represents a single search result."""

    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        manufacturer: Optional[str] = None,
        product_name: Optional[str] = None,
    ) -> None:
        """Initialize a search result.

        Args:
            title: The title of the search result
            url: The URL of the result
            snippet: The text snippet/description
            manufacturer: Extracted manufacturer name (if available)
            product_name: Extracted product name (if available)
        """
        self.title = title
        self.url = url
        self.snippet = snippet
        self.manufacturer = manufacturer
        self.product_name = product_name

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "manufacturer": self.manufacturer,
            "product_name": self.product_name,
        }


class ProductSearcher:
    """Searches for product specifications using free search APIs."""

    def __init__(self, api: str = "duckduckgo", api_key: Optional[str] = None) -> None:
        """Initialize the product searcher.

        Args:
            api: Which search API to use ('duckduckgo', 'brave', 'serpapi')
            api_key: API key for services that require it (Brave, SerpApi)
        """
        self.api = api.lower()
        self.api_key = api_key

        # Common manufacturer names to help with extraction
        self.known_manufacturers = [
            "ABB",
            "FANUC",
            "KUKA",
            "Yaskawa",
            "Universal Robots",
            "UR",
            "Kawasaki",
            "Staubli",
            "Omron",
            "Epson",
            "Denso",
            "Mitsubishi",
            "Nachi",
            "Comau",
            "Franka Emika",
            "Doosan",
            "Techman",
            "Hanwha",
            "Boston Dynamics",
            "Agility Robotics",
        ]

        # URL patterns that likely contain specs
        self.spec_url_patterns = [
            r"datasheet",
            r"spec",
            r"specification",
            r"technical",
            r"product",
            r"catalog",
            r"manual",
            r"doc",
            r"documentation",
            r"downloads?",
        ]

    def search_duckduckgo(
        self, query: str, max_results: int = 10
    ) -> List[SearchResult]:
        """Search using DuckDuckGo HTML API (no API key required).

        Args:
            query: The search query
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects
        """
        logger.info(f"Searching DuckDuckGo for: {query}")

        encoded_query = quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            req = Request(url, headers=headers)

            with urlopen(req, timeout=10) as response:
                html_content = response.read().decode("utf-8")

            results = self._parse_duckduckgo_html(html_content, max_results)
            logger.info(f"Found {len(results)} results from DuckDuckGo")
            return results

        except (HTTPError, URLError) as e:
            logger.error(f"Error searching DuckDuckGo: {e}")
            return []

    def _parse_duckduckgo_html(
        self, html_content: str, max_results: int
    ) -> List[SearchResult]:
        """Parse DuckDuckGo HTML results.

        Args:
            html_content: The HTML content from DuckDuckGo
            max_results: Maximum number of results to extract

        Returns:
            List of SearchResult objects
        """
        results: List[SearchResult] = []

        # Simple regex-based parsing (more robust than full HTML parsing for this use case)
        # Find result divs
        result_pattern = r'<div class="result[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>'
        result_matches = re.finditer(result_pattern, html_content, re.DOTALL)

        for match in result_matches:
            if len(results) >= max_results:
                break

            result_html = match.group(1)

            # Extract title and URL
            title_match = re.search(
                r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                result_html,
                re.DOTALL,
            )
            if not title_match:
                continue

            url = html.unescape(title_match.group(1))
            title = re.sub(r"<[^>]+>", "", title_match.group(2))
            title = html.unescape(title).strip()

            # Extract snippet
            snippet_match = re.search(
                r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
                result_html,
                re.DOTALL,
            )
            snippet = ""
            if snippet_match:
                snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1))
                snippet = html.unescape(snippet).strip()

            # Clean up DuckDuckGo redirect URLs
            if url.startswith("//duckduckgo.com/l/?"):
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if "uddg" in params:
                    url = params["uddg"][0]

            results.append(SearchResult(title=title, url=url, snippet=snippet))

        return results

    def search_brave(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using Brave Search API (requires API key).

        Args:
            query: The search query
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects
        """
        if not self.api_key:
            logger.error("Brave Search requires an API key")
            return []

        logger.info(f"Searching Brave for: {query}")

        url = f"https://api.search.brave.com/res/v1/web/search?q={quote_plus(query)}&count={max_results}"

        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
            }
            req = Request(url, headers=headers)

            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

            results: List[SearchResult] = []
            for item in data.get("web", {}).get("results", []):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("description", ""),
                    )
                )

            logger.info(f"Found {len(results)} results from Brave")
            return results

        except (HTTPError, URLError) as e:
            logger.error(f"Error searching Brave: {e}")
            return []

    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using the configured API.

        Args:
            query: The search query
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects
        """
        if self.api == "duckduckgo":
            return self.search_duckduckgo(query, max_results)
        elif self.api == "brave":
            return self.search_brave(query, max_results)
        else:
            logger.error(f"Unknown search API: {self.api}")
            return []

    def is_likely_spec_page(self, url: str) -> bool:
        """Check if a URL likely contains product specifications.

        Args:
            url: The URL to check

        Returns:
            True if the URL likely contains specs
        """
        url_lower = url.lower()

        # Check for PDF datasheets
        if url_lower.endswith(".pdf"):
            return True

        # Check for spec-related keywords in URL
        for pattern in self.spec_url_patterns:
            if re.search(pattern, url_lower):
                return True

        return False

    def extract_manufacturer_and_product(self, result: SearchResult) -> SearchResult:
        """Extract manufacturer and product name from search result.

        Args:
            result: The search result to process

        Returns:
            Updated SearchResult with manufacturer and product_name filled in
        """
        text = f"{result.title} {result.snippet}".lower()

        # Try to find known manufacturer
        for manufacturer in self.known_manufacturers:
            if manufacturer.lower() in text:
                result.manufacturer = manufacturer
                break

        # Try to extract product name/model number
        # Look for patterns like: "Model ABC-123", "Series XYZ", etc.
        model_patterns = [
            r"\b([A-Z]{2,}[-\s]?\d{2,}[A-Z0-9]*)\b",  # ABC-123, UR5, KR210
            r"\bmodel\s+([A-Z0-9\-]+)\b",
            r"\bseries\s+([A-Z0-9\-]+)\b",
        ]

        for pattern in model_patterns:
            match = re.search(pattern, result.title, re.IGNORECASE)
            if match:
                result.product_name = match.group(1).strip()
                break

        return result

    def filter_and_enrich_results(
        self, results: List[SearchResult], min_quality: float = 0.5
    ) -> List[SearchResult]:
        """Filter results to likely spec pages and enrich with metadata.

        Args:
            results: List of raw search results
            min_quality: Minimum quality score (0-1) for inclusion

        Returns:
            Filtered and enriched list of SearchResult objects
        """
        filtered: List[SearchResult] = []

        for result in results:
            # Calculate quality score
            score = 0.0

            # Check if URL looks like specs
            if self.is_likely_spec_page(result.url):
                score += 0.5

            # Check if title/snippet mentions specs
            text = f"{result.title} {result.snippet}".lower()
            spec_keywords = [
                "specification",
                "datasheet",
                "technical",
                "manual",
                "robot",
            ]
            for keyword in spec_keywords:
                if keyword in text:
                    score += 0.1

            # Only include if score is high enough
            if score >= min_quality:
                # Enrich with manufacturer and product info
                result = self.extract_manufacturer_and_product(result)
                filtered.append(result)
                logger.debug(f"Kept result (score={score:.2f}): {result.title[:50]}...")
            else:
                logger.debug(
                    f"Filtered out (score={score:.2f}): {result.title[:50]}..."
                )

        return filtered


def search_for_products(
    product_type: str,
    search_terms: List[str],
    max_results_per_query: int = 10,
    api: str = "duckduckgo",
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search for products and return results in urls.json format.

    Args:
        product_type: Type of product (motor, drive, robot_arm, etc.)
        search_terms: List of search queries to run
        max_results_per_query: Maximum results to fetch per query
        api: Which search API to use
        api_key: API key for services that require it

    Returns:
        List of product entries in urls.json format
    """
    searcher = ProductSearcher(api=api, api_key=api_key)
    all_results: List[SearchResult] = []

    for query in search_terms:
        logger.info(f"Searching for: {query}")

        # Add product type to query if not already present
        if product_type.lower() not in query.lower():
            enhanced_query = f"{product_type} {query}"
        else:
            enhanced_query = query

        # Perform search
        results = searcher.search(enhanced_query, max_results=max_results_per_query)

        # Filter and enrich results
        filtered = searcher.filter_and_enrich_results(results)
        all_results.extend(filtered)

        # Be respectful with rate limiting
        time.sleep(1)

    # Convert to urls.json format
    output: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()

    for result in all_results:
        # Deduplicate by URL
        if result.url in seen_urls:
            continue
        seen_urls.add(result.url)

        entry: Dict[str, Any] = {
            "url": result.url,
            "manufacturer": result.manufacturer or "Unknown",
            "product_name": result.product_name or result.title[:50],
        }

        # Add pages field if it's a PDF
        if result.url.lower().endswith(".pdf"):
            entry["pages"] = "1-10"  # Default to first 10 pages

        output.append(entry)

    logger.info(f"Found {len(output)} unique product URLs")
    return output


def main() -> None:
    """CLI entry point for product searcher."""
    parser = argparse.ArgumentParser(
        description="Search for product specifications and generate urls.json entries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for robot arms
  python searcher.py --type robot_arm --query "industrial robot arm specifications" --output urls.json

  # Search for multiple motor types
  python searcher.py --type motor --query "servo motor datasheet" "stepper motor specs" -o motor_urls.json

  # Use Brave Search API
  export BRAVE_API_KEY="your-api-key"
  python searcher.py --type drive --query "VFD drive datasheet" --api brave --output drive_urls.json

  # Append to existing urls.json
  python searcher.py --type gearhead --query "gearbox specifications" --append urls.json
        """,
    )

    parser.add_argument(
        "-t",
        "--type",
        required=True,
        help="Product type (motor, drive, robot_arm, gearhead, etc.)",
    )

    parser.add_argument(
        "-q",
        "--query",
        nargs="+",
        required=True,
        help="Search query/queries (can specify multiple)",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("search_results.json"),
        help="Output file path (default: search_results.json)",
    )

    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing urls.json file instead of creating new",
    )

    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum results per search query (default: 10)",
    )

    parser.add_argument(
        "--api",
        choices=["duckduckgo", "brave"],
        default="duckduckgo",
        help="Search API to use (default: duckduckgo)",
    )

    parser.add_argument(
        "--api-key",
        help="API key for services that require it (Brave). Can also use BRAVE_API_KEY env var",
    )

    args = parser.parse_args()

    # Get API key from args or environment
    api_key = args.api_key or os.environ.get("BRAVE_API_KEY")

    # Perform search
    results = search_for_products(
        product_type=args.type,
        search_terms=args.query,
        max_results_per_query=args.max_results,
        api=args.api,
        api_key=api_key,
    )

    if not results:
        logger.warning("No results found")
        sys.exit(1)

    # Prepare output
    if args.append and args.output.exists():
        # Load existing data
        logger.info(f"Appending to existing file: {args.output}")
        try:
            with open(args.output, "r") as f:
                existing_data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Could not parse existing JSON file: {args.output}")
            existing_data = {}

        # Append to product type array
        if args.type not in existing_data:
            existing_data[args.type] = []

        existing_data[args.type].extend(results)
        output_data = existing_data

        logger.info(
            f"Added {len(results)} new entries to '{args.type}' (total: {len(existing_data[args.type])})"
        )
    else:
        # Create new file
        output_data = {args.type: results}
        logger.info(f"Creating new file with {len(results)} entries")

    # Write output
    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"Results saved to: {args.output}")

    # Print summary
    print("\n" + "=" * 80)
    print(f"Search Summary for '{args.type}'")
    print("=" * 80)
    print(f"Total URLs found: {len(results)}")
    print(f"Output file: {args.output}")
    print("\nSample results:")
    for i, result in enumerate(results[:5], 1):
        print(f"\n{i}. {result['product_name']}")
        print(f"   Manufacturer: {result['manufacturer']}")
        print(f"   URL: {result['url'][:80]}...")

    if len(results) > 5:
        print(f"\n... and {len(results) - 5} more")

    print("\n" + "=" * 80)
    print("Next steps:")
    print(f"  1. Review the URLs in {args.output}")
    print(
        f"  2. Run scraper.py to extract data: uv run datasheetminer/scraper.py --type {args.type} --from-json {args.output} --json-index 0"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
