# Frontend testing — close the spillover gaps

## Why this exists

The frontend has 14 test files (284 passing, 1 documentation skip) covering
filters, sanitize, formatting, unit conversion, localStorage (helper +
per-key contract), theme, network status, attribute icons, and a couple of
components. What it does *not* cover is the class of bug that has bitten
this app most often: **state spilling across product-type switches,
persisted state surviving a schema change in a broken shape, and toggles
that look like they work but don't propagate**.

Goal: lock down every "simple, obvious, easy to break" feature with a unit or
component test so a refactor in a year can't silently regress it. Scope is
*deliberately narrow* — we are not chasing a coverage percentage, we are
naming each failure mode that would be embarrassing in prod and writing the
test that catches it.

## Pre-req — ✅ resolved 2026-04-30

The two failing AttributeSelector cases this plan was originally gated on
are no longer present. `npx vitest run src/components/AttributeSelector.test.tsx`
shows 8/8 pass. Suite is green; new tests can land without red-noise cover.

## What "simple but crucial" means here

A feature qualifies if **all four** are true:

1. It's used on every session (header toggle, filter, type switch, table render).
2. The state lives in `localStorage` *or* in `AppContext` *or* survives a route change.
3. A regression would be visible to the user within seconds (wrong unit, wrong
   columns, lingering selection, stale filter chip).
4. It's small enough that a focused test suite under 50 lines locks it down.

Anything that fails 1–3 is out of scope. We're not chasing snapshot tests of
the entire `ProductList` or visual-regression of charts here — those belong in
a Playwright/visual layer, see "Out of scope" at the bottom.

## The spillover/state-leak bestiary

These are the failure modes this plan is built around. Every test below maps
back to one of these.

| # | Failure mode | Where it would happen |
|---|---|---|
| L1 | Selected product modal stays open after switching product type | `ProductList` `selectedProduct` not cleared in the type-switch effect |
| L2 | Filter chips from `motor` carry into `drive` view | `filters` state not reset on `productType` change |
| L3 | Sort state survives type switch and produces nonsense column refs | `sorts` not reset on `productType` change |
| L4 | Pagination `currentPage=7` survives a type switch with only 2 pages of results | `currentPage` not reset on `productType` change *or* on filter change |
| L5 | `productListHiddenColumns` from `motor` hides nonexistent columns on `drive` | hidden-columns state is global (not per-type) — confirm this is intentional, else partition the key |
| L6 | `specodex.build` written by an older schema crashes context init on next visit | `safeLoad` validator missing a field, falls through to `{}` instead of crashing |
| L7 | `unitSystem='imperial'` doesn't propagate to a chip's slider min/max | `FilterChip` uses raw metric bounds, ignores `useApp().unitSystem` |
| L8 | `rowDensity='comfy'` written by header toggle but `ProductList` reads from a stale prop | `ProductList` re-reads from context, not from a closure copy |
| L9 | Build tray slot replacement leaves the old product visible for a frame | `addToBuild` doesn't fully replace the entry on type collision |
| L10 | `compatibleOnly=true` on initial load filters to zero rows when build is empty | guard on empty build missing in `ProductList` filter |
| L11 | Theme toggle writes `localStorage.theme='dark'` but DOM `data-theme` stays light on next load | mount effect order in `ThemeToggle` |
| L12 | `safeLoad` accepts `{}` for a value typed as `string[]` because the validator is too loose | every persisted-state validator |

## Test plan — by surface

### Phase 1: persistence keys (cheapest, highest value) — ✅ shipped 2026-04-30

`src/utils/localStorage.persistence.test.ts` covers all six `safeLoad`/
`safeLoadString` keys (`unitSystem`, `productListRowDensity`,
`specodex.compatibleOnly`, `specodex.build`, `productListHiddenColumns`,
`productListRestoredColumns`) with 4 scenarios each: missing,
malformed/off-schema, wrong-shape, round-trip. The `theme` key (raw
`getItem` in `ThemeToggle.tsx`) is intentionally deferred to Phase 4
where the ThemeToggle test already lives — the persistence file marks
that as a `.skip` documentation row so a future "add a new persisted
key" PR knows to add it here too.

Side effect: extracted the inline validators (`isBuild`, `isUnitSystem`,
`isRowDensity`, `isBoolean`, `RowDensity`) from `AppContext.tsx` to
named exports so the test can import them. Caught and fixed an existing
L6 instance — `isBuild` accepted `[]` because `Object.entries([])` is
empty and `.every(...)` is vacuously true. Added an `Array.isArray(v)`
guard.

26 new tests + 1 documentation skip; suite is now 14 files, 284 passing.

### Phase 2: AppContext as a black box — ✅ shipped 2026-04-30

`src/context/AppContext.test.tsx` covers the documented setter contract
via `renderHook(() => useApp(), { wrapper: AppProvider })` with `apiClient`
mocked at module level (any accidental call rejects loudly):

- Defaults hydration: `metric`, `compact`, `compatibleOnly=true`, `build={}`.
- `setUnitSystem('imperial')` → context + `localStorage.unitSystem === 'imperial'`; round-trip across re-mount; off-schema falls back to metric (L7).
- `setRowDensity('comfy')` → context + persistence + re-mount round-trip (L8).
- `setCompatibleOnly(false)` → context + JSON-encoded persistence + re-mount round-trip (L10).
- `addToBuild(motorA)` then `addToBuild(motorB)` replaces the slot (not array growth, asserts `Array.isArray(build) === false`) (L9).
- `addToBuild(driveA)` after a motor places into independent slots.
- `addToBuild(robotArm)` is a no-op when `product_type` ∉ `BUILD_SLOTS`.
- `removeFromBuild('motor')` deletes the key entirely (`'motor' in build === false`).
- `clearBuild()` empties; persisted `{}` survives unmount/remount.
- Stale `specodex.build` hydration: object-with-string-slot, array, unknown-slot-name all fall back to `{}` without throwing (L6).
- A valid prefilled build round-trips on mount.

19 new tests; suite is now 15 files, 303 passing.

### Phase 3: ProductList type-switch reset — ✅ shipped 2026-04-30 (helper-level; full DOM test deferred)

The implementation refactored `handleProductTypeChange` to call a small
exported helper, `defaultStateForType(type)`, that returns the bundle of
state the type-switch resets. The test
(`src/components/ProductList.typeSwitch.test.tsx`) pins that bundle:

- L1 fix shipped — `selectedProduct` and `clickPosition` are now in the
  reset bundle. Pre-fix, switching types left an open detail modal stuck
  on the old type's product. Test asserts both are null.
- L2 — filters get a fresh `buildDefaultFiltersForType(newType)` array,
  every chip in `mode: 'include'` with `value === undefined`.
- L3 — sorts cleared for every type, including `null`.
- Linear-mode reset — `appType: 'rotary'`, `linearTravel: 0`,
  `loadMass: 0` so a "linear motor / 50 mm travel" config doesn't leak
  into a drive screen.
- Fresh-object guarantee — two consecutive calls return non-`Object.is`
  filters/sorts arrays, so React's reference-equality treats every
  switch as a real state change.

Skipped intentionally:
- L4 (`currentPage` reset to 1) is wired transitively through a
  `useEffect` on `[filters, sorts, itemsPerPage]`. Phase 1 already pins
  the filter/sort identity contract; the indirect path is correct as
  long as filters returns a fresh array, which test #5 above asserts.
- `userHiddenKeys`, `userRestoredKeys`, `unitSystem`, `rowDensity` —
  intentional cross-type persistence; not in the reset bundle.

The full DOM-level test (open modal, switch type via FilterBar dropdown,
assert `.product-detail-overlay` gone) is deferred. It adds little
safety beyond the bundle test as long as `handleProductTypeChange`
keeps calling `defaultStateForType` for every slice it resets, and
costs heavy mock setup (Dropdown is a portal-using custom widget,
ProductList is a 1300-line component with many context dependencies).
Pick this up if/when the wiring drifts.

6 new tests; suite is now 19 files, 324 passing.

### Phase 4: header toggles — ✅ shipped 2026-04-30

Three new component tests covering the three header chips:

- **`UnitToggle.test.tsx`** (7 tests) — both default and compact variants.
  Defaults SI; clicking flips to imperial + persists to
  `localStorage.unitSystem`; aria-label tracks the *next* state ("Switch
  to metric units" when on imperial — catches the "looks like it worked
  but didn't" case from L7); hydrates from imperial in storage. Compact
  variant: SI + IMP pills with `.active` class on the current one;
  active class moves on click; UNITS caption is `aria-hidden`.
- **`DensityToggle.test.tsx`** (5 tests) — defaults compact;
  `aria-pressed` reflects "currently compact"; click flips to comfy +
  persists `productListRowDensity`; hydrates from comfy; SVG icon flips
  from 3 lines to 2 bars on click (visual feedback wired correctly, L8).
- **`GitHubLink.test.tsx`** (3 tests) — href pinned to canonical
  `JimothyJohn/specodex`; opens in new tab with `rel` containing
  `noopener` + `noreferrer`; aria-label + title both "Source on GitHub".

15 new tests; suite is now 18 files, 318 passing.

### Phase 5: FilterChip × unit system — ✅ shipped 2026-04-30

Extended `FilterChip.test.tsx` with a "slider × unit system" describe
block covering L7 at the chip layer:

- Slider min/max labels render in metric (`5`, `100`) with unit `Nm`
  when `unitSystem='metric'`, and in imperial (`44.25`, `885.1`) with
  unit `in·lb` when `unitSystem='imperial'`. The `Nm` ↔ `in·lb`
  conversion factor (8.850746) and the 4-sig-fig roundDisplay are
  exercised end-to-end.
- Round trip: in imperial, click the readout, type `100` (in·lb), press
  Enter — `onUpdate` receives `value` as the *canonical metric* number
  (`100 / 8.850746 ≈ 11.30`), operator preserved. Confirms the
  display-vs-storage split: filter state stays metric, only the labels
  flip.
- Unit-missing fallback: products carrying `{ value: 5 }` (no `unit`
  key) still render valid range labels and no `NaN` text leaks into the
  DOM. Display unit comes from `attributeMetadata.unit` as the backstop.

4 new tests; the file is now 12 tests. Suite is 19 files, 328 passing.

### Phase 6: BuildTray + compat — 1 file

**`src/components/BuildTray.test.tsx`** (new) —

- Hidden when build is empty.
- Renders one slot for each filled `BUILD_SLOTS` entry, in slot order.
- `removeFromBuild` button on each slot calls the right setter.
- Junction badge between two adjacent filled slots reflects the report shape
  (mock `apiClient.checkCompat`); single-slot build shows no junctions.
- "Clear" empties the tray.

This + Phase 2's build cases together pin down the build flow without needing
a real backend.

### Phase 7: ErrorBoundary — 1 small file

**`src/components/ErrorBoundary.test.tsx`** (new) — render a child that throws
on mount, assert fallback UI shows. Render a healthy child, assert no fallback.
3 cases, ~30 lines. Right now a render-time crash anywhere in the app shows a
white page — this test makes sure the boundary at least exists and catches.

### Phase 8: smoke-render every page — 1 file

**`src/test/smokeRender.test.tsx`** (new) — render `<App />` wrapped in
`MemoryRouter` for each route (`/`, `/welcome`, `/datasheets`, `/management`,
`/admin`) with `apiClient` fully mocked. Assert: no thrown errors, no
`ErrorBoundary` fallback, the route's heading is in the DOM. This is one file
that catches "I broke the imports" before CI does.

## Order to implement

1. ✅ Pre-req cleared (no failing tests).
2. ✅ Phase 1 shipped 2026-04-30.
3. ✅ Phase 2 shipped 2026-04-30.
4. ✅ Phase 3 shipped 2026-04-30 (helper-level + L1 bug fix; full DOM test deferred).
5. ✅ Phase 4 shipped 2026-04-30.
6. ✅ Phase 5 shipped 2026-04-30.
7. Phase 6 (BuildTray). ~1h.
8. Phase 7 (ErrorBoundary), Phase 8 (smoke-render). ~1h together.

Each phase is independently shippable; don't try to land all in one PR.

## Conventions for the new tests

- Use the existing `src/test/utils.tsx` `render` wrapper (it already pulls in
  `AppProvider` + router). Don't reinvent.
- Mock `apiClient` at the module level — never hit `fetch` from a unit test.
- For localStorage tests, clear it in a `beforeEach`. The `vitest` `setup.ts`
  doesn't do this globally because some tests rely on persistence within a file.
- Use `screen.getBy*` over `container.querySelector` — accessible queries
  surface a11y regressions for free.
- One file per surface, named `<Surface>.test.{ts,tsx}` colocated with the
  source. The smoke-render test is the only exception (lives in `src/test/`).

## Out of scope

- **Visual-regression / Playwright.** This plan is unit + component only. Full
  end-to-end coverage of the rendered table, distribution chart, modal stacking,
  etc. is a separate effort — see `webapp-testing` skill for the harness.
- **Backend route tests.** Owned by the backend test suite (`app/backend/`).
- **Coverage threshold enforcement.** Ratcheting `vitest --coverage` up in CI
  is its own PR and risks blocking unrelated work; do it once the above lands.

## Triggers

Surface this doc when current work touches:

- `app/frontend/src/utils/localStorage.ts` or any `safeLoad`/`safeSave` call
- `app/frontend/src/context/AppContext.tsx` (especially adding a new
  persisted key — this plan's Phase 1 table needs a new row)
- `app/frontend/src/components/ProductList.tsx` (the type-switch effect at
  the top of the file is the heart of Phase 3)
- `app/frontend/src/components/FilterChip.tsx` and the `unitSystem` flow
- `app/frontend/src/components/BuildTray.tsx`, `ProductDetailModal.tsx`
- Any `*.test.{ts,tsx}` change under `app/frontend/src/`
- User mentions: "spillover", "state leak", "stale filter", "modal won't close",
  "wrong unit", "missing column", "stuck on page N", "build won't clear",
  "frontend tests", "vitest"
