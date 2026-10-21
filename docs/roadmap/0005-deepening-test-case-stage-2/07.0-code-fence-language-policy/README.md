# Story 07.0 — Missing language labels on code fences (`DS110`)

**Profile:** `fast` · **Default severity:** `warning` · **Rule module proposal:** `src/docsentinel/detectors/fence_languages.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS110` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/07.0-code-fence-language-policy/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/07.0-code-fence-language-policy/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/07.0-code-fence-language-policy/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Reuse DS109 fence scan to enumerate valid opening fences and info strings.
- When enabled, report nonempty meaningful fenced code blocks with empty language marker.
- Info first token names the language, e.g. python, bash, text, console, diff; treat whitespace-only info as absent.
- Do not execute examples or validate syntax here (DS219 in M4).
- Malformed fences are owned by DS109: DS110 must avoid double-reporting a fence never successfully closed.

## Responsibility boundaries

- DS109 supplies validity and spans. DS219 handles code syntax; DS110 handles only fence metadata.

## Scenario summary

- **14** independent `tests/assets/ds110/{2–4-word-scenario}/` directories: 8 CLEAN; 6 FINDING; 0 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/07.0-code-fence-language-policy/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
