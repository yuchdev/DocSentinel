---
name: document-tests
description: Document existing test functions with consistent Unit, Mock, Integration, or E2E docstrings without changing test behavior.
---

# Document tests

Use the requested path, defaulting to `tests/`. First inventory test functions and existing
docstrings. Preserve custom docstrings unless the user explicitly authorizes replacement in named
files.

Classify by the outer boundary exercised:

- Unit: pure logic with no mocks or I/O.
- Mock: one unit with an external collaborator patched or mocked.
- Integration: multiple real components wired together, with external edges controlled.
- E2E: a full CLI, HTTP, browser, or other user-facing entry point.

For each undocumented test, add only a docstring whose title starts `[Class]`, summarizes the verified
behavior, and includes `Scenario`, `Boundaries`, and `On-failure-first-check`. Read ambiguous test
bodies; do not infer from names alone or describe behavior that assertions do not exercise.

The diff must contain docstrings only—no fixture, assertion, import, ordering, or logic changes.
Verify with `uv run pytest <path> --collect-only -q`; for a small scope, also run the tests. Report
test/class counts, changed and preserved docstrings, ambiguity decisions, and exact verification.