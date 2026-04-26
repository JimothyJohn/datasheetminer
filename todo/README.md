# Backlog index

Single source of truth for *planned but not immediately necessary* work. Every active or deferred initiative in this repo gets a doc in `todo/`; this file is the index and the call-sheet.

**Workflow:** before starting non-trivial work, scan the **Trigger conditions** table below. If anything you're about to touch matches, read the linked doc first and surface the deferred item with the user — don't silently fold it in.

When deferring new work, add a doc here with a `## Triggers` section at the bottom and update this index. Pick triggers (file paths, topics) that future-you will plausibly mention, so the right doc auto-surfaces in future sessions.

---

## Active and deferred work

| # | Doc | Status | Effort | One-line summary |
|---|-----|--------|--------|------------------|
| 1 | [CICD.md](CICD.md) | 🔴 urgent (CI red since 2026-03-30) | 🟢 small | Fix `tests/unit/test_admin.py` import, then close the local↔CI gap. |
| 2 | [REBRAND.md](REBRAND.md) | 🚧 in progress (Stages 1+2 ✅ 2026-04-26) | 🟡 medium | Datasheetminer → Specodex. Staged: landing ✅ → app chrome ✅ → repo rename → DNS cutover. Domain registered 2026-04-26. |
| 3 | [INTEGRATION.md](INTEGRATION.md) | 🚧 phases A+B shipped 2026-04-26 | 🟢 small | Motion-system builder — drive → motor → gearhead. Next slice: chain-review modal + BOM copy + "looks complete" tray state. UI-only. |
| 4 | [DEDUPE.md](DEDUPE.md) | ⏸ deferred | 🟡 medium (high blast radius) | One-time cross-vendor sweep for prefix-drift duplicates left by `--force` re-ingests pre-family-aware-ID fix. Audit + safe-merge + human review. |
| 5 | [GODMODE.md](GODMODE.md) | 📐 planned | 🔴 large | One-page admin dashboard: Gemini + Claude usage, ingest health, DB health, repo activity, deploy state. Local + deployed split. |

Status legend: ✅ done · 🚧 in progress · ⏸ deferred · 🔴 urgent · 📐 planned
Effort legend: 🟢 ≤ 1 day, low risk · 🟡 multi-day, some unknowns · 🔴 multi-week or high blast radius

---

## Suggested chronological order

The order in the table above is the order to tackle these in. Reasoning:

1. **CICD first.** CI has been red since 2026-03-30; until it goes green, every deploy is hand-flown and every PR's signal is ambiguous. Single test file's import — short, contained, unblocks everything else. Don't start anything else with CI red.

2. **REBRAND finish.** Already in flight, two of four stages done. The remaining work (repo rename, DNS cutover for `specodex.com`) is mostly mechanical AWS + GitHub plumbing. Close the thread before it goes stale, and so future docs/links stop referencing the old name. Sequence the repo rename *before* INTEGRATION's next slice so trigger paths in the docs don't drift mid-feature.

3. **INTEGRATION next slice.** Small, high user-facing payoff (chain-review modal + BOM copy + completion state). Half-day estimate, UI-only, no backend changes. Good momentum lift after the chores above.

4. **DEDUPE.** Deferred for a reason — touches production DynamoDB rows and needs human review on conflicts. Don't schedule alongside other in-flight data work; pick a session where nothing else is mutating the table. Risk is "wrong merge silently loses spec data" — measure twice, cut once.

5. **GODMODE last.** Biggest surface area (Gemini + Claude usage telemetry, ingest log analytics, DynamoDB health, repo activity, deploy state). Planned but cold — no one's blocking on it. Pick up only after the above four land, and ideally only when there's a real operational pain point to anchor the design.

**Out-of-band exceptions.** Urgent bugs, security issues, or user-visible breakage jump the queue. The order above is for self-directed work, not interrupts.

---

## Trigger conditions — when to surface which doc

If your current task matches any "trigger" entry, the linked doc is queued and worth raising before you go further.

| Trigger (files / topics in your current task) | Surface |
|---|---|
| `.github/workflows/`, `tests/unit/test_admin.py`, `cli/quickstart.py`, push to master, deploy attempt, "CI red" | [CICD.md](CICD.md) |
| `cli/admin.py:purge`/`promote`, `datasheetminer/ids.py:compute_product_id` or `_strip_family_prefix`, new vendor catalog with prefix-form drift (Mitsubishi MR-J5, Yaskawa Σ-7, Siemens 1FK); user mentions "duplicate", "dedupe", "merge rows", "same product twice", "two part numbers for one motor"; promotion to staging/prod | [DEDUPE.md](DEDUPE.md) |
| `app/backend/src/routes/admin.ts`, `app/backend/src/middleware/adminOnly.ts`, `AdminPanel.tsx`, `datasheetminer/ingest_log.py`, `datasheetminer/llm.py`, `cli/bench.py:PRICING`, "godmode/dashboard/observability/Gemini cost/Claude usage/what's going on" | [GODMODE.md](GODMODE.md) |
| `datasheetminer/integration/{ports,adapters,compat}.py`, `app/backend/src/services/compat.ts`, `app/backend/src/routes/compat.ts`, `app/frontend/src/utils/compat.ts`, `BuildTray.tsx`, `CompatChecker.tsx`, `tests/unit/test_integration.py`; user mentions "compat", "compatibility", "pairing", "matching", "build", "BOM", "system", "chain", "compatible parts" | [INTEGRATION.md](INTEGRATION.md) |
| `app/frontend/src/` styling/theme/palette/fonts; landing page or App.tsx routes; "datasheetminer" in user-facing copy; ACM cert / Route 53 / CloudFront alt-domain for `specodex.com`; CDK Frontend stack viewer cert; repo rename | [REBRAND.md](REBRAND.md) |

When multiple docs match, mention all of them. Surfacing once is cheap; silently shipping work that conflicts with a deferred plan is expensive.

---

## How this index is kept honest

- Every `todo/*.md` ends with its own `## Triggers` section. This index aggregates them.
- When a doc's work is fully shipped, mark it ✅ here and either delete the doc or leave it as historical record (caller's call).
- When a new initiative starts that won't ship in the current session, write a `todo/<area>.md` with a Triggers section *before* leaving the session. Otherwise the deferred work has no surface.
- The matching memory pointer is `~/.claude/projects/-Users-nick-github-datasheetminer/memory/project_todo_backlog.md` (claude-code's auto-memory) — that's what makes this discoverable in future sessions without the user having to say "check todo/".
