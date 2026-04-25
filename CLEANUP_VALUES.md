# Cleanup of legacy `value;unit` strings in DynamoDB

Scope: `products-dev` (1,772 items). 685 items (~38.7%) carry at least one
string value containing `;` — i.e. the canonical compact form was written
to the table without going through `DynamoDBClient._parse_compact_units`
at `datasheetminer/db/dynamo.py:71`. Pre-validation legacy.

The cleanup script is `scripts/cleanup_semicolon_legacy.py`. Categorizer
already patched to absorb the common corruption shapes uncovered during
the dry-run.

## Dry-run results

| Bucket | Hits | Action | Status |
|---|---|---|---|
| garbage (`;null`, `;unknown`) | 493 | Delete field | Auto |
| multivalue (`,` / `(` / `/` / `x` separators) | 367 | Flag — schema redesign | Manual |
| recoverable_pm (`±N`, `/-N`, `- N`, `±;N°`) | 360 | Re-parse → `{value, unit}` | Auto |
| wrong_field (alpha-leading, `*` artifacts) | 339 | Delete field | Auto |
| bound (`≤N`, `≥N`, `>N`, `<N`) | 178 | Flag — needs bound semantics | Manual |
| recoverable_rng (`min-max`, `min~max`) | 96 | Re-parse → `{min, max, unit}` | Auto |
| recoverable (plain `N`, scientific `1e-6`) | 83 | Re-parse → `{value, unit}` | Auto |
| uncategorized | 14 | Flag — true outliers | Manual |
| wordy | 2 | Flag — hand-edit | Manual |

Aggregate: **597 items touched**, **832 field removals**, **263 items**
with at least one re-parsed string.

Reports (regenerate by running the script in dry-run mode) write to
`outputs/semicolon_cleanup/`.

## How the apply works

For every offending item the script:

1. Categorizes each `;`-bearing string via `categorize()` in the script.
2. For `garbage` / `wrong_field`: `del item[path]`.
3. For `recoverable*`: replaces the string with a `{value, unit}` (or
   `{min, max, unit}`) dict in-place.
4. Runs the whole item through `DynamoDBClient._parse_compact_units` and
   `_convert_floats_to_decimal` so any incidentally-still-stringy
   leaf the categorizer didn't touch is also coerced.
5. `put_item(Item=cleaned)` — full-row replace.

`bound`, `multivalue`, `wordy`, `uncategorized` are **left in place**
and only written to flag reports. They need schema decisions before
backfilling.

## Run it

    # 1. Dry-run, regenerate reports, eyeball numbers
    uv run python scripts/cleanup_semicolon_legacy.py

    # 2. Spot-check 5 entries each from the destructive buckets — these
    #    fields are gone after --apply:
    jq '.[:5]' outputs/semicolon_cleanup/*.json   # multivalue / wordy / etc.
    # garbage and wrong_field are NOT exported (they're auto-deleted);
    # to preview them, comment out the `if cat in DESTRUCTIVE` branch
    # and re-run dry-run, OR just trust the regex set.

    # 3. Apply
    uv run python scripts/cleanup_semicolon_legacy.py --apply

    # 4. Verify residual = 0
    uv run python -c "
    from datasheetminer.db.dynamo import DynamoDBClient
    c = DynamoDBClient()
    SKIP = {'PK','SK','product_id','datasheet_id','datasheet_url'}
    def walk(v):
        if isinstance(v, str): return ';' in v
        if isinstance(v, dict): return any(walk(x) for k,x in v.items() if k not in SKIP)
        if isinstance(v, list): return any(walk(x) for x in v)
        return False
    n = 0
    kw = {}
    while True:
        r = c.table.scan(**kw)
        for it in r.get('Items', []):
            if any(walk(v) for k,v in it.items() if k not in SKIP):
                n += 1
        if 'LastEvaluatedKey' in r: kw['ExclusiveStartKey'] = r['LastEvaluatedKey']
        else: break
    print('rows still carrying ;:', n)
    "

If step 4 returns > 0, inspect — some category likely needs a new branch
in `categorize()`.

## Manual-review buckets

### `bound.json` — 178 hits (`≤`, `≥`, `>`, `<`)

Schema treats these as point values; physically they are upper / lower
bounds. Two options:

- **Cheap**: drop the operator, store as point. Lossy for filters
  (a `≤ 12 arcmin` row will match a `= 12 arcmin` filter).
- **Right**: extend the value-unit dict shape with `{kind: "max"|"min"|"point", value, unit}`. Update Pydantic models, frontend
  formatters, filter logic. Backfill these 178 hits with explicit
  `kind`. Larger blast radius, correct semantics.

Recommend **right** — `≤` matters for backlash, repeatability, and
service-life specs where the customer cares about worst-case bound.

### `multivalue.json` — 367 hits

Two distinct sub-shapes inside the bucket:

1. **Variants** — `12/24;V`, `2000/2800;mm/s`, `4000, 8000;Hz`. The
   product genuinely supports multiple discrete values. Schema fix:
   list-typed field (`list[ValueUnit]`).
2. **Per-axis / per-component** — `±0.015;mm (Z), ±0.005° (T)`,
   `320x240;pixels`. The value differs per axis. Schema fix: object
   with named axes (`{x, y, z}`) or a structured `Resolution` model.

**Plan**:

- Triage the report into the two sub-types (one-time pass).
- Identify which fields actually need a list/axis representation by
  frequency (top: joint working ranges, power_source, max_speed,
  noise_level when stated as "60-65 dB(A) range").
- Extend the relevant Pydantic models. Re-extract affected rows via
  `./Quickstart bench --live --update-cache` against the new schema or
  re-run the LLM through `scraper.process_datasheet` with the new
  model registered.
- Once the model lands, the data path is correct going forward. The
  legacy 367 strings get re-extracted on the next batch run and
  validated, so no hand-migration is needed.

### `wordy.json` — 2 hits

- `"3 Times of Rated Output Torque;unknown"` (`max_peak_torque` on
  several Delta gearheads). Relational quantity, can't be numeric.
  Either drop the field for those rows, or add `peak_torque_note: str`
  on `Gearhead` and demote the relational text there.
- `"Lifetime;lubrication"` (`warranty`). The string actually describes
  *lubrication lifetime*, not warranty. Move to a `lubrication: str`
  field on `Gearhead` or delete.

Two-row impact each — easiest path is hand-edit via the AWS console.

### `uncategorized.json` — 14 hits

- `24V;2A` (×6) — voltage and current jammed into one string, in
  `tool_io.power_supply_voltage` / similar. Wrong field; safest is to
  delete (treat as `wrong_field` in a follow-up patch).
- `≤ Ø 8;mm` (×6), `≤ Ø 14;mm` (×2) — bound + diameter combo on
  `input_shaft_diameter`. Once `bound` is solved with explicit
  `{kind: "max", value, unit}`, these collapse into that shape.

## Filter-friendly canonical values (separate, larger plan)

Distinct from the semicolon issue: many string-typed fields have high
cardinality due to formatting drift (`"IP65"`, `"IP 65"`, `"IP-65"`,
`" IP65 "`). Filters become useless when every row's value is unique.

### Vocabulary layer

Proposed `datasheetminer/vocab/<field>.yml`:

    # datasheetminer/vocab/feedback_type.yml
    canonical:
      - resolver
      - encoder_optical
      - encoder_magnetic
      - encoder_inductive
      - hall_sensor
    aliases:
      "optical encoder": encoder_optical
      "magnetic encoder": encoder_magnetic
      "incremental encoder": encoder_optical    # default; refine if needed
      "absolute encoder": encoder_optical
      "resolver feedback": resolver

### Normalizer

`datasheetminer/normalize.py`:

    def normalize(field: str, value: str) -> tuple[str, bool]:
        """Returns (canonical_value, was_known).

        was_known=False signals an unrecognized value — log it for
        promotion to canonical or alias on the next vocab review.
        """

Hook point: in `datasheetminer/utils.py:parse_gemini_response`, after
the BeforeValidators run, walk every field that has a vocab and
substitute the canonical form. Falls back to the LLM-provided value
when no vocab exists for the field (current behavior).

### Unknown-value capture

When `was_known=False`, append to `outputs/unknown_vocab/<field>.csv`
with `(value, manufacturer, part_number, count)`. Periodic review:
high-frequency unknowns get promoted to `canonical` or aliased; one-off
typos get aliased to the canonical they likely meant.

### Backfill

One-shot script (model: `scripts/backfill_vocab.py`): scan, normalize,
`put_item`. Same pattern as `cleanup_semicolon_legacy.py`. Idempotent
if the normalizer is.

### Frontend filter generation

`app/frontend/src/types/filters.ts:deriveAttributesFromRecords`
currently builds chip options from the records actually present. After
the vocab layer ships, derive option lists from the vocab files
(loaded via the backend) so chip options are stable across stages and
include canonical values that no row has yet — useful when the catalog
is small and the user wants to know what filter values *exist*.

### Priority field list

In rough order of UI impact (high cardinality + commonly filtered):

1. `mounting`            (mechanical)
2. `feedback_type`       (motor)
3. `cooling`             (motor / drive)
4. `fieldbus`            (drive)
5. `control_modes`       (drive)
6. `phases`              (drive / motor — should be int already; audit)
7. `ip_rating`           (already int-coerced via `_coerce_ip_rating`; audit residual strings)
8. `controller.power_source` (robot_arm)

Pick the top 2–3 to ship the vocab layer with so the abstraction is
proven before broad rollout.

## Open questions before --apply

- **`controller.power_source`** (42 hits, mostly `multivalue` / `wrong_field`):
  these aren't really product-spec values, they're prose. Worth
  inspecting whether the field belongs on the model at all.
- **`warranty`** (44 hits, all `wrong_field` or `wordy`): same — does
  this field carry useful structured data anywhere, or should it just
  be dropped from the schema?
- **Prod table**: this run targets `products-dev`. Confirm there is no
  separate `products-prod` table that needs the same treatment, or
  promote the cleanup post-deploy.
