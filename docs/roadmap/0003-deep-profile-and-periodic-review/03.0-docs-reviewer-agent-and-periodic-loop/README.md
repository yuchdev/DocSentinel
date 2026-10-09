# Story 03.0 - `docs-reviewer` Agent & Periodic Review Loop

The one requirement in `deep`'s charter that **cannot** be a code detector. `DS301` (Story 02.0)
produces a shortlist of *candidate* contradictions, but deciding which candidates are real - and
catching doc-vs-code *behavioral* drift (a doc describes one behavior, the code implements another,
distinct from Milestone 0002's `docsig` *signature*-only check) - requires reading and understanding
both sides. That is agent work, not regex or model-triple work.

This story adds a `docs-reviewer` agent (sibling of the existing
[`background-reviewer`](/.claude/agents/background-reviewer.md), whose tool-profile and
dated-report-to-`docs/reviews/` convention it mirrors) and a periodic `deep-review` loop that runs
the confirmed `deep` scan plus the agent on a **cadence** - weekly or on-demand - deliberately
*not* per-commit, because `deep` is slow, heuristic, and advisory. These are `.claude/` markdown
artifacts, not Python, so the tasks below adapt the usual task shape: no "Symbols / fields" code
table, replaced by the agent's responsibilities / tool-profile and the loop's step algorithm.

## Tasks

| # | Task | Output |
|---|------|--------|
| 01 | [`docs-reviewer` agent definition](01-docs-reviewer-agent-definition.md) | `.claude/agents/docs-reviewer.md`: triage `DS301` candidates + behavioral-drift review, dated report to `docs/reviews/` |
| 02 | [`deep-review` periodic loop](02-deep-review-periodic-loop.md) | `.claude/loops/deep-review.md`: weekly / on-demand confirmed deep scan + `docs-reviewer`, `ScheduleWakeup` self-reschedule |

01 defines the agent the loop drives; 02 drives it on a cadence. 02 depends on 01 existing and on
Story 01.0 (the confirmed-deep invocation the loop issues) and Story 02.0 (`DS301`, the candidate
source the loop captures). Neither task touches `src/` or `tests/`.
