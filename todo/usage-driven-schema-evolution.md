# Usage-Driven Schema Evolution

> "Eventually I'll want to use the most-added specs to update the default
> schema into stored tables but that's WAY down the line. I principally
> want the way users click on the website to intelligently make it more
> adaptable and powerful for theirs and others preferences."

Long-term vision: let the real interaction signal — what users click,
hide, restore, sort, and filter on — drive the default filter + column
schema, instead of a human hand-tuning `getXxxAttributes()` lists in
`app/frontend/src/types/filters.ts`. The infrastructure for this lands
piecewise as new product types get added; no single big rewrite.

## The signal we already capture (locally)

Nothing is logged yet. But every one of these already lives in
`localStorage` as of 2026-04-17:

| Key | Signal | Weight hint |
|---|---|---|
| `productListHiddenColumns` | user ×'d this column → less useful | strong negative |
| `productListMaxVisibleColumns` | user wants at most N columns | calibrates cap default |
| `productListColumnSortDirection` | A→Z vs Z→A preference | minor |
| `productListRowDensity` | compact vs comfy | UX, not schema |
| (pending) `productListSortedAttributes` | user sorted by this column | strong positive |
| (pending) `productListFilteredAttributes` | user filtered on this column | strongest positive |

The last two aren't stored yet — sort + filter state lives in component
state, not `localStorage`. Extending persistence to cover them is the
first concrete step.

## Four implementation stages

### Stage 1 — Instrument

Emit structured events (client-side only, no network) on:
- column hide (`column_hidden`)
- column restore (`column_restored`)
- column sorted (`column_sorted`, with direction)
- filter added (`filter_added`, with operator + attribute)
- attribute-selector opened (`restore_dropdown_opened`)

Store as a capped rolling buffer in `localStorage`
(e.g. `productListInteractionLog`, last 500 events). No UUID, no user
id — just events + timestamps. Pure local telemetry until Stage 3.

**Cost:** ~1 day. Touches `ProductList.tsx` and `FilterBar.tsx`. Adds
one tiny `utils/interactionLog.ts`. No backend changes.

### Stage 2 — Local score

Derive a per-`(product_type, attribute)` usefulness score from the
event log. Simple linear model:

```
score(type, attr) =
    1.0 * filters(attr)
  + 0.6 * sorts(attr)
  + 0.3 * restores(attr)
  - 0.8 * hides(attr)
```

Normalize per `product_type` so hot fields in one type don't dominate
the global picture.

Use the score to **re-rank** the default `columnAttributes` ordering:
instead of strict alphabetical, surface the user's high-score
attributes first. Fall back to alphabetical for never-touched
attributes (neutral score). Keep the Z↓A / A↓Z toggle as an override.

**Cost:** ~half day of frontend work. No backend. This alone makes the
UI feel "adaptive" for a single user.

### Stage 3 — Aggregate

Only after Stage 2 is validated worth doing: send the local score
(not raw events) to a lightweight backend endpoint. One POST per
session-end, payload shape:

```json
{
  "session_id": "<uuid>",
  "product_type": "motor",
  "scores": { "rated_power": 12.3, "rated_torque": 9.7, ... }
}
```

Persist in a DynamoDB item per `(product_type, session_id)`. Batch-job
(or on-write aggregate) rolls up `avg(score)` + `count(sessions)` per
`(product_type, attribute)` into an `AttributePopularity` item.

**Cost:** moderate — new DynamoDB access pattern, opt-in consent
copy, telemetry endpoint, and privacy review before this ships. Don't
start until Stage 2 has ≥ 1 month of local data proving the signal is
real. Consent is load-bearing — most users will opt in if the value
is clear ("help us show the specs you care about first") but silently
collecting behavioral data isn't worth the trust hit.

### Stage 4 — Feed back into the code

Two application targets, in decreasing risk:

1. **Rank curated static lists** (low risk). Rewrite
   `getMotorAttributes()` etc. to sort by aggregate popularity. Safe
   because the attributes themselves don't change — only their order.
   Done as a scheduled PR (e.g. weekly cron opens a PR with the new
   ordering, human merges).

2. **Propose new Pydantic fields** (higher risk). When
   `deriveAttributesFromRecords` consistently surfaces a field that's
   not in any static list AND has a high aggregate score, surface it
   as a suggestion for `schemagen` — "users care about field X on 40%
   of contactor records, consider adding to `Contactor` model". Still
   human-merged, never auto-applied.

## Out of scope / explicit non-goals

- **Auto-applying schema changes.** A bad aggregation that auto-mutates
  `models/drive.py` is a nightmare to roll back. Human merge, always.
- **Personalized per-user column ordering in Stage 3+.** The popularity
  aggregate is per-`product_type`, not per-user. If personalization
  becomes a goal it's a separate feature with its own consent model.
- **Cross-product-type learning.** Keep scores keyed by
  `(product_type, attribute)`. A field popular on motors doesn't tell
  us anything about contactors; don't generalize.

## What to do first

Stage 1 is the smallest useful piece. It's strictly additive, ships
without any backend, and gives us local data to calibrate the Stage 2
score weights. Start there when the UX work queue is empty; skip the
rest until the logs show a clear signal.

## Open questions

- **Weighting:** are my 1.0 / 0.6 / 0.3 / -0.8 weights right? Won't
  know until Stage 1 runs for a couple weeks.
- **Storage budget for the rolling event log:** 500 events × ~80 bytes
  = 40 KB per user in localStorage. Fine. If we ever go higher, swap
  to IndexedDB.
- **What happens when a schema field is renamed?** Scores keyed by the
  old name get orphaned. Need a migration path before Stage 4.
