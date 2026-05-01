# RUST_ONE — port the page finder, not the project

## Why this doc exists

`branch:rust` tried to port everything: Pydantic models → Rust structs, Express
routes → Axum, integration adapters, S3 upload, Stripe, admin tooling, SAM/CFN
deploy. 87 files, 19k+ insertions, and Phase 2/3 still half-landed. That's a
rewrite, not a port. Backing away.

This doc is the opposite: pick the **single piece** of the codebase that's
cleanest to lift into Rust without touching anything else, ship it, see if it
helps, and stop there. If it works, the question of "should we port more?"
becomes an evidence-based one. If it doesn't, we delete one crate and forget it.

## Layer recap (correcting the mental model)

The repo is three languages, not two:

| Layer            | Path             | Language           |
| ---------------- | ---------------- | ------------------ |
| Web UI           | `app/frontend/`  | TypeScript / React |
| HTTP API         | `app/backend/`   | TypeScript / Express |
| Data pipeline    | `specodex/`, `cli/` | Python          |

So "the backend is Python" isn't right — the API is Node. Python is the *ingest
pipeline*: PDF → page finder → Gemini → Pydantic → DynamoDB. That's the part
that actually does CPU work; the API just reads the table.

## The pick: `specodex/page_finder.py::find_spec_pages_by_text`

One function. Pure compute. Zero network. Zero AWS. Zero LLM.

```python
# specodex/page_finder.py:220
def find_spec_pages_by_text(pdf_bytes: bytes) -> list[int]:
    """Free, no API calls. Returns 0-indexed pages matching spec keywords."""
```

Why this and nothing else:

1. **Smallest defensible contract.** `bytes → list[int]`. No schema, no IO, no
   stateful client.
2. **No external dependency.** Doesn't need `GEMINI_API_KEY`, doesn't talk to
   DynamoDB, doesn't sign anything. Just reads a PDF and matches keywords.
3. **It's the hot loop.** Every ingest run scans every page of every PDF
   through this function before deciding which pages are worth $LLM money. The
   J5 catalog is 616 pages. Python + PyMuPDF is fine but not free.
4. **Reversible.** It's behind one import (`from specodex.page_finder import
   find_spec_pages_by_text`) used by `scraper.py`, `cli/bench.py`,
   `cli/schemagen.py`, `cli/inspect_datasheet.py`, and the unit tests. Wrap a
   subprocess call inside the existing function and every caller keeps working.
5. **Tight scope.** ~250 LOC of Python (the text-heuristic chunk of
   `page_finder.py` plus the `SPEC_KEYWORDS` table) maps to maybe ~400 LOC of
   Rust. Small enough to write from scratch in a sitting; the keyword table
   is the bulk and ports literally.
6. **Measurable.** `./Quickstart bench` already times the page-finding stage
   per fixture. Land the swap, re-run bench, compare.

What we **don't** touch:

- `find_spec_pages_scored` / `classify_pages` / the Gemini-image fallback —
  has API calls, fixtures, prompts. Stays in Python.
- Pydantic models, integration adapters, every route in `app/backend` — out
  of scope. Forever, unless a separate doc reopens it.
- Any deploy / IaC / Lambda packaging change. The Rust binary runs locally and
  in CI; production ingest is still `./Quickstart process` on Python.

## Shape of the change

### 1. Set up the `rust/` workspace from scratch

One workspace, one member. The abandoned `branch:rust` is gone, so this is a
clean-slate scaffold:

```
rust/
├── Cargo.toml                  # [workspace] resolver = "2", members = ["crates/specodex-pdf"]
└── crates/specodex-pdf/
    ├── Cargo.toml              # one [[bin]]: specodex-page-finder
    └── src/
        ├── lib.rs              # find_spec_pages_by_text(&[u8]) -> Vec<usize>
        ├── keywords.rs         # SPEC_KEYWORDS const — port the table verbatim from page_finder.py:43
        ├── page_finder.rs      # extract_pages_via_pdftotext + spec_pages_from_text_pages
        └── bin/
            ├── specodex-page-finder.rs   # stdin → JSON stdout (the production binary)
            └── parity.rs                 # diff Rust vs Python over benchmark fixtures (CI gate)
```

Add `rust/target/` to `.gitignore` if not already covered. The `stripe/` Rust
crate stays at the repo root as a separate workspace — different concern,
different Lambda, no value in unifying for one sibling.

### 2. Decide the PDF text extractor (one decision, one paragraph)

Shell out to **Poppler `pdftotext`** for v1. Two pure-Rust crates were tried
on the abandoned port and both lost: `pdf-extract` doesn't emit form-feeds
(can't tell where one page ends and the next begins) and crashes on encrypted
or complex PDFs; `pdfium-render` and `mupdf-rs` need a system lib that
complicates the Lambda build. Poppler is on every dev machine via Homebrew,
on GitHub Actions runners by default, and installable on the Lambda base
image via `apt`. Document the dependency, ship a `command -v pdftotext` check
in `Quickstart verify`, move on. `pdfium-render` / `mupdf-rs` is a v2 question
we open if Poppler bites us.

The contract: `pdftotext -enc UTF-8 - -` reads PDF on stdin, writes
form-feed-separated text to stdout. Split on `\u{000c}` for per-page text.

**Risk to flag:** Poppler's text extraction is not bit-identical to PyMuPDF's.
That's exactly what the `parity` binary (step 1) is for — run it on every
benchmark fixture as part of CI and require zero diff before the swap goes
live (see step 4).

### 3. Ship one binary, one Python wrapper

**Binary:** `specodex-page-finder`.

```
specodex-page-finder < input.pdf
# stdout: {"pages": [3, 4, 7, 12]}
# exit 0 on success, non-zero on parse error
```

Stdin/stdout, JSON out, no flags for v1. One concern, one binary.

**Python wrapper:** edit `specodex/page_finder.py:220` to try the binary first
and fall back to the existing PyMuPDF implementation on any failure (binary
missing, non-zero exit, JSON parse error). Log which path ran at DEBUG. Both
implementations stay; the Rust one becomes the default when present.

```python
# Sketch — actual impl in the implementation step
def find_spec_pages_by_text(pdf_bytes: bytes) -> list[int]:
    if _rust_binary := _find_rust_binary():
        try:
            return _run_rust(_rust_binary, pdf_bytes)
        except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.warning("rust page-finder failed (%s); falling back to PyMuPDF", e)
    return _find_spec_pages_by_text_python(pdf_bytes)
```

Why fallback rather than hard requirement: dev flow doesn't break on a fresh
checkout where someone hasn't run `cargo build --release`. CI catches drift via
the parity test (step 4); production catches it via the env check on
`Quickstart verify`.

### 4. Parity gate, then performance gate

**Parity** comes first. Add to `./Quickstart verify`:

```
cargo run --release --manifest-path rust/Cargo.toml \
  -p specodex-pdf --bin parity
```

This runs Rust + Python on every PDF in `tests/benchmark/datasheets/` and
fails on any difference. Zero-diff is the bar. If Poppler and PyMuPDF disagree
on a fixture, that's the work to do — either tune the extractor, broaden the
keyword match, or accept the diff with a `tests/benchmark/parity-known-diffs.json`
allowlist (and only with a written reason per fixture).

**Performance** comes second. Run `./Quickstart bench` before and after on the
same fixtures, attach the two `outputs/benchmarks/<ts>.json` files to the PR.
No a-priori speedup target — measure, then judge. If it's not faster, that's
useful information; we still have the binary as a stepping stone.

### 5. Tests stay where they are

`tests/unit/test_page_finder_edge.py` exists and patches `specodex.page_finder.*`
at the module level. The wrapper change preserves the public function name and
signature, so those tests don't move. The Rust crate gets its own unit tests
under `rust/crates/specodex-pdf/src/page_finder.rs` — at minimum, table-driven
cases for `spec_pages_from_text_pages` covering empty pages, single-keyword
non-matches, and threshold-boundary matches.

## Acceptance criteria

- [ ] `rust/` workspace exists at master with one member: `specodex-pdf`.
- [ ] `cargo build --release -p specodex-pdf` succeeds on macOS dev box and on
      the GitHub Actions Ubuntu runner.
- [ ] `specodex-page-finder` binary runs end-to-end on stdin and emits the
      JSON contract above.
- [ ] `parity` reports zero diff on every PDF in
      `tests/benchmark/datasheets/` (or every diff is allowlisted with a
      written reason).
- [ ] `find_spec_pages_by_text` calls the Rust binary by default and falls back
      to PyMuPDF on any error, with a single WARNING log line.
- [ ] `./Quickstart verify` includes the parity check and fails the build on
      drift.
- [ ] `./Quickstart bench` results are attached to the PR (before/after).
- [ ] Existing `tests/unit/test_page_finder_edge.py` passes unchanged.

## Non-goals (write them down so they stay non-goals)

- **No** port of `find_spec_pages_scored` or any Gemini call.
- **No** port of any Pydantic model, schema builder, or DB layer.
- **No** port of `app/backend` routes or middleware.
- **No** new deploy target. The Rust binary is built locally and in CI; the
  Python pipeline still runs the same way it does today.
- **No** PyO3 / Rust extension module dance. Subprocess is fine, the cost
  (one fork+exec per PDF) is invisible next to a 60s LLM round-trip.
- **No** "while we're in here" cleanup of unrelated Python code.

## If this lands and we like it

That's a separate doc and a separate decision. The natural next-smallest cuts,
in order of obviousness:

1. **`specodex/quality.py`** (122 LOC) — pure scoring, no IO, same shape as
   page_finder. Trivial to port if we want a second exercise.
2. **The Express read paths** (`/api/products`, `/api/products/categories`,
   `/api/products/summary`, `/api/v1/search`) — DynamoDB-only, no Stripe, no
   S3, no admin write paths. Could land as a sibling Lambda behind an ALB
   weighting and A/B'd against the Node Lambda.

But none of that is on the table until step 1 (this doc) ships and the bench
numbers are in.

## Status

- [ ] Scaffold `rust/Cargo.toml` (one-member workspace) + `crates/specodex-pdf/`
- [ ] Port `SPEC_KEYWORDS` from `specodex/page_finder.py:43` to `keywords.rs`
- [ ] Implement `find_spec_pages_by_text` over `pdftotext` form-feed split
- [ ] Ship `specodex-page-finder` binary (stdin → JSON stdout)
- [ ] Ship `parity` binary that diffs Rust vs Python on every benchmark fixture
- [ ] Wire the Python wrapper with subprocess + PyMuPDF fallback
- [ ] Add `command -v pdftotext` check + parity run to `Quickstart verify`
- [ ] Run `Quickstart bench` before/after, attach results to the PR
