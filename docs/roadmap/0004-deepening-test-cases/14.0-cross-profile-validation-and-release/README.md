# Story 14.0 — Cross-profile validation and release gate

## Goal

Verify that the 12 independently shipped rules compose cleanly with the three existing exact profiles and the repository's baseline/CLI/CI conventions. This story is the milestone's integration gate, not a substitute for individual rule tests.

## Tasks

| # | Task | Deliverable |
|---|---|---|
| 01 | [Full fixture coverage audit](/docs/roadmap/0004-deepening-test-cases/14.0-cross-profile-validation-and-release/01-fixture-coverage-audit.md) | 3+ positive/negative and every edge fixture proven for all 12 rules |
| 02 | [Profiles, CLI, reports and CI](/docs/roadmap/0004-deepening-test-cases/14.0-cross-profile-validation-and-release/02-profiles-cli-and-ci.md) | Real end-to-end test matrix across all profiles, selected rules and degraded readiness |
| 03 | [Docs, security and release acceptance](/docs/roadmap/0004-deepening-test-cases/14.0-cross-profile-validation-and-release/03-documentation-and-handoff.md) | Rule catalog, security audit, performance budgets, status update |

Depends on Stories 01.0–13.0. Mark milestone complete only when every rule and every named fixture is present with named integration assertions.
