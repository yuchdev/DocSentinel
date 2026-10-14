# Story 08.0 — DS216: Stale source symbol references

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `standard` · **Default severity:** `error`

## Objective

Find qualified references to known in-repository Python symbols that no longer exist, using AST indexing without executing source code.

**Detector:** `src/docsentinel/detectors/standard/symbols.py`  
**Inputs:** Markdown qualified symbol mentions and source index from configured Python roots  
**Dependency / reuse:** Extend `code_discovery.py` and parse Python AST; share symbol index with DS217/DS218/DS316.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS216 detector](/docs/roadmap/0004-deepening-test-cases/08.0-stale-source-symbol-references/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS216 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/08.0-stale-source-symbol-references/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/08.0-stale-source-symbol-references/03-integration-and-verification.md) | `tests/integration/test_detectors_symbols_ds216.py`, `tests/unit/test_symbol_index_ds216.py`, public/CLI assertions |

## Rule semantics

Only validate symbols demonstrably local through explicit imports/path prefixes or configured module mappings. Parse modules, functions, classes, methods, aliases when statically resolvable. External modules and dynamic attributes are not automatically missing; unsupported claims are omitted with traceable limits.

## Non-goal and false-positive boundary

Do not flag random `Foo.bar` as absent without proving it refers to in-repo Python code.

## Test coverage contract

- **9** expected-clean cases, **3** expected-findings cases, **1** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds216/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS216` in `standard`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `standard` and other profile tests remain green; no unexpected work starts on `fast` scan.
