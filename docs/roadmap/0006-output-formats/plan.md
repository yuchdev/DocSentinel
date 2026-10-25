# Milestone 0006 - Output Formats

**Package:** `docsentinel` | **Module root:** `src/docsentinel/` | **Config namespace:** `doc_sentinel`

> Naming note: the package, CLI and import path are `docsentinel`; the configuration namespace is
> deliberately `doc_sentinel`. See
> [Milestone 0001's naming note](/docs/roadmap/0001-generic-implementation/plan.md).

## Goal

Make a single scan produce every report a consumer needs, in the format that consumer needs.
Today `docsentinel scan` renders exactly one of `text`, `json` or `github` to **stdout**, so
anyone wanting several reports (a machine-readable one for tooling, a human-readable one to commit,
an annotation stream for CI) has to re-run the scan once per format and shell-redirect each result.

The trigger was a real use: a full review of CanonixEngine's `docs/` needed three profiles in three
formats (nine runs and nine redirects), and the committed summary had to be written by hand
because no Markdown report exists. This milestone removes that friction without touching detection.

## Stories

| Story | Name                          | Category | Output                                                                                                                  |
|-------|-------------------------------|----------|-------------------------------------------------------------------------------------------------------------------------|
| 01.0  | Multi-Format Output Plumbing  | feature  | `--output PATH` and repeatable `--format`, so one scan writes several report files; per-format renderer registry        |
| 02.0  | New Report Renderers          | feature  | `markdown` (human-readable, committable summary) and `sarif` (SARIF 2.1.0 for code-scanning tools) renderers            |

## Cross-cutting guidelines (every story)

- **Rendering only.** No detector, rule, severity or exit-code behavior changes. `ScanResult`, JSON
  schema v1, the `enabled_rules` semantics and CLI exit codes (`0`/`1`/`2`) are unchanged; a
  scan produces the same findings whatever the formats requested.
- **One scan, many renderings.** Formats are rendered from the same in-memory `ScanResult`; a
  multi-format run never scans twice.
- **Neutralize every sink.** Every new renderer routes document-derived text (paths, messages)
  through the existing `neutralize_text` / `_neutralize_controls` helpers in `reporting.py`, so
  control, bidi and zero-width characters cannot reach any report. Machine formats (JSON, SARIF)
  escape per their own spec in addition.
- **Honest about empty and pending.** A report for a run that evaluated no rules (for example the
  `deep` profile with its model missing) says so in every format, never a bare "no findings". The
  `deep` banner and advisory wording are preserved in each renderer.
- **Deterministic output.** Same input, same bytes: stable ordering, no timestamps or absolute
  paths in report bodies (a caller-supplied label is the only varying part).
- **No new runtime dependencies.** Renderers use the standard library only.
- **Full type annotations, no bare `except:`** - see
  [`docs/dev/python_coding_standard.md`](/docs/dev/python_coding_standard.md).

## Out of scope

- HTML and JUnit XML reports. Both are plausible follow-ups once the renderer registry from Story
  01.0 exists; they are deliberately not specified until there is a concrete consumer.
- Changing which findings a profile emits, or merging profiles into one run (profiles stay exact).
- Diffing two reports (trend or regression views).

## Known issue noted while motivating this milestone

Not part of this milestone's scope, recorded so it is not lost: on an Intel macOS machine,
loading `en_core_web_sm` for the `deep` profile failed with
`OverflowError: Python int too large to convert to C ssize_t` under `preshed` 3.0.14, and worked
with `preshed<3.0.10`. `docsentinel doctor` still reported the deep profile as ready. Triage
separately (a dependency bound, or a `doctor` smoke-load of the model).
