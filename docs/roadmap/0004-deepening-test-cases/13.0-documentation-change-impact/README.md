# Story 13.0 — DS316: Documentation change impact

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `deep` · **Default severity:** `warning`

## Objective

Report documents plausibly affected by an explicitly supplied set of changed local source/config/schema files using traceable references, without semantic hallucination.

**Detector:** `src/docsentinel/detectors/impact.py`  
**Inputs:** Explicit changed-files list from CLI/API, document-to-source reference graph, optional mapping  
**Dependency / reuse:** Reuse DS107 graph and DS216 code path/symbol index where installed; avoid model requirement when DS316 is the only selected deep rule.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS316 detector](/docs/roadmap/0004-deepening-test-cases/13.0-documentation-change-impact/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS316 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/13.0-documentation-change-impact/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/13.0-documentation-change-impact/03-integration-and-verification.md) | `tests/integration/test_detectors_impact_ds316.py`, `tests/unit/test_impact_graph_ds316.py`, public/CLI assertions |

## Rule semantics

No inferred git diff or network calls. A document is impacted only via direct local source path/symbol mapping or configured dependency edges. Missing change set yields not evaluated, not a clean assertion. Sources outside root are rejected; duplicate changed paths and cycles are normalized.

## Non-goal and false-positive boundary

Do not flag a document as stale; report “review recommended because X changed”, with explicit evidence.

## Test coverage contract

- **5** expected-clean cases, **8** expected-findings cases, **2** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds316/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS316` in `deep`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `deep` and other profile tests remain green; no unexpected work starts on `fast` scan.
