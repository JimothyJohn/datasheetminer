# tests

Test suite organized by execution environment. Only unit tests run offline with zero external dependencies.

## Structure

| Directory | Runner | Count | Requires |
|-----------|--------|------:|----------|
| `unit/` | pytest | ~670+ | Nothing (mocks, fixtures) |
| `integration/` | pytest | ~50 | Local build artifacts |
| `staging/` | pytest | ~40 | `API_BASE_URL` env var pointing to live staging server |
| `post_deploy/` | pytest | ~17 | `API_BASE_URL` env var pointing to production |

## Running Tests

```bash
# Unit tests only (fast, offline)
uv run pytest tests/unit/ -v

# With coverage
uv run pytest tests/unit/ --cov=datasheetminer --cov-report=term

# Staging tests (requires live server)
API_BASE_URL=https://staging.example.com uv run pytest tests/staging/ -v
```

## Key Files

- `conftest.py` — shared pytest fixtures
- `fixtures.py` — deterministic test data factories
- `COVERAGE.md` — detailed coverage breakdown by module

See [COVERAGE.md](COVERAGE.md) for the full report.
