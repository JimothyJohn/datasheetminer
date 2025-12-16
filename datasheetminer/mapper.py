#!/usr/bin/env python3
"""
Mapper Utility

This script uses Google Custom Search to find industrial equipment manufacturers
and provides their website details.
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Any

from googleapiclient.discovery import build
from dotenv import load_dotenv

from datasheetminer.models.manufacturer import Manufacturer

load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# https://programmablesearchengine.google.com/about/
CX_ID = os.getenv("SEARCH_ENGINE_ID")

def find_manufacturers(query: str, api_key: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Finds manufacturers based on a query using Google Custom Search API.
    """
    logger.info(f"Searching for manufacturers matching: '{query}'")
    
    try:
        service = build(
            "customsearch", "v1", developerKey=api_key
        )

        res = (
            service.cse()
            .list(
                q=query,
                cx=CX_ID,
            )
            .execute()
        )
        
        items = res.get("items", [])
        results = []
        logger.info(f"Found {len(items)} items")
        
        for item in items[:limit]:
            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet")
            })
            
        return results

    except Exception as e:
        logger.error(f"Error searching for manufacturers: {e}")
        return []

def results_to_manufacturers(results: List[Dict[str, Any]]) -> List[Manufacturer]:
    """
    Converts search results to Manufacturer Pydantic models.
    """
    manufacturers = []
    for res in results:
        manufacturers.append(
            Manufacturer(
                name=res.get("title", "Unknown"),
                website=res.get("link")
            )
        )
    return manufacturers

def main():
    parser = argparse.ArgumentParser(description="Datasheetminer Mapper - Find Manufacturers using Google Search")
    parser.add_argument("query", help="What to search for (e.g. 'industrial motors')")
    parser.add_argument("--limit", type=int, default=5, help="Max number of results to retrieve")
    parser.add_argument("--api-key", help="Google Search API Key (defaults to GOOGLE_SEARCH_API_KEY env var)")
    
    args = parser.parse_args()
    
    # Prefer arg, then GOOGLE_SEARCH_API_KEY, then fallback to GEMINI_API_KEY for backward compat if user hasn't switched env vars yet
    api_key = args.api_key or os.environ.get("GOOGLE_SEARCH_API_KEY")
    
    if not api_key:
        print("Error: detailed API key is required. Set GOOGLE_SEARCH_API_KEY or pass --api-key.")
        sys.exit(1)
        
    print(f"🔎 Finding manufacturers for: {args.query}...")
    results = find_manufacturers(args.query, api_key, limit=args.limit)
    
    if not results:
        print("No results found.")
        sys.exit(0)
    
    manufacturers = results_to_manufacturers(results)
        
    print(f"✅ Found {len(manufacturers)} manufacturers:")
    
    for i, m in enumerate(manufacturers):
        print(f"\n{i+1}. {m.name}")
        print(f"   🔗 {m.website}")
        print(f"   🆔 {m.id}")
            
    # Output results
    output_filename = f"mapper_results_{args.query.replace(' ', '_')}.json"
    
    # Convert models to dicts for JSON serialization
    serialized_results = [m.model_dump(mode='json') for m in manufacturers]
    
    with open(output_filename, "w") as f:
        json.dump(serialized_results, f, indent=2)
        
    print(f"\n✨ Done. Results saved to {output_filename}")


if __name__ == "__main__":
    main()
