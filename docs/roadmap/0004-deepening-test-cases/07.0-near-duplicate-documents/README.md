# Story 07.0 — DS208: Near duplicate documents

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `standard` · **Default severity:** `warning`

## Objective

Surface whole-document near duplicates rather than mere repeated paragraphs or headings.

**Detector:** `src/docsentinel/detectors/standard/documents.py`  
**Inputs:** Whole-doc normalized Markdown prose, document vectors  
**Dependency / reuse:** Reuse standard corpus vectorizer helpers carefully; document-level aggregation may require a separate vectorizer.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS208 detector](/docs/roadmap/0004-deepening-test-cases/07.0-near-duplicate-documents/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS208 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/07.0-near-duplicate-documents/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/07.0-near-duplicate-documents/03-integration-and-verification.md) | `tests/integration/test_detectors_documents_ds208.py`, `tests/unit/test_document_similarity_ds208.py`, public/CLI assertions |

## Rule semantics

Compute similarity over meaningful body text after stripping boilerplate/code/frontmatter/navigation where supported. Require minimum content, compare only distinct Markdown documents, report pair once at later document. Exclude re-exported and generated documents by configured patterns.

## Non-goal and false-positive boundary

Two distinct manuals sharing navigation boilerplate must not be flagged solely for template similarity.

## Test coverage contract

- **8** expected-clean cases, **5** expected-findings cases, **0** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds208/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS208` in `standard`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `standard` and other profile tests remain green; no unexpected work starts on `fast` scan.
