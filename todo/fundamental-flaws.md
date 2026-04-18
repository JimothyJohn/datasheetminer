# Fundamental Flaws Plan

Three issues flagged during edge-case hardening (2026-04-17) that are bigger
than a one-line fix. Ordered by blast radius: the regex issue can silently
corrupt stored reads, the N/A-quality issue pollutes the public dataset,
and the `test_protections.py` failures mean the intake guard rollout broke a
test harness that nobody's come back to clean up.

---

## 1. `_parse_compact_units` greedy-unit bug

### Flaw

The regex in `datasheetminer/db/dynamo.py:92`:

```python
re.match(r"^(-?[\d.]+)(?:-(-?[\d.]+))?;(.*)$", obj)
```

The final `(.*)` captures the unit greedily. Input `"1;2;3;V"` parses as
`{value: 1, unit: "2;3;V"}` instead of falling through to the string-passthrough
branch. We documented this in `tests/unit/test_compact_units_regex.py`.

### Why it's fundamental

- The regex is the **only** deserializer between DynamoDB strings and typed
  values. Every product read goes through it.
- A tighten-up (require exactly one `;`) may change the shape of already-stored
  values. For instance, if a stored unit is genuinely `"m/s"` (one semicolon)
  the tight regex still works — but if anything in prod accidentally wrote
  `"1;2;V"` we'd start returning the raw string instead of the dict.
- We don't know what's in prod without scanning.

### Plan

**Step 1 — Audit what's stored.** One-shot script at `cli/admin/audit_units.py`
that does a full table scan, runs every string field through `_parse_compact_units`,
and logs the ones where the unit portion contains a `;`. Read-only, no writes.

    ./Quickstart admin audit-units --stage prod -o outputs/audit/units-<ts>.jsonl

Success criterion: output is empty. If non-empty, the rows listed are either
real data that needs a one-off cleanup, or bugs in the writer path that need
upstream fixes before we tighten the reader.

**Step 2 — Decide migration.** Two paths:

  - **(a) No dirty rows found.** Tighten the regex in one PR. Add a strict
    mode to `_parse_compact_units` and flip the default. Test file already
    has the quirk documented — flip that assertion to the new behavior.
  - **(b) Dirty rows exist.** Write `cli/admin/repair_units.py` that reads
    each dirty row, re-derives the intended value + unit from context
    (usually the original LLM extraction is still in `outputs/`), and
    PutItems the corrected record. Only then tighten the regex.

**Step 3 — Tighten.** Change the regex to `r"^(-?[\d.]+)(?:-(-?[\d.]+))?;([^;]*)$"`.
Unit cannot contain a semicolon. Update the test expectations. Deploy.

**Step 4 — Add a writer-side invariant.** Add a Pydantic `AfterValidator` to
`ValueUnit` / `MinMaxUnit` in `datasheetminer/models/common.py` that rejects
the canonical `"value;unit"` string if unit contains `;`. Writer and reader
now agree; regressions surface at validation time, not at read time.

### Cost

~half day if audit is clean, ~1-2 days if there's a repair pass. Zero infra
changes; pure Python + one scan.

### Open question

Does `m/s` ever collide with any unit variant we emit? Scan `datasheetminer/units.py`
— no canonical unit contains `;`, so we're safe. But `_ALIAS_MAP` is user-extensible
via new product types; add an assertion in the unit-registration path.

---

## 2. `part_number = "N/A"` counts as a filled field

### Flaw

`datasheetminer/quality.py::_META_FIELDS` excludes `product_id`, `product_name`,
`manufacturer`, `PK`, `SK`, datasheet metadata, and MSRP bookkeeping — but
NOT `part_number`. So a record with `part_number="N/A"` scores as one filled
field against the quality threshold. Documented in
`tests/unit/test_quality_boundary.py::TestPlaceholderPartNumbers`.

### Why it's fundamental

- `part_number` is the primary human-facing identifier across the UI. A
  table row with `"N/A"` in the part-number column is worse than no row.
- The **existing `todo/NA-filter.md`** says "many part numbers in the current
  products table have significant amount of N/A" and asks for "as much
  hardening and simplifying as necessary to make this seamless." This flaw
  is the single root cause.
- Changing quality semantics retroactively rejects records that are already
  in prod. We need a migration story, not just a code change.

### Plan

Two fixes, paired:

**Step 1 — Define placeholder semantics.** Add a module
`datasheetminer/placeholders.py`:

```python
PLACEHOLDER_STRINGS = frozenset({
    "", "N/A", "n/a", "NA", "TBD", "tbd", "-", "--",
    "None", "none", "null", "NULL", "?", "TBA",
})

def is_placeholder(value: object) -> bool:
    """True if `value` is None or a known placeholder string."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() in PLACEHOLDER_STRINGS:
        return True
    return False
```

Single source of truth. Every "is this field meaningfully populated?"
check routes through this.

**Step 2 — Upgrade `quality.py`.** `score_product` currently does
`if value is None`. Change to `if is_placeholder(value)`. Add a model-level
validator to `ProductBase.part_number` that stores `None` (not `"N/A"`) for
placeholder input. Writer + scorer agree.

**Step 3 — Upstream: fix the LLM prompt.** The reason `"N/A"` keeps showing
up is that Gemini emits it when it can't find a part number. Update the prompt
in `datasheetminer/llm.py` to explicitly say "omit the field or use null —
never write the literal string N/A." Add an integration test using a cached
response fixture with and without N/A to verify the fix.

**Step 4 — Backfill existing data.** `cli/admin/purge_na.py`:

- Full table scan in each product_type partition.
- For each record, re-score with the new `is_placeholder` rule.
- Records that now drop below the threshold are **archived** (moved to a
  `PURGED#` PK partition) not deleted — so we can recover if the threshold
  was wrong.
- Log the count by manufacturer so we can see which source catalogs are
  the biggest offenders.

    ./Quickstart admin purge-na --stage dev --dry-run   # report only
    ./Quickstart admin purge-na --stage dev --archive   # move below-threshold to PURGED#

**Step 5 — Frontend: treat placeholders as missing.** `app/frontend/src/utils/formatting.ts`
currently renders `part_number || '—'`. If the backend ever slips and returns
`"N/A"`, the UI shows `"N/A"`. Add a defensive `isPlaceholder` in
`app/frontend/src/utils/sanitize.ts` (where `sanitizeUrl` lives) and use it
everywhere the frontend renders a potentially-placeholder value.

### Cost

~2-3 days end-to-end. The backfill is the slow part — it's a full table scan
and a lot of writes, probably rate-limit throttled.

### Interaction with other work

- Unblocks `todo/NA-filter.md` entirely (same root cause).
- Ties into `todo/usage-driven-schema-evolution.md` — the usage-signal work
  should weight fields by `is_placeholder`-adjusted fill rate, not raw None.
- Changes benchmark results: existing `tests/benchmark/expected/*.json` may
  contain `"N/A"` strings that will now fail precision/recall. Refresh.

---

## 3. `test_protections.py` failures from intake-guards rollout

### Flaw

8 tests in `tests/unit/test_protections.py` and `tests/unit/test_agent_cli.py`
fail on `master`, confirmed pre-existing (stash-verified):

- `TestContentHashDedup::test_duplicate_hash_skips_without_scanning`
- `TestContentHashDedup::test_new_hash_proceeds_to_scan`
- `TestContentHashDedup::test_content_hash_stored_on_datasheet`
- `TestSpecDensity::test_low_density_rejected`
- `TestSpecDensity::test_high_density_approved`
- `TestSpecDensity::test_density_at_threshold_passes`
- `TestBuildMetadata::test_basic`
- `TestBuildMetadata::test_no_pages`

The spec-density tests all fail with:

    assert 'spec density too low' in 'file too small (17 bytes, min 1024)'

The intake-guards rollout (`cli/intake_guards.py`) added `check_file_integrity`
which rejects bytes < 1024 bytes BEFORE the spec-density check runs. The tests
pass `b"fake pdf bytes"` — 14 bytes — so the new integrity guard fires first
and the test's density-rejection message never surfaces.

### Why it's fundamental (small F)

- Not a product bug per se. But a broken test suite is a signal we're ignoring,
  and broken signals erode trust.
- Every new PR has to mentally diff "8 existing failures + mine" against
  "my new failures" — slow, error-prone.
- The guard rollout was a meaningful behavior change and the test-update PR
  was forgotten. This is the kind of debt that compounds.

### Plan

**Step 1 — Fix the test fixtures.** The guards are correct; the tests are
stale. Replace `b"fake pdf bytes"` with a fixture of ≥ 1024 bytes that starts
with `%PDF-`. Add a shared helper in `tests/conftest.py`:

```python
@pytest.fixture
def minimal_pdf_bytes() -> bytes:
    """Synthetic PDF-header-prefixed bytes that pass check_file_integrity."""
    return b"%PDF-1.4\n" + b"x" * 1200
```

Every `TestContentHashDedup` + `TestSpecDensity` test switches to this fixture.

**Step 2 — Fix `TestBuildMetadata`.** Failure is different (botocore-related,
probably a mock drift). Read the actual error, patch the mock.

**Step 3 — Run the full suite.** `uv run pytest tests/unit -x`. Everything
green.

**Step 4 — Prevent recurrence.** Add a CI check that fails if the overall
Python test count drops from the previous commit. `./Quickstart test --strict`
mode that exits non-zero on any failure regardless of pre-existing state.
Remove the mental model of "known-failing tests"; either they pass or they're
deleted with a reason.

### Cost

~1-2 hours. These are shallow fixture updates, not real bugs.

---

## Order + staging

1. **Fix #3 first.** Cheapest, clears the test-suite signal so #1 and #2 have
   a clean baseline to verify against.
2. **Fix #2 next.** Biggest user-visible win (fixes NA-filter which has been
   sitting in `todo/` for a month). Backfill runs during #1 lull.
3. **Fix #1 last.** Needs a prod scan first; don't touch the regex until the
   audit is clean.

Everything above can ship without new infrastructure. No new dependencies.
Each PR is independently revertable — no cross-coupling.

## Non-goals

- No switch from DynamoDB to Postgres/etc. to "properly" type the value/unit
  column. That's a quarter of work for a problem solved by a one-line regex
  tighten-up plus a writer-side invariant.
- No reworking of the Pydantic model hierarchy. `ProductBase` stays as-is.
- No frontend changes beyond the defensive placeholder check in #2 Step 5.
