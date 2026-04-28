# Backlog index

Single source of truth for *planned but not immediately necessary* work. Every active or deferred initiative in this repo gets a doc in `todo/`; this file is the index and the call-sheet.

**Workflow:** before starting non-trivial work, scan the **Trigger conditions** table below. If anything you're about to touch matches, read the linked doc first and surface the deferred item with the user — don't silently fold it in.

When deferring new work, add a doc here with a `## Triggers` section at the bottom and update this index. Pick triggers (file paths, topics) that future-you will plausibly mention, so the right doc auto-surfaces in future sessions.

---

## Active and deferred work

Ordered by **dependency-and-rework risk**, not by urgency or size. The
goal is to avoid landing work that has to be redone once a downstream
refactor reshapes its substrate. See the chronological-order section
below for the reasoning per row.

| # | Doc | Status | Effort | One-line summary |
|---|-----|--------|--------|------------------|
| 1 | [CICD.md](CICD.md) | 🚧 nearly done — verify on next push | 🟢 small | Fix `tests/unit/test_admin.py` import, then close the local↔CI gap. Expected to go green on the next master push. |
| 2 | [REBRAND.md](REBRAND.md) | 🚧 in progress (Stages 1+2 ✅ 2026-04-26) | 🟡 medium | Datasheetminer → Specodex. Staged: landing ✅ → app chrome ✅ → repo rename → DNS cutover. Domain registered 2026-04-26. |
| 3 | [UNITS.md](UNITS.md) | 📐 planned | 🟡 medium (1.5–2 days code + ½ day review) | **Linchpin.** Drop `"value;unit"` compact strings — go full JSON dicts end-to-end. Reshapes Pydantic models, DB layer, and frontend rendering, so it gates DEDUPE / INTEGRATION / FRONTEND_TESTING / GODMODE. |
| 4 | [DEDUPE.md](DEDUPE.md) | ⏸ deferred | 🟡 medium (high blast radius) | One-time cross-vendor sweep for prefix-drift duplicates left by `--force` re-ingests pre-family-aware-ID fix. Audit + safe-merge + human review. |
| 5 | [INTEGRATION.md](INTEGRATION.md) | 🚧 phases A+B shipped 2026-04-26 | 🟢 small | Motion-system builder — drive → motor → gearhead. Next slice: chain-review modal + BOM copy + "looks complete" tray state. UI-only. |
| 6 | [FRONTEND_TESTING.md](FRONTEND_TESTING.md) | 📐 planned | 🟢 small (half-day, 8 phases) | Lock down "simple but crucial" frontend state — persistence keys, AppContext setters, ProductList type-switch resets, header toggles, FilterChip unit propagation. Catches L1–L12 spillover bestiary. |
| 7 | [GODMODE.md](GODMODE.md) | 📐 planned | 🔴 large | One-page admin dashboard: Gemini + Claude usage, ingest health, DB health, repo activity, deploy state. Local + deployed split. |

Status legend: ✅ done · 🚧 in progress · ⏸ deferred · 🔴 urgent · 📐 planned
Effort legend: 🟢 ≤ 1 day, low risk · 🟡 multi-day, some unknowns · 🔴 multi-week or high blast radius

---

## Suggested chronological order

Sequenced to minimize **rework after a downstream refactor reshapes
the substrate**. UNITS is the linchpin — it touches Pydantic models,
the DynamoDB serialization layer, and the frontend rendering path,
which together are the substrate for DEDUPE (DB rows), INTEGRATION's
spec rendering, FRONTEND_TESTING's assertions, and any GODMODE panel
that displays specs. Land UNITS first and the rest of the queue
operates on a stable shape; land it later and each of those four
gets re-touched.

1. **CICD — close out.** Expected to go green on the next master push. Verify on the next deploy attempt and mark ✅ here. Don't start dependency-sensitive work until CI signal is trustworthy.

2. **REBRAND finish.** Already in flight, two of four stages done. Repo rename + DNS cutover for `specodex.com` is mechanical AWS + GitHub plumbing — touches no Python/TS code paths, so it's genuinely independent of UNITS. Close the thread before it goes stale, and so future docs/links stop referencing the old name.

3. **UNITS — landmine clearance.** Phases 1–4 ship as one PR series with no behavior change visible to users (same Gemini schema, same DynamoDB shape, same API responses). Phase 5 is the user-visible fix (rotor_inertia stops leaking semicolons). Phase 6 is housekeeping. Land this **before** anything that consumes spec values:
   - DEDUPE compares fields across rows — much cleaner against uniform `{value, unit}` dicts than against a mix of dicts and regex-leaked strings.
   - INTEGRATION's chain-review modal renders specs — if it ships first, devs may mirror the defensive `String(value)` fallback that UNITS phase 4 deletes.
   - FRONTEND_TESTING locks down `FilterChip × unitSystem` and rendering paths — assertions baked against the current shape get rewritten when UNITS phase 4 lands.
   - GODMODE panels that display specs would inherit the same risk.

4. **DEDUPE.** Operates on the post-UNITS uniform data. Auto-merge's "complementary fields" check is dict-vs-dict, no string-vs-dict edge cases. Still touches production DynamoDB rows and needs human review on conflicts — don't schedule alongside other data work.

5. **INTEGRATION next slice.** UI-only, chain-review modal + BOM copy + completion state. Lands on the cleaned-up frontend rendering path with no string fallback to mirror.

6. **FRONTEND_TESTING.** Tests get written against the canonical post-UNITS shape (`{value, unit}` everywhere, no string fallback). Doing this before UNITS means re-asserting every unit-handling test once UNITS reshapes the code paths.

7. **GODMODE last.** Biggest surface area (Gemini + Claude usage telemetry, ingest log analytics, DynamoDB health, repo activity, deploy state). Planned but cold — no one's blocking on it. Lands on a stable substrate so panels don't get retouched.

**Soft parallelism.** REBRAND and UNITS don't overlap in code paths
(REBRAND = DNS + git remote; UNITS = Python/TS code + data) so they
can interleave if you have a window blocked on AWS propagation.
Everything from #4 down should run in series — they all touch
overlapping frontend or DB surface area.

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
| `app/frontend/src/utils/localStorage.ts`; `app/frontend/src/context/AppContext.tsx` (new persisted key); `ProductList.tsx` type-switch effect; `FilterChip.tsx` × `unitSystem`; `BuildTray.tsx`; `*.test.{ts,tsx}` under `app/frontend/`; user mentions "spillover", "state leak", "stale filter", "stuck on page", "wrong unit", "frontend tests", "vitest" | [FRONTEND_TESTING.md](FRONTEND_TESTING.md) |
| `specodex/models/common.py` (`ValueUnit`/`MinMaxUnit`/`handle_*_input`/`validate_*_str`); product model field annotations or hardcoded `"X;unit"` defaults; `specodex/units.py:normalize_value_unit`/`_COMPACT_RE`; `specodex/db/dynamo.py:_parse_compact_units`; `app/backend/src/db/dynamodb.ts:parseCompactUnits`; `specodex/models/llm_schema.py:to_gemini_schema`; `specodex/schemagen/renderer.py`; user mentions "semicolon in UI", "value;unit", "rotor inertia displayed wrong", "compact string", "scientific notation in specs" | [UNITS.md](UNITS.md) |

When multiple docs match, mention all of them. Surfacing once is cheap; silently shipping work that conflicts with a deferred plan is expensive.

---

## How this index is kept honest

- Every `todo/*.md` ends with its own `## Triggers` section. This index aggregates them.
- When a doc's work is fully shipped, mark it ✅ here and either delete the doc or leave it as historical record (caller's call).
- When a new initiative starts that won't ship in the current session, write a `todo/<area>.md` with a Triggers section *before* leaving the session. Otherwise the deferred work has no surface.
- The matching memory pointer is `~/.claude/projects/-Users-nick-github-datasheetminer/memory/project_todo_backlog.md` (claude-code's auto-memory) — that's what makes this discoverable in future sessions without the user having to say "check todo/".
