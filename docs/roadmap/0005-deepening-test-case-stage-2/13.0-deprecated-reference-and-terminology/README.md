# Story 13.0 — Deprecated names and migrated references (`DS115`)

**Profile:** `fast` · **Default severity:** `warning` · **Rule module proposal:** `src/docsentinel/detectors/deprecated_refs.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS115` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/13.0-deprecated-reference-and-terminology/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/13.0-deprecated-reference-and-terminology/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/13.0-deprecated-reference-and-terminology/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Load a versioned, root-contained TOML mapping with explicit `[[replacement]]` entries (old, new, kind, optional scope); validate conflicting keys and target types.
- Match obsolete path references and identifiers only where explicit mapping applies; support Markdown links, path-like code spans and prose terms per kind.
- Use token boundaries rather than naive substring replacement: old `APIv1` must not match `APIv10`.
- Exclude code fences and quoted historical migration examples by explicit exemption policy, not by guessing date semantics.
- Emit old token, suggested replacement and mapping provenance, without modifying source automatically.

## Responsibility boundaries

- DS205 canonical terminology from M4 is not necessarily deprecated; DS115 requires explicit deprecated mapping.
- DS101 checks existence; a legacy path can exist yet still be prohibited.

## Scenario summary

- **14** independent `tests/assets/ds115/{2–4-word-scenario}/` directories: 6 CLEAN; 6 FINDING; 2 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/13.0-deprecated-reference-and-terminology/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
