#!/usr/bin/env python3
"""
Example MCP (Model Context Protocol) integration script for datasheetminer.

AI-generated comment: This script demonstrates how to use the datasheetminer CLI
programmatically for integration with MCP backends and database systems. It shows
various ways to process documents and store results in different formats.
"""

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import sqlite3
import csv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DocumentAnalysis:
    """Data class for storing document analysis results."""
    
    # AI-generated comment: This dataclass provides a structured way to store
    # analysis results, making it easy to serialize to various formats and
    # integrate with database systems.
    
    prompt: str
    url: str
    response: str
    timestamp: str
    analysis_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_csv_row(self) -> List[str]:
        """Convert to CSV row format."""
        return [
            self.analysis_id or "",
            self.prompt,
            self.url,
            self.response[:100] + "..." if len(self.response) > 100 else self.response,
            self.timestamp
        ]


class DatasheetMinerMCP:
    """
    MCP integration class for datasheetminer CLI.
    
    AI-generated comment: This class provides a programmatic interface to the
    datasheetminer CLI, making it easy to integrate with MCP backends and
    database systems. It handles batch processing, result storage, and
    various output formats.
    """
    
    def __init__(self, api_key: str, base_output_dir: Optional[Path] = None):
        """
        Initialize the MCP integration.
        
        Args:
            api_key: Gemini API key for authentication
            base_output_dir: Base directory for output files (optional)
        """
        self.api_key = api_key
        self.base_output_dir = base_output_dir or Path("mcp_output")
        self.base_output_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for different output types
        (self.base_output_dir / "json").mkdir(exist_ok=True)
        (self.base_output_dir / "csv").mkdir(exist_ok=True)
        (self.base_output_dir / "markdown").mkdir(exist_ok=True)
        (self.base_output_dir / "database").mkdir(exist_ok=True)
    
    def run_analysis(self, prompt: str, url: str, output_format: str = "text") -> DocumentAnalysis:
        """
        Run a single document analysis using the CLI.
        
        Args:
            prompt: Analysis prompt
            url: Document URL
            output_format: Output format (text, json, markdown)
            
        Returns:
            DocumentAnalysis object with results
        """
        try:
            # AI-generated comment: Use subprocess to call the CLI and capture output.
            # This approach allows for programmatic control while maintaining the
            # CLI's error handling and validation.
            
            cmd = [
                sys.executable, "-m", "datasheetminer",
                "--prompt", prompt,
                "--url", url,
                "--x-api-key", self.api_key,
                "--format", output_format
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Create analysis result
            analysis = DocumentAnalysis(
                prompt=prompt,
                url=url,
                response=result.stdout.strip(),
                timestamp=datetime.now().isoformat(),
                analysis_id=f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(url) % 10000:04d}"
            )
            
            logger.info(f"Analysis completed for {url}")
            return analysis
            
        except subprocess.CalledProcessError as e:
            logger.error(f"CLI execution failed: {e}")
            logger.error(f"STDOUT: {e.stdout}")
            logger.error(f"STDERR: {e.stderr}")
            raise
    
    def batch_analyze(self, analyses: List[Dict[str, str]], output_format: str = "text") -> List[DocumentAnalysis]:
        """
        Run multiple document analyses in batch.
        
        Args:
            analyses: List of dictionaries with 'prompt' and 'url' keys
            output_format: Output format for all analyses
            
        Returns:
            List of DocumentAnalysis objects
        """
        results = []
        
        for i, analysis_request in enumerate(analyses, 1):
            logger.info(f"Processing analysis {i}/{len(analyses)}: {analysis_request['url']}")
            
            try:
                result = self.run_analysis(
                    analysis_request['prompt'],
                    analysis_request['url'],
                    output_format
                )
                results.append(result)
                
                # Add small delay to avoid rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to analyze {analysis_request['url']}: {e}")
                # Continue with next analysis
        
        return results
    
    def save_to_json(self, analyses: List[DocumentAnalysis], filename: Optional[str] = None) -> Path:
        """
        Save analysis results to JSON file.
        
        Args:
            analyses: List of DocumentAnalysis objects
            filename: Output filename (optional)
            
        Returns:
            Path to saved file
        """
        if not filename:
            filename = f"analyses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output_path = self.base_output_dir / "json" / filename
        
        data = {
            "metadata": {
                "total_analyses": len(analyses),
                "generated_at": datetime.now().isoformat(),
                "format": "json"
            },
            "analyses": [analysis.to_dict() for analysis in analyses]
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved {len(analyses)} analyses to {output_path}")
        return output_path
    
    def save_to_csv(self, analyses: List[DocumentAnalysis], filename: Optional[str] = None) -> Path:
        """
        Save analysis results to CSV file.
        
        Args:
            analyses: List of DocumentAnalysis objects
            filename: Output filename (optional)
            
        Returns:
            Path to saved file
        """
        if not filename:
            filename = f"analyses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        output_path = self.base_output_dir / "csv" / filename
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow(['Analysis ID', 'Prompt', 'URL', 'Response Preview', 'Timestamp'])
            
            # Write data rows
            for analysis in analyses:
                writer.writerow(analysis.to_csv_row())
        
        logger.info(f"Saved {len(analyses)} analyses to {output_path}")
        return output_path
    
    def save_to_database(self, analyses: List[DocumentAnalysis], db_path: Optional[Path] = None) -> Path:
        """
        Save analysis results to SQLite database.
        
        Args:
            analyses: List of DocumentAnalysis objects
            db_path: Database file path (optional)
            
        Returns:
            Path to database file
        """
        if not db_path:
            db_path = self.base_output_dir / "database" / f"analyses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        # Ensure database directory exists
        db_path.parent.mkdir(exist_ok=True)
        
        # AI-generated comment: Create SQLite database with proper schema for
        # storing analysis results. This provides a structured way to query
        # and analyze results programmatically.
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                prompt TEXT NOT NULL,
                url TEXT NOT NULL,
                response TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        ''')
        
        # Insert data
        for analysis in analyses:
            cursor.execute('''
                INSERT OR REPLACE INTO analyses (id, prompt, url, response, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                analysis.analysis_id,
                analysis.prompt,
                analysis.url,
                analysis.response,
                analysis.timestamp,
                json.dumps(analysis.metadata) if analysis.metadata else None
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Saved {len(analyses)} analyses to database {db_path}")
        return db_path
    
    def query_database(self, db_path: Path, query: str) -> List[tuple]:
        """
        Query the analysis database.
        
        Args:
            db_path: Path to database file
            query: SQL query string
            
        Returns:
            List of query results
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        conn.close()
        return results


async def main():
    """Example usage of the MCP integration."""
    
    # AI-generated comment: This main function demonstrates how to use the
    # MCP integration class for batch processing and various output formats.
    
    # Set your API key (in production, use environment variables)
    api_key = "your-gemini-api-key-here"
    
    # Initialize MCP integration
    mcp = DatasheetMinerMCP(api_key)
    
    # Example analysis requests
    analyses_requests = [
        {
            "prompt": "Extract key technical specifications and summarize the main features",
            "url": "https://example.com/datasheet1.pdf"
        },
        {
            "prompt": "Identify the power requirements and operating conditions",
            "url": "https://example.com/datasheet2.pdf"
        },
        {
            "prompt": "List all safety warnings and compliance information",
            "url": "https://example.com/datasheet3.pdf"
        }
    ]
    
    try:
        # Run batch analysis
        logger.info("Starting batch analysis...")
        results = await mcp.batch_analyze(analyses_requests, output_format="markdown")
        
        if results:
            # Save results in multiple formats
            json_file = mcp.save_to_json(results)
            csv_file = mcp.save_to_csv(results)
            db_file = mcp.save_to_database(results)
            
            logger.info(f"Analysis complete! Results saved to:")
            logger.info(f"  JSON: {json_file}")
            logger.info(f"  CSV: {csv_file}")
            logger.info(f"  Database: {db_file}")
            
            # Example database query
            query_results = mcp.query_database(db_file, "SELECT COUNT(*) FROM analyses")
            logger.info(f"Total analyses in database: {query_results[0][0]}")
            
        else:
            logger.warning("No analyses completed successfully")
            
    except Exception as e:
        logger.error(f"Batch analysis failed: {e}")


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
