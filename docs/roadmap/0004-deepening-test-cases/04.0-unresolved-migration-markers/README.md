# Story 04.0 — DS119: Unresolved migration markers

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `fast` · **Default severity:** `warning`

## Objective

Identify visible editorial TODO/TBD/FIXME/PLACEHOLDER markers left in publishable prose, without guessing whether a task is old from file age.

**Detector:** `src/docsentinel/detectors/markers.py`  
**Inputs:** Markdown text outside code, configurable marker vocabulary and exemptions  
**Dependency / reuse:** Reuse/extend lightweight Markdown masking without adding runtime dependencies.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS119 detector](/docs/roadmap/0004-deepening-test-cases/04.0-unresolved-migration-markers/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS119 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/04.0-unresolved-migration-markers/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/04.0-unresolved-migration-markers/03-integration-and-verification.md) | `tests/integration/test_detectors_markers_ds119.py`, `tests/unit/test_marker_matching_ds119.py`, public/CLI assertions |

## Rule semantics

Match distinct tokens with punctuation and optional owner syntax; ignore fenced code, inline code, URLs and escaped literals. Existing DS102 owns HTML comments; avoid double-reporting TODO within comments unless explicitly configured.

## Non-goal and false-positive boundary

“Stale” here means still unresolved in publishable text, not older than a guessed time horizon.

## Test coverage contract

- **7** expected-clean cases, **6** expected-findings cases, **0** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds119/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS119` in `fast`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `fast` and other profile tests remain green; no unexpected work starts on `fast` scan.
