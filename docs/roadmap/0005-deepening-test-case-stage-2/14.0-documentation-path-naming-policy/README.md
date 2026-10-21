# Story 14.0 — Documentation file and directory naming policy (`DS118`)

**Profile:** `fast` · **Default severity:** `warning` · **Rule module proposal:** `src/docsentinel/detectors/naming.py`  
**Prerequisites:** Story 01.0; current master compatibility and any M4 shared dependency as noted.

## Goal

Implement `DS118` as an explainable, **stdlib-only** Markdown analysis rule. This story is not done until every named test asset is committed and exercised.

## Tasks

| Task | Deliverable |
|---|---|
| [01](/docs/roadmap/0005-deepening-test-case-stage-2/14.0-documentation-path-naming-policy/01-detector-design-and-code.md) | detector design and code |
| [02](/docs/roadmap/0005-deepening-test-case-stage-2/14.0-documentation-path-naming-policy/02-markdown-fixture-assets.md) | markdown fixture assets |
| [03](/docs/roadmap/0005-deepening-test-case-stage-2/14.0-documentation-path-naming-policy/03-tests-and-acceptance.md) | tests and acceptance |

## Detector behavior

- Evaluate discovered Markdown paths only, not arbitrary project source files or excluded directories.
- Validate path components via portable ASCII naming policy: lowercase letters/digits and hyphen or underscore according to selected style.
- Support explicit exemptions for canonical README.md/index.md and numeric ADR prefixes.
- Report violation once per offending path component or document with stable path/line=None and suggested rename; never rename files.
- Preserve source containment and Unicode behavior via explicit policy; do not lowercase paths in place on case-sensitive filesystems.

## Responsibility boundaries

- DS115 handles deprecated names already in prose/links; DS118 only pathname format.
- DS101 will identify broken links after user renames; DS118 must not rewrite them.

## Scenario summary

- **14** independent `tests/assets/ds118/{2–4-word-scenario}/` directories: 6 CLEAN; 8 FINDING; 0 ERROR.
- All case details are in [Task 02](/docs/roadmap/0005-deepening-test-case-stage-2/14.0-documentation-path-naming-policy/02-markdown-fixture-assets.md) and the [master matrix](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md).
- `ERROR` scenarios must have explicit safe error handling; they do not count as successful detector findings.

## Definition of done

- Detector registered once and runnable as exact fast-profile rule with working select/ignore; imports stdlib only.
- All cases created with real Markdown; each has an explicit integration assertion. Line, path, severity and diagnostic meaning are checked.
- Old DS101–103 and other new fast checks not regressed; disabled optional policies never masquerade as evaluated.
