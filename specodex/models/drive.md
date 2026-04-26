# Drive Model — Design Notes & Default Columns

Companion to `drive.py`. Documents the schema for servo and variable-
frequency drives, and the default-visible column curation in
`app/frontend/src/types/filters.ts:getDriveAttributes`.

## Scope

Power-electronic drives that control motors from a DC bus or AC
mains — **servo drives** (for position/velocity control of servo
motors) and **variable-frequency drives / VFDs** (for induction
motor speed control). The two share enough of the spec-sheet
vocabulary (input voltage, rated/peak current, output power,
fieldbus, I/O counts) to live under one model with a `type`
discriminator.

Out of scope: soft starters (different capability, different
utilization categories), DC drives (niche; rarely ingested), motor
controllers integrated with the motor (those live as motor records
with `encoder_feedback_support` covering the control side).

## Reference sources

The servo-drive end of the model was exercised hard by the batch
ingest documented in `.claude/skills/servo-drive-ingest.md` — 20
catalogs across Yaskawa Sigma-7, Mitsubishi MR-J5, Rockwell Kinetix,
ABB ACS, Omron G5, Kollmorgen AKD, Siemens SINAMICS. The VFD side
is less populated; adding one or two GA-tier VFD catalogs (ABB
ACS580, Siemens G120, Allen-Bradley PowerFlex 755) would tighten
the schema further and is a good multi-source `schemagen` candidate.

## Default-visible columns (expert curation)

Five specs define a drive's fit for a given motor + application:

| Field | Unit | Why default |
|---|---|---|
| `output_power` | W | Primary sizing metric. Vendor product names often encode it. |
| `input_voltage` | V | Mains compatibility; matches the motor's rated_voltage. Range because drives accept wide windows. |
| `rated_current` | A | Continuous current matched to motor draw. |
| `peak_current` | A | Transient overload — matters for servo torque peaks. |
| `ip_rating` | - | Panel vs washdown vs hazardous-area fit. |

Also visible: `manufacturer`, `part_number`, `type`, `series`.

### Hidden by default (opt-in via restore)

- **I/O counts** — `digital_inputs`, `digital_outputs`, `analog_inputs`,
  `analog_outputs`, `ethernet_ports`. These vary by SKU within a
  family and are integration-specific. Nobody shops the catalog
  sorted by "gimme the one with 4 analog outs"; they check the
  number on a shortlisted model.
- **Arrays of strings** — `fieldbus`, `control_modes`,
  `encoder_feedback_support`, `safety_features`, `safety_rating`,
  `approvals`. Not sortable; already hidden by the kind fallback
  (non-unit bearing → hidden). Use the filter chips to
  include-by-membership ("only show drives that speak EtherCAT").
- `input_voltage_phases`, `max_humidity` — tertiary details.
- `ambient_temp`, `weight` — valid specs, but not primary comparison
  fields for drive selection.

## Design decisions

### `input_voltage` as `MinMaxUnit`, not `ValueUnit`

Universal drives accept a range ("200-240 V AC" / "380-480 V AC").
Single-value would force extraction to pick one end. See
motor.md for the same reasoning.

### Array fields for fieldbus / feedback / modes

Most vendors publish a set of supported options per SKU. A single
value would force the extractor to guess which is "the" one; a list
captures the union and lets the filter chip do set-membership
queries.

### Why `input_voltage_phases` is a list of ints, not a string

`[1]` / `[1, 3]` / `[3]` — a drive may support 1-phase only, 1 or
3-phase input, or 3-phase only. Storing as a list lets the filter
query "only 3-phase drives" via array-membership without string
parsing.

### Known gaps

- No field captures **regen capability** (built-in braking resistor,
  regen unit support). Matters for gantry and vertical-axis servos.
- No field for **DC bus voltage** — increasingly relevant for
  multi-drive DC-bus sharing setups.
- `ambient_temp` validation historically nulled rows when Gemini
  emitted `{"unit": "V"}` (dict without min/max). Covered in
  `project_benchmark_findings.md` in user memory; not fixed here.

## Fields

See `drive.py`. Current set: `type`, `series`, `input_voltage`,
`input_voltage_frequency`, `input_voltage_phases`, `rated_current`,
`peak_current`, `output_power`, `switching_frequency`, `fieldbus`,
`encoder_feedback_support`, `ethernet_ports`, `digital_inputs`,
`digital_outputs`, `analog_inputs`, `analog_outputs`, `safety_rating`,
`approvals`, `max_humidity`, `ip_rating`, `ambient_temp`.
