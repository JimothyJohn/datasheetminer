"""Intake guard functions — validate PDFs before promotion to good_examples/.

Each guard checks one failure pattern discovered from rejected PDFs.
Guards are pure functions with no external dependencies (no S3, DynamoDB,
or API calls), making them fully testable offline.

Guards run after the Gemini triage scan (except file integrity, which runs
before to save API cost). Invalid PDFs are blocked from promotion.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

log = logging.getLogger("dsm-agent.intake.guards")

# Minimum file size for a real datasheet PDF (bytes).
# A single-page PDF with one table is typically >5KB.
_MIN_PDF_SIZE = 1024


# Per-product-type spec density thresholds — calibrated from observed
# extraction outcomes.  Higher for types where sparse datasheets
# consistently produce unusable records.
_DENSITY_THRESHOLDS: dict[str, float] = {
    "motor": 0.25,
    "drive": 0.25,
    "gearhead": 0.20,
    "robot_arm": 0.20,
}
_DEFAULT_DENSITY_THRESHOLD = 0.20


class GuardVerdict(BaseModel):
    """Result of a single guard check."""

    passed: bool
    guard_name: str
    reason: str | None = None
    severity: Literal["block", "warn"] = Field(
        default="block",
        description="'block' prevents promotion; 'warn' logs but allows it",
    )


# ---------------------------------------------------------------------------
# Guard 1 — File integrity (runs BEFORE Gemini scan)
# ---------------------------------------------------------------------------


def check_file_integrity(pdf_bytes: bytes) -> GuardVerdict:
    """Validate that the bytes are actually a PDF of reasonable size.

    Catches HTML error pages, truncated downloads, and empty files.
    """
    name = "file_integrity"

    if not pdf_bytes:
        return GuardVerdict(
            passed=False,
            guard_name=name,
            reason="empty file (0 bytes)",
        )

    if len(pdf_bytes) < _MIN_PDF_SIZE:
        return GuardVerdict(
            passed=False,
            guard_name=name,
            reason=f"file too small ({len(pdf_bytes)} bytes, min {_MIN_PDF_SIZE})",
        )

    # PDF magic bytes: %PDF (first 4 bytes)
    if not pdf_bytes[:4].startswith(b"%PDF"):
        # Sniff for HTML — common when a URL returns a redirect/error page
        head = pdf_bytes[:256].lower()
        if b"<html" in head or b"<!doctype" in head:
            return GuardVerdict(
                passed=False,
                guard_name=name,
                reason="not a PDF — file contains HTML (likely a redirect or error page)",
            )
        return GuardVerdict(
            passed=False,
            guard_name=name,
            reason="not a PDF — missing %PDF magic bytes",
        )

    return GuardVerdict(passed=True, guard_name=name)


# ---------------------------------------------------------------------------
# Guard 2 — Manufacturer identity
# ---------------------------------------------------------------------------


def check_manufacturer_identity(scan: BaseModel) -> GuardVerdict:
    """Reject documents where the manufacturer cannot be identified.

    If the triage scan can't determine who makes the product, the
    extraction pipeline will also fail at ID generation.
    """
    from specodex.spec_rules import GENERIC_MANUFACTURERS

    name = "manufacturer_identity"
    mfr = getattr(scan, "manufacturer", None)
    normalized = (mfr or "").strip().lower()

    if not normalized or normalized in GENERIC_MANUFACTURERS:
        return GuardVerdict(
            passed=False,
            guard_name=name,
            reason=f"manufacturer is '{mfr or 'None'}' — cannot identify product origin",
        )

    return GuardVerdict(passed=True, guard_name=name)


# ---------------------------------------------------------------------------
# Guard 3 — Document scope
# ---------------------------------------------------------------------------


def check_document_scope(scan: BaseModel) -> GuardVerdict:
    """Detect multi-category catalogs that mix unrelated product types.

    Single-category catalogs with many variants (e.g. 100 motor models)
    are fine and only produce a warning.  Multi-category documents
    (motors + gearheads + drives in one PDF) are blocked because the
    extraction pipeline can't handle mixed schemas.
    """
    name = "document_scope"

    is_multi = getattr(scan, "is_multi_category", False)
    if is_multi:
        return GuardVerdict(
            passed=False,
            guard_name=name,
            reason="multi-category catalog — document spans multiple product types",
        )

    return GuardVerdict(passed=True, guard_name=name)


# ---------------------------------------------------------------------------
# Guard 4 — Extraction feasibility
# ---------------------------------------------------------------------------


def check_extraction_feasibility(scan: BaseModel) -> GuardVerdict:
    """Predict whether extraction will produce identifiable products.

    A document needs at minimum: a recognizable manufacturer and either
    a product name or spec pages to have any chance of producing usable
    records.  Score each signal and block if too few are present.
    """
    name = "extraction_feasibility"

    signals = 0
    total = 4

    mfr = getattr(scan, "manufacturer", None)
    if mfr and mfr.strip():
        signals += 1

    product_name = getattr(scan, "product_name", None)
    if product_name and product_name.strip():
        signals += 1

    spec_pages = getattr(scan, "spec_pages", None)
    if spec_pages and len(spec_pages) > 0:
        signals += 1

    density = getattr(scan, "spec_density", None) or 0.0
    if density >= 0.2:
        signals += 1

    # Need at least 2 of 4 signals to proceed
    if signals < 2:
        return GuardVerdict(
            passed=False,
            guard_name=name,
            reason=(
                f"extraction unlikely to succeed — only {signals}/{total} "
                f"identity signals present (manufacturer={mfr!r}, "
                f"product_name={product_name!r}, "
                f"spec_pages={bool(spec_pages)}, density={density:.2f})"
            ),
        )

    return GuardVerdict(passed=True, guard_name=name)


# ---------------------------------------------------------------------------
# Guard 5 — Calibrated spec density
# ---------------------------------------------------------------------------


def check_spec_density_calibrated(scan: BaseModel) -> GuardVerdict:
    """Apply per-product-type density thresholds.

    Replaces the flat MIN_SPEC_DENSITY = 0.2 with calibrated thresholds
    based on observed extraction outcomes per product type.
    """
    name = "spec_density_calibrated"

    density = getattr(scan, "spec_density", None) or 0.0
    product_type = getattr(scan, "product_type", None) or ""
    threshold = _DENSITY_THRESHOLDS.get(product_type, _DEFAULT_DENSITY_THRESHOLD)

    if density < threshold:
        return GuardVerdict(
            passed=False,
            guard_name=name,
            reason=(
                f"spec density {density:.2f} below threshold {threshold:.2f} "
                f"for product type '{product_type}'"
            ),
        )

    return GuardVerdict(passed=True, guard_name=name)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_guards(
    scan: BaseModel,
    pdf_bytes: bytes | None = None,
) -> list[GuardVerdict]:
    """Run all post-scan guards and collect verdicts.

    Note: check_file_integrity should be called separately BEFORE the
    Gemini scan.  This function runs the remaining guards that depend
    on scan results.
    """
    verdicts: list[GuardVerdict] = []

    for guard_fn in (
        check_manufacturer_identity,
        check_document_scope,
        check_extraction_feasibility,
        check_spec_density_calibrated,
    ):
        verdict = guard_fn(scan)
        verdicts.append(verdict)
        if not verdict.passed:
            log.warning(
                "Guard '%s' %s: %s",
                verdict.guard_name,
                verdict.severity.upper(),
                verdict.reason,
            )

    return verdicts


def any_blocking(verdicts: list[GuardVerdict]) -> GuardVerdict | None:
    """Return the first blocking verdict, or None if all passed/warned."""
    for v in verdicts:
        if not v.passed and v.severity == "block":
            return v
    return None
