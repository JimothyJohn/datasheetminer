# Dependency Cleanup

Remove unused dependencies to shrink install time, reduce attack surface, and simplify lock files.

## Backend (`app/backend/package.json`) — 5 removals

| Package | Reason |
|---|---|
| `canvas` | Zero imports in `app/backend/src/` |
| `muhammara` | Zero imports in `app/backend/src/` |
| `pdf-img-convert` | Zero imports in `app/backend/src/` |
| `pdf-parse` | Zero imports in `app/backend/src/` |
| `@aws-sdk/lib-dynamodb` | Listed but never imported — code uses `@aws-sdk/client-dynamodb` + `@aws-sdk/util-dynamodb` directly. Also remove from `externalModules` in `app/infrastructure/lib/api-stack.ts:51-57` |

## Python (`pyproject.toml`) — 3 production, 1 dev

| Package | Reason |
|---|---|
| `pycryptodome` | Zero imports (`Crypto` never used) |
| `playwright` | Zero imports (no browser automation in codebase) |
| `google-api-python-client` | Only imported in `mapper.py` which is dead code (not a CLI entry point) |
| `awslambdaric` (dev) | Zero imports in production or test code |

## Verified KEEP

- `pypdf2` — used in `datasheetminer/utils.py:17`
- `axios` — used in `scraper.ts:2`
- `pdf-lib`, `pdfjs-dist` — dynamically imported in `scraper.ts`
- All other deps have verified import sites

## Steps

1. Edit `app/backend/package.json` — remove 5 deps
2. Edit `app/infrastructure/lib/api-stack.ts` — remove `@aws-sdk/lib-dynamodb` from `externalModules`
3. Edit `pyproject.toml` — remove 3 production deps + 1 dev dep
4. `cd app && npm install` to regenerate lock
5. `uv sync` to regenerate Python lock
6. Run tests: backend Jest, frontend Vitest, Python pytest
