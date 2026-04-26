# Gearhead Model — Design Notes & Default Columns

Companion to `gearhead.py`. Documents the schema for planetary,
harmonic, cycloidal, and helical gearheads; and the default-visible
column curation in
`app/frontend/src/types/filters.ts:getGearheadAttributes`.

## Scope

Precision gearheads for servo systems — planetary (GAM, Neugart,
Wittenstein alpha, Stober), harmonic (Harmonic Drive, Nidec CSD),
cycloidal (Nabtesco, Sumitomo). Emphasis on **servo-grade
characteristics** (low backlash, high torsional rigidity, defined
service life) rather than industrial worm-gear reducers or
transmissions.

Out of scope: integral motor-gearheads (captured on the motor
model), automotive transmissions, large-scale industrial reducers
where backlash isn't published.

## Reference sources

Primary references: GAM GP series, Wittenstein alpha TP+, Neugart
PLE, Harmonic Drive CSD/CPL, Nabtesco RV-E/RV-N. Schema field choices
reflect the intersection of their spec tables.

A formal multi-source `schemagen` pass has not been run on gearheads
yet — the current field set was hand-evolved from the early motor
work. Candidate future work: ingest three top-tier servo gearhead
catalogs side-by-side via `./Quickstart schemagen` to regenerate the
schema + reasoning doc from first principles.

## Default-visible columns (expert curation)

Six columns by default:

| Field | Unit | Why default |
|---|---|---|
| `gear_ratio` | - | Primary selection criterion. Unitless. |
| `gear_type` | - | Planetary vs harmonic vs cycloidal — shapes everything else. |
| `max_continuous_torque` | Nm | Sizing metric paired with the motor's rated_torque. |
| `max_peak_torque` | Nm | Transient capacity — must exceed motor peak × ratio. |
| `backlash` | arcmin | The servo-grade differentiator. Higher-end harmonic is <1 arcmin; planetary is 3-10. |
| `efficiency` | % | Power budget impact; varies 70-95% across types. |

Also visible: `manufacturer`, `part_number`.

### Hidden by default

Installation-specific or application-detail:

- `input_shaft_diameter`, `output_shaft_diameter` — matter only after
  the ratio/torque fit is decided.
- `max_radial_load`, `max_axial_load` — depend on mounting geometry
  and duty cycle.
- `nominal_input_speed`, `max_input_speed` — often underspec'd
  (datasheets list a single value that users can exceed with
  derating curves).
- `torsional_rigidity` — harmonic-gearbox differentiator, but the
  unit (Nm/arcmin) is alien to most buyers.
- `rotor_inertia` (reflected output inertia) — rarely published, and
  computed values are derivable from geometry.
- `noise_level`, `service_life`, `lubrication_type` — marketing /
  maintenance detail.
- `operating_temp`, `weight` — secondary.

## Design decisions

### `gear_ratio` as `Optional[float]`, not ValueUnit

It's a pure unitless ratio. Storing as `ValueUnit` with `unit=':1'`
would force the extractor to emit a dict shape for every value.

### `backlash` in arcmin

arcmin is the universal unit servo-grade datasheets use. Converting
to degrees or mrad would make cross-vendor comparison arithmetic. A
BeforeValidator accepts "arcmin", "arc min", "'" etc. and normalizes.

### `efficiency` as `float` (percentage), not ValueUnit

Same reasoning as gear_ratio — it's a unitless percentage; the `unit`
metadata entry labels it '%'. The field itself stores the raw number
(e.g. `0.92` or `92` — inconsistent across vendors; BeforeValidator
normalizes to the 0-100 convention).

### Why both `max_continuous_torque` and `max_peak_torque`

Gearheads are rated for two duty regimes: continuous running and
transient peaks (emergency stops, starts). Servo sizing checks both
separately, so both are first-class fields.

### Known gaps

- No field for **moment of inertia at output** — relevant for servo
  tuning, rarely published.
- No field for **efficiency vs load-factor curve** — vendors publish
  curves rather than the single-point the schema captures.
- Harmonic-specific fields (flexspline lifetime, ratchet torque) not
  modelled. Would clutter the general schema; handle via a subclass
  if the volume justifies it.

## Fields

See `gearhead.py`. Current set: `gear_ratio`, `gear_type`, `stages`,
`nominal_input_speed`, `max_input_speed`, `max_continuous_torque`,
`max_peak_torque`, `backlash`, `efficiency`, `torsional_rigidity`,
`rotor_inertia`, `noise_level`, `frame_size`, `input_shaft_diameter`,
`output_shaft_diameter`, `max_radial_load`, `max_axial_load`,
`ip_rating`, `operating_temp`, `service_life`, `lubrication_type`.
