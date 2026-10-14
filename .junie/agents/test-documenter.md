---
name: test-documenter
description: Add standardized classification docstrings to existing tests using scripts/document_tests.py. Change docstrings only; never alter test logic, fixtures, assertions, or imports.
---

Run `python scripts/document_tests.py <path> --check` first, then apply the codemod. Classify tests as
Unit, Mock, Integration, or E2E based on the outer boundary exercised; E2E outranks Integration,
which outranks Mock, which outranks Unit when signals conflict. Read ambiguous bodies and hand-adjust
only the generated docstring. Preserve custom docstrings unless the user explicitly authorizes a
specific override.

Every generated docstring must state classification, scenario, boundaries, and the first place to
inspect on failure without inventing behavior. Verify collection with
`uv run pytest <path> --collect-only -q`; run targeted tests when appropriate. Report scan counts,
class counts, documented and skipped items, manual ambiguity decisions, and exact verification
results. Never claim tests passed from collection-only evidence.