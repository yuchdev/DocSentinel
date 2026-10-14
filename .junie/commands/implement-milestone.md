---
description: Research and deliver a roadmap milestone story-by-story and task-by-task, preserving dependency order and milestone exit gates.
allowPromptArgument: true
---

# Implement a roadmap milestone

Target milestone: `$prompt`

Resolve exactly one milestone by number, slug, or title. Require `plan.md`; stop rather than inventing
an unspecified milestone. On cold start, delegate concise reconnaissance of the plan, status, story
dependency graph, shared contracts, security markers, exit gates, and as-built artifacts.

Before implementation:

- Create a missing status table from the plan.
- Treat complete rows as provisional until spot-verified.
- Detect absent, matching, and materially divergent existing implementations. Verify matching work;
  pause on contract-level divergence and ask the user whether to follow the spec or ratify reality.
- Audit that every planned story has a README and task specs and every shared contract/exit gate is
  covered. Ask `app-architect` to fill clear decomposition gaps; ask the user about new scope.
- Record decisions and gap dispositions in milestone status.

Select the first dependency-ready story and execute the `implement-story` algorithm one task at a
time. Add the milestone's shared-contract anchors to each specialist brief. After every task, update
only the task row and that story's milestone progress cell. At story close, run its full gates,
record delivered work, tests, deferrals, and any spec reconciliation, then advance dependencies.

At milestone close, run documented exit gates once, including locked dependency sync, pytest with the
DocSentinel plugin when required, self-scan, build, honesty review, and `link-check` for roadmap docs.
Update status and the roadmap index only after all gates pass. Stop on a cycle, unresolved divergence,
story-level blocker, or failed exit gate.

Junie has no repository-discovered delayed wakeup equivalent, so retain the compact cursor in the
current command run and continue until completion or a stop condition; do not fabricate scheduler
state under `.claude/`.