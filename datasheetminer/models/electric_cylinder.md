# ElectricCylinder Model — Design Notes & Default Columns

Companion to `electric_cylinder.py`. Documents the schema for
integrated electric linear actuators (motor + gearhead + lead-screw
bundled into a single cylinder), and the default-visible column
curation in
`app/frontend/src/types/filters.ts:getElectricCylinderAttributes`.

## Scope

Self-contained **electric linear actuators** — a stepper or BLDC
motor driving a lead screw or ball screw inside a cylinder housing,
producing force + stroke (not torque + speed). Targets: factory
automation push/pull, door openers, medical adjustable beds, test
fixtures.

Covered variants (`type` field): linear actuator, linear servo,
micro linear actuator, tubular linear motor.

Out of scope: standalone lead-screw stages with separate motors
(model those as a motor + lead-screw subassembly), hydraulic or
pneumatic cylinders (different physics), rack-and-pinion systems,
linear belt drives (gantry territory).

## Reference sources

Primary references: Faulhaber L-series, Linak LA36, Thomson
Electrak HD, Tolomatic ERD, SMAC LAL35, Actuonix L16. No formal
multi-source `schemagen` pass has been run for this type; the
current field set was hand-evolved to cover the intersection of
those catalogs. Strong candidate for a `./Quickstart schemagen`
regeneration once 3-4 current PDFs are available locally.

## Default-visible columns (expert curation)

Six fields are the primary selection profile:

| Field | Unit | Why default |
|---|---|---|
| `stroke` | mm | Primary sizing metric. Every vendor product name encodes it. |
| `max_push_force` | N | Output force — paired with stroke defines capability. |
| `continuous_force` | N | Duty-cycle rating, matters for anything not momentary. |
| `max_linear_speed` | mm/s | Throughput / cycle-time budget. |
| `rated_voltage` | V | Drive / supply fit. Range because many accept 12-24V or 24-48V windows. |
| `positioning_repeatability` | mm | Precision grade — separates toys from machine-automation. |

Also visible: `manufacturer`, `part_number`, `type`, `series`.

### Hidden by default

- `max_pull_force` — usually equal to or symmetric with push; not a
  primary differentiator.
- `linear_speed_at_rated_load` — secondary detail; `max_linear_speed`
  is the headline.
- `rated_current`, `peak_current`, `rated_power` — derivable from
  voltage + force + efficiency for rough sizing.
- `lead_screw_pitch`, `gear_ratio`, `backlash`, `max_radial_load`,
  `max_axial_load` — mechanical-installation details.
- `encoder_feedback_support`, `fieldbus`, `ip_rating`,
  `operating_temp`, `service_life`, `noise_level`, `weight` —
  application-fit detail rather than primary sort keys.

## Design decisions

### `stroke` + `max_push_force` as ValueUnit, not MinMaxUnit

Both are single headline values per SKU (not ranges). A vendor's
family may offer many strokes (50/100/200/300 mm) as separate SKUs —
each record carries one.

### Why `rated_voltage` IS MinMaxUnit

Unlike the force / stroke fields, voltage is often published as a
window ("12-24 V DC" / "24-48 V DC") that covers the full drive
compatibility range.

### Integrated motor specs vs separate Motor model

Electric cylinders bundle motor + gearhead + screw. The schema
captures the **electrical interface** (voltage, current, power) at
the top level so cylinders can be filtered on supply compatibility,
but doesn't try to re-capture the motor's internal design
(torque_constant, back-EMF). For those, point at the vendor's
motor-side datasheet.

### `gear_ratio` as optional float

Some cylinders are direct-drive (no gearbox between motor and
screw); others have an integrated gearhead. `gear_ratio` is
optional and `1.0` isn't the implicit default — absence means "not
published" or "not applicable".

### Known gaps

- **Duty cycle** (% on-time) isn't captured. Critical for Linak
  medical actuators and Thomson servicing-duty ones.
- **Side load capacity** — `max_radial_load` covers one mode; bending
  moment handling under off-axis load is unspecified.
- **Screw type** (ball vs lead vs roller) isn't a first-class field;
  it's implied by `motor_type` + `gear_ratio` but could be explicit.

## Fields

See `electric_cylinder.py`. Current set: `type`, `series`, `stroke`,
`max_push_force`, `max_pull_force`, `continuous_force`,
`max_linear_speed`, `linear_speed_at_rated_load`,
`positioning_repeatability`, `rated_voltage`, `rated_current`,
`peak_current`, `rated_power`, `motor_type`, `lead_screw_pitch`,
`gear_ratio`, `backlash`, `max_radial_load`, `max_axial_load`,
`encoder_feedback_support`, `fieldbus`, `ip_rating`, `operating_temp`,
`service_life`, `noise_level`.
