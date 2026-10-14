# Story 02.0 — DS107: Orphan documentation

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `fast` · **Default severity:** `warning`

## Objective

Build a directed graph of local Markdown links from configured entry points; report documents unreachable through navigation, not merely files without inbound references.

**Detector:** `src/docsentinel/detectors/orphans.py`  
**Inputs:** Markdown inventory, configured entrypoint paths, local Markdown link graph  
**Dependency / reuse:** Reuse DS101 path/anchor target resolution where safe. Introduce a small graph helper used later by DS316.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS107 detector](/docs/roadmap/0004-deepening-test-cases/02.0-orphan-documentation/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS107 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/02.0-orphan-documentation/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/02.0-orphan-documentation/03-integration-and-verification.md) | `tests/integration/test_detectors_orphans_ds107.py`, `tests/unit/test_navigation_graph_ds107.py`, public/CLI assertions |

## Rule semantics

Explicit entrypoints only; root-relative paths resolve against scan root, relative paths against originating document; follow links transitively; ignore excluded docs, external links, fragments, code spans/fences and symlink escapes. If no usable entrypoint exists, produce an explicit not-evaluated state rather than labelling the entire tree orphaned.

## Non-goal and false-positive boundary

Do not mistake an unlinked source-code file for an orphan document. Missing entrypoints are not an excuse to mark all files orphaned.

## Test coverage contract

- **5** expected-clean cases, **8** expected-findings cases, **1** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds107/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS107` in `fast`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `fast` and other profile tests remain green; no unexpected work starts on `fast` scan.
