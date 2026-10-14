# Story 10.0 — DS218: CLI option synchronization

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `standard` · **Default severity:** `error`

## Objective

Compare an explicitly mapped argparse CLI contract with its documented options and literal defaults.

**Detector:** `src/docsentinel/detectors/standard/cli_sync.py`  
**Inputs:** Python argparse AST, selected Markdown CLI reference sections, explicit command mapping  
**Dependency / reuse:** Use AST and DS216 source-index utilities; avoid code imports.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS218 detector](/docs/roadmap/0004-deepening-test-cases/10.0-cli-option-synchronization/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS218 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/10.0-cli-option-synchronization/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/10.0-cli-option-synchronization/03-integration-and-verification.md) | `tests/integration/test_detectors_cli_sync_ds218.py`, `tests/unit/test_argparse_index_ds218.py`, public/CLI assertions |

## Rule semantics

Parse `ArgumentParser.add_argument` literals, aliases, store_true/store_false, subparser scopes where statically evident. Do not execute script or import argparse CLI. Recognize option reference tables and specially marked command snippets; avoid mistaking flags in arbitrary shell examples for reference claims.

## Non-goal and false-positive boundary

Only recognized argparse syntax is supported initially; Click/Typer adapters require separate work and tests.

## Test coverage contract

- **8** expected-clean cases, **3** expected-findings cases, **2** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds218/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS218` in `standard`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `standard` and other profile tests remain green; no unexpected work starts on `fast` scan.
