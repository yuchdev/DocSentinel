---
name: test-gap
description: Analyze test coverage for a path or package and return behavior-focused missing tests ranked by risk and blast radius.
---

# Test-gap analysis

Run the repository's pytest coverage command with `term-missing`, scoped to the requested target when
possible. Give the output and target to `testing-expert` and map every important uncovered branch to
behavior, not merely a line number.

Rank gaps:

- P0: core decisions, untrusted-input parsing, escalation/approval, security and redaction, or
  deduplication whose failure creates false assurance or exposure.
- P1: strategies, orchestration transitions, validation, serialization, and component wiring.
- P2: presentation, non-security logging shape, and low-risk CLI polish.

Within a tier, rank likelihood times reachability. For every P0 item provide path/line range, the
untested behavior, why it matters, and a concrete input-to-expected-outcome test. Report measured
coverage and offer to have `testing-expert` implement P0 tests; do not rank by percentage gain alone.