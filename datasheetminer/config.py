GUARDRAILS = """
Your output should be raw JSON with no additional text or formatting.
"""

SCHEMA_GUIDANCE = """
The schemas are designed for NoSQL databases, with specific best practices for AWS DynamoDB in mind:

- **Self-Contained Documents**: Each JSON object represents a single item and contains all its relevant information. This is ideal for DynamoDB as it avoids the need for complex, multi-item transactions that are less efficient.
- **Data Provenance**: A `datasheet` object is included to store the source URL and page numbers for the extracted data. This is crucial for verification and traceability.
"""
