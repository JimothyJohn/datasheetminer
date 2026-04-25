# Metric ↔ Imperial unit toggle

## Goal

A header switch (next to `ThemeToggle`) that flips every metric value on
the site to its imperial equivalent and back, without touching the
database. All conversion happens at display time. State persists in
`localStorage` like the theme.

Examples (canonical → imperial):

| Quantity     | Canonical (DB) | Imperial         | Factor                |
|--------------|----------------|------------------|-----------------------|
| Force        | `N`            | `lbf`            | 1 N = 0.224809 lbf    |
| Torque       | `Nm`           | `in·lb`          | 1 Nm = 8.85075 in·lb  |
| Mass         | `kg`           | `lb`             | 1 kg = 2.20462 lb     |
| Length       | `mm`           | `in`             | 1 mm = 0.0393701 in   |
| Temperature  | `°C`           | `°F`             | F = C × 9/5 + 32      |
| Inertia      | `kg·cm²`       | `oz·in²`         | 1 kg·cm² = 13.887 oz·in² |
| Linear speed | `m/s`          | `ft/s`           | 1 m/s = 3.28084 ft/s  |
| Pressure     | `bar`          | `psi`            | 1 bar = 14.5038 psi   |

Quantities with no idiomatic imperial form pass through unchanged:
voltage (V), current (A), resistance (Ω), inductance (mH), rotational
speed (rpm), frequency (Hz), efficiency (%), backlash (arcmin), service
life (hours), IP rating, dB(A), counts, booleans.

Power (W ↔ hp) is **out of scope for v1** — most catalogs already
publish both, and converting silently makes column units ambiguous.
Revisit if a user asks.

## Non-goals

- No backend / DynamoDB changes. The store stays canonical metric. A
  user with imperial toggled who exports a row to JSON still sees `Nm`,
  because that is what the DB holds.
- No re-ingest, no migration, no edits to `datasheetminer/units.py`
  (that file is ingest-time alias→canonical normalization, a separate
  concern from display-time canonical→imperial).
- No conversion of compound units (`V/krpm`, `Nm/A`, `Nm/arcmin`,
  `Nm/√A`). These are coefficients, not human-facing readouts; flipping
  half of the unit would mislead more than it would help. They display
  as-is regardless of toggle.
- No user-configurable per-quantity overrides (e.g. "I want lb-ft, not
  in·lb"). One imperial preset, hardcoded.

## Architecture

Conversion is a **pure display-layer transformation** that runs after
the API response is parsed and before any string formatting. The
internal state of the app (sort comparators, filter ranges,
`Product` objects in React state) stays metric. Only the rendered text
and the displayed unit string change.

This means filter chips, range sliders, and sort logic all keep working
without modification — they continue to operate on canonical numeric
values. The toggle only affects what the user sees and types.

### Data flow

```
DynamoDB (canonical metric)
  → backend deserialization (already produces {value,unit} / {min,max,unit} objects)
  → React state (still canonical metric)
  → display components
      → unit-conversion shim (reads UnitSystemContext)
      → formatValue / renderNestedObject
      → DOM
```

Filter inputs accept user-typed values in **whichever system is
active**, then convert *into* canonical metric before applying the
filter. So if the user toggles to imperial and types "10 lbf" in a
force filter, the comparator runs against 44.48 N internally.

## Implementation plan

Six pieces, in dependency order. Each step is independently testable.

### 1. Conversion utility — `app/frontend/src/utils/unitConversion.ts` (new)

Pure functions, no React, no DOM. Exported surface:

```ts
export type UnitSystem = 'metric' | 'imperial';

// Per-family conversion entry: canonical metric → imperial.
//   target: imperial unit string for display
//   forward(metricValue): imperial number
//   inverse(imperialValue): metric number   (for filter input parsing)
//   precision: significant figures in display (default 4)
interface UnitConversion {
  target: string;
  forward: (n: number) => number;
  inverse: (n: number) => number;
  precision?: number;
}

// Keyed by *canonical* metric unit string as it appears in AttributeMetadata
// and in the value-unit objects coming back from the API.
export const IMPERIAL_CONVERSIONS: Record<string, UnitConversion>;

// Convert a single { value, unit } pair. Returns the same shape with
// numeric value rounded and unit replaced. If the unit isn't in the
// table, returns the input untouched.
export function convertValueUnit(
  vu: { value: number | string; unit: string },
  system: UnitSystem,
): { value: number | string; unit: string };

// Same for { min, max, unit } pairs.
export function convertMinMaxUnit(
  mmu: { min: number | string; max: number | string; unit: string },
  system: UnitSystem,
): { min: number | string; max: number | string; unit: string };

// Inverse direction — accepts a number in the active display system
// and returns the canonical metric value. Used by filter input parsing.
export function toCanonical(value: number, displayUnit: string, system: UnitSystem): number;

// Resolve the unit string we should *show* for a given canonical unit
// under the active system. Used by ProductList column headers and
// filter chip labels where unit is rendered separately from value.
export function displayUnit(canonicalUnit: string, system: UnitSystem): string;
```

Initial `IMPERIAL_CONVERSIONS` table (mirrors the metric canonicals
in `datasheetminer/models/common.py:UnitFamily` definitions):

| Canonical key | target | forward                       |
|---------------|--------|-------------------------------|
| `N`           | `lbf`  | `n => n * 0.2248089`          |
| `Nm`          | `in·lb`| `n => n * 8.850746`           |
| `kg`          | `lb`   | `n => n * 2.204623`           |
| `mm`          | `in`   | `n => n * 0.0393701`          |
| `°C`          | `°F`   | `n => n * 9/5 + 32`           |
| `kg·cm²`      | `oz·in²`| `n => n * 13.8874`           |
| `m/s`         | `ft/s` | `n => n * 3.28084`            |
| `bar`         | `psi`  | `n => n * 14.50377`           |

Round display values: 4 sig figs, drop trailing zeros, integer when
whole. Reuse the rounding logic from
`datasheetminer/units.py:_round_converted` (port to TS — small).

**Tests** (`unitConversion.test.ts`):
- Each entry round-trips: `inverse(forward(x)) ≈ x` within 1e-9.
- `convertValueUnit({value: 100, unit: 'N'}, 'imperial')` → `{value: 22.48, unit: 'lbf'}`.
- `convertValueUnit({value: 100, unit: 'N'}, 'metric')` → unchanged.
- Unknown unit (e.g. `V`) passes through in both directions.
- Range conversion preserves min ≤ max ordering.
- Negative temperatures (offset, not multiplier): `0 °C` → `32 °F`,
  `-40 °C` → `-40 °F`.
- String values that aren't parseable as numbers (`"~5"`, `"approx 10"`)
  pass through with unit replaced — better to mis-label than to crash.

### 2. State — extend `AppContext` (`app/frontend/src/context/AppContext.tsx`)

Add a single field + setter to the existing context (don't make a new
provider — this is shared global state and `AppContext` is already the
shared bus):

```ts
interface AppContextType extends AppState {
  // ...existing fields
  unitSystem: UnitSystem;
  setUnitSystem: (s: UnitSystem) => void;
}
```

Initial value loaded from `localStorage` via `safeLoadString` (key:
`'unitSystem'`, default `'metric'`). On set, persist via `safeSave` and
update state. No re-fetch needed — conversion is purely client-side.

**Why AppContext, not a new context**: a separate provider would force
every consumer that already calls `useApp()` to also call
`useUnitSystem()`, doubling the wiring. The state is one boolean and
the API surface is two methods; the cost of co-locating it is zero.

### 3. Toggle UI — `app/frontend/src/components/UnitToggle.tsx` (new)

Mirror `ThemeToggle.tsx` exactly (same shape, same className
conventions, same a11y attributes). Two-state button showing `M` /
`Imp` (or sun/moon-equivalent SI/US icons). Reads `unitSystem` from
`useApp()`, calls `setUnitSystem` on click.

Mount it next to `<ThemeToggle />` in the header. One-line edit in
whichever component currently renders the theme toggle (search for
`<ThemeToggle` to find the parent).

### 4. Display integration — three call sites

The frontend has **three** spots where `{value, unit}` objects get
turned into strings. Each needs a one-line read of `unitSystem` from
context and a wrap of the input through `convertValueUnit` /
`convertMinMaxUnit` before the existing format logic runs.

**4a. `app/frontend/src/utils/formatting.ts:formatValue`** — used by
`ProductList`. Currently a free function; add an optional `system`
parameter (default `'metric'` so existing tests still pass) and apply
`convertValueUnit` / `convertMinMaxUnit` at each `'value' in value &&
'unit' in value` and `'min' in value && 'max' in value && 'unit' in
value` branch (lines 86-114 and the array branches at 86-99). The
recursive call passes `system` through.

`ProductList.tsx:25` calls this; it should read `unitSystem` from
`useApp()` and pass it down. Same for the column header derivation
that renders unit strings — use `displayUnit(canonical, system)`.

**4b. `app/frontend/src/components/ProductDetailModal.tsx:formatValue`** —
local function at line 54, mirrors the one above. Same change: thread
`system` from `useApp()` through `formatValue` and `renderNestedObject`.
This is the modal that opens on row click.

**4c. `app/frontend/src/components/FilterBar.tsx` / `FilterChip.tsx`** —
filter chip labels show ranges and units. Convert displayed unit and
range bounds. **Don't** convert the underlying filter state — keep the
state in canonical metric, only translate at the UI boundary.

After this step the **display side** is done: every rendered value
flips when the toggle flips.

### 5. Filter input — accept imperial input when imperial is active

`app/frontend/src/utils/filterValues.ts` parses user-typed range
filters. When `unitSystem === 'imperial'`, the parsed numbers are in
the displayed imperial unit and need `toCanonical(n, canonicalUnit,
'imperial')` before being stored as filter state.

Mechanically: filter state stays metric; only the input/output adapter
layer translates. This keeps comparator logic untouched — comparators
already compare against canonical numeric values from the records.

The cleanest place to thread it is wherever the filter input change
handler lives (likely `FilterBar.tsx`). The handler reads `unitSystem`
from context and calls `toCanonical` before `setFilterValue`.

**Test** (`filterValues.test.ts` — extend existing):
- User types `10` in a torque filter with imperial active → state
  stores `1.1298 Nm`. Re-rendering with metric active shows `1.13 Nm`;
  re-rendering with imperial shows `10 in·lb`.
- Same with range filters: typing `0–100 lbf` stores `0–444.82 N`.

### 6. Distribution chart axes — `DistributionChart.tsx`

Histogram axis labels currently bake the canonical unit into the tick
formatter. Read `unitSystem` from context, run bucket boundaries
through `convertValueUnit` for display, leave the underlying bucketing
metric.

Charts are the most visually loud place a unit mismatch shows up
("Torque distribution" with Nm-scale ticks but lbf labels). Worth
auditing every axis, not just the one a quick grep finds.

## Verification

After each step:

```bash
(cd app/frontend && npm run typecheck)   # or npx tsc --noEmit
(cd app/frontend && npm test)
./Quickstart dev
```

Manual end-to-end check (no automated harness for this — the toggle is
visual):

1. Load `localhost:5173`, select **Motor** type.
2. Confirm columns show `Nm`, `kg`, `mm` units in headers.
3. Click the unit toggle. **Every** `Nm` should flip to `in·lb`, `kg`
   to `lb`, `mm` to `in`. Voltage, current, RPM headers stay
   unchanged.
4. Open a product detail modal. Same flip in the spec table. Nested
   dimension objects flip together.
5. Filter chip ranges flip. Type a value in the active system; confirm
   the filter still selects the right rows after toggling back.
6. Reload the page — toggle persists.
7. Hard cases to eyeball:
   - A product with `weight: {value: 1.5, unit: 'kg'}` should read
     `3.31 lb` after toggle.
   - A product with `operating_temp: {min: -20, max: 60, unit: '°C'}`
     should read `-4 to 140 °F`.
   - A product whose `efficiency` is `92 %` should not change.
   - A product whose `voltage` is `100-240 V` should not change.

## Edge cases worth flagging in the PR

- **Compound units left untouched**: `V/krpm`, `Nm/A`, `Nm/arcmin`,
  `Nm/√A`. Document this in the toggle's tooltip ("Imperial display —
  compound coefficients shown as-is") so users don't think it's a bug.
- **Strings that aren't parseable** (`"~5;Nm"`, `"approx 100;A"`):
  unit gets relabeled but value passes through. Better than dropping
  the row, worse than not showing it; flag explicitly so reviewers
  know.
- **CSV / JSON export** (if present): exports use canonical metric
  regardless of toggle. The toggle is a viewing pref, not a data
  contract. If users want imperial exports, that's a separate feature.
- **Sort stability**: sorting by `peak_torque` should produce the same
  row ordering whether the toggle is metric or imperial (because
  comparators run on canonical numeric values). Add a quick test in
  `ProductList.test.tsx` (or wherever sort tests live) asserting
  this.

## Files touched

| File                                                    | Change |
|---------------------------------------------------------|--------|
| `app/frontend/src/utils/unitConversion.ts`              | new    |
| `app/frontend/src/utils/unitConversion.test.ts`         | new    |
| `app/frontend/src/components/UnitToggle.tsx`            | new    |
| `app/frontend/src/context/AppContext.tsx`               | +unitSystem state, +setUnitSystem |
| `app/frontend/src/utils/formatting.ts`                  | thread `system` param |
| `app/frontend/src/utils/formatting.test.ts`             | add imperial cases |
| `app/frontend/src/components/ProductDetailModal.tsx`    | thread `useApp().unitSystem` |
| `app/frontend/src/components/ProductList.tsx`           | thread system to header units + formatValue |
| `app/frontend/src/components/FilterBar.tsx`             | imperial input parsing + chip display |
| `app/frontend/src/components/FilterChip.tsx`            | unit display via `displayUnit()` |
| `app/frontend/src/components/DistributionChart.tsx`     | imperial axis labels |
| `app/frontend/src/utils/filterValues.ts`                | `toCanonical` adapter on input |
| `app/frontend/src/utils/filterValues.test.ts`           | add imperial input cases |
| (header component, wherever `<ThemeToggle />` lives)    | mount `<UnitToggle />` adjacent |

No backend, no Python, no DynamoDB changes.

## Estimated effort

- Step 1 (conversion utility + tests): 1–2 h. Pure functions, the
  longest part is getting the conversion factors right and writing
  round-trip tests.
- Step 2 (context wiring): 15 min.
- Step 3 (toggle component): 15 min — copy of `ThemeToggle`.
- Step 4 (display integration, 3 sites): 1 h. Mostly mechanical
  threading.
- Step 5 (filter input adapter): 30 min.
- Step 6 (chart axes): 30 min — depends on how many axes there are.

Total: half a day, mostly mechanical wiring once the utility is
correct. The risk is in step 4 — missing a render path means a unit
that doesn't flip and looks like a bug.

## Triggers

Surface this doc when the current task touches any of:

- `app/frontend/src/context/AppContext.tsx` (the natural mount point for the toggle state)
- `app/frontend/src/components/ThemeToggle.tsx` (template for the new `UnitToggle`)
- `app/frontend/src/utils/formatting.ts` (display-time number rendering)
- `app/frontend/src/components/FilterChip.tsx` / `DistributionChart.tsx` (chart axes + filter input)
- `datasheetminer/units.py` — flag that *display-time* conversion belongs in the frontend, not here
- User mentions "imperial", "metric", "lbf", "in·lb", "psi", "°F", "unit toggle"
