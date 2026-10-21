# Story 11.0 — Path traversal outside documentation root (`DS116`)

**Profile:** `fast` · **Default severity:** `error` · **Rule module proposal:** `src/docsentinel/detectors/path_boundaries.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS116` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/11.0-repository-root-path-boundaries/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/11.0-repository-root-path-boundaries/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/11.0-repository-root-path-boundaries/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Normalize local target paths lexically, then reject any `..` that resolves outside supplied root.
- Check both decoded and raw path; decode percent-escaping once to prevent %2e%2e root traversal bypass.
- Reject absolute OS paths, drive-letter paths and UNC in locally interpreted documentation references unless explicitly treated as external literal examples.
- Reject symlink traversal out of root using a safe, non-following containment check; never read outside target contents.
- Validate Markdown links, image sources, explicitly referenced local assets and path-like code spans through shared resolver without changing DS101/DS103 public behavior.

## Responsibility boundaries

- DS101/DS103 existence checks should not read an escaped target; DS116 owns explicit policy violation report.
- DS113 asset existence and DS112 nav resolution reuse safe resolver.

## Scenario summary

- **15** independent `tests/assets/ds116/{2–4-word-scenario}/` directories: 5 CLEAN; 10 FINDING; 0 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/11.0-repository-root-path-boundaries/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
