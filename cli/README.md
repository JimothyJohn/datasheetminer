# cli

Command-line tools for batch processing, querying, and data management.

## Entry Points

| Command | File | Description |
|---------|------|-------------|
| `dsm-agent` | `agent.py` | Agent-facing CLI for end-to-end datasheet-to-database conversion. JSON output, structured exit codes. |
| `dsm` | `query.py` | Query products in DynamoDB with `--where` filters and `--sort` ordering |

## Supporting Modules

| File | Purpose |
|------|---------|
| `processor.py` | Processes extracted CSV into validated Pydantic models |
| `intake.py` | Scans S3 triage/ for incoming PDFs, classifies TOC and spec pages |
| `intake_guards.py` | Validation guards for the intake pipeline |
| `batch_process.py` | Bulk extraction from multiple datasheets |
| `triage.py` | Quality assessment and error classification for failed extractions |
| `quickstart.py` | Setup and demo script |

## Example

See [EXAMPLE.md](EXAMPLE.md) for a full motor sizing walkthrough using `dsm find`.
