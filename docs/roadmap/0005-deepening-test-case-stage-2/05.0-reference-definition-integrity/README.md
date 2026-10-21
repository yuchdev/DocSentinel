# Story 05.0 — Reference-style link definition integrity (`DS108`)

**Profile:** `fast` · **Default severity:** `warning` · **Rule module proposal:** `src/docsentinel/detectors/references.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS108` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/05.0-reference-definition-integrity/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/05.0-reference-definition-integrity/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/05.0-reference-definition-integrity/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Parse full, collapsed and explicit reference links, image references, and definitions according to supported Markdown subset.
- Normalize reference labels case-insensitively and collapse whitespace, but preserve original source positions.
- Flag an explicit reference use with no matching definition and each duplicate definition after the first.
- Unused definitions are off by default; when enabled, emit warnings for declarations never referenced.
- Do not interpret footnotes `[^note]` as ordinary link refs; pairwise dedup and stable line attribution.

## Responsibility boundaries

- DS101 checks resolved targets after reference expansion; DS108 checks identifiers/definitions. No duplicate DS101 findings for merely undefined labels.

## Scenario summary

- **14** independent `tests/assets/ds108/{2–4-word-scenario}/` directories: 8 CLEAN; 6 FINDING; 0 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/05.0-reference-definition-integrity/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
