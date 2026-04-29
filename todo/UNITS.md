# Drop the `"value;unit"` compact string — go full JSON

**Status (2026-04-28):** ✅ done end-to-end. Phases 1–4 shipped in
`a8f6162` (structured `ValueUnit`/`MinMaxUnit` BaseModels, compact
string layer deleted). Phases 5–6 shipped in `aac7050` (backfill
script + docs). Data backfill ran the same day across all three
DynamoDB tables:

| Stage | Scanned | Fixed (rows) | Unparseable (review) |
|---|---|---|---|
| dev | 2877 | 273 (132 + 141 rescue-mode) | ~363 (legacy data quality) |
| staging | 0 | — | empty table |
| prod | 2593 | 10 | 10 (legacy data quality) |

The original `rotor_inertia: "5.5e-5;kg·cm²"` UI bug from "Why now"
below is fixed in prod.

**Phase 5 follow-ups** (parser rescue + scan validation, landed
post-initial-run):

- `~` between numbers as range separator (`-40~+100;°C`) → `MinMaxUnit`
- thousands-separator comma in numbers (`30,000;hr`) → `ValueUnit`
- `≤`/`<=`/`≥`/`>=` prefix → half-open `MinMaxUnit`
- `_expected_product_count` sanity check via `Select=COUNT` before the
  data scan, warns on mismatch (the first prod dry-run terminated
  after 846 of 2593 rows; the count-vs-scan diff makes any recurrence
  loud).

**Deliberately deferred** (left in review for human triage):

- `±X;unit` — semantically ambiguous between scalar tolerance
  (`pose_repeatability: ±0.02 mm` is one number) and bilateral range
  (`working_range: ±360°` is -360..+360). The migration script can't
  tell field types at the dict-walk layer; auto-fixing either way is
  wrong half the time.
- `;null` / `;unknown` literal sentinels (`±360°;null`,
  `IP67;mH`-style mixed-up fields). These are bad LLM emissions, not
  encoding artefacts; rescuing them would silently corrupt the
  catalogue.

**Phase 4 deviation kept on purpose:** the frontend `String(value)`
fallback in `ProductDetailModal.tsx:84` is NOT just a unit fallback
— it's the catch-all for bare-string scalars (`product_name` etc.).
The doc's "migrated data never has strings" was unit-specific
reasoning mistakenly generalised; deleting that line would break
legitimate fields. After the prod backfill, no compact-unit string
flows through it anyway, so the safety net is harmless.

## Goal

Stop encoding numeric specs as `"value;unit"` / `"min-max;unit"` strings
inside the Pydantic models. Carry them as plain dicts end-to-end:
`{"value": <number>, "unit": <string>}` and
`{"min": <number>, "max": <number>, "unit": <string>}`. Same shape
Gemini already emits, same shape DynamoDB already stores, same shape
the frontend already consumes. The compact string is a Python-only
artifact that the rest of the pipeline has to round-trip through —
delete it.

## Why now

Parker BE motors are surfacing `"5.5e-5;kg·cm²"` (literal semicolon)
in the Product Detail UI for `rotor_inertia`. The frontend's
`{value, unit}` rendering check fails when the value is a bare string,
so it falls through to `String(value)` and dumps the raw compact form.

Root cause is the round-trip. We have:

1. Gemini emits `{"value": 5.5e-5, "unit": "kg·cm²"}` ✅
2. `BeforeValidator` collapses to `"5.5e-5;kg·cm²"` 🟡
3. `AfterValidator` normalizes units, returns the joined string 🟡
4. `model.model_dump()` returns the joined string 🟡
5. `_parse_compact_units()` regex re-splits to `{value, unit}` for
   DynamoDB write — **iff** the regex matches.
6. Regex is `^(-?[\d.]+)(?:-(-?[\d.]+))?;(.*)$`. `5.5e-5` doesn't
   match `[\d.]+` (the `e` and second `-` fail), so step 5 silently
   leaves the string as-is.
7. DynamoDB stores the string. TS `parseCompactUnits` has the same
   regex limitation. UI renders `String("5.5e-5;kg·cm²")`. 🔴

The semicolon is the canary. Every regex layer between LLM output and
DynamoDB write is a place where exotic-but-valid LLM output (scientific
notation, fractional ranges with negatives, units with embedded
punctuation, inline annotations like `2+`) silently regresses to a raw
string. We've already lost a column-and-a-half to this in
`common.py:50–58` (`# We used to enforce float(parts[0]), but "2+" or
"approx 5" might occur. Let's just ensure it's not empty.`). Cleaning
up the regex tomorrow won't help — the next exotic value will hit the
same wall.

The compact string was a token-saving gesture from when we cared about
LLM input length. Gemini already emits the structured form; we're
paying nothing for the structured form on input, and paying real bugs
to compress it on output. Kill it.

## Non-goals

- **No new unit-conversion logic.** `specodex/units.py:normalize_value_unit`
  still does the canonical-unit work; it just operates on dicts now,
  not strings.
- **No frontend change beyond removing the legacy string fallback.**
  The frontend already consumes `{value, unit}` dicts. It has a
  defensive `String(value)` branch for the rare string case — that
  branch becomes dead code and gets deleted.
- **No DynamoDB schema migration.** DynamoDB already stores the
  structured form. We're aligning the Python in-memory representation
  with what's already on disk; nothing migrates.
- **No new product types.** Existing six (`drive`, `motor`, `gearhead`,
  `robot_arm`, `electric_cylinder`, `contactor`) get the refactor,
  schemagen emits the new shape for future types.

## Approach

Pydantic gets two real types — `ValueUnit` and `MinMaxUnit` — backed by
`pydantic.BaseModel`, not `Annotated[Optional[str], …]`. The BeforeValidators
that coerce LLM-quirk inputs (space-separated, qualifier-prefixed, `to`
ranges) move to `model_validator(mode="before")` on those classes. The
AfterValidator that does unit normalization moves to
`model_validator(mode="after")` and rewrites `self.unit` in place.

Six phases, each independently shippable. Each phase is a single PR
that leaves the tree green.

### Phase 1 — Introduce structured `ValueUnit` / `MinMaxUnit` classes

Add the new types alongside the old aliases. Don't touch any model
field yet.

```python
# specodex/models/common.py
class ValueUnit(BaseModel):
    value: float
    unit: str

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, data: Any) -> Any:
        # Accepts: dict {value, unit}, "N unit", "N;unit", {"min", "max", ...}
        # Returns: dict {value, unit} or None
        ...

    @model_validator(mode="after")
    def _normalize_unit(self) -> "ValueUnit":
        # Apply specodex.units.normalize_value_unit on the dict form
        ...

class MinMaxUnit(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    unit: str
    # similar before/after validators
```

Keep `ValueUnitMarker` / `MinMaxUnitMarker` semantics so
`llm_schema.py:to_gemini_schema` still detects them — but detection
now keys on the class itself (`issubclass(annotation, ValueUnit)`) not
on metadata markers.

`specodex/units.py:normalize_value_unit` gets a sibling
`normalize_value_unit_dict({"value", "unit"}) -> {"value", "unit"}` that
operates on the structured form. The existing string version stays
during the transition.

**Files touched:**

- `specodex/models/common.py` — new classes, leave old `Annotated` aliases in place
- `specodex/units.py` — add dict-form normalizer
- `tests/unit/test_models_common.py` — new tests for the new classes

**Done when:** new classes pass unit tests in isolation, no existing
tests change.

### Phase 2 — Migrate one model end-to-end as the proof

Pick `motor.py` first (highest-traffic, has the field that broke).
Switch every `Speed`/`Torque`/`Voltage`/`Inertia` etc. annotation to
the new structured class. The `_typed_value_unit(family)` factory
becomes `class Voltage(ValueUnit): _family = VOLTAGE` (subclassing
the new BaseModel and overriding the family check).

Adjust:

- `specodex/llm.py` — Gemini schema generation already emits objects;
  no change to the wire format. Verify `to_gemini_schema` still
  produces the same output for migrated fields.
- `specodex/utils.py:parse_gemini_response` — Pydantic now accepts the
  dict directly without the BeforeValidator hop. Drop any "convert dict
  to compact string" comments.
- `specodex/db/dynamo.py:_serialize_item` — `_parse_compact_units` is
  now a no-op for migrated fields (they're already dicts in
  `model_dump()`). Leave the helper in place; it still has work to do
  for un-migrated models in this phase.
- `specodex/quality.py` — `is_placeholder` already handles dicts (it
  uses `getattr` and treats `None` as missing). Verify with a test.
- `app/backend/src/db/dynamodb.ts:deserializeProduct` — already
  consumes dicts. No change needed for migrated fields, but exercise
  the path to confirm.

Tests for the migrated model get reshaped: `assert motor.rated_power
== "100;W"` becomes `assert motor.rated_power == ValueUnit(value=100,
unit="W")` (or the dict-equivalent comparison).

**Files touched:**

- `specodex/models/motor.py` — field annotations
- `specodex/models/common.py` — `Voltage`, `Current`, `Power`, etc. as
  subclasses of new `ValueUnit` rather than `Annotated` aliases
- `tests/unit/test_models_motor.py`, `test_value_unit_property.py`,
  `test_units.py` — assertions updated
- `tests/benchmark/expected/*.json` — regenerate with `--update-cache`
  if the cached LLM responses are still valid (they should be — same
  wire format)

**Done when:** `./Quickstart verify` passes; one motor benchmark
fixture round-trips end-to-end with no semicolons in the artifacts.

### Phase 3 — Migrate the remaining five models

Apply the Phase 2 pattern to `drive.py`, `gearhead.py`,
`robot_arm.py`, `electric_cylinder.py`, `contactor.py`. Each as a
separate commit so a regression bisects cleanly.

Special cases to watch:

- `contactor.py:212` — `short_circuit_withstand_icw:
  Optional[List[ContactorIcwRating]]` — nested Pydantic, already
  structured. No change.
- `robot_arm.py:91`, `:105`, `:117`, `:131`, `:135`, `:139`, `:190` —
  hardcoded default strings (`"2;A"`, `"0-50;°C"`, `";VAC"`, etc.).
  Replace with structured defaults (`ValueUnit(value=2, unit="A")`,
  `MinMaxUnit(min=0, max=50, unit="°C")`).  The `";VAC"` default in
  `power_source` is meaningless under the new schema — make it `None`
  and let extraction populate it, same as every other field.

**Done when:** all six models migrated, `./Quickstart verify` green,
`grep -rn '";"' specodex/models/` returns nothing.

### Phase 4 — Delete the compact-string layer

With every model migrated, the compact string is dead weight.

- `specodex/models/common.py` — delete `validate_value_unit_str`,
  `validate_min_max_unit_str`, `handle_value_unit_input`,
  `handle_min_max_unit_input`, `_normalize_compact_str`. Delete the
  old `Annotated[Optional[str], …]` `ValueUnit` / `MinMaxUnit` aliases.
  Delete the marker dataclasses if they're no longer needed (they're
  used by `llm_schema.py` for Gemini schema detection — keep those if
  detection still routes through markers; otherwise switch to
  `issubclass`).
- `specodex/db/dynamo.py:_parse_compact_units` — delete entirely.
  `_serialize_item` no longer needs to call it — `model_dump()` already
  produces dicts.
- `app/backend/src/db/dynamodb.ts:parseCompactUnits` — delete entirely.
  `deserializeProduct` no longer needs to call it.
- `specodex/units.py` — delete `normalize_value_unit(str)`. Keep the
  dict version. Delete `_COMPACT_RE`.
- `app/frontend/src/components/ProductDetailModal.tsx` — delete the
  `String(value)` fallback branch (`formatValue` line ~84). Migrated
  data never has strings; the fallback is a stale safety net that's
  actually masking the bug we're fixing.

Tests:

- `tests/unit/test_compact_units_regex.py` — delete (regex is gone).
- `tests/unit/test_models_common.py` — delete tests for the deleted
  validators.
- `tests/unit/test_db.py` — assertions about compact-string parsing
  become assertions about pass-through-as-dict.

**Done when:** `grep -rn 'compact' specodex/ app/ tests/` returns
nothing meaningful, `grep -rn 'value;unit' specodex/ app/ docs/`
returns nothing, `./Quickstart verify` green.

### Phase 5 — Migrate existing data (rotor_inertia leak fix)

DynamoDB already stores dicts for fields that round-tripped through
the old regex successfully. The leaked-string rows are the cases
where the regex didn't match — scientific notation, weird qualifiers,
ranges with negatives.

`cli/migrate_units_to_dict.py` (new):

1. Scan all rows in DynamoDB.
2. For each `ValueUnit`/`MinMaxUnit`-shaped field, detect strings
   containing `;`.
3. Parse using the **new** structured-input coercer (handles
   scientific notation, qualifiers, etc. — that's the whole point of
   moving the parsing into the Pydantic model).
4. For each parseable row, write the dict form back.
5. For each unparseable row, emit a manual-review entry to
   `outputs/units_migration_review.md` — same pattern as DEDUPE.md
   Phase 3.

Run order: dev first, eyeball the review file, fix any genuinely
broken records by hand, then promote-the-cleaned-set or re-run on
staging/prod. Same `--stage`-gated safety as DEDUPE.

**Files touched:**

- `cli/migrate_units_to_dict.py` — new
- `tests/unit/test_migrate_units.py` — new
- `outputs/units_migration_review_<stage>_<ts>.md` — generated

**Done when:** dev DynamoDB has zero rows where any `ValueUnit`/
`MinMaxUnit` field is a string. Same for staging, then prod.

### Phase 6 — Schemagen + docs

- `specodex/schemagen/renderer.py:37–38` — emit `Optional[ValueUnit]`
  / `Optional[MinMaxUnit]` (already does, but the imports change to
  the new classes).
- `CLAUDE.md:42` — the Pipeline architecture line (`utils.py — maps
  raw LLM JSON through common.py BeforeValidators into canonical
  "value;unit" strings`) now reads `… into structured ValueUnit /
  MinMaxUnit dicts`. Update.
- `tests/benchmark/expected/*.json` — confirm fixtures match the new
  shape; regenerate with `./Quickstart bench --live --update-cache`
  if they don't.

**Done when:** a schemagen run on a new vendor PDF produces a model
file that uses the new types, no compact-string references remain in
docs.

## Files touched (cumulative)

| File | Change |
|---|---|
| `specodex/models/common.py` | new `ValueUnit`/`MinMaxUnit` BaseModels; old aliases + validators deleted |
| `specodex/models/{motor,drive,gearhead,robot_arm,electric_cylinder,contactor}.py` | field annotations + hardcoded defaults |
| `specodex/units.py` | dict-form normalizer added; string version + `_COMPACT_RE` deleted |
| `specodex/db/dynamo.py` | `_parse_compact_units` deleted |
| `specodex/utils.py:parse_gemini_response` | comment cleanup; logic unchanged |
| `specodex/llm.py` | verify schema detection still works against new BaseModels |
| `specodex/schemagen/renderer.py` | emits new types |
| `app/backend/src/db/dynamodb.ts` | `parseCompactUnits` deleted |
| `app/frontend/src/components/ProductDetailModal.tsx` | string fallback in `formatValue` deleted |
| `cli/migrate_units_to_dict.py` | new |
| `tests/unit/test_models_common.py` | reshaped |
| `tests/unit/test_db.py` | reshaped |
| `tests/unit/test_compact_units_regex.py` | deleted |
| `tests/unit/test_value_unit_property.py` | reshaped |
| `tests/unit/test_units.py` | reshaped |
| `tests/unit/test_llm.py` | assertions on parsed shape |
| `tests/unit/test_migrate_units.py` | new |
| `tests/benchmark/expected/*.json` | regenerate with `--update-cache` |
| `CLAUDE.md` | line 42 reference updated |

## Estimated effort

- Phase 1 (new classes): 2–3 h
- Phase 2 (motor migration as proof): 2 h
- Phase 3 (remaining 5 models): 3–4 h (mechanical, but six places each)
- Phase 4 (delete the layer): 1–2 h
- Phase 5 (data migration): 2–3 h script + 1 h dev review + promote
- Phase 6 (schemagen + docs): 1 h

Total: 1.5–2 days of code, plus a half-day of human review on the
data migration. Phases 1–4 ship as one PR series with no behavior
change visible to users (same Gemini schema, same DynamoDB shape,
same API responses). Phase 5 is the user-visible fix — rotor_inertia
stops showing semicolons. Phase 6 is housekeeping.

## Risks

- **Gemini schema detection regression.** `to_gemini_schema` currently
  detects `ValueUnitMarker`/`MinMaxUnitMarker` in field metadata. The
  new types are BaseModels — detection switches to class-based
  (`issubclass(annotation, ValueUnit)`). A miss here means Gemini gets
  a generic OBJECT schema and silently breaks extraction. **Mitigate:**
  Phase 2 explicitly diffs `to_gemini_schema(Motor)` before/after; if
  it changes shape, fix detection before merging.
- **Quality gate.** `quality.py:score_product` does `getattr` checks
  for non-None. A `ValueUnit(value=..., unit=...)` is truthy, so this
  should keep working — but verify. A `ValueUnit` with `value=0` is
  also truthy (Pydantic models are always truthy regardless of field
  values), so we don't accidentally start dropping zero-valued specs.
- **Frontend rendering.** Migrated fields arrive as the same dict
  shape the frontend already handles. The risk is the deleted
  `String(value)` fallback removes a defensive net for un-migrated
  legacy rows. **Mitigate:** Phase 5 (data migration) lands before
  Phase 4's frontend cleanup, or the frontend cleanup waits a release
  cycle.
- **Test fixtures.** `tests/benchmark/expected/*.json` were generated
  off the compact-string format. They may already be in dict form
  (Gemini emits dicts; the cache stores raw responses). **Mitigate:**
  inspect a fixture before assuming, regenerate with `--update-cache`
  if needed.

## Triggers

Surface this doc when the current task touches any of:

- `specodex/models/common.py` (`ValueUnit`, `MinMaxUnit`,
  `handle_value_unit_input`, `handle_min_max_unit_input`,
  `validate_*_str`, `_normalize_compact_str`)
- `specodex/models/{motor,drive,gearhead,robot_arm,electric_cylinder,contactor}.py`
  field annotations or default values
- `specodex/units.py:normalize_value_unit` or `_COMPACT_RE`
- `specodex/db/dynamo.py:_parse_compact_units` or
  `app/backend/src/db/dynamodb.ts:parseCompactUnits`
- `specodex/models/llm_schema.py:to_gemini_schema` — Gemini wire-format
  detection
- `specodex/schemagen/renderer.py` — new product type scaffolding
- User mentions "semicolon", "value;unit", "rotor inertia displayed
  wrong", "compact string", "unit format leaking into UI", "scientific
  notation in specs", new vendor with quirky number formats
- Adding a new product type that needs structured numeric specs (the
  scaffolded model uses the new types only after Phase 6)
