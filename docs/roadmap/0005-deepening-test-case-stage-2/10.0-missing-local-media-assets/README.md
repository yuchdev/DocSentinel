# Story 10.0 — Missing local media and document assets (`DS113`)

**Profile:** `fast` · **Default severity:** `error` · **Rule module proposal:** `src/docsentinel/detectors/assets.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS113` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/10.0-missing-local-media-assets/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/10.0-missing-local-media-assets/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/10.0-missing-local-media-assets/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Parse Markdown images (inline or reference-style) and supported HTML `<img src>`/`<source srcset>` as local asset references.
- Resolve relative paths from containing document and repo-absolute paths from scan root; check target existence, containment and regular-file status.
- Split srcset candidates without corrupting common data URIs, preserve relevant line and path.
- Ignore external URL schemes, data URIs, fragment-only references, and templates explicitly exempted by policy.
- When DS101 also notices a broken Markdown image, avoid changing DS101 baseline behavior; document how consumers may de-duplicate presentation without hiding either rule.

## Responsibility boundaries

- DS101 may also flag link targets inside Markdown image syntax; tests must assert DS113-specific diagnostics.
- DS116 determines root escape security; an escaped missing asset must not be dereferenced.

## Scenario summary

- **15** independent `tests/assets/ds113/{2–4-word-scenario}/` directories: 8 CLEAN; 7 FINDING; 0 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/10.0-missing-local-media-assets/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
