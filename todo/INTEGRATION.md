# Motion-system builder (drive → motor → gearhead)

## Scope

**Current slice:** the rotary chain only — `drive → motor → gearhead`. Linear
actuators are explicitly out of scope until the rotary path is shipped and used.

**Compat policy:** *fits-partial* — the engine never returns `fail` over the
API. `fail` from the strict engine is downgraded to `partial` with the same
per-field detail. Reason: cross-product schemas aren't normalised yet
(fieldbus protocol strings vary by vendor, encoder names too), so a strict
gate would produce false negatives the user has no way to override. Once
shared enums exist, flip a flag to re-enable strict mode.

## Goal

Let a user assemble a rotary motion system from products in the catalog and
get *informational, per-junction* compatibility feedback as they go:

    drive  →  motor  →  gearhead
              ────────  ─────────
               power     shaft

Today the user can search/filter each type in isolation but has no way to ask
"is this drive ok with that motor?" or "show me only the gearheads that fit this
motor's frame and shaft." The substrate to answer those questions already
exists in Python — it just isn't exposed.

## What exists today (the "integration points built earlier")

| Layer | Where | What it does |
|---|---|---|
| Port schemas | `specodex/integration/ports.py` | `ElectricalPowerPort`, `MechanicalShaftPort`, `FeedbackPort`, `FieldbusPort`, `CoilPort`. Pure data with `direction: input\|output` and unit-aware `ValueUnit`/`MinMaxUnit` fields. |
| Per-product adapters | `specodex/integration/adapters.py` | `ports_for(product)` returns `{port_name: Port}` for Motor, Drive, Gearhead, Contactor, ElectricCylinder, RobotArm. **Gap:** no adapter for `LinearActuator`. |
| Compat engine | `specodex/integration/compat.py:check(a, b)` | Pairs every output port on A with every input port on B of the same `kind`, runs unit-aware comparators, returns `CompatibilityReport(status: ok\|partial\|fail, results: [CompatResult])` with per-field `CheckResult` detail. |
| Tests | `tests/unit/test_integration.py` | Happy paths + failure modes for all comparators. |

The comparators already cover what matters:

- **Electrical power** — voltage range containment, supply ≥ demand for current
  and power, AC/DC match.
- **Mechanical shaft** — `frame_size` exact equality, shaft OD within 0.1 mm,
  speed demand ≤ supply.
- **Feedback** — motor's encoder type ∈ drive's supported list.
- **Fieldbus** — non-empty intersection of declared protocols.

What's *missing* to deliver the user-facing feature:

1. **No HTTP surface.** `app/backend/src/routes/` has no compat route; the engine
   is Python-only.
2. **No `LinearActuator` adapter.** Without it, the rotary chain stops at the
   gearhead. The integrated `ElectricCylinder` works because it has a
   `power_input` port (drive can feed it directly).
3. **No UI primitives for multi-product selection.** `AppContext` carries
   `products`, `summary`, `categories`, unit system — no "selected build" /
   "shortlist" / "chain" state. `ProductDetailModal` and `ProductList` are
   single-product surfaces.
4. **No fieldbus protocol on Motor.** `Motor.encoder_feedback_support` exists
   but motors don't expose `fieldbus` — fine, fieldbus is a drive↔PLC concern,
   not motor↔drive.

## Approaches

Four shapes, ordered from cheapest to richest. They compose: A unblocks B, B
unblocks C.

### A. Pairwise checker on the detail page (smallest viable)

On `ProductDetailModal` for any product, show a "Check compatibility with…"
selector. User picks a second product (typed search filtered to the kinds that
have a port pair). Backend returns the existing `CompatibilityReport`, UI
renders junctions with traffic-light status and per-field detail.

- **New backend:** `POST /api/v1/compat/check` body `{a_id, b_id}` → JSON
  serialization of `CompatibilityReport`. Lambda handler hydrates both products
  from DynamoDB by `id`, calls `check(a, b)`, returns the report.
- **New frontend:** modal section + a small `CompatBadge` component (red /
  amber / green + tooltip).
- **Cost:** ~1 route + ~2 components + adapter gap fix for `LinearActuator`.
- **Risk:** none — purely additive. Doesn't change search, list, or filter.

### B. Persistent build tray ("cart for engineers")

Layer on top of A:

- `AppContext` gains `build: Record<ProductType, Product | null>` covering
  the four slots (`drive`, `motor`, `gearhead`, `actuator`). Persist in
  `localStorage` like the unit system and column prefs.
- "Add to build" button on every product card and modal — slots in by
  `product_type`, replaces previous selection in that slot.
- Sticky tray (bottom of viewport, collapsible) showing the chain with junction
  badges between adjacent products and a "Clear" / "Export BOM" footer.
- Junction status comes from `POST /api/v1/compat/check-chain` (new) which takes
  an ordered array of product IDs and returns one `CompatibilityReport` per
  adjacent pair.
- **Cost:** 1 more route + tray component + context surgery.
- **Risk:** UX scope creep (where does the tray live on mobile?).

### C. Slot-aware filtering ("show me motors that fit this drive")

Once B exists, the next step is to *narrow* the catalog as the build progresses.
When the user has a drive selected and clicks the empty motor slot, the list
view filters to motors where `compat.check(drive, motor).status != 'fail'`.

- **New backend:** `GET /api/v1/compat/candidates?against=<id>&type=<next_type>`
  returns the catalog page filtered + ranked by compat status. Naive impl:
  scan the type partition and call `check()` per row. Will not scale past a few
  thousand rows per type — fine for now (drives/motors are <500 each).
- A `partial` result (one side missing the spec) is *included*, not excluded —
  the user can still pick it but the badge stays amber.
- **Cost:** 1 route + a filter mode toggle in `FilterBar`.
- **Risk:** the scan-per-request shape gets expensive as the catalog grows.
  When it does, precompute compatibility groups (`frame_size`, `voltage_class`,
  `encoder_family`) at write time and index by group.

### D. Spec-first wizard (future, not in scope)

User states the application requirement (load mass, stroke, duty cycle,
target speed) → system proposes candidate chains end-to-end, ranked. Requires:
a sizing engine (torque margin, RMS torque, gear-ratio sweep), application
templates (vertical lift vs. horizontal slide vs. rotary index), and probably
ML re-ranking on top. **Worth naming so we don't accidentally architect
ourselves out of it**, but not a near-term build.

## Recommended path

Ship A → B → C in that order, gated on real usage signal between each:

1. **A** ✅ shipped — pairwise check inside `ProductDetailModal`, fits-partial,
   verified live.
2. **B** ✅ shipped — persistent build tray + slot-aware filter (the "C" piece
   collapsed in here because the natural place for it was the same flow). Drive
   → motor narrows the visible motor list; motor → gearhead narrows the
   gearhead list; tray persists across reloads via localStorage.
3. **D** (spec-first wizard) is the only thing left in the original plan — see
   the section below.

## Concrete first slice (A — what we're building now)

### Bridge decision: TS port (not Python lambda)

The backend is pure Express on Lambda; there's no Python runtime in the API
deployment artefact. Options surveyed:

- **Re-implement compat in TS** — chosen. ~80 lines for fits-partial mode
  covering two junctions (drive↔motor power+feedback, motor↔gearhead shaft).
  Keeps the API single-language and avoids a second lambda + IAM dance.
- Python sidecar lambda — adds infra and a network hop for what is, in
  partial-only mode, a handful of string comparisons.
- Subprocess — Node Lambda image has no Python, so non-starter.

The Python engine in `specodex/integration/` stays — it's the source
of truth for stricter checks once shared enums land, and the CLI/bench paths
keep using it. The TS port mirrors the same junction definitions and is
contract-tested against a JSON fixture both implementations consume.

### Python compat: add fits-partial flag

Add `strict: bool = True` to `check()`; when `False`, downgrade every `fail`
to `partial` while keeping the per-field detail intact. Keeps the existing
test suite green and lets callers pick the policy per call site.

### Serialization

`CompatibilityReport` is a dataclass tree. Add a `to_dict()` (via
`dataclasses.asdict`) so callers can JSON-encode without surgery. Pydantic
port deferred — not needed for this slice and the cost is non-trivial.

### Route

`app/backend/src/routes/compat.ts` — single `POST /api/v1/compat/check`,
zod-validated body `{ a: { id, type }, b: { id, type } }`. Hydrates both via
the existing `dynamodb.ts:getProduct(id, type)` shape (PK `PRODUCT#<TYPE>`,
SK `PRODUCT#<id>`), runs the TS compat port in fits-partial mode, returns
the report.

### UI

`app/frontend/src/components/CompatBadge.tsx` — props
`{ status: 'ok' | 'partial', detail?: string }` (no `fail` in the type
union — fits-partial). Tooltip lists per-field detail.

`ProductDetailModal` gains a "Check against another product…" expandable
section that:

1. Determines eligible adjacent types from the current product:
   `drive` → can pair with `motor`; `motor` → `drive` or `gearhead`;
   `gearhead` → `motor`. Other types: section is hidden.
2. Renders a typeahead picker scoped to the eligible type(s), populated
   from the existing `/api/products?type=<...>` endpoint.
3. On selection, POSTs to `/api/v1/compat/check` and renders junctions with
   side-by-side field values + badges.

### Junction definitions (the two we ship)

| From | To | Junction kind | Fields compared |
|---|---|---|---|
| `drive.motor_output` | `motor.power_input` | electrical power | voltage, current, power, ac_dc |
| `drive.feedback` | `motor.feedback` | feedback | encoder type membership |
| `motor.shaft_output` | `gearhead.shaft_input` | mechanical shaft | frame_size, shaft_diameter, max_speed |

Fieldbus is intentionally **not** in this slice — drive and motor sides use
different vendor strings ("EtherCAT" vs "EtherCAT P", "PROFINET IRT" vs
"PROFINET RT") and the partial-mode UI would always show "no overlap" without
adding signal. Re-introduce when the shared protocol enum exists.

## What shipped (B)

- **Strict-mode TS port** in `app/backend/src/services/compat.ts` plus the
  client-side mirror at `app/frontend/src/utils/compat.ts`. Comparators
  return `ok | partial | fail`; the API layer softens fail→partial via
  `softenReport()` so the user never sees a hard red gate.
- **AppContext build state** — `build: Partial<Record<BuildSlot, Product>>`,
  `addToBuild`, `removeFromBuild`, `clearBuild`, plus a `compatibleOnly`
  toggle. Persisted under `specodex.build` and `specodex.compatibleOnly`.
- **`BuildTray` component** — sticky bottom strip showing each filled slot,
  remove buttons, junction badges between adjacent filled slots, and a
  Clear link. Hidden when the build is empty.
- **Add-to-build button** in `ProductDetailModal` — toggles between Add /
  Replace / Remove based on the current build state.
- **`ProductList` compat filter** — when the active type is adjacent to a
  build anchor, narrows the visible list to candidates that don't strict-fail
  any anchor. A banner near the top of the list shows the count delta and
  offers a "Show all" override.

## Next slice — "build complete" affordances

Phases A and B shipped. End-of-chain affordances:

1. **Whole-chain audit view.** ✅ shipped 2026-04-30.
   `ChainReviewModal` opens from the BuildTray's "Review chain" button
   (visible whenever ≥1 adjacent pair is filled — drive+motor and/or
   motor+gearhead). On open, fires one `apiClient.checkCompat` call
   per adjacent filled pair in parallel and stacks the resulting
   reports in BUILD_SLOTS order. Reuses `CompatBadge` + the spec-table
   render shape from `CompatChecker` so the layout is familiar. Escape
   and outside-click close. Helper `adjacentFilledPairs(build)` is
   exported and unit-tested separately.

2. **BOM export.** ✅ shipped 2026-04-30. Tray's "Copy BOM" button
   (next to Clear) writes a plain-text block to the clipboard via
   `navigator.clipboard.writeText`:

       Drive:    Bardac — P2-74250-3HF4N-T
       Motor:    ABB — E2BA315SMB6
       Gearhead: SEW

       Drive → Motor: ✓ compatible
       Motor → Gearhead: ! frame_size: motor 80 ≠ gearhead 90

   Slot lines are padded to a fixed column; missing `part_number` drops
   the suffix cleanly; junctions block is included only when ≥1 adjacent
   pair exists. Button label flips to "Copied!" / "Copy failed" for
   ~1.6s on each click. Pure-function helper `buildBomText(build,
   junctions)` is exported and unit-tested separately. No server work.

3. **"Looks complete" badge on the tray.** ✅ shipped 2026-04-30.
   When all three slots are filled AND every junction rolls up to `ok`,
   the tray adds the `is-complete` class (green border-top accent) and
   renders a `✓` marker with `aria-label="Build complete"` next to
   the "Build:" label. Pure visual; no behavioural change.

4. **(Stretch) "Save build as preset"** — name it, store an array in
   localStorage, restore from a dropdown next to Clear. Useful once a user
   has more than one project. Skip until someone asks.

### Why this scope

These are pure UI additions on top of the existing engine. They do **not**
require: new backend routes, schema changes, additional compat junctions,
or LinearActuator support. (Linear actuator is still tracked in
[ACTUATOR.md](ACTUATOR.md) and feeds into a future Phase D — spec-first
sizing wizard — which is the only remaining item from the original plan.)

### Where the code lives

All shipped 2026-04-30:

- `app/frontend/src/components/ChainReviewModal.tsx` (new) — whole-chain
  audit modal, 11 tests in `ChainReviewModal.test.tsx`.
- `app/frontend/src/components/BuildTray.tsx` — Review chain button
  (gated on `adjacentFilledPairs(build).length > 0`), Copy BOM, ✓
  marker, `is-complete` class.
- `app/frontend/src/App.css` — tray Review/Copy/Clear button styling,
  complete-state border, ChainReviewModal overlay + dialog.

No backend touch.

### What's left in this slice

- (Stretch) **Save build as preset** — name + persist to localStorage,
  restore via dropdown. Park until a user asks; one-project users won't
  miss it.

## Open questions

- **Who owns the fieldbus check between motor and drive?** Currently `Motor`
  has no `fieldbus` field — the implicit assumption is that the *drive*
  carries the network spec and the motor is dumb. That's true for analog
  servo motors but increasingly false for digital/integrated servo (where the
  motor speaks EtherCAT directly). Defer until a vendor catalog forces the
  question.
- **Bidirectional voltage check on drive↔motor.** Today `_drive_ports`
  declares `motor_output.voltage = d.input_voltage` (the drive reproduces its
  input on the output side via PWM). For some drives this is wrong (e.g. a
  24 VDC input → 48 VDC bus boost). Acceptable approximation; revisit if a
  user reports a false-pass.
- **`partial` vs. `fail` policy in slot-aware filtering (C).** Strict mode
  (only `ok`) hides too much when datasheets are incomplete; permissive mode
  (`ok` + `partial`) is the right default but should be a user toggle.
- **Where does Contactor sit in the chain?** It has a `load_output` that fits
  a motor's `power_input`, so it could optionally precede the drive (line
  contactor) or replace the drive entirely (across-the-line motor start).
  Doesn't fit the four-slot model cleanly. Park as an optional fifth slot or
  hide from the builder until someone asks.

## Triggers

Surface this doc when current work touches:

- `specodex/integration/{ports,adapters,compat}.py`
- `tests/unit/test_integration.py`
- `app/backend/src/routes/` and you're adding a new route, or anyone says
  "compat", "compatibility", "pairing", "matching", "build", "BOM", "system",
  "chain"
- `app/frontend/src/context/AppContext.tsx` (build state would live here)
- `ProductDetailModal.tsx`, `ProductList.tsx`, `FilterBar.tsx` (the three
  surfaces this feature mutates)
- `LinearActuator` model — the adapter gap is the cheapest pre-req
- Any conversation about "drive → motor → gearhead → actuator", "select a
  motor that fits this drive", or "show only compatible parts"
