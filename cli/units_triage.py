"""UNITS migration review triage.

Parses ``outputs/units_migration_review_<stage>_<ts>.md`` (the artifact
``cli.migrate_units_to_dict`` emits for unparseable strings) and groups the
findings by recognizable pattern: ``±``-prefixed deltas, trailing ``;null``,
trailing ``;unknown``, IP-rating with a wrong unit suffix, etc. Emits a
triage markdown that lets the operator scan a few hundred raw strings as a
dozen pattern groups instead of row-by-row.

Read-only — no DB touch, no edits to the source review file.

Usage:
    uv run python -m cli.units_triage outputs/units_migration_review_dev_*.md
    uv run python -m cli.units_triage <file> --output outputs/units_triage.md
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "outputs"

log = logging.getLogger("units_triage")


# ── Pattern matchers ───────────────────────────────────────────────────
#
# Each matcher returns a triage *category* string when the raw cell text
# matches. Categories are processed in order — the first match wins, so
# put more specific patterns above more general ones.

# `±` prefix with `;<unit>` suffix — usually a legitimate symmetric tolerance.
# Auto-rescue candidate: drop the `±` and store as a MinMaxUnit.
RE_PLUSMINUS = re.compile(r"^±")

# Trailing `;null` — extractor recorded the value but couldn't infer a unit.
# Often the unit is in the parent column header; needs human eyeball.
RE_TRAILING_NULL = re.compile(r";null\b")

# Trailing `;unknown` — same as `;null` but the extractor marked it
# explicitly. Usually a sign the LLM gave up on the cell.
RE_TRAILING_UNKNOWN = re.compile(r";unknown\b")

# IP-rating with a unit appended — e.g. ``IP65;mm`` (unit should be empty).
RE_IP_RATING_WRONG_UNIT = re.compile(r"^IP\d+;(?!null$|unknown$).+", re.IGNORECASE)

# Range with em-dash or en-dash — e.g. ``-90–135°;null``.
RE_RANGE_WITH_DASH = re.compile(r"\d+\s*[-–—]\s*\d+")

# Comma-separated list of values — e.g. ``5,10,15;Nm``. Often a categorical
# spec rather than a single value.
RE_COMMA_SEPARATED = re.compile(r"\d+,\d+(?:,\d+)*\s*[;]")

# Tilde-prefixed approximate value — ``~10;Nm``.
RE_APPROXIMATE = re.compile(r"^~")

# Fraction form — ``1/2;in``.
RE_FRACTION = re.compile(r"^\d+\s*/\s*\d+\s*[;]")

# Empty unit (semicolon followed by end of cell).
RE_EMPTY_UNIT = re.compile(r";\s*$")


PATTERN_MATCHERS: tuple[tuple[str, re.Pattern, str], ...] = (
    ("plusminus_tolerance", RE_PLUSMINUS, "Auto-rescue: ± prefix → MinMaxUnit"),
    (
        "ip_rating_wrong_unit",
        RE_IP_RATING_WRONG_UNIT,
        "Fix unit: IP rating with non-IP unit suffix",
    ),
    (
        "trailing_null_unit",
        RE_TRAILING_NULL,
        "Manual: unit dropped to null — recover from parent column header",
    ),
    (
        "trailing_unknown_unit",
        RE_TRAILING_UNKNOWN,
        "Manual: extractor explicitly gave up on the unit",
    ),
    ("range_with_dash", RE_RANGE_WITH_DASH, "Auto-rescue: range form → MinMaxUnit"),
    (
        "comma_separated_values",
        RE_COMMA_SEPARATED,
        "Manual: categorical / list value, not a single number",
    ),
    ("approximate", RE_APPROXIMATE, "Auto-rescue: ~ prefix → ValueUnit (drop ~)"),
    ("fraction", RE_FRACTION, "Manual: fraction form, decide whether to coerce"),
    ("empty_unit", RE_EMPTY_UNIT, "Manual: blank unit suffix"),
    ("other", re.compile(r"."), "Uncategorized — eyeball directly"),
)


# ── Parsing ────────────────────────────────────────────────────────────


@dataclass
class Row:
    pk: str
    sk: str
    product_name: str | None
    manufacturer: str | None
    field_path: str
    raw: str


@dataclass
class Group:
    category: str
    description: str
    rows: list[Row] = field(default_factory=list)


# Section header: `## `PRODUCT#FOO` / `PRODUCT#bar``
RE_SECTION = re.compile(r"^## `([^`]+)` / `([^`]+)`")
# Bullet metadata line: `- **product_name:** Foo` or `- **manufacturer:** Bar`
RE_META = re.compile(r"^-\s+\*\*([a-z_]+):\*\*\s*(.+)$")
# Table row: `| `field_path` | `raw_value` |` — strip backticks.
RE_TABLE_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|")


def parse_review(text: str) -> list[Row]:
    """Walk the markdown line-by-line, extracting (PK, SK, field, raw) tuples.

    Robust to the small variations between the dev and prod review formats
    — both use the same section header + bullet meta + table-row layout
    that ``cli/migrate_units_to_dict.py`` emits.
    """
    rows: list[Row] = []
    pk: str | None = None
    sk: str | None = None
    product_name: str | None = None
    manufacturer: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        m_section = RE_SECTION.match(line)
        if m_section:
            pk, sk = m_section.group(1), m_section.group(2)
            product_name = manufacturer = None
            continue
        m_meta = RE_META.match(line)
        if m_meta:
            key, value = m_meta.group(1), m_meta.group(2).strip()
            if key == "product_name":
                product_name = value
            elif key == "manufacturer":
                manufacturer = value
            continue
        m_row = RE_TABLE_ROW.match(line)
        if m_row and pk and sk:
            field_path, raw = m_row.group(1), m_row.group(2)
            # The header row of each table has `Field path` / `Raw string`
            # — exclude it (it doesn't have backticks around the cells).
            rows.append(
                Row(
                    pk=pk,
                    sk=sk,
                    product_name=product_name,
                    manufacturer=manufacturer,
                    field_path=field_path,
                    raw=raw,
                )
            )
    return rows


# ── Classification ─────────────────────────────────────────────────────


def classify(raw: str) -> tuple[str, str]:
    """Return (category, description) for a raw cell value.

    First matcher wins — patterns are ordered by specificity in
    ``PATTERN_MATCHERS``.
    """
    for category, pattern, description in PATTERN_MATCHERS:
        if pattern.search(raw):
            return category, description
    return "other", "Uncategorized — eyeball directly"


def group_by_pattern(rows: list[Row]) -> list[Group]:
    """Bucket rows into Groups, one per category, in matcher order."""
    bucket: dict[str, list[Row]] = defaultdict(list)
    descriptions: dict[str, str] = {}
    for row in rows:
        category, description = classify(row.raw)
        bucket[category].append(row)
        descriptions.setdefault(category, description)
    # Preserve the matcher order so the output is deterministic and
    # mirrors the priority of action items (auto-rescues at the top).
    out: list[Group] = []
    for category, _, description in PATTERN_MATCHERS:
        if category in bucket:
            out.append(
                Group(category=category, description=description, rows=bucket[category])
            )
    return out


# ── Rendering ──────────────────────────────────────────────────────────


def render_triage_md(source_path: Path, rows: list[Row], groups: list[Group]) -> str:
    """Build the triage markdown — pattern summary first, then samples.

    Sample size is capped at 10 per group; the rest are folded into a
    `<details>` block so the file stays scannable for a few hundred rows.
    """
    lines = [
        f"# UNITS migration triage — {source_path.name}",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}_",
        "",
        f"Source: `{source_path}`",
        f"Total flagged rows: **{len(rows)}** across **{len(groups)}** pattern groups.",
        "",
        "## Summary",
        "",
        "| Category | Count | Suggested action |",
        "|---|---|---|",
    ]
    for g in groups:
        lines.append(f"| `{g.category}` | {len(g.rows)} | {g.description} |")
    lines.append("")
    for g in groups:
        lines.extend(
            [
                f"## `{g.category}` ({len(g.rows)} rows)",
                "",
                f"_{g.description}_",
                "",
            ]
        )
        sample = g.rows[:10]
        rest = g.rows[10:]
        lines.extend(
            [
                "| product | manufacturer | field | raw |",
                "|---|---|---|---|",
            ]
        )
        for row in sample:
            product = row.product_name or "—"
            mfg = row.manufacturer or "—"
            # Markdown-escape the bar character in raw cells so the table
            # renders correctly. Backtick the raw so HTML doesn't eat it.
            raw_safe = row.raw.replace("|", "\\|")
            lines.append(f"| {product} | {mfg} | `{row.field_path}` | `{raw_safe}` |")
        if rest:
            lines.extend(
                [
                    "",
                    f"<details><summary>{len(rest)} more</summary>",
                    "",
                    "| product | manufacturer | field | raw |",
                    "|---|---|---|---|",
                ]
            )
            for row in rest:
                product = row.product_name or "—"
                mfg = row.manufacturer or "—"
                raw_safe = row.raw.replace("|", "\\|")
                lines.append(
                    f"| {product} | {mfg} | `{row.field_path}` | `{raw_safe}` |"
                )
            lines.extend(["", "</details>"])
        lines.append("")
    return "\n".join(lines) + "\n"


# ── CLI ────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="units_triage", description=__doc__)
    parser.add_argument(
        "source",
        type=Path,
        help="Source review markdown (e.g. outputs/units_migration_review_dev_*.md)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Triage MD path (default: outputs/units_triage_<stage>_<ts>.md)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress INFO logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    if not args.source.exists():
        print(f"source not found: {args.source}", file=sys.stderr)
        return 2

    text = args.source.read_text()
    rows = parse_review(text)
    groups = group_by_pattern(rows)
    log.info(
        "Parsed %s flagged rows from %s into %s groups",
        len(rows),
        args.source.name,
        len(groups),
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        out = args.output
    else:
        # units_migration_review_dev_<ts>.md → units_triage_dev_<ts>.md
        stem = args.source.stem.replace("units_migration_review_", "units_triage_")
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        # Preserve original timestamp for traceability; append "from"-ts to
        # avoid clobbering when re-triaging the same source.
        out = OUTPUT_DIR / f"{stem}_triaged_{ts}.md"
    out.write_text(render_triage_md(args.source, rows, groups))
    log.info("Wrote triage: %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
