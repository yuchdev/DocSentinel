# Story 04.0 — Empty or contentless sections (`DS106`)

**Profile:** `fast` · **Default severity:** `warning` · **Rule module proposal:** `src/docsentinel/detectors/sections.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS106` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/04.0-contentless-section-detection/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/04.0-contentless-section-detection/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/04.0-contentless-section-detection/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Build heading ranges; for each leaf section, inspect visible non-whitespace text and supported blocks between heading and next heading.
- Skip HTML comments, fenced and indented empty code blocks, separators and blank lines; a nonempty fenced code block or table counts as content.
- Structural parents with only nested child sections are not empty by default.
- Flag the section heading location only once; trailing heading at EOF is a finding.
- Do not confuse an empty frontmatter record with a body section.

## Responsibility boundaries

- DS111 validates metadata; DS119 finds markers; DS106 checks visible section content regardless of both.

## Scenario summary

- **14** independent `tests/assets/ds106/{2–4-word-scenario}/` directories: 7 CLEAN; 7 FINDING; 0 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/04.0-contentless-section-detection/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
