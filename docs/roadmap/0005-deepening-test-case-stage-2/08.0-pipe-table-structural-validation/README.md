# Story 08.0 — Malformed GFM pipe-table structure (`DS117`)

**Profile:** `fast` · **Default severity:** `warning` · **Rule module proposal:** `src/docsentinel/detectors/tables.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS117` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/08.0-pipe-table-structural-validation/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/08.0-pipe-table-structural-validation/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/08.0-pipe-table-structural-validation/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Recognize table headers only when followed by a valid GFM delimiter row with separators and optional colons.
- Parse unescaped pipe separators, respecting backslash escapes and backtick code spans; allow optional outer pipes.
- Check header, delimiter and body row logical cell counts consistently; padded empty cells are valid.
- Handle alignment markers (left, right, center), CRLF and multiple tables with stable lines.
- Treat unsupported block constructs as non-tables rather than emitting guessed findings.

## Responsibility boundaries

- DS109/DS110 fence mask prevents fake tables in code. Heading/section rules may count table content.

## Scenario summary

- **15** independent `tests/assets/ds117/{2–4-word-scenario}/` directories: 9 CLEAN; 6 FINDING; 0 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/08.0-pipe-table-structural-validation/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
