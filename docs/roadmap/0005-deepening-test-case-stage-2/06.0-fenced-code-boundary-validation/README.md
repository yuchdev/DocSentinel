# Story 06.0 — Malformed or unclosed fenced code blocks (`DS109`)

**Profile:** `fast` · **Default severity:** `error` · **Rule module proposal:** `src/docsentinel/detectors/fences.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS109` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/06.0-fenced-code-boundary-validation/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/06.0-fenced-code-boundary-validation/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/06.0-fenced-code-boundary-validation/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Scan backtick and tilde fences with opener length >=3, indent <=3 and matching closing character.
- Closing run must be at least opener length and may contain only permitted trailing whitespace.
- Backtick opener info string may not contain backticks; reject malformed opener if identified as intentional fence.
- Preserve exact line ranges for opening and EOF errors; do not treat shorter closure as completion.
- Offer shared fence mask to other DS1xx analyzers; test linear-time behavior on very long or adversarial fenced input.

## Responsibility boundaries

- DS101–103 already mask fences; migration must not regress inherited stripping semantics without explicit review.
- DS110 consumes parsed fence opener info without re-parsing differently.

## Scenario summary

- **14** independent `tests/assets/ds109/{2–4-word-scenario}/` directories: 7 CLEAN; 7 FINDING; 0 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/06.0-fenced-code-boundary-validation/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
