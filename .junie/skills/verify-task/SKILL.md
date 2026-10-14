---
name: verify-task
description: Compare an implementation diff with a roadmap task specification through the task-verifier agent before test-gap and PR review.
---

# Verify task compliance

Resolve the supplied spec path directly when it ends in `.md`; otherwise resolve it below
`docs/roadmap/` with `.md`. Stop with an actionable error if it does not exist.

Gather staged and unstaged changed files and diff. If the tree is clean, use the most recent commit
diff and state that scope explicitly. Spawn `task-verifier` with the spec path, changed-file list,
and diff boundary, then return its compliance matrix without softening the verdict.

- PASS: proceed to `test-gap` and `pr-review`.
- PARTIAL: list exact deviations and recommend fixing before merge.
- FAIL: list missing requirements and return them to `python-expert`, then re-run verification.
- Missing/timed-out verifier: verification is incomplete and cannot pass.

Always end with one explicit next step.