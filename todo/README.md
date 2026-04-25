# Backlog index

Single source of truth for *planned but not immediately necessary* work. Every active or deferred initiative in this repo gets a doc in `todo/`; this file is the index.

**Workflow:** before starting non-trivial work, scan the **Trigger conditions** table below. If anything you're about to touch matches, read the linked doc first and surface the deferred item with the user — don't silently fold it in.

When deferring new work, add a doc here with a `## Triggers` section at the bottom and update this index. The "trigger keywords" column is what makes the right doc auto-surface in future sessions; pick file paths or topics that future-you will plausibly mention.

---

## Active and deferred work

| Doc | Status | One-line summary |
|---|---|---|
| [ACTUATOR.md](ACTUATOR.md) | 🚧 in progress | Add `linear_actuator` product type; re-route 12 Tolomatic slugs out of `electric_cylinder`; clean up DB rows. |
| [CICD.md](CICD.md) | 🔴 urgent (CI red since 2026-03-30) | Fix `tests/unit/test_admin.py` import, then close the local↔CI gap. |
| [CONVERSION.md](CONVERSION.md) | ⏸ deferred | Header toggle for metric↔imperial display. Display-layer only, no DB changes. |
| [LOG_FEEDBACK.md](LOG_FEEDBACK.md) | 📝 itemized backlog | 14 independent log-derived improvements (429 handling, log volume, retention, etc.). |
| [MANUAL_UPDATES.md](MANUAL_UPDATES.md) | 📋 human-only checklist | Things agents can't do: repo secrets, branch protection, env files. |
| [edge-case-hardening.md](edge-case-hardening.md) | ✅ mostly shipped / ⏸ partial deferred | Test/coverage hardening across stack. See its Status table for per-phase state. |

Status legend: ✅ done · 🚧 in progress · ⏸ deferred · 🔴 urgent · 📝 itemized · 📋 manual

---

## Trigger conditions — when to surface which doc

Read this column-by-column. If your current task matches any "trigger" entry, the linked doc is queued and worth raising before you go further.

| Trigger (files / topics in your current task) | Surface |
|---|---|
| `datasheetminer/models/common.py`, any `datasheetminer/models/<type>.py`, `cli/schemagen`, `cli/ingest_tolomatic.py:SLUG_TO_TYPE`, talk of "actuator/cylinder/rodless/slide/stage" | [ACTUATOR.md](ACTUATOR.md) — also unblocks Phase 1d in [edge-case-hardening.md](edge-case-hardening.md) |
| `.github/workflows/`, `tests/unit/test_admin.py`, `cli/quickstart.py`, push to master, deploy attempt, "CI red" | [CICD.md](CICD.md) |
| `app/frontend/src/context/AppContext.tsx`, `ThemeToggle`, header components, "metric/imperial/units toggle/conversion" | [CONVERSION.md](CONVERSION.md) |
| Gemini retry / 429 / `RESOURCE_EXHAUSTED`, CloudWatch retention, `httpcore`/`httpx` log volume, `outputs/ingest_logs/`, scraper double-validation | [LOG_FEEDBACK.md](LOG_FEEDBACK.md) |
| GitHub repo secrets, AWS access keys, `.env.{dev,staging,prod}`, branch protection, DynamoDB deletion protection | [MANUAL_UPDATES.md](MANUAL_UPDATES.md) |
| `app/frontend/src/components/ProductList.tsx`, `FilterBar.tsx`, `AppContext.tsx`; user mentions latency/p95/load/perf; DynamoDB schema or PK/SK change; new product model | [edge-case-hardening.md](edge-case-hardening.md) |

When multiple docs match, mention all of them. Surfacing once is cheap; silently shipping work that conflicts with a deferred plan is expensive.

---

## How this index is kept honest

- Every `todo/*.md` ends with its own `## Triggers` section. This index aggregates them.
- When a doc's work is fully shipped, mark it ✅ here and either delete the doc or leave it as historical record (caller's call).
- When a new initiative starts that won't ship in the current session, write a `todo/<area>.md` with a Triggers section *before* leaving the session. Otherwise the deferred work has no surface.
- The matching memory pointer is `~/.claude/projects/-Users-nick-github-datasheetminer/memory/project_todo_backlog.md` (claude-code's auto-memory) — that's what makes this discoverable in future sessions without the user having to say "check todo/".
