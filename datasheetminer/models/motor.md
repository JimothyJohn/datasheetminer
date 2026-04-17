# Motor Model — Design Notes & Default Columns

Companion to `motor.py`. Documents the schema, reasoning behind the
field set, and the **default-visible column selection** now enforced
by `app/frontend/src/types/filters.ts:getMotorAttributes`.

## Scope

General-purpose industrial motors — AC servo, brushless DC, brushed
DC, AC induction, AC synchronous, permanent magnet, hybrid. Driven by
a separate drive (see `drive.py`); the motor model does not capture
drive-side parameters (switching frequency, fieldbus, etc.).

Out of scope: linear motors (see `electric_cylinder.py`), stepper
motor microstep counts (not universally published), through-bore
hollow-shaft specifics, motor-integrated gearboxes (modelled
separately).

## Reference sources

No single canonical standard defines "the" motor spec sheet, but the
field set here converges across servo catalogs from Kollmorgen,
Yaskawa Sigma-7, Mitsubishi J5, Rockwell Kinetix, and Nidec
frameless — we've ingested these into DynamoDB and the common
denominator of their spec tables informed the field list.

The Mitsubishi J5 and Nidec D-Series frameless PDFs in
`tests/benchmark/datasheets/` are the concrete references; benchmark
ground-truth in `tests/benchmark/expected/` reflects what we expect
to extract from each.

## Default-visible columns (expert curation)

The UI defaults to eight columns for motor tables — the specs an
integrator actually sorts by when shopping the catalog:

| Field | Unit | Why default |
|---|---|---|
| `rated_power` | W | Primary sizing metric. Every datasheet leads with it. |
| `rated_torque` | Nm | Core mechanical output. Cross-vendor headline. |
| `peak_torque` | Nm | Transient overload capacity — matters for servo sizing. |
| `rated_speed` | rpm | Operating point; paired with torque to define power curve. |
| `rated_voltage` | V | Drive compatibility. Range because 3-phase motors have voltage windows. |
| `rated_current` | A | Drive sizing — paired with voltage. |
| `rotor_inertia` | kg·cm² | Reflected-inertia calculations for geared servos. |

Also visible (non-unit but essential for scanning): `manufacturer`,
`part_number`, `type`, `series`.

### Hidden by default (opt-in via restore)

Unit-bearing but **not** comparison-useful for product discovery —
these are motor-designer / control-engineer details:

- `voltage_constant` (Ke, V/krpm) — relates back-EMF to speed; used
  when tuning a drive, not when selecting a motor.
- `torque_constant` (Kt, Nm/A) — used for current loop design.
- `resistance`, `inductance` — winding parameters for electrical
  modelling. Interesting to a drive designer, noise to a buyer.
- `peak_current` — inferable from peak_torque / torque_constant;
  integrators rarely sort by it.
- `weight` — often missing from the record and inconsistent across
  vendors (frame-size catalog entries group dozens of weights).

All can be surfaced via the `+ N hidden` restore dropdown.

## Design decisions

### `rated_voltage` as `MinMaxUnit`, not `ValueUnit`

Three-phase motors are often spec'd across a voltage window
(200-230 V / 380-480 V). A single value field would force extraction
to pick one end and lose the range. The BeforeValidator accepts both
scalar (`{value, unit}`) and range (`{min, max, unit}`) dict shapes
and coerces to canonical `"min-max;unit"` strings.

### Why no `max_speed` distinct from `rated_speed`

`motor.py` once had both. They're nearly always identical for servo
motors, and when they differ (induction motors spec'd at base-speed
with a field-weakening extended speed) the detail belongs in a
dedicated field (e.g. `max_speed_field_weakening`) rather than a
generic `max_speed`. For now the schema has only `rated_speed`; the
dynamic filter path will pick up any `max_speed` that gets ingested.

### `encoder_feedback_support` as `str`, not `List[str]`

Most servo datasheets publish a single encoder option per SKU
("Absolute 24-bit", "Incremental 2500 PPR"). Some vendors list
variants as separate SKUs; lumping feedback options into a list-per-
record pretends SKUs are interchangeable when they're not.

### Known gaps

- `ambient_temp` is absent — drive.py has it, but motors rarely publish
  a temperature range at the motor level (it's a system spec). Add if
  enough records carry it.
- No field captures **continuous operating zone** or the torque/speed
  curve. Those are essential for servo selection but come as graphs,
  not table scalars. Needs a dedicated shape (list of points) if
  someone decides to capture it.

## Fields

See `motor.py` for the authoritative list. Current field set: `type`,
`series`, `rated_voltage`, `rated_speed`, `max_speed`, `rated_torque`,
`peak_torque`, `rated_power`, `encoder_feedback_support`, `poles`,
`rated_current`, `peak_current`, `voltage_constant`, `torque_constant`,
`resistance`, `inductance`, `ip_rating`, `rotor_inertia`,
`axial_load_force_rating`, `radial_load_force_rating`.
