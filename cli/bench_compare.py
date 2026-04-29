"""Compare two ./Quickstart bench JSON reports for precision/recall regressions.

Used by .github/workflows/bench.yml to gate on quality drift between weekly
runs. Stand-alone CLI so the logic is testable and the workflow YAML stays
thin.

Usage:
    uv run python -m cli.bench_compare <baseline.json> <candidate.json>
        [--max-drop 5.0] [--summary-md PATH]

Exits 1 (with a tabular dump on stderr) when any fixture's precision or
recall drops by more than --max-drop percentage points relative to the
baseline. New fixtures present only in candidate are reported but don't
fail. Fixtures present only in baseline (i.e. dropped fixtures) report a
warning, also non-fatal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, dict[str, float]]:
    """Read a bench report and return {slug -> {precision, recall}}."""
    raw = json.loads(path.read_text())
    out: dict[str, dict[str, float]] = {}
    for fix in raw.get("fixtures", []):
        slug = fix.get("slug")
        if not slug:
            continue
        quality = fix.get("quality") or {}
        out[slug] = {
            "precision": float(quality.get("precision") or 0.0),
            "recall": float(quality.get("recall") or 0.0),
            "status": str(quality.get("status") or "unknown"),
        }
    return out


def _format_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _diff_pp(new: float, old: float) -> float:
    """Difference in percentage points (new - old, both fractions in [0, 1])."""
    return (new - old) * 100.0


def compare(
    baseline: dict[str, dict[str, float]],
    candidate: dict[str, dict[str, float]],
    max_drop_pp: float,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Return (regressions, new_fixtures, dropped_fixtures).

    regressions: list of dicts with {slug, metric, baseline, candidate, drop_pp}.
    """
    regressions: list[dict[str, Any]] = []
    new_fixtures: list[str] = []
    dropped_fixtures: list[str] = []

    for slug in sorted(set(baseline) | set(candidate)):
        if slug not in baseline:
            new_fixtures.append(slug)
            continue
        if slug not in candidate:
            dropped_fixtures.append(slug)
            continue
        b = baseline[slug]
        c = candidate[slug]
        for metric in ("precision", "recall"):
            drop_pp = _diff_pp(c[metric], b[metric])
            if drop_pp < -max_drop_pp:
                regressions.append(
                    {
                        "slug": slug,
                        "metric": metric,
                        "baseline": b[metric],
                        "candidate": c[metric],
                        "drop_pp": drop_pp,
                    }
                )
    return regressions, new_fixtures, dropped_fixtures


def _markdown_summary(
    baseline: dict[str, dict[str, float]],
    candidate: dict[str, dict[str, float]],
    regressions: list[dict[str, Any]],
    new_fixtures: list[str],
    dropped_fixtures: list[str],
    max_drop_pp: float,
) -> str:
    lines = ["## Bench precision/recall delta", ""]
    if regressions:
        lines.append(f"❌ {len(regressions)} regression(s) > {max_drop_pp}pp")
    else:
        lines.append(f"✅ no regressions > {max_drop_pp}pp")
    lines.extend(
        [
            "",
            "| Fixture | Metric | Baseline | Candidate | Δpp |",
            "|---|---|---|---|---|",
        ]
    )
    for slug in sorted(set(baseline) | set(candidate)):
        if slug in baseline and slug in candidate:
            for metric in ("precision", "recall"):
                b = baseline[slug][metric]
                c = candidate[slug][metric]
                delta = _diff_pp(c, b)
                marker = "❌" if delta < -max_drop_pp else ("⚠" if delta < 0 else "")
                lines.append(
                    f"| `{slug}` | {metric} | {_format_pct(b)} | {_format_pct(c)} | "
                    f"{marker} {delta:+.1f} |"
                )
    if new_fixtures:
        lines.extend(
            ["", f"**New fixtures (not in baseline):** {', '.join(new_fixtures)}"]
        )
    if dropped_fixtures:
        lines.extend(
            [
                "",
                f"**Dropped fixtures (only in baseline):** {', '.join(dropped_fixtures)}",
            ]
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench_compare", description=__doc__)
    parser.add_argument(
        "baseline", type=Path, help="Older bench JSON to compare against"
    )
    parser.add_argument("candidate", type=Path, help="Newer bench JSON")
    parser.add_argument(
        "--max-drop",
        type=float,
        default=5.0,
        help="Fail if any fixture drops more than N percentage points (default: 5.0)",
    )
    parser.add_argument(
        "--summary-md",
        type=Path,
        default=None,
        help="Write a markdown summary table here (e.g. $GITHUB_STEP_SUMMARY)",
    )
    args = parser.parse_args(argv)

    if not args.baseline.exists():
        print(f"baseline not found: {args.baseline}", file=sys.stderr)
        return 2
    if not args.candidate.exists():
        print(f"candidate not found: {args.candidate}", file=sys.stderr)
        return 2

    baseline = _load(args.baseline)
    candidate = _load(args.candidate)
    regressions, new_fixtures, dropped_fixtures = compare(
        baseline, candidate, max_drop_pp=args.max_drop
    )

    if args.summary_md:
        summary = _markdown_summary(
            baseline,
            candidate,
            regressions,
            new_fixtures,
            dropped_fixtures,
            args.max_drop,
        )
        # Append, not overwrite — GITHUB_STEP_SUMMARY accumulates.
        with args.summary_md.open("a") as f:
            f.write(summary)

    if regressions:
        print(f"REGRESSIONS ({len(regressions)} > {args.max_drop}pp):", file=sys.stderr)
        for r in regressions:
            print(
                f"  {r['slug']}/{r['metric']}: "
                f"{_format_pct(r['baseline'])} → {_format_pct(r['candidate'])} "
                f"({r['drop_pp']:+.1f}pp)",
                file=sys.stderr,
            )
        return 1

    if new_fixtures:
        print(
            f"new fixtures (not in baseline): {', '.join(new_fixtures)}",
            file=sys.stderr,
        )
    if dropped_fixtures:
        print(
            f"dropped fixtures (only in baseline): {', '.join(dropped_fixtures)}",
            file=sys.stderr,
        )
    print(f"OK: no precision/recall regressions > {args.max_drop}pp", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
