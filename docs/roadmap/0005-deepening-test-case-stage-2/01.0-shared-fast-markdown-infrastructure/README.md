# Story 01.0 — shared stdlib Markdown scanner, policy config and fixture contracts

**Category:** infrastructure / prerequisite. **Depends on:** M1–M3, verify M4's actual merge state.

## Goal

Deliver the smallest reusable **standard-library-only** parsing and safe reference context for the thirteen DS1xx rules, without overwriting interfaces created by the previous milestone.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/01.0-shared-fast-markdown-infrastructure/01-standard-library-markdown-block-scanner.md) | standard library markdown block scanner |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/01.0-shared-fast-markdown-infrastructure/02-safe-reference-and-policy-config.md) | safe reference and policy config |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/01.0-shared-fast-markdown-infrastructure/03-fixture-manifest-and-runner.md) | fixture manifest and runner |

## Definition of done

- Scanner and path resolution cover representative Markdown inputs with one-based line mapping.
- Typed config options are validated without breaking current config precedence or profile exactness.
- Fixture manifest verification actively fails on absent or untested scenarios.
- Old DS101–103 tests and existing optional profile imports keep working.
