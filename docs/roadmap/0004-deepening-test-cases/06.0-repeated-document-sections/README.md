# Story 06.0 — DS207: Repeated document sections

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `standard` · **Default severity:** `warning`

## Objective

Detect genuinely duplicated multi-paragraph sections, preserving heading provenance and distinguishing the rule from DS202 paragraph similarity.

**Detector:** `src/docsentinel/detectors/standard/sections.py`  
**Inputs:** Heading-delimited sections from Markdown documents, document corpus statistics  
**Dependency / reuse:** Reuse DS202 TF-IDF normalization/indexing where technically appropriate without changing DS202 thresholds.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS207 detector](/docs/roadmap/0004-deepening-test-cases/06.0-repeated-document-sections/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS207 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/06.0-repeated-document-sections/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/06.0-repeated-document-sections/03-integration-and-verification.md) | `tests/integration/test_detectors_sections_ds207.py`, `tests/unit/test_section_similarity_ds207.py`, public/CLI assertions |

## Rule semantics

Normalize prose (not code) across two or more paragraphs; require configurable minimum token count and section length. Compare section contents across different documents by default; flag one later section with earlier provenance; avoid duplicate emitted pairs.

## Non-goal and false-positive boundary

Two short identical headings with different substantive bodies are not duplicate sections.

## Test coverage contract

- **8** expected-clean cases, **5** expected-findings cases, **0** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds207/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS207` in `standard`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `standard` and other profile tests remain green; no unexpected work starts on `fast` scan.
