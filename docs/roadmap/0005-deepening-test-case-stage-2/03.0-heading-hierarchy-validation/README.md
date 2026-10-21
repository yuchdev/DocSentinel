# Story 03.0 — Heading hierarchy and section levels (`DS105`)

**Profile:** `fast` · **Default severity:** `warning` · **Rule module proposal:** `src/docsentinel/detectors/headings.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS105` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/03.0-heading-hierarchy-validation/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/03.0-heading-hierarchy-validation/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/03.0-heading-hierarchy-validation/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Collect ATX heading tokens and supported setext headings once from shared Markdown block scanner; each token retains source line and level.
- Flag level jumps larger than one relative to preceding actual heading; first heading must match policy unless exempt.
- Headers inside code, comments, HTML blocks, or YAML frontmatter are not heading tokens.
- Evaluate each document independently; line uses offending heading, not predecessor.
- Multiple H1s are permitted by default; optional policy warns on subsequent H1s.

## Responsibility boundaries

- Use same heading scanner as DS104 and DS106; keep DS101 generated-anchor behavior unchanged.

## Scenario summary

- **14** independent `tests/assets/ds105/{2–4-word-scenario}/` directories: 9 CLEAN; 5 FINDING; 0 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/03.0-heading-hierarchy-validation/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
