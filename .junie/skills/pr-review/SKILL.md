---
name: pr-review
description: Produce one merge verdict by running feature and security review in parallel for a PR, branch, or working-tree diff.
---

# Unified PR review

Resolve the requested PR or branch diff; when no target is supplied, use the working-tree diff.
Capture changed files and the review boundary. Spawn `feature-reviewer` and `security-auditor` in
parallel with that same scope, then wait for both.

Synthesize one report with feature verdict and blocking issues, security verdict and findings,
deduplicated combined blockers, non-blocking suggestions, and one merge verdict:

- Critical security finding: `BLOCK`.
- Any feature blocker: `REQUEST_CHANGES`.
- Both complete with no blocker: `APPROVE`.
- Either required reviewer fails or times out: `REQUEST_CHANGES`, naming the missing review.

Post a PR comment only when the user explicitly requests it and the PR is known. Never approve an
incomplete review.