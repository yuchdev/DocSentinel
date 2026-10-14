# Story 01.0 — Shared foundations and fixture enforcement

**Milestone:** [0004 — Deepening Test Cases](/docs/roadmap/0004-deepening-test-cases/plan.md)

## Goal

Establish a stable analyzer/context API, honest partial coverage reporting, source/Markdown indexing utilities, safe deep rule capability gating, and automated enforcement of the user's fixture shape before any of the 12 rule stories merge.

## Tasks

| # | Task | Deliverable |
|---|---|---|
| 01 | [Normalize analyzer and configuration dispatch](/docs/roadmap/0004-deepening-test-cases/01.0-shared-foundations-and-fixtures/01-analyzer-context-and-config.md) | Compatible Config dispatch, explicit changed_paths context, no regression |
| 02 | [Enforce Markdown asset directories](/docs/roadmap/0004-deepening-test-cases/01.0-shared-foundations-and-fixtures/02-fixture-catalog-and-validation.md) | Fixture matrix test, 2–4-word slug validation, exact per-rule coverage assertions |
| 03 | [Per-rule readiness and execution status](/docs/roadmap/0004-deepening-test-cases/01.0-shared-foundations-and-fixtures/03-readiness-and-deep-capabilities.md) | Honest pending/error semantics; model-free DS302/DS316 under deep opt-in |

## Dependencies

Must land **before** any rule story, even if rule implementation can be developed on a branch in parallel. Existing 0001/0002/0003 regression suites form the compatibility bar.

## Outcomes

- All three profiles remain exact and existing detectors retain API behavior.
- No new rule can be merged with only mock/unit tests and no named Markdown fixture cases.
- Deep capability checks are rule-selective; no global model loading for DS302/DS316-only scans.
- The fixture validator catches missing/sloppy/unused directories, but never scans assets as real project documentation.
