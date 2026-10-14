# Story 09.0 — DS217: Configuration key synchronization

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md) · **Profile:** `standard` · **Default severity:** `error`

## Objective

Compare explicitly documented configuration keys and literal defaults against supported live configuration schemas, with evidence mapping and no execution.

**Detector:** `src/docsentinel/detectors/standard/config_sync.py`  
**Inputs:** Markdown config tables/TOML fences, explicit schema mappings, parsed source literals  
**Dependency / reuse:** Use `tomllib` and Python AST plus DS216 symbol index; never import project modules.

## Tasks

| Task | Specification | Deliverables |
|---|---|---|
| 01 | [Implement DS217 detector](/docs/roadmap/0004-deepening-test-cases/09.0-configuration-key-synchronization/01-implement-detector.md) | Rule registration, algorithms, settings, type-safe source handling |
| 02 | [Build DS217 Markdown asset suite](/docs/roadmap/0004-deepening-test-cases/09.0-configuration-key-synchronization/02-markdown-asset-cases.md) | All named Markdown scenarios and companion source files |
| 03 | [Integration and regression tests](/docs/roadmap/0004-deepening-test-cases/09.0-configuration-key-synchronization/03-integration-and-verification.md) | `tests/integration/test_detectors_config_sync_ds217.py`, `tests/unit/test_config_claims_ds217.py`, public/CLI assertions |

## Rule semantics

Require configured mapping between documentation and source. Support TOML literal defaults and Python dataclass/typed class literal defaults in v1; unknown computed/default_factory/env defaults are unverifiable, not mismatches. Separate missing key from unequal documented default; respect versions/scopes and numeric type.

## Non-goal and false-positive boundary

A numeric value in free prose is never presumed to be a config default solely because it resembles a schema value.

## Test coverage contract

- **6** expected-clean cases, **5** expected-findings cases, **2** explicitly pending or unsupported cases; plus remaining special cases classified as pass/fail.
- Every one is an on-disk fixture under `tests/assets/ds217/{two_to_four_word_slug}/` and contains `.md`.
- Read [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) and [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md); new rule cannot pass review without tested assets, not merely unit strings.
- All fixture scenarios listed in Task 02 are **mandatory**; cases with output `clean` may still be edge cases guarding against false positives.

## Completion criteria

- [ ] Tasks 01–03 done; registration contains exactly rule `DS217` in `standard`.
- [ ] All named assets exist, exercise real prose/source declarations, and are test-loaded.
- [ ] All 3+ clean and 3+ finding requirements pass, with exact expected rule ID and locations.
- [ ] At least one CLI/API round-trip, baseline behavior, and deterministic ordering demonstrated.
- [ ] Existing `standard` and other profile tests remain green; no unexpected work starts on `fast` scan.
