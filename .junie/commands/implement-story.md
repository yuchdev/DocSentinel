---
description: Drive one decomposed roadmap story to completion, one task at a time, with verification and review gates.
allowPromptArgument: true
---

# Implement a roadmap story

Target story: `$prompt`

Resolve the target uniquely from the roadmap by explicit milestone/story number, story number, or
case-insensitive title. Stop for clarification on zero or multiple matches. Read the milestone status,
story README task table, and only the current pending task specification; a completed story is
verified, not rebuilt.

Process exactly one task as the atomic unit before recording progress:

1. Prefer an in-progress task, otherwise the first not-started task.
2. Delegate design, Python, tests, security, and docs to the matching `.junie/agents` specialist.
   Give agents paths and concise scope, not pasted file bodies. Run independent units in parallel.
3. For auth, secrets, integrations, or untrusted-input parsing, require `security-auditor` before
   implementation; a critical finding stops the workflow for human approval.
4. Run task-scoped tests and style checks, fixing failures without weakening gates.
5. Run `verify-task`. Retry one implementation round on FAIL; preserve PARTIAL deviations for review.
6. Run `test-gap` always, `dep-audit` when dependency manifests changed, `secret-scan` for sensitive
   surfaces, and `link-check` when docs or public APIs changed.
7. Change only the task's README status row and continue with the next task.

When core story work is complete, run the repository's full test gate, require `pr-review` approval,
update the milestone status row and story summary, and run `link-check` on roadmap docs. Minor optional
work may be explicitly deferred; major incomplete work keeps the story in progress. Stop on unresolved
test failure, repeated spec FAIL, critical security finding, or unresolved review blockers.

Junie executes this as one command workflow rather than Claude's delayed `ScheduleWakeup` loop. Keep
a compact in-session task cursor and continue until the story is complete or a stop condition occurs.