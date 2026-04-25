# Add `linear_actuator` product type

## Problem

The recent Tolomatic ingest (`cli/ingest_tolomatic.py`) routes everything
mechanical-linear into `electric_cylinder`. About half of those products
aren't electric cylinders — they're rodless: belt-driven carriages,
ball-screw rodless modules, linear slides, precision stages. The
`ElectricCylinder` model in `datasheetminer/models/electric_cylinder.py`
is built around an integrated motor pushing a rod (force out the end),
which doesn't fit a carriage moving along a rail.

Need a new `linear_actuator` product type to capture the rodless half,
re-route the affected Tolomatic slugs, and clean up DB rows that landed
in the wrong type.

## Slug classification (Tolomatic)

From `cli/ingest_tolomatic.py:34-83` — 27 entries currently typed as
`electric_cylinder`. Split:

### Stay as `electric_cylinder` (rod-style, push/pull from a rod)

ERD, ERD-SS2, IMA, IMA Food Grade, IMA-S, RSA, RSA/RSM, RSH, RSX,
ServoChoke SVC, ServoPlace, ServoWeld GSWA-33, ServoWeld GSWA-44-04,
ServoWeld SWA/SWB, CSWX. **15 slugs.**

### Move to new `linear_actuator` (rodless / slide / stage)

| Slug | Product | Drive |
|---|---|---|
| `b3s-ball-screw-linear-actuators` | B3S | ball screw rodless |
| `b3w-linear-belt-drive-actuators` | B3W | belt drive |
| `bcs-rodless-screw-actuators` | BCS | rodless screw |
| `gsa-linear-slide-actuators` | GSA | linear slide |
| `mxb-p-heavy-duty-linear-actuator` | MXB-P | heavy belt, guided |
| `mxb-u-unguided-belt-driven-actuators` | MXB-U | belt, unguided |
| `mxbs-linear-belt-drive-actuator` | MXB-S | belt drive |
| `mxe-p-screw-driven-actuators` | MXE-P | screw rodless |
| `mxe-s-linear-screw-actuators` | MXE-S | screw rodless |
| `sls-electric-linear-slide-actuator` | SLS | linear slide |
| `tkb-precision-linear-stages` | TKB | precision stage |
| `trs-twin-profile-rail-stage-w-enclosed-design` | TRS | twin-rail stage |

**12 slugs.** Borderline cases worth re-checking before commit:
- `bcs-rodless-screw-actuators` is rodless mechanically but the catalog
  copy could read either way; verify by skimming a BCS spec page.
- `mxb-u-unguided-belt-driven-actuators` is "unguided" — might be
  closer to a rod-style than other MXB variants.

## Schemagen — sources used so far

3 PDFs + 3 Tolomatic spec-table images. Tolomatic-only would have
biased the schema; the 3 outside vendors round it out.

| Source | Type | Vendor | URL / path |
|---|---|---|---|
| `rexroth-ckk-ckr.pdf` | PDF, 16 pages | Bosch Rexroth | https://boschrexroth.africa/public/front_end/pdfs/products/c648801d2e1766837a3231b32fac8363.pdf |
| `smc-lef.pdf` | PDF, 222 pages | SMC | https://static.smc.eu/pdf/LEF-F_EU.pdf |
| `thk-kr.pdf` | PDF, 6 pages | THK | https://www.thk.com/sites/default/files/thkcom/us/Catalog-KR-RL.pdf |
| `3600-4176_10_B3_cat-21.png` | image | Tolomatic | `/tmp/tolomatic-scrape/samples/` |
| `3600-4231_01_GSA-ST-HT_cat-6.png` | image | Tolomatic | `/tmp/tolomatic-scrape/samples/` |
| `8300-4000_16_MXE_cat-21.png` | image | Tolomatic | `/tmp/tolomatic-scrape/samples/` |

PDFs are at `/tmp/linear-actuator-schemagen/sources/` — re-curl if `/tmp`
got wiped. Page-finder filtered SMC to 38/222 pages so total payload was
5.4 MB, well within Gemini limits. Cost: ~16k input + 2.9k output
tokens (~$0.005).

Vendors that gated their PDFs and got skipped: Festo (403 on product
page), Parker (Akamai 403 on CDN), IAI (registration wall). Add later
only if the schema needs another perspective.

## Schemagen draft — issues to fix before `--write`

Dry-run output lives at `/tmp/linear-actuator-schemagen/schemagen-dryrun.log`.
Don't `--write` the first draft. Six things to fix:

1. **Class name regressed to `ElectricCylinder`.** Gemini ignored the
   rename hint, and the CLI's class-name override at
   `cli/schemagen.py:364-365` only fires when `--class-name` is passed
   explicitly. Re-run with `--class-name LinearActuator`. (Possible
   schemagen bug worth filing separately: the derived default isn't
   applied when Gemini disagrees.)

2. **`type` and `actuation_mechanism` literals are too narrow.** Both
   came back as `Literal['ball_screw', 'belt_drive']`. Need at least
   `linear_slide`, `linear_stage`, `lm_guide_actuator`, `rodless_screw`
   for `type`; the two fields are also redundant — `type` should be
   form factor, `actuation_mechanism` should be drive. Probably needs
   either a more directive `--type` name (`rodless_actuator`?) or a
   hand-edit before write.

3. **`motor_type: Literal['step_motor', 'servo_motor']` misses
   `motorless`.** Rexroth/THK/SMC all sell motorless variants — many
   rows would drop their motor_type silently.

4. **`ip_rating: int` — wrong type.** Repo standard is the `IpRating`
   shared validator (`models/common.py`), which emits strings like
   "IP67M". As `int` the field would silently drop those rows on
   validation.

5. **Registry-reuse warnings (13 of them) are mostly noise.** They flag
   `value_unit` vs `str` mismatches against existing fields like
   `stroke`, `max_push_force`, `rated_voltage`. But `Length`, `Force`,
   `Current` from `common.py` *are* `value_unit` BeforeValidators that
   serialize to strings — schemagen's registry doesn't see through the
   alias. Safe to ignore for this run; worth fixing in
   `schemagen/prompt.py:build_field_registry` later so future
   schemagen runs don't cry wolf.

6. **Reasoning doc has duplicate `### General` headers.** Renderer bug
   in `datasheetminer/schemagen/renderer.py` — categories aren't
   deduplicated. Cosmetic.

## Recommended next pass

```bash
source .env && \
./Quickstart schemagen \
  /tmp/linear-actuator-schemagen/sources/rexroth-ckk-ckr.pdf \
  /tmp/linear-actuator-schemagen/sources/smc-lef.pdf \
  /tmp/linear-actuator-schemagen/sources/thk-kr.pdf \
  /tmp/tolomatic-scrape/samples/3600-4176_10_B3_cat-21.png \
  /tmp/tolomatic-scrape/samples/3600-4231_01_GSA-ST-HT_cat-6.png \
  /tmp/tolomatic-scrape/samples/8300-4000_16_MXE_cat-21.png \
  --type linear_actuator \
  --class-name LinearActuator
```

If pass #2 still hard-codes the `type`/`actuation_mechanism` literals,
hand-edit the generated `models/linear_actuator.py` before `--write`:

- Broaden `type` literal: `linear_slide | linear_stage |
  rodless_screw | rodless_belt | lm_guide_actuator`.
- Drop `actuation_mechanism` (overlaps with `type`) or rename to
  drive-only: `ball_screw | lead_screw | belt | linear_motor`.
- Add `motorless` to `motor_type`.
- Change `ip_rating: int` → `ip_rating: IpRating` (import from
  `.common`).

Then `--write` and let schemagen run its post-write verification pass
against the first source.

## Downstream changes after the model is in

Per `CLAUDE.md` ("Adding a new product type"), six places need updating
or the type silently 400s in prod:

1. `datasheetminer/models/linear_actuator.py` — schemagen writes this.
2. `datasheetminer/models/common.py` — `ProductType` literal; schemagen
   patches this.
3. `app/backend/src/config/productTypes.ts` — add `linear_actuator` to
   `VALID_PRODUCT_TYPES`. Without this, `getCategories()` filters it
   out of the dropdown.
4. `app/backend/src/types/models.ts` — add a `LinearActuator` interface
   plus include it in the `Product` and `ProductType` unions.
5. `app/backend/src/routes/search.ts` — add `linear_actuator` to the
   zod `type` enum. Without this, `/api/v1/search?type=linear_actuator`
   returns 400.
6. `app/frontend/src/types/models.ts` — add to the `ProductType` union.

Smoke test (per `CLAUDE.md` § "Smoke-testing a new type end-to-end"):

```bash
./Quickstart test
(cd app/backend && npx tsc --noEmit)
(cd app/frontend && npx tsc --noEmit)
./Quickstart dev
# in another terminal:
curl -s localhost:3001/api/products/categories | jq '.data[].type'
curl -s "localhost:3001/api/v1/search?type=linear_actuator" | jq '.success'
```

## Re-ingest plan for affected Tolomatic slugs

After the model is registered, two things to do:

1. **Update `cli/ingest_tolomatic.py:SLUG_TO_TYPE`** — change the 12
   slugs above from `("electric_cylinder", ...)` to
   `("linear_actuator", ...)`.

2. **Re-run the affected slugs through the ingest pipeline.** The
   ingest log keys by URL hash, so a re-run on the same URL would be
   skipped by `should_skip` (see `datasheetminer/ingest_log.py:117`).
   Use `--force` to bypass:

   ```bash
   source .env && uv run python cli/ingest_tolomatic.py \
     --filter b3s --force
   # repeat per slug, or batch by family prefix (b3, mxb, mxe, ...)
   ```

   The new ingest will write fresh `linear_actuator` rows. The old
   `electric_cylinder` rows for the same products are still in
   DynamoDB — see cleanup below.

## DB cleanup of misclassified rows

The 12 rodless slugs already wrote rows under `product_type =
electric_cylinder`. After re-ingest, those rows need to be deleted (not
updated — the new ingest creates new PKs because product_type is part
of the key composition; double-check this in
`datasheetminer/db/dynamo.py` before doing anything destructive).

Approach to confirm with a dry-run first:

1. Query DynamoDB for rows where `product_type = electric_cylinder` AND
   `manufacturer = Tolomatic` AND `series` matches one of the rodless
   product names (B3S, B3W, BCS, GSA, MXB-P, MXB-U, MXB-S, MXE-P,
   MXE-S, SLS, TKB, TRS).
2. List them. Sanity-check the count matches expectations (~12-30
   variants depending on how each catalog expanded).
3. Delete via `cli/admin.py` if there's a purge subcommand, otherwise
   one-shot script.

**Don't run this before the new `linear_actuator` rows are in** — the
UI would show an empty actuator category and angry users.

## Open questions

- Should `linear_actuator` and `electric_cylinder` actually be one
  unified `LinearMotion` type with a `form_factor` discriminator, vs
  two sibling types? Two types means six TS allowlist edits each time;
  one type means a chunkier model with optional fields per form factor.
  Two types is what the current architecture is biased toward; flag
  before reversing.
- Do we want to add a non-Tolomatic non-PDF (e.g. an SMC LEFB image
  from directindustry) to balance the image-vs-PDF ratio in the
  schemagen input? Current ratio is 3:3 but all 3 images are
  Tolomatic.
- The single-vendor warning from `CLAUDE.md` was honored (4 vendors:
  Tolomatic, Rexroth, SMC, THK). Festo and Parker were attempted and
  blocked. If the schema still feels Tolomatic-flavored after pass #2,
  we may need to either find a way past Parker's CDN gate or grab a
  SMC LEFB part-sheet PDF (different SMC product line than the LEF
  catalog already used).

## Triggers

Surface this doc when the current task touches any of:

- `datasheetminer/models/common.py` (`ProductType` literal additions)
- `datasheetminer/models/electric_cylinder.py` or any new `linear_actuator.py`
- `cli/schemagen/` or any `./Quickstart schemagen` invocation
- `cli/ingest_tolomatic.py:SLUG_TO_TYPE`
- The 6-step product-type registration in `CLAUDE.md` (frontend types, backend zod enum, etc.)
- Discussion of "actuator", "cylinder", "rodless", "slide", "stage", or routing Tolomatic products
- Once this lands, also unblocks Phase 1d in [edge-case-hardening.md](edge-case-hardening.md).
