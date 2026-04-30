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

### Phase 2: AppContext as a black box — 1 file

**`src/context/AppContext.test.tsx`** (new) — render `<AppProvider>` with a
test consumer that exercises each setter through `useApp()`. Don't test
data-fetching here (that's `api/client.test.ts`); test state transitions.

Cases:

- `setUnitSystem('imperial')` → `useApp().unitSystem === 'imperial'` and
  `localStorage.unitSystem === 'imperial'` (L7).
- `setRowDensity('comfy')` → context updates and `localStorage.productListRowDensity` updates (L8).
- `addToBuild(motor)` populates the `motor` slot; calling again with a different
  motor *replaces* the slot (no array growth, no stale entry) (L9).
- `addToBuild(p)` where `p.product_type` is not in `BUILD_SLOTS` is a no-op
  (the slot rejection path).
- `removeFromBuild('motor')` deletes the key entirely (not just sets to undefined).
- `clearBuild()` empties everything; subsequent reload re-reads `{}`.
- `setCompatibleOnly(false)` persists; round-trip across a re-mount.
- Stale `specodex.build` shape (e.g. `{ motor: 'string-not-product' }`) falls
  back to `{}` on init without throwing (L6).

### Phase 3: ProductList type-switch reset — 1 file

**`src/components/ProductList.typeSwitch.test.tsx`** (new) — the *single most
important* file in this plan. This is where L1–L4 live.

Mock `useApp()` to control `currentProductType` and `products`. Render
`<ProductList />`. For each transition (`null → motor`, `motor → drive`),
assert:

- `selectedProduct` clears (L1) — open a modal in the first type, switch type, modal gone.
- `filters` clears (L2) — add a chip in the first type, switch, no chip rendered.
- `sorts` clears (L3) — set a sort, switch, default sort restored.
- `currentPage` resets to 1 (L4) — paginate to page 3, switch, page 1 active.
- Adding/removing a filter while on the same type *also* resets `currentPage` (L4).

Then assert what *does not* reset across type switch (intentional persistence):

- `userHiddenKeys`, `userRestoredKeys` — confirm L5 is by design. If the
  product confirms it should be per-type, partition the localStorage key
  before writing the test.
- `unitSystem`, `rowDensity` — header toggles persist across type switches.

### Phase 4: header toggles — 3 small files (or one combined)

Existing: `ThemeToggle.test.tsx`, `NetworkStatus.test.tsx`.

Add:

- **`UnitToggle.test.tsx`** — clicking flips `useApp().unitSystem`; the rendered
  label matches the *next* unit system (covers the "looks like it worked but
  didn't" case); compact mode renders smaller markup; persists to `localStorage.unitSystem`.
- **`DensityToggle.test.tsx`** — clicking flips `rowDensity`; persists; the
  toggle's `aria-pressed` reflects current state.
- **`GitHubLink.test.tsx`** (3 lines) — renders with correct href, target,
  rel, aria-label. Trivial but locks the URL in case it gets rewritten.

### Phase 5: FilterChip × unit system — 1 file extension

`FilterChip.test.tsx` exists. Extend with the unit-aware cases:

- A `MinMaxUnit` filter on a metric field renders the slider in metric when
  `unitSystem='metric'`, imperial when `'imperial'` (L7).
- Editing the value in imperial and committing writes the *converted metric*
  value back via `onUpdate` (the store stays canonical metric).
- A `MinMaxUnit` filter against a record where the unit is missing falls
  through gracefully (no NaN in the slider).

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
3. Phase 2 (`AppContext.test.tsx`). Locks in the build/unit/density semantics
   the rest of the app depends on. ~2h. **Next.**
4. Phase 3 (`ProductList.typeSwitch.test.tsx`). Highest user-visible payoff —
   the spillover bugs L1–L4 are the ones a user notices. ~2h.
5. Phase 4 (header toggles). Quick wins, ~1h total.
6. Phase 5 (FilterChip unit system). Locks in L7. ~1h.
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
