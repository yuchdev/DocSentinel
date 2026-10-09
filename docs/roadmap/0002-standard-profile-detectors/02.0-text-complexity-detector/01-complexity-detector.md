# Task 01 - Complexity Detector & Grade Threshold (`DS201`)

**Story:** [02.0 - Text Complexity Detector](README.md)
**Depends on:** Milestone 0002 Story 01.0 (the `standard` subpackage + loader must exist to register
into); Milestone 0001 Story 01.0 (rule registry, `ANALYZERS` keyed by code) and Story 01.0 Task 02
(`Config` dataclass this task adds a field to)

## Purpose

Covers `CLAUDE.md`'s "high-complexity text" requirement with a deterministic, model-free readability
score: flag any document whose prose grade level exceeds a configurable threshold. `textstat`
computes this as a pure function of the text (no network, no model), which is exactly what keeps it
inside the deterministic-first premise while still being too heavy for `fast`.

## Decision this task implements

1. **Metric: Flesch-Kincaid Grade Level, cross-checked by Gunning Fog.** Compute both
   `textstat.flesch_kincaid_grade(text)` and `textstat.gunning_fog(text)`. Flag the document when
   **both** exceed `max_grade_level`. Requiring both to agree (rather than either alone) cuts false
   positives from the known quirks of any single readability formula on technical prose - a document
   is only "too complex" if two independent formulas concur. The reported grade in the message is
   the Flesch-Kincaid value (the more widely recognized of the two).
2. **Default threshold: `max_grade_level = 14.0`** (early-undergraduate). This is deliberately
   conservative - it flags only genuinely dense prose, not ordinary technical writing - because
   `DS201` is `warning` severity and a flood of complexity warnings trains users to ignore them.
   Projects that want a stricter readability bar lower it in config.
3. **Documented limitation: one global threshold for the whole corpus.** A terse ADR and a
   prose-heavy user manual genuinely want different bands, but per-category thresholds need a
   config schema (path-glob → threshold maps) that is out of scope for this milestone and easy to
   over-build. This task ships a single `max_grade_level` and records per-category thresholds as
   explicit future work in the module docstring and in `docs/architecture/README.md`. Do **not**
   add a nested per-category config here.
4. **Short-document guard.** Readability formulas are unstable on very short text (a two-sentence
   note can score grade 20). Skip any document whose extracted prose has fewer than
   `_MIN_WORDS = 50` words - no finding, because the score is not trustworthy. This is a determinism
   /false-positive guard, not a config knob.
5. **Prose extraction excludes code.** Fenced code blocks, inline code spans, and Markdown link
   *targets* (URLs) are not prose and would skew the score; strip them before measuring, keeping the
   visible link text. Headings and list text *are* prose and are kept.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/standard/complexity.py` | Create |
| `src/docsentinel/config.py` | Modify - add `Config.max_grade_level` + validation |
| `tests/test_detectors_complexity.py` | Create |
| `tests/test_config.py` | Modify - add `max_grade_level` validation tests |

## Symbols / fields

`src/docsentinel/detectors/standard/complexity.py`:

| Symbol | Kind | Notes |
|--------|------|-------|
| `DS201` | module-level `Rule` via `register_rule(...)` | `Rule(code="DS201", profile="standard", title="Text complexity", description="Document prose exceeds the configured readability grade level.", severity="warning")`. `warning`: readability is advisory. |
| `_MIN_WORDS` | module-level `int` | `50` - short-document guard (Decision §4). |
| `_extract_prose(text: str) -> str` | function | Strips fenced code blocks, inline code spans, and link targets (keeps link text); returns the remaining prose joined for scoring. Local to this module (per the no-shared-helpers-across-detectors convention for small text helpers; the TF-IDF corpus helper shared in Story 03.0 is a separately justified exception, not a precedent to fold this into). |
| `grade_level(prose: str) -> tuple[float, float]` | function | Returns `(flesch_kincaid_grade, gunning_fog)` via `textstat`. Isolated so tests can assert the metric wiring without a full `Document`. |
| `check_document(root: Path, document: Document, *, max_grade: float) -> tuple[Finding, ...]` | function | Reads `(root / document.path).read_text("utf-8")`, extracts prose, applies the short-doc guard, computes both grades, emits one `Finding(rule="DS201", path=document.path, message=..., severity="warning")` when both exceed `max_grade`. Message shape: `f"readability grade {fk:.1f} exceeds max {max_grade:.1f} (Gunning Fog {fog:.1f})"`. |
| `detect(root: Path, documents: tuple[Document, ...]) -> tuple[Finding, ...]` | function, the `Analyzer` registered into `ANALYZERS["DS201"]` | Loads config via `load_config(root)` to read `max_grade_level` (see Note below), filters `documents` to `.md`, calls `check_document` on each, concatenates. |

> Note on config access inside an `Analyzer`: the `Analyzer` signature
> (`Callable[[Path, tuple[Document, ...]], tuple[Finding, ...]]`) does not pass `Config`. `DS201`
> needs `max_grade_level`. Resolve it the same way a detector that needs config settings must:
> call `load_config(root)` inside `detect`. This re-reads the config file per scan (once, at the
> top of `detect`), which is acceptable - it is one small TOML read. **Do not** change the
> `Analyzer` type alias to thread `Config` through; Milestone 0001 Story 01.0 Task 03 explicitly
> froze that signature. If a future milestone finds multiple detectors re-reading config wasteful,
> widening the signature is its own cross-cutting decision, not something to sneak in here.

`src/docsentinel/config.py`:

| Symbol | Change |
|--------|--------|
| `Config.max_grade_level: float = 14.0` | New field, appended after the existing fields (keyword construction everywhere, per Milestone 0001 Story 01.0 Task 02's note on not relying on positional field order). |
| validation in `load_config` | `max_grade_level`, if present, must be a number (`int`/`float`, not `bool`) and `> 0`; otherwise `ConfigError`. Accept it as a top-level key in `doc_sentinel.toml` and under `[tool.doc_sentinel]`, same as every other key. |

## Validators (raise `ConfigError`)

- `max_grade_level` present but not a real number, or a `bool`, or `<= 0` → `ConfigError(
  "max_grade_level must be a positive number")`.
- No cross-field validation needed.

## Tests (`tests/test_detectors_complexity.py`)

- `test_simple_prose_is_not_flagged` - a short, plainly-written paragraph (well under grade 14)
  produces zero findings.
- `test_dense_prose_over_threshold_is_flagged` - a deliberately convoluted, long-sentence,
  polysyllabic paragraph (comfortably over grade 14 on both formulas) produces exactly one `DS201`
  finding with the grade in its message.
- `test_short_document_is_skipped` - a document whose prose is under `_MIN_WORDS` words produces no
  finding even if its tiny sample scores high (guards the short-doc rule).
- `test_only_flagged_when_both_formulas_agree` - construct (or monkeypatch `grade_level` to return)
  a case where Flesch-Kincaid is over threshold but Gunning Fog is under; assert no finding (the
  "both must agree" rule).
- `test_code_blocks_excluded_from_score` - two documents with identical prose, one with a large
  fenced code block appended; both yield the same grade and the same finding-or-not outcome (code
  did not shift the score).
- `test_threshold_is_configurable` - the same dense document is flagged at `max_grade_level=10` and
  clean at `max_grade_level=25`.
- `test_non_markdown_documents_are_not_scanned` - a `.txt` `Document` produces no `DS201` findings.
- `test_detect_reads_max_grade_from_config` - a `doc_sentinel.toml` with `max_grade_level = 10` in
  `tmp_path` causes `detect(tmp_path, docs)` to use `10`, not the `14.0` default.

`tests/test_config.py` additions:
- `test_max_grade_level_default_is_14` - `Config().max_grade_level == 14.0`.
- `test_max_grade_level_non_number_raises` - `max_grade_level = "high"` → `ConfigError`.
- `test_max_grade_level_non_positive_raises` - `max_grade_level = 0` and `-3` → `ConfigError`.

## Success criteria

- [ ] `DS201` fires only when both readability formulas exceed the threshold and the document clears
      the short-document guard - each of those three gates has a covering test.
- [ ] `max_grade_level` round-trips through both config file shapes and is validated as a positive
      number.
- [ ] `complexity.py` imports `textstat` at module scope - which is safe precisely because this
      module is only ever imported via the Story 01.0 lazy loader, never on the `fast` path. A test
      (Task 02) confirms importing it outside that path is not triggered by a `fast` scan.

## Constraints

- Full type annotations; no bare `except:`. File reads use the same `OSError`/`UnicodeDecodeError`
  handling convention as `DS101` (propagate, do not swallow - a document that cannot be read is
  itself worth surfacing).
- `textstat`'s language defaults to English; this milestone does not configure locale-specific
  readability (that would reintroduce a non-deterministic-by-environment input). Note the
  English-only assumption in the module docstring.
- Do not add per-category thresholds (Decision §3) - single global `max_grade_level` only.
</content>
