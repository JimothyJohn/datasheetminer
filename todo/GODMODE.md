# GOD mode dashboard — data-quality observatory

A single page that answers **"how clean is the catalog right now and where
should I spend the next ingester improvement?"** Read-only on the database,
zero new infrastructure, designed to drive a tight feedback loop:

> dashboard surfaces an oddity → adjust prompt / page_finder / model /
> validators → re-ingest → dashboard shows the fix

Everything else (Gemini cost monitoring, Claude usage, deploy state,
CloudWatch errors, repo activity) belongs in other docs or skips the
dashboard entirely. **Scope is data quality, full stop.**

## Goal

One report — `./Quickstart godmode` writes `outputs/godmode/<ts>.html` and
updates `latest.html` — that surfaces, at a glance:

1. **Coverage matrix.** For each `(product_type, field)`: % of products
   where the value is non-null and non-placeholder. Heat-map the gaps.
2. **String oddities.** Across every string field on every product, count
   patterns that almost certainly indicate misextraction:
   - contains `;` (compact-string leak — should be 0 post-UNITS migration)
   - literal `null` / `unknown` / `N/A` / `-` / `TBD` as the value
   - leading/trailing whitespace
   - non-ASCII outside the expected unit symbols (`°`, `±`, `Ω`, `μ`, `²`)
   - mixed encodings on the same field across products
3. **Per-field distributions.** Numeric fields → histogram (10 buckets,
   p5/p50/p95 marked). Categorical fields → top-20 with counts. Spotting:
   - numeric fields stuck at one value across many products (LLM
     memorising a column header)
   - categorical fields with hundreds of singletons (parsing each row's
     freeform text instead of canonicalising)
4. **Cluster commonalities.** For each `(manufacturer, product_type)`
   bucket of size ≥ 3: which fields hold the same value across **every**
   product in the bucket? Often a vendor-template artefact — the LLM
   extracted the catalog header instead of the per-row value.
5. **Range outliers.** Per `ValueUnit` family (voltage/current/torque/...),
   products whose value sits > 3σ from the family median. Often
   misextractions: a "5000V" servo is a typo for "500V", a "0.1mm" robot
   reach is a unit confusion.
6. **Unit-family mismatches.** How often does a `Torque` field carry a
   non-torque unit? `UNITS` rejected such rows to `None` post-migration —
   this surfaces the rejected-prone manufacturers + fields so you can
   tighten the schema hint or the prompt example.
7. **Per-manufacturer failure modes.** Top-N most-failing fields per
   manufacturer, with up to 3 sample raw-string values per failure. The
   sample values are the input to the next prompt-engineering pass.
8. **Quality-score distribution.** Histogram of `specodex.quality.score()`
   across the catalog, broken down by `(product_type, manufacturer)`. The
   bottom decile is where ingester improvements move the most product.
9. **Drift signal.** Diff against the previous snapshot in
   `outputs/godmode/`: which fields' null-rate jumped, which manufacturers
   started failing, which `string oddities` patterns appeared since last
   run. The simplest "what broke this week?" answer.

Stupid simple on purpose: read DynamoDB once, compute everything in Python,
emit a self-contained HTML report. No new agents, no metrics pipeline, no
backend route, no auth surface.

## Non-goals (explicit cut from the prior version of this doc)

- **No Gemini token / cost panel.** Cost tracking belongs in
  `cli/bench.py:PRICING` + a future `todo/COST.md`.
- **No Claude usage panel.** Claude Code transcript parsing is a developer
  tool, not a data quality signal.
- **No repo activity panel.** Commits / LOC / churn — `git log` already
  answers those without a dashboard.
- **No deploy state panel.** That's the `/cicd` skill's territory;
  smoke tests already verify deploys.
- **No CloudWatch error panel.** `aws logs tail --follow` is the right
  tool, not a panel.
- **No backlog state panel.** `todo/README.md` is the index of record.
- **No real-time push.** This is offline analysis — re-run the CLI
  whenever you want a fresh view.
- **No frontend integration.** Pure CLI report → HTML file. No
  `/godmode` route, no admin auth, no React component. If we ever want
  in-app access, the report is a static HTML file the existing CDN can
  serve.
- **No anomaly ML.** Threshold-based callouts only. Outliers are 3σ from
  family median; oddities are pattern matches; cluster commonalities are
  exact-equal across a bucket. All explainable in one sentence.

## Architecture

One Python module, three layers:

    cli/godmode.py
      ├─ scan(stage)                       # one DynamoDB Scan per stage,
      │                                    # cap at SCAN_LIMIT, paginated
      ├─ analyse(rows) -> Snapshot         # all of #1-8 above
      ├─ diff(snapshot, prev) -> Drift     # #9
      └─ render(snapshot, drift) -> html   # self-contained HTML

Output:

    outputs/godmode/
      ├─ <ts>.json                # machine-readable snapshot (so diff works)
      ├─ <ts>.html                # the report
      └─ latest.html              # symlink / copy of newest

`./Quickstart godmode --stage dev` runs against dev (read-only), defaults
to dev. `--stage prod` is allowed but cautioned — the scan is read-only
but costs DynamoDB read units; sample with `--limit 5000` first.

## Data model

The dashboard only knows about ProductBase rows (`PK = "PRODUCT#*"`). For
each row, walk every field declared on the Pydantic model class for that
`product_type`. Decide per field:

| Field type | Coverage check | Oddities to flag | Distribution |
|---|---|---|---|
| `Optional[str]` | non-null, non-placeholder string | `;`, `null`/`unknown`/`-`/`TBD`/`N/A`, leading/trailing whitespace, mixed encoding | top-20 categorical |
| `Optional[ValueUnit]` | not null | unit not in family's accepted set | numeric histogram of `value`, top-N of `unit` |
| `Optional[MinMaxUnit]` | not null AND has at least one of min/max | min > max, unit not in family | histograms of min and max separately |
| `Optional[List[X]]` | non-empty list | empty-string elements, duplicate elements | length distribution |
| `Optional[int]` (e.g. `IpRating`) | not null, in expected range (e.g. IP00–IP69) | values outside the rating-spec range | top-20 |
| nested `BaseModel` | recurse into its fields | recurse | recurse |

Placeholder values come from `specodex.quality:is_placeholder` — keep that
function as the single source of truth and have the dashboard call it.

## What "good" looks like (acceptance signals)

The dashboard is doing its job when these statements are answerable from a
single page in <30 s:

- "Which manufacturer has the worst coverage on `rated_torque` right now?"
- "How many products still hold a string with `;` somewhere?" (post-UNITS,
  the answer must be 0)
- "Which `(manufacturer, type)` pairs have an inertia value identical
  across the whole bucket?" (signals the LLM grabbed a header)
- "Did anything regress since last week's snapshot?"
- "Where should I aim the next prompt tweak?" (= bottom decile of quality
  score, top-N failing fields, sample values to feed back)

If the answer requires opening a separate tool, the dashboard isn't doing
the job and the relevant section needs more.

## MVP slice — ship this first

Order is by signal-per-effort: each step's output is useful before the
next one lands.

1. **`scan(stage)` + JSON snapshot.** Just dump rows to JSON-with-counts.
   No HTML yet. Lets us start collecting daily snapshots for the diff.
   *(45 min)*

2. **Coverage matrix + string oddities.** The two highest-leverage
   panels. HTML is a single `<table>` for coverage and a flat list of
   `(field, pattern, count, sample_values[])` for oddities. *(2 h)*

3. **Per-field distributions.** Numeric histograms via plain HTML+CSS
   bars (no chart library). Categorical top-20 as `<ol>`. *(2 h)*

4. **Cluster commonalities + range outliers.** Both are O(n) post-scan.
   Render as collapsible `<details>` blocks. *(1.5 h)*

5. **Unit-family mismatches + per-manufacturer failure modes.** Reuse
   the existing `UnitFamily.contains` + `is_placeholder`. The sample-
   values list is what makes this actionable. *(1.5 h)*

6. **Quality-score distribution + drift.** Quality score reuses
   `specodex.quality:score`. Drift requires a prior `<ts>.json` to diff
   against — first run shows nothing in this panel, that's fine. *(1 h)*

About a day for the full thing. No MVP-vs-followup split — every panel
above is core to the data-quality remit.

## Files touched

| File | Change |
|---|---|
| `cli/godmode.py` | **new** — scan, analyse, diff, render |
| `cli/quickstart.py` | add `godmode` subcommand dispatching to `cli/godmode.py` |
| `Quickstart` | one-line passthrough (already a shim) |
| `outputs/godmode/` | **new directory** — gitignore the whole thing |
| `tests/unit/test_godmode.py` | **new** — analyse() against fixture rows; pure logic, fast |
| `CLAUDE.md` | add `./Quickstart godmode` to the entry-point list with one-liner |
| `.gitignore` | add `outputs/godmode/` |

No backend/frontend changes. No Lambda. No new deps beyond what `cli/`
already imports (`boto3`, stdlib).

## Estimated effort

- `scan` + JSON snapshot: 45 min
- Coverage matrix + string oddities: 2 h
- Per-field distributions: 2 h
- Cluster commonalities + range outliers: 1.5 h
- Unit-family mismatches + per-manufacturer failure modes: 1.5 h
- Quality-score distribution + drift: 1 h
- HTML/CSS polish (mil-spec aesthetic, monospace, hairline tables, no
  chart libs): 1 h
- Tests against fixture data: 1 h

About **a day and a half** for the whole report. Each panel is
independently shippable.

## Open questions

1. **Snapshot retention.** Daily `<ts>.json` accumulates ~50 KB/day at
   current scale (3k rows × ~15 fields summary). Keep the last 90? 365?
   All? Recommend 90, prune older with a tiny script.
2. **Prod scan cost.** Worst case at 50k rows: one full Scan = ~$0.05
   per refresh. Acceptable for an on-demand tool. If we ever auto-run
   it, gate on `--stage prod` requiring `--confirm`.
3. **Frontend access.** Skip for now (per non-goals), but: the static
   HTML could be served at `/godmode/latest.html` from the existing
   CloudFront distribution if we ever want a teammate to look. Trivial
   to add later — don't pre-build for it.
4. **Drift threshold.** Below what delta does a field's null-rate jump
   count as "regression"? Recommend +5pp absolute or +50% relative,
   whichever is larger. Tweak after we see real drift signal.

## Triggers

Surface this doc when the current task touches any of:

- `specodex/quality.py` (`is_placeholder`, `score`) — the dashboard is a
  consumer; signature changes ripple
- `specodex/models/common.py` (`ValueUnit`, `MinMaxUnit`, `UnitFamily`,
  field-marker dataclasses) — the dashboard introspects these
- `specodex/models/{motor,drive,gearhead,robot_arm,electric_cylinder,contactor,linear_actuator}.py`
  — adding fields means the coverage matrix gets a new column
- `cli/ingest_report.py` — overlapping concern (manufacturer-grouped
  fail counts); decide whether to merge or keep separate
- `outputs/godmode/`
- User mentions "data quality", "what's wrong with the catalog", "why
  is `<field>` empty", "the LLM is hallucinating", "ingester drift",
  "manufacturer outreach prioritisation"
- Adding a new product type — the coverage matrix gets a new row, the
  test fixture should add one example
