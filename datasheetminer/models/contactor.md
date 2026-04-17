# Contactor Model — Design Notes & Sources

Companion to `contactor.py`. Explains the field set, why it was chosen
over the initial Mitsubishi-derived draft, and the datasheets the design
was grounded in. Regenerate this doc if the model changes materially.

## Scope

General-purpose **industrial electromagnetic contactors** (magnetic
starters) and their solid-state equivalents, used for motor starting,
resistive load switching, and auxiliary control. Governed by
**IEC 60947-4-1** in Europe/Asia and **UL 508** / CSA 22.2 No. 14 in
North America.

Out of scope for this model: definite-purpose contactors (HVAC /
lighting), vacuum contactors for medium voltage, and pilot-duty
miniature relays. Those would earn their own models when the repo
ingests them.

## Sources

Six manufacturer datasheets were read end-to-end before finalizing the
schema. Every claim below cites at least one.

| Vendor | Product line | Source |
|---|---|---|
| ABB | AF09–AF38 | [Galco technical data PDF](https://docs.galco.com/techdoc/abbg/cont_af09-af38_td.pdf) · [Controller Service mirror (AF09–AF96)](https://www.controllerservice.com/images/products/abb/abb_motor_control_102-119_af_contactors.pdf) |
| Schneider Electric | TeSys D (LC1D09BD) | [Octopart datasheet PDF](https://datasheet.octopart.com/LC1D09BD-Schneider-Electric-datasheet-111094726.pdf) |
| Siemens | SIRIUS 3RT2016-1BB41 | [Octopart datasheet PDF](https://datasheet.octopart.com/3RT2016-1BB41-Siemens-datasheet-101613911.pdf) |
| Allen-Bradley / Rockwell | Bulletin 100-C (100-TD013G) | [100-TD013G IEC Contactor Specifications](https://lvmcc-pubs.rockwellautomation.com/pubs/100-TD013G-EN-P.pdf) |
| Fuji Electric | SC-series (SC-03 – SC-N14) | [EN_01 AC-operated magnetic contactors](https://www.fujielectric.com/fcs/support_contact/support/standard/box/pdf/EN/EN_01.pdf) |
| Mitsubishi Electric | MS-T/N | `tests/benchmark/datasheets/mitsubishi-contactors-catalog.pdf` (local) |

Eaton XT was targeted but the vendor page returns 403 and the
CDN-hosted datasheet exceeded WebFetch limits. Eaton's XT fields
follow the same IEC 60947-4-1 structure per its public marketing, but
no Eaton-specific claim lives in this schema.

## Why the Mitsubishi-first draft was wrong

The first pass at `contactor.py` was schemagen'd from a single PDF and
inherited three Mitsubishi-specific habits that don't generalize:

1. **Per-voltage scalar fields** `rated_operating_current_ac3_220v`,
   `_440v`, `_500v`, `_690v` and the matching `rated_capacity_ac3_*v`.
   No other vendor breaks AC-3 ratings out this way. ABB, Schneider,
   Siemens, Rockwell, Fuji all publish the rating table as a
   **multi-row block keyed by voltage**. The scalar-per-voltage shape
   forces the extractor to pick four specific voltages and drops any
   other (e.g. Rockwell publishes 230 / 400–415 / 500 / 690 — the
   440V column doesn't exist).
2. **`frame_size: str`** holding Mitsubishi's "T10 / N125" notation.
   Every vendor has its own frame code (ABB "AF09", Siemens "S00",
   Fuji "SC-N1"), and some US-market SKUs *also* publish a NEMA size
   ("00" … "9"). Two distinct concepts collapsed into one field.
3. **`approvals: List[str]`** mixing formal standards (IEC, UL, CSA,
   GB) with marks/certifications (CE, CCC, cULus). These are two
   different filterable concepts — a user asking "UL 508 compliant"
   is looking at a standard, not a mark.

## Schema decisions

### Rating tables as `List[ContactorPowerRating]`

AC-3 / AC-1 / AC-4 ratings are inherently multi-row. Every source
publishes them that way. The generalized schema captures the full
table as `List[ContactorPowerRating]` where each row carries
`voltage`, `voltage_group`, `current`, `power_kw`, `power_hp`, and
optional `ambient_temp`.

- **Both kW and hp are stored, never converted.** Fuji publishes kW
  only; ABB/Allen-Bradley publish both; Siemens SIRIUS data has hp
  for the US-market SKUs. Converting kW→hp at ingest would mask
  whether the vendor actually publishes a UL rating.
  (Sources: ABB AF09–AF38 PDF; Siemens 3RT2016-1BB41 PDF, both blocks
  visible side-by-side.)
- **Voltage groups are preserved verbatim.** Fuji groups "380–440 V",
  ABB groups "380–400 V". Snapping to canonical bins is the reader's
  job, not the extractor's.
- **Ambient temperature rows for AC-1.** ABB and Allen-Bradley both
  publish Ie AC-1 at 40 °C / 60 °C / 70 °C as separate rows in the
  same table. The optional `ambient_temp` field on the row keeps
  those pairs bound.

### Headline scalars for filtering

Lists-of-objects aren't naturally filterable in the UI (the frontend's
`deriveAttributesFromRecords` can't produce a sort-by-me chip from a
nested array). Three top-level scalar fields were added so the
filter/sort surface has something to grip:

- `ie_ac3_400v` — IEC headline current at 400 V AC-3. Every European
  datasheet includes this row; it appears in the Siemens and
  Schneider product name itself ("CONTACTOR, AC-3, 4KW/400V").
- `motor_power_ac3_400v_kw` — IEC headline motor power, same
  reasoning.
- `motor_power_ac3_480v_hp` — NEMA headline motor power. 460/480 V
  is the de-facto UL headline voltage (Allen-Bradley, ABB US-market
  SKUs sort by this).

Mitsubishi's 440V-centric headline is a JIS-market quirk (Japanese
motors are 200/220/440 V) and is not adopted as a schema default.

### Short-circuit withstand as a curve

Icw is published as a curve — ABB gives 1 s / 10 s / 30 s / 1 min /
15 min, Allen-Bradley gives 0.5 s / 1 s / 3 s / 10 s — and a scalar
loses that shape. `short_circuit_withstand_icw:
List[ContactorIcwRating]` captures the duration/current pairs.
**SCCR** (UL short-circuit current rating) is a *separate* single
scalar and is stored on its own field — confusing it with Icw is a
common mistake.

### Coil range vs individual SKU

A series datasheet (ABB AF, Schneider TeSys D) typically shows the
**range of coil voltages the family supports** ("24–500 V AC, 12–500 V
DC"), while a single-SKU datasheet shows **one Uc**. Both shapes need
to land in the same schema:

- `coil_voltage_range_ac` / `coil_voltage_range_dc` — range fields
  for series-level datasheets.
- `coil_voltage_options` — list of discrete designations for SKUs that
  enumerate ("24V AC", "230V AC", "24V DC").

### Pickup/dropout as unitless ratios

Every vendor specifies pickup and drop-out as a **fraction of Uc**:
ABB "0.85…1.1 Uc", Schneider "0.7…1.25 Uc", Allen-Bradley "0.85…1.1 ×
Us". Storing in volts loses the portability. `MinMaxUnit` with
`unit='×Uc'` keeps the ratio semantics intact and the existing
`handle_min_max_unit_input` BeforeValidator accepts any unit string
(including "×Uc") without coercion.

### Standards vs certifications split

Two separate fields with distinct fill rules:

- `standards_compliance: List[str]` — formal standards the device
  claims conformance to. Whitelist-ish: IEC 60947-4-1, UL 508, CSA
  22.2 No. 14, EN 60947-4-1, GB 14048.4.
- `certifications: List[str]` — third-party marks: CE, CCC, UL
  Listed, cULus, BV, DNV, GL, EAC.

A user filtering "UL 508" gets a different answer than "UL Listed"
and the schema should let them distinguish.

## Normalization traps

These are worth mentioning because they'll bite the LLM extraction
path and the quality gate if they aren't explicit:

1. **AC inrush vs DC inrush units.** AC coils are spec'd in VA, DC in
   W. Sealed is often reported *both* (ABB AF: "2.2 VA / 2 W"). The
   BeforeValidator already accepts any unit; both fields are
   `ValueUnit` so the LLM can emit whichever the datasheet uses.
2. **kW / hp fractional notation.** NEMA tables have "7-1/2 hp",
   "1/3 hp". Normalize to float (7.5, 0.333) in the extraction
   BeforeValidator, not in the UI.
3. **Voltage binning.** Vendor voltage groups vary — "380-400",
   "380-415", "380-440". `voltage_group: str` captures the raw label;
   `voltage: ValueUnit` captures the canonical value (when a single
   voltage is unambiguous) or is omitted.
4. **"Headline" extraction for filter fields.** When populating
   `ie_ac3_400v`, prefer the exact 400 V row from the AC-3 table.
   If the vendor publishes only 380-415 V grouped, extract that row
   and flag in the log — don't interpolate.

## Open questions

- **Altitude derating curves.** Most vendors give a single
  `altitude_max` at a derating factor (2000 m / 3000 m) but not the
  full curve. `altitude_max: ValueUnit` is an OK starting point;
  revisit if someone actually needs the derating shape.
- **Electrical endurance as single scalar vs curve.** The schema
  captures `electrical_durability_ac3` as a scalar. Some vendors
  (ABB, Rockwell) publish life curves across load factor. A
  `List[{load, operations}]` type would be more faithful but nobody
  has asked to filter by it yet.
- **Reversing / mechanically-latched variants.** Modelled via the
  `type` discriminator, but reversing contactors are really *two*
  physical contactors + an interlock; a linking field between the
  two SKUs might be useful later.
