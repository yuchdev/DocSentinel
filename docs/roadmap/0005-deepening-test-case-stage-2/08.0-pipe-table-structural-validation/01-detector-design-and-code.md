# Task 01 — implement DS117: Malformed GFM pipe-table structure

**Parent story:** [Story 08.0](/docs/roadmap/0005-deepening-test-case-stage-2/08.0-pipe-table-structural-validation/README.md)  
**Proposed source:** `src/docsentinel/detectors/tables.py`  
**Rule identity:** `Rule(code="DS117", profile="fast", title="Malformed GFM pipe-table structure", severity="warning")`.

## Required behavior and algorithm

1. Recognize table headers only when followed by a valid GFM delimiter row with separators and optional colons.
2. Parse unescaped pipe separators, respecting backslash escapes and backtick code spans; allow optional outer pipes.
3. Check header, delimiter and body row logical cell counts consistently; padded empty cells are valid.
4. Handle alignment markers (left, right, center), CRLF and multiple tables with stable lines.
5. Treat unsupported block constructs as non-tables rather than emitting guessed findings.

## Configuration additions and defaults

- `table_dialect = "gfm-subset" (default)`
- `table_strict_cells = true (default)`
- `table_enable = true (default)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `doc_sentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Do not treat prose containing pipes but lacking delimiter row as table.
- Pipe characters inside code spans or escaped with backslash do not delimit columns.
- Do not diagnose HTML tables; no HTML table parsing in fast profile.

## Relationship to previously shipped or planned rules

- DS109/DS110 fence mask prevents fake tables in code. Heading/section rules may count table content.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS117` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS117` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
