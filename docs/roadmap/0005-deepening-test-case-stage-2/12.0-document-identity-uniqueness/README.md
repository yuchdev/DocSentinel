# Story 12.0 — Duplicate stable document identifiers (`DS114`)

**Profile:** `fast` · **Default severity:** `error` · **Rule module proposal:** `src/docsentinel/detectors/document_ids.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS114` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/12.0-document-identity-uniqueness/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/12.0-document-identity-uniqueness/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/12.0-document-identity-uniqueness/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Read only explicitly configured frontmatter identifiers using DS111-compatible scalar frontmatter parser.
- Normalize values for whitespace and Unicode NFC; case sensitivity follows explicit config.
- Detect collisions across multiple documents and attribute to later sorted document path with reference to original.
- Do not treat repeated prose titles or headings as stable document IDs without explicit opt-in.
- Malformed or absent frontmatter must not be silently conflated with duplicate IDs; delegate malformed metadata to DS111.

## Responsibility boundaries

- DS111 validates required metadata and duplicate frontmatter keys; DS114 validates corpus-wide uniqueness.
- DS104 local HTML anchor identity is separate namespace.

## Scenario summary

- **14** independent `tests/assets/ds114/{2–4-word-scenario}/` directories: 7 CLEAN; 6 FINDING; 1 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/12.0-document-identity-uniqueness/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
