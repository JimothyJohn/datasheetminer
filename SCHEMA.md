# Data Schema Examples

This document provides schema guidance for extracting structured data from technical datasheets.

## Schema Evolution

As you process more datasheets, refine these schemas to:
- Add new fields discovered in datasheets
- Standardize units and naming conventions
- Share relevant parameters between components

## DynamoDB & NoSQL Considerations

The schemas below are designed for NoSQL databases, with specific best practices for AWS DynamoDB in mind:

- **Self-Contained Documents**: Each JSON object represents a single item and contains all its relevant information. This is ideal for DynamoDB as it avoids the need for complex, multi-item transactions that are less efficient.
- **Flexible Schema**: You can easily add new fields to documents without affecting existing items in your table.
- **Single-Table Design**: A `type` field has been added to distinguish between different kinds of items ('motor', 'drive'). This is a common pattern in DynamoDB for storing different entity types in the same table, which can be more efficient and reduce operational overhead. You can create a GSI on this `type` field to efficiently query for all items of a certain type.
- **Data Provenance**: A `datasheet` object is included to store the source URL and page numbers for the extracted data. This is crucial for verification and traceability.
