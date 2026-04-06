# db

DynamoDB interface for product and datasheet storage.

## Single-Table Design

All items share one DynamoDB table with composite keys:

- **Products**: `PK=PRODUCT#MOTOR`, `SK=PRODUCT#<uuid>`
- **Datasheets**: `PK=DATASHEET#MOTOR`, `SK=DATASHEET#<uuid>`

## Files

| File | Purpose |
|------|---------|
| `dynamo.py` | Full CRUD client — create, read, list, batch operations, dedup checks, `value;unit` parsing |
| `pusher.py` | Batch push utility for bulk extraction results |
| `query.py` | Product query interface with filtering |
