# Story 05.0 — DS205: Terminology consistency

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `standard` · **Default severity:** `warning`

## Objective

Enforce an explicit canonical terminology dictionary, with case-aware aliases, scoped exclusions, and minimal false positives.

**Detector:** `src/docsentinel/detectors/standard/terminology.py`  
**Inputs:** Markdown visible prose, configured terminology file containing canonical term and aliases  
**Dependency / reuse:** May reuse DS119 masking; do not load NLP/embedding model. Dictionary is simple TOML in standalone file.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS205 detector](/docs/roadmap/0004-deepening-test-cases/05.0-terminology-consistency/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS205 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/05.0-terminology-consistency/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/05.0-terminology-consistency/03-integration-and-verification.md) | `tests/integration/test_detectors_terminology_ds205.py`, `tests/unit/test_terminology_dictionary_ds205.py`, public/CLI assertions |

## Rule semantics

A violation requires an explicit mapping from an alias to a canonical term; no automatic semantic synonym inference. Honor token boundaries, plural/case policy, Markdown link labels vs destinations, and allow legitimate quotations/code. Dictionary entries must be unambiguous.

## Non-goal and false-positive boundary

“translation chain” and “translation pipeline” are interchangeable only when the project has explicitly declared them so.

## Test coverage contract

- **6** expected-clean cases, **5** expected-findings cases, **2** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds205/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS205` in `standard`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `standard` and other profile tests remain green; no unexpected work starts on `fast` scan.
