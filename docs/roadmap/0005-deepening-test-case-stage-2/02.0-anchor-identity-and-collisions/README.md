# Story 02.0 — Conflicting heading and explicit anchors (`DS104`)

**Profile:** `fast` · **Default severity:** `warning` · **Rule module proposal:** `src/docsentinel/detectors/anchors.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS104` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/02.0-anchor-identity-and-collisions/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/02.0-anchor-identity-and-collisions/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/02.0-anchor-identity-and-collisions/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Build anchors with DS101 heading_anchors/slugify rules, preserving generated suffixes; do not issue findings for ordinary repeated headings because GitHub assigns -1, -2 suffixes.
- Index explicit `<a id=...>` and `<a name=...>` plus heading attribute IDs only if documented syntax supported; keep line, spelling and source kind.
- Report repeated explicit identifiers and explicit-vs-generated collisions with stable line, while normal duplicate heading slugs remain valid.
- Distinguish HTML ID case sensitivity and HTML name behavior; do not lowercase literal explicit IDs.
- One finding per offending later identifier in stable document/line order; no global collisions between independent documents.

## Responsibility boundaries

- DS101 owns link resolution, DS104 owns collisions; shared anchor inventory must agree on suffixed headings.
- M4 DS111 may expose frontmatter IDs, but HTML anchors are not document IDs (DS114).

## Scenario summary

- **14** independent `tests/assets/ds104/{2–4-word-scenario}/` directories: 8 CLEAN; 6 FINDING; 0 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/02.0-anchor-identity-and-collisions/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
