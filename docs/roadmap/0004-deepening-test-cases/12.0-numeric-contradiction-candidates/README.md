# Story 12.0 — DS302: Numeric contradiction candidates

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `deep` · **Default severity:** `warning`

## Objective

Extract numeric claims with explicit subject/property/scope and identify candidate value or range conflicts across Markdown documents, without relying on an LLM.

**Detector:** `src/docsentinel/detectors/numeric_claims.py`  
**Inputs:** Visible Markdown sentences and tables containing comparable numeric assertions, optional scope annotation  
**Dependency / reuse:** Pure Python extraction preferred; share context with DS301 only where safe. DS302 must work without downloading spaCy when selected alone under deep confirmation.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS302 detector](/docs/roadmap/0004-deepening-test-cases/12.0-numeric-contradiction-candidates/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS302 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/12.0-numeric-contradiction-candidates/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/12.0-numeric-contradiction-candidates/03-integration-and-verification.md) | `tests/integration/test_detectors_numeric_ds302.py`, `tests/unit/test_numeric_claims_ds302.py`, public/CLI assertions |

## Rule semantics

Normalize integers/decimals, common spelled numbers and recognized units only when dimensionally compatible. Match canonical subject + property + scope (version/environment/default-vs-max). Range contradictions require disjoint constraints; matching values are clean. Never compare bare numbers without matched referents.

## Non-goal and false-positive boundary

Every result is a candidate, not a proven fact; exclude equations, examples, years and code when not tied to a clear subject/property.

## Test coverage contract

- **10** expected-clean cases, **5** expected-findings cases, **1** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds302/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS302` in `deep`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `deep` and other profile tests remain green; no unexpected work starts on `fast` scan.
