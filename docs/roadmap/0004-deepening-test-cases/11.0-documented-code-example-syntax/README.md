# Story 11.0 — DS219: Documented code example syntax

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `standard` · **Default severity:** `error`

## Objective

Validate explicitly designated complete fenced code samples as syntax, without executing examples or mistaking illustrative fragments for full programs.

**Detector:** `src/docsentinel/detectors/standard/examples.py`  
**Inputs:** Markdown fenced code blocks and optional check=syntax info attribute  
**Dependency / reuse:** Python standard library parsers; standard lazy loader remains intact; PyYAML is not required.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS219 detector](/docs/roadmap/0004-deepening-test-cases/11.0-documented-code-example-syntax/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS219 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/11.0-documented-code-example-syntax/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/11.0-documented-code-example-syntax/03-integration-and-verification.md) | `tests/integration/test_detectors_examples_ds219.py`, `tests/unit/test_fence_parser_ds219.py`, public/CLI assertions |

## Rule semantics

Use only safe parsers (ast.parse for Python, json.loads, tomllib.loads). Default validate fences explicitly marked `check=syntax`; do not run code. Unsupported languages, partial snippets or REPL transcripts produce explicit skipped/unverified status. Preserve fence start line and language label.

## Non-goal and false-positive boundary

No `exec`, `eval`, subprocess or shell invocation; this rule cannot prove runtime correctness.

## Test coverage contract

- **8** expected-clean cases, **4** expected-findings cases, **2** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds219/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS219` in `standard`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `standard` and other profile tests remain green; no unexpected work starts on `fast` scan.
