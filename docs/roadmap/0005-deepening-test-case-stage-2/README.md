# DocSentinel 0005 — Stage 2 archival specification

**Source branch checked:** `yuchdev/DocSentinel@48ddf303b6f9b87c901833b29e8d75ffa3543950` (master). The `0004` **specification** is already committed but its proposed rules were not present in the inspected source modules. This plan builds on the *interfaces* defined for M4, with an explicit rebase gate before implementation.

## What is in this directory

- [Milestone plan](/docs/roadmap/0005-deepening-test-case-stage-2/plan.md) and [live completion status template](/docs/roadmap/0005-deepening-test-case-stage-2/status.md).
- [Implementation contracts](/docs/roadmap/0005-deepening-test-case-stage-2/implementation-contracts.md) and [parser API design](/docs/roadmap/0005-deepening-test-case-stage-2/parser-contract.md).
- [Execution guide](/docs/roadmap/0005-deepening-test-case-stage-2/execution-guide.md) for sequential GitHub agent PRs.
- [Full 191-case Markdown fixture matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md) (185 specified + 6 DS116 close-gate cases, see [status.md](/docs/roadmap/0005-deepening-test-case-stage-2/status.md)) with companion `.csv` and `.json` for catalog verification.
- Fifteen story directories; each has README plus three separately implementable tasks = **45 story/task specs**.

## Scope

Thirteen new `fast` rules: **DS104, DS105, DS106, DS108, DS109, DS110, DS112, DS113, DS114, DS115, DS116, DS117, DS118**. Grouping is structural Markdown, refs/navigation/path, documentation governance. No new AI / heavy NLP runtime dependencies.

There are **96 CLEAN**, **85 FINDING**, **4 ERROR** asset scenarios, with at least three clean and three findings per rule. Every required test case will ultimately live at `tests/assets/dsNNN/{slug}/` as real Markdown text; **those assets and actual code are not included in this spec archive**.

Extract the archive at repository root, then implement Story 01.0, then stories in the plan's dependency order. Update the main `docs/roadmap/README.md` milestone table as a separate implementation/documentation task; do not silently overwrite that file from this archive.
