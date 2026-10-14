# Story 03.0 — DS111: Required document metadata

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `fast` · **Default severity:** `error`

## Objective

Validate explicitly required frontmatter fields for selected document path groups without mandating frontmatter on every README in a generic repository.

**Detector:** `src/docsentinel/detectors/metadata.py`  
**Inputs:** Markdown frontmatter, path selectors, required keys  
**Dependency / reuse:** Stdlib re and pathlib; no PyYAML in fast. Read through same Markdown loading conventions.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS111 detector](/docs/roadmap/0004-deepening-test-cases/03.0-required-document-metadata/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS111 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/03.0-required-document-metadata/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/03.0-required-document-metadata/03-integration-and-verification.md) | `tests/integration/test_detectors_metadata_ds111.py`, `tests/unit/test_frontmatter_ds111.py`, public/CLI assertions |

## Rule semantics

Only apply to configured path patterns. Recognize leading YAML-style --- scalar keys using a deliberately limited stdlib parser; distinguish missing key, empty value, duplicated key and valid zero/false. Do not advertise full YAML compatibility. Unsupported syntax must produce clear unsupported-input handling rather than silent success.

## Non-goal and false-positive boundary

Do not mistake `---` used as a thematic rule halfway through prose for a frontmatter block. Do not treat `0` or `false` as empty.

## Test coverage contract

- **6** expected-clean cases, **6** expected-findings cases, **1** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds111/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS111` in `fast`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `fast` and other profile tests remain green; no unexpected work starts on `fast` scan.
