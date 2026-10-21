# Story 09.0 — Declared documentation navigation integrity (`DS112`)

**Profile:** `fast` · **Default severity:** `warning` · **Rule module proposal:** `src/docsentinel/detectors/navigation.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS112` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/09.0-configured-navigation-integrity/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/09.0-configured-navigation-integrity/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/09.0-configured-navigation-integrity/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Read only configured navigation index Markdown documents; inspect actual local links in list items (and optionally configured nav sections).
- Check required targets appear exactly once when navigation_required is provided, and duplicates are reported once each at later link.
- Detect nonexistent local destinations in designated navigation, distinguishing them from ordinary prose links.
- Use DS107 graph for shared normalized path resolution when M4 landed; do not infer navigation by every Markdown hyperlink.
- Missing/unreadable configured index is a clear config/readiness error, not silent clean result; never follow symlinks beyond root.

## Responsibility boundaries

- DS101 validates general links; DS112 checks only declared navigation contract. DS107 handles graph reachability from index, not explicit required inclusion.

## Scenario summary

- **14** independent `tests/assets/ds112/{2–4-word-scenario}/` directories: 8 CLEAN; 5 FINDING; 1 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/09.0-configured-navigation-integrity/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
