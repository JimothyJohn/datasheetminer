"""One-shot: clean up legacy ``"value;unit"`` strings stored in DynamoDB
that bypassed ``DynamoDBClient._parse_compact_units`` at ingest time.

The writer at ``specodex/db/dynamo.py:71`` converts canonical
``"value;unit"`` strings into ``{value, unit}`` dicts before
``put_item``. Any item whose string value still contains ``;`` was
written before that step ran (or by a path that bypassed it).

Categories applied per offending string:

    recoverable      Numeric value + valid unit. Re-parsed via
                     ``_parse_compact_units`` and re-written. Idempotent.
    recoverable_pm   Tolerance form ``"±N;unit"`` — magnitude treated as
                     ``{value: N, unit}``. Sign convention is symmetric
                     (repeatability, working ranges) so the ± is implicit.
    recoverable_rng  Range with ``+`` sign such as ``"-25-+90;°C"`` —
                     re-parsed as ``{min, max, unit}``.
    garbage          Unit is ``null`` / ``unknown`` / ``none`` / empty.
                     Field removed.
    wrong_field      Value side is alphabetic (e.g. ``"IP42;mH"``) — LLM
                     stuffed the wrong attribute into a numeric field.
                     Field removed.
    multivalue       Contains commas or option-parens, suggesting the
                     field should hold a list. Field LEFT IN PLACE; row
                     id and value written to a flag report for human
                     review (planned: replace with list-typed schema).
    wordy            Long prose value. Field LEFT IN PLACE; flagged.
    bound            Inequality like ``"≤12;arcmin"``. Flagged.

Dry-run by default. Pass ``--apply`` to write changes.

Usage:
    uv run python scripts/cleanup_semicolon_legacy.py
    uv run python scripts/cleanup_semicolon_legacy.py --apply
    uv run python scripts/cleanup_semicolon_legacy.py --table products-dev --apply
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
load_dotenv(REPO / ".env")

import boto3  # noqa: E402

from specodex.db.dynamo import DynamoDBClient  # noqa: E402

GARBAGE_UNITS = {"null", "unknown", "none", "", "n/a", "tbd", "?", "na"}

# Identifier / metadata fields that we never modify even if they contain ';'.
SKIP_KEYS = {"PK", "SK", "product_id", "datasheet_id", "datasheet_url"}

NUM = r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"  # int / float / scientific
NUMERIC = re.compile(rf"^{NUM}$")
NUMERIC_RANGE = re.compile(rf"^({NUM})-({NUM})$")
PM_TOLERANCE = re.compile(rf"^±\s*({NUM})(?:°)?$")
INEQUALITY = re.compile(rf"^[≤≥<>]\s*{NUM}$")
# "/-N" — the ± glyph corrupted to "/" during some prior ingest. Same shape
# as ±N (joints / pose_repeatability / shaft fields).
SLASH_PM = re.compile(rf"^/-({NUM})(?:°)?$")
# "Ø N" / "Ø N mm" — diameter prefix. We discard the Ø marker (the field
# is already typed as a diameter) and keep magnitude + unit.
DIAMETER = re.compile(rf"^Ø\s*({NUM})$")


@dataclass
class Hit:
    product_id: str
    product_type: str
    manufacturer: str
    part_number: str
    path: str  # field path, e.g. "joints[3].working_range"
    raw: str  # original string value
    category: str
    replacement: Any | None = None  # parsed dict if recoverable, else None


def categorize(raw: str) -> tuple[str, Any | None]:
    """Return (category, replacement-or-None) for a string containing ';'."""
    if ";" not in raw:
        return ("no_semicolon", None)
    val_side_raw, _, unit_raw = raw.partition(";")
    val = val_side_raw.strip()
    unit = unit_raw.strip()

    # Repair the broken-split "±;N°" / "±;N°/s" shape: the original
    # "±N°[/s]" string was split at a stray internal ';' so we end up
    # with val="±" and the magnitude in the unit slot. Re-stitch and
    # extract magnitude + degree-or-degree-per-second unit.
    if val == "±" and unit and unit[0].isdigit():
        m = re.match(rf"^({NUM})(°(?:/s)?)?$", unit)
        if m:
            mag = float(m.group(1))
            recovered_unit = m.group(2) if m.group(2) else "°"
            return ("recoverable_pm", {"value": mag, "unit": recovered_unit})

    # Unit garbage takes precedence — even if value is fine, the row is
    # un-filterable without a unit, so drop it.
    if unit.lower() in GARBAGE_UNITS:
        return ("garbage", None)

    # Multi-value: option-paren ("340 (360 option)"), comma-separated
    # multi-axis ("±0.015;mm (Z), ±0.005° (T)"), slash variants
    # ("12/24;V", "2000/2800;mm/s"), or x-separated dimensions
    # ("320x240;pixels").
    if "," in raw or "(" in val or "/" in val or re.search(r"\dx\d", val):
        return ("multivalue", None)

    # Strip a leading diameter marker — the field is already typed as a
    # diameter, the Ø is presentational only.
    m = DIAMETER.match(val)
    if m:
        return ("recoverable", {"value": float(m.group(1)), "unit": unit})

    # Tolerance "±N" — store magnitude, sign is implicit.
    m = PM_TOLERANCE.match(val)
    if m:
        return ("recoverable_pm", {"value": float(m.group(1)), "unit": unit})

    # "/-N" — corrupted ± glyph (joints/repeatability/shaft data).
    m = SLASH_PM.match(val)
    if m:
        return ("recoverable_pm", {"value": float(m.group(1)), "unit": unit})

    # "- N" with a space — looks like a stripped ± glyph in tolerance
    # fields (input_shaft_diameter, output_shaft_diameter). Magnitude
    # only; assume ± since these are tolerance specs.
    m = re.match(rf"^-\s+({NUM})$", val)
    if m:
        return ("recoverable_pm", {"value": float(m.group(1)), "unit": unit})

    # Asterisk artifacts ("50***;A") — corrupt source text; cannot trust.
    if "*" in val:
        return ("wrong_field", None)

    # Inequality "≤12" / ">100" — flag, don't auto-rewrite.
    if INEQUALITY.match(val):
        return ("bound", None)

    # Tilde range "-40~+100" → "-40-+90". Normalize, then run numeric checks.
    val_norm = val.replace("~", "-")
    cleaned = val_norm.replace(",", "")
    # Strip a single leading '+' (`+90` → `90`); preserve embedded '+' in
    # ranges so "-25-+90" still parses via NUMERIC_RANGE.
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    cleaned = cleaned.lstrip()

    # Plain numeric: "60", "-25", "0.1", "1.98E-6"
    if NUMERIC.match(cleaned):
        return ("recoverable", {"value": float(cleaned), "unit": unit})

    # Range "min-max", possibly with leading +/-
    m = NUMERIC_RANGE.match(cleaned)
    if m:
        return (
            "recoverable_rng",
            {"min": float(m.group(1)), "max": float(m.group(2)), "unit": unit},
        )

    # Starts with letter → wrong-field content (IP rating in numeric field, etc.)
    if re.match(r"^[A-Za-z]", val):
        if len(val) <= 30:
            return ("wrong_field", None)
        return ("wordy", None)

    # Has prose-like spaces but didn't match anything above
    if " " in val and len(val) > 20:
        return ("wordy", None)

    return ("uncategorized", None)


def walk(value: Any, path: str):
    """Yield (path, str) for every str leaf containing ';'."""
    if isinstance(value, str):
        if ";" in value:
            yield (path, value)
    elif isinstance(value, dict):
        for k, v in value.items():
            sub = f"{path}.{k}" if path else k
            yield from walk(v, sub)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk(v, f"{path}[{i}]")


def collect_hits(item: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for k, v in item.items():
        if k in SKIP_KEYS:
            continue
        for path, raw in walk(v, k):
            out.append((path, raw))
    return out


def remove_path(item: dict, path: str) -> bool:
    """Delete the leaf at the given dotted/indexed path in `item`. Mutates."""
    tokens = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    cur: Any = item
    for tok in tokens[:-1]:
        if tok.startswith("["):
            cur = cur[int(tok[1:-1])]
        else:
            cur = cur[tok]
    last = tokens[-1]
    if last.startswith("["):
        del cur[int(last[1:-1])]
    else:
        cur.pop(last, None)
    return True


def replace_path(item: dict, path: str, new_value: Any) -> bool:
    """Set the leaf at the given path. Mutates."""
    tokens = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    cur: Any = item
    for tok in tokens[:-1]:
        if tok.startswith("["):
            cur = cur[int(tok[1:-1])]
        else:
            cur = cur[tok]
    last = tokens[-1]
    if last.startswith("["):
        cur[int(last[1:-1])] = new_value
    else:
        cur[last] = new_value
    return True


def scan_table(client: DynamoDBClient):
    kwargs = {}
    while True:
        resp = client.table.scan(**kwargs)
        for item in resp.get("Items", []):
            yield item
        if "LastEvaluatedKey" in resp:
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        else:
            break


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--table", default=os.environ.get("DYNAMODB_TABLE_NAME", "products-dev")
    )
    ap.add_argument(
        "--apply", action="store_true", help="Write changes. Default is dry-run."
    )
    ap.add_argument(
        "--report-dir",
        default=str(REPO / "outputs" / "semicolon_cleanup"),
        help="Directory to write flag reports (multivalue.json, wordy.json, ...).",
    )
    args = ap.parse_args()

    client = DynamoDBClient(table_name=args.table)
    print(f"Scanning {args.table}  (apply={args.apply})")

    cat_counts: Counter[str] = Counter()
    field_counts: Counter[str] = Counter()
    flagged: dict[str, list[Hit]] = defaultdict(list)

    items_modified = 0
    fields_removed = 0
    items_recovered = 0  # items where ≥1 recoverable string was re-parsed via PutItem

    DESTRUCTIVE = {"garbage", "wrong_field"}
    RECOVERABLE = {"recoverable", "recoverable_pm", "recoverable_rng"}
    FLAG_ONLY = {"multivalue", "wordy", "bound", "uncategorized"}

    for item in scan_table(client):
        pk = str(item.get("PK", ""))
        if not pk.startswith("PRODUCT#"):
            continue

        hits = collect_hits(item)
        if not hits:
            continue

        product_id = str(item.get("product_id", ""))
        ptype = str(item.get("product_type", ""))
        mfg = str(item.get("manufacturer", ""))
        pn = str(item.get("part_number", ""))

        modified = False
        had_recoverable = False
        for path, raw in hits:
            cat, repl = categorize(raw)
            cat_counts[cat] += 1
            field_counts[path.split("[")[0]] += 1

            hit = Hit(product_id, ptype, mfg, pn, path, raw, cat, repl)

            if cat in DESTRUCTIVE:
                if args.apply:
                    remove_path(item, path)
                fields_removed += 1
                modified = True
            elif cat in RECOVERABLE:
                # Replace the string with the parsed dict in-place. PutItem
                # below will write the cleaned shape.
                if args.apply and repl is not None:
                    replace_path(item, path, repl)
                had_recoverable = True
                modified = True
            elif cat in FLAG_ONLY:
                flagged[cat].append(hit)
            # else: no_semicolon won't reach here

        if modified:
            if args.apply:
                # Re-walk the rest of the item through _parse_compact_units to
                # idempotently catch any other "value;unit" leaves that ended
                # up as strings via a path that bypassed the writer.
                cleaned_item = client._parse_compact_units(item)
                cleaned_item = client._convert_floats_to_decimal(cleaned_item)
                client.table.put_item(Item=cleaned_item)
            items_modified += 1
            if had_recoverable:
                items_recovered += 1

    print()
    print("=== Category counts (per-field-hit, not per-row) ===")
    for cat, n in cat_counts.most_common():
        print(f"  {cat:20} {n}")

    print()
    print("=== Top 20 field paths ===")
    for path, n in field_counts.most_common(20):
        print(f"  {n:5}  {path}")

    print()
    print(f"Items touched:        {items_modified}")
    print(f"  with re-parse:      {items_recovered}")
    print(f"Field removals:       {fields_removed}")

    # Write flag reports
    if flagged:
        out_dir = Path(args.report_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for cat, hits in flagged.items():
            path = out_dir / f"{cat}.json"
            with path.open("w") as fh:
                json.dump(
                    [
                        {
                            "product_id": h.product_id,
                            "product_type": h.product_type,
                            "manufacturer": h.manufacturer,
                            "part_number": h.part_number,
                            "path": h.path,
                            "value": h.raw,
                        }
                        for h in hits
                    ],
                    fh,
                    indent=2,
                )
            print(f"Wrote {len(hits):4d} {cat:12} hits → {path}")

    if not args.apply:
        print()
        print("(dry-run — no writes. Re-run with --apply to commit.)")


if __name__ == "__main__":
    main()
