# Enhance Intake Triage with Lessons from Rejected PDFs

## Context

Four PDFs in `bad_examples/` and one corrupt file in `triage/` reveal blind spots in the intake triage system (`cli/intake.py`). The current Gemini scan checks for TOC, spec tables, and density ≥ 0.2 — but these checks pass documents that consistently fail downstream extraction. The failures fall into distinct, preventable patterns that the triage tool should catch before spending Gemini extraction tokens.

**Failure patterns discovered:**

| PDF | Pattern | Why triage missed it |
|-----|---------|---------------------|
| RPX32-DataSheet-UK.pdf (162 bytes) | Not a PDF — HTML 301 redirect | No file format validation |
| 23h118s119-m1-portescap (7.6MB) | Multi-category distributor catalog (8 product types mixed) | Triage doesn't check document scope |
| 0900766b813e67a1 (2.6MB) | Valid specs but manufacturer/model unparseable → 0 usable records | Triage doesn't assess identity extractability |
| 8803450814494 / 8815460712478 | Unknown manufacturer, no model numbers → ID generation fails | Manufacturer quality not validated |

## Plan

### Step 1: Create `cli/intake_guards.py` — guard functions module

New file with five pure guard functions. Each takes an `IntakeScanResult` (and optionally raw bytes) and returns a `GuardVerdict`.

```python
class GuardVerdict(BaseModel):
    passed: bool
    guard_name: str
    reason: str | None = None
    severity: Literal["block", "warn"] = "block"
```

**Guard 1: `check_file_integrity(pdf_bytes: bytes) -> GuardVerdict`**
- Validates PDF magic bytes (`%PDF` header) — catches HTML error pages, truncated files, non-PDFs
- Minimum size threshold (e.g., 1024 bytes) — a real datasheet is never <1KB
- Runs BEFORE the Gemini scan to save API cost
- Severity: **block**

**Guard 2: `check_manufacturer_identity(scan: IntakeScanResult) -> GuardVerdict`**
- Rejects when `scan.manufacturer` is None or in `GENERIC_MANUFACTURERS` (reuse from `datasheetminer/spec_rules.py`)
- Severity: **block** — if triage can't identify the manufacturer, extraction won't either

**Guard 3: `check_document_scope(scan: IntakeScanResult) -> GuardVerdict`**
- Uses two new fields on `IntakeScanResult`:
  - `distinct_product_count: int | None` — how many distinct products are described
  - `is_multi_category: bool` — does the document span multiple product types (motors AND gearheads AND drives)
- Blocks multi-category documents (the Portescap catalog pattern)
- Warns (but allows) single-category documents with many variants (Kollmorgen AKM catalog is fine — 100 motors from one family)
- Severity: **block** for multi-category, **warn** for high product count

**Guard 4: `check_extraction_feasibility(scan: IntakeScanResult) -> GuardVerdict`**
- Heuristic score combining: manufacturer present + product_name present + spec_pages non-empty + density > threshold
- If the scan can't even identify a product name, extraction will fail at ID generation
- Severity: **block** when score is critically low

**Guard 5: `check_spec_density_calibrated(scan: IntakeScanResult) -> GuardVerdict`**
- Replaces the flat `MIN_SPEC_DENSITY = 0.2` with per-product-type thresholds:
  - motor: 0.25, drive: 0.25, gearhead: 0.20, robot_arm: 0.20, default: 0.20
- Severity: **block**

**Orchestrator: `run_guards(scan, pdf_bytes) -> list[GuardVerdict]`**
- Runs all guards, collects all verdicts (for logging all issues, not just the first)
- Helper: `any_blocking(verdicts) -> GuardVerdict | None` — returns first blocking failure or None

### Step 2: Extend `IntakeScanResult` in `cli/intake.py`

Add two optional fields (backward-compatible defaults):

```python
distinct_product_count: int | None = Field(None, description="Number of distinct products described")
is_multi_category: bool = Field(False, description="Whether document spans multiple product types")
```

### Step 3: Enhance `_TRIAGE_PROMPT` in `cli/intake.py`

Add to the existing prompt (additive, not a rewrite):

```
- distinct_product_count: how many distinct product models/variants are documented (integer)
- is_multi_category: true if the document covers multiple product types (e.g. motors AND gearheads AND drives in one catalog), false if it covers only one type or variants within one type

Important distinctions:
- A catalog with 50 motor variants is single-category (is_multi_category=false, distinct_product_count=50)
- A distributor brochure covering motors, gearheads, and encoders is multi-category (is_multi_category=true)
- The manufacturer field should be the MANUFACTURER (who makes the product), not the distributor or reseller
```

### Step 4: Wire guards into `intake_single()` in `cli/intake.py`

Minimal changes to the existing flow:

```python
def intake_single(...):
    # ... download pdf_bytes ...

    # NEW: Pre-scan file integrity check (before Gemini call)
    from cli.intake_guards import check_file_integrity, run_guards, any_blocking
    integrity = check_file_integrity(pdf_bytes)
    if not integrity.passed:
        return {"s3_key": triage_key, "status": "rejected", "reason": integrity.reason}

    # ... content hash dedup (existing) ...
    # ... scan_pdf() (existing) ...
    # ... is_valid_datasheet check (existing) ...

    # NEW: Run guards on scan result (replaces the MIN_SPEC_DENSITY check)
    verdicts = run_guards(scan, pdf_bytes)
    blocker = any_blocking(verdicts)
    if blocker:
        log.warning("Guard '%s' blocked %s: %s", blocker.guard_name, triage_key, blocker.reason)
        return {"s3_key": triage_key, "status": "rejected", "reason": blocker.reason,
                "guard": blocker.guard_name, "all_verdicts": [v.model_dump() for v in verdicts]}

    # ... promote_pdf() (existing) ...
```

Remove the standalone `MIN_SPEC_DENSITY` check (lines 319-335) — it's now handled by `check_spec_density_calibrated`.

### Step 5: Create `tests/unit/test_intake_guards.py`

Test each guard in isolation with deterministic fixtures:

- **TestFileIntegrity**: valid PDF bytes, HTML error page, empty bytes, tiny file, truncated PDF
- **TestManufacturerIdentity**: real manufacturer, "Unknown", None, empty, case variants
- **TestDocumentScope**: single-product, single-category multi-product, multi-category catalog
- **TestExtractionFeasibility**: all metadata present, missing product_name, missing everything
- **TestSpecDensityCalibrated**: per-type thresholds, edge cases at boundaries
- **TestRunGuards**: multiple guards, first blocker returned, all verdicts collected
- **TestAnyBlocking**: no blockers (all pass/warn), one blocker, multiple blockers

## Files to create/modify

| File | Action | Scope |
|------|--------|-------|
| `cli/intake_guards.py` | **Create** | Guard functions, GuardVerdict model, orchestrator |
| `tests/unit/test_intake_guards.py` | **Create** | Comprehensive guard tests |
| `cli/intake.py` | **Edit** | Add 2 fields to IntakeScanResult, extend prompt, wire guards into intake_single |

Read-only dependencies (no changes):
- `datasheetminer/spec_rules.py` — provides `GENERIC_MANUFACTURERS`
- `datasheetminer/quality.py` — reference for field lists per product type

## Verification

1. `uv run pytest tests/unit/test_intake_guards.py -v` — all guard tests pass
2. `uv run pytest tests/unit/test_intake.py -v` — existing intake tests still pass (backward compat)
3. Manual smoke test: construct `IntakeScanResult` fixtures matching each bad_example pattern and verify guards reject them:
   - RPX32 (162-byte HTML) → `check_file_integrity` blocks
   - Portescap catalog (multi-category) → `check_document_scope` blocks
   - 0900766b813e67a1 (no manufacturer) → `check_manufacturer_identity` blocks
   - 880345/881546 (Unknown mfr) → `check_manufacturer_identity` blocks
