# RobotArm Model — Design Notes & Default Columns

Companion to `robot_arm.py`. Documents the schema for industrial and
collaborative robot arms, and the default-visible column curation in
`app/frontend/src/types/filters.ts:getRobotArmAttributes`.

## Scope

Serial-kinematic multi-axis articulated arms — industrial 6-axis
arms (Fanuc, KUKA, ABB, Yaskawa Motoman), collaborative arms
(Universal Robots, Doosan, Techman, AUBO), SCARA (Epson, Yamaha),
and delta-parallel picker arms (ABB FlexPicker, Omron Hornet).

Out of scope: mobile robots (AMRs/AGVs — different spec vocabulary),
grippers and end-effectors, cartesian gantries / linear stages (use
`electric_cylinder.py` or a dedicated `gantry` type), quadruped and
humanoid platforms.

## Reference sources

No single canonical reference. The field set reflects the
intersection of spec tables from Universal Robots UR10e, ABB IRB
1600, Fanuc CRX, Yaskawa GP series, and Epson T3 SCARA. A fresh
multi-source `schemagen` pass with 3-4 current cobot and industrial
datasheets would be valuable.

## Default-visible columns (expert curation)

Six columns surface the primary selection criteria:

| Field | Unit | Why default |
|---|---|---|
| `payload` | kg | Primary sizing metric. Every datasheet headlines it. |
| `reach` | mm | Workspace envelope. Paired with payload defines the arm's class. |
| `degrees_of_freedom` | - | 4-axis SCARA vs 6-axis vs 7-axis collaborative. Shapes capability. |
| `pose_repeatability` | mm | Precision grade — separates pick-and-place ($) from assembly ($$$). |
| `max_tcp_speed` | m/s | Throughput metric for cycle-time calculations. |
| `ip_rating` | - | Environment fit (IP54 office cobot vs IP67 washdown). |

Also visible: `manufacturer`, `part_number`, `product_family`.

### Hidden by default

- `noise_level`, `mounting_position`, `cleanroom_class`, `operating_temp`,
  `materials`, `safety_certifications` — specialist or application-
  fit detail.
- `weight` — matters for mobile-base integration but not primary.

The nested structures (`joints`, `tool_io`, `controller`, etc.) don't
appear as filter chips at all — they're too complex to sort by.
Users drill into those in the detail view.

## Design decisions

### Nested sub-models for joints / controller / IO

A robot arm has multi-axis joint specs, a controller cabinet, a
teach pendant, and a tool interface. Representing these as flat
fields on the top level would explode the schema. The sub-models
(`JointSpecs`, `ToolIO`, `Controller`, `TeachPendant`,
`ForceTorqueSensor`) capture each subsystem coherently while
keeping the top-level `RobotArm` scannable.

### `payload` as `ValueUnit`, `pose_repeatability` as `ValueUnit`

Both are single-value specs every datasheet publishes. Collaborative
arms sometimes publish payload at different reaches (e.g. "5 kg at
any pose, 7 kg within reduced envelope") — if that detail matters,
capture in a follow-up `payload_curve` field rather than inflating
this one.

### `degrees_of_freedom` as `int`

Nearly always 4, 6, or 7. No unit, no fractional values. Storing
as a ValueUnit would add noise.

### Why no `ISO class`, `safety rating (Cat 3, PLd, SIL 2, ...)` top-level

Currently lives under `safety_certifications` as a list of strings.
If filtering on specific safety ratings becomes a common query,
promote the most-queried ones to scalar fields.

### Known gaps

- **Working envelope** isn't captured beyond `reach`. True workspace
  is a 3D shape — lean on `reach` as the scalar proxy.
- **Joint speeds** live per-joint in `JointSpecs` but aren't exposed
  at the top level for cross-product sort (the slowest joint
  dominates cycle time for many motions).
- **Force-torque sensor specs** — optional sub-model, but many cobot
  vendors publish force-mode parameters inline. Could flatten if
  filtering on "arms with wrist F/T" becomes common.

## Fields

See `robot_arm.py`. Top-level: `payload`, `reach`,
`degrees_of_freedom`, `pose_repeatability`, `max_tcp_speed`,
`ip_rating`, `cleanroom_class`, `noise_level`, `mounting_position`,
`operating_temp`, `materials`, `safety_certifications`, `weight`.
Nested sub-models: `joints` (list), `force_torque_sensor`, `tool_io`,
`controller`, `teach_pendant`.
