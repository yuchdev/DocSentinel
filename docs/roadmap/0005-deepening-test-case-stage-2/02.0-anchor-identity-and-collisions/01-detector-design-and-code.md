# Task 01 — implement DS104: Conflicting heading and explicit anchors

**Parent story:** [Story 02.0](/docs/roadmap/0005-deepening-test-case-stage-2/02.0-anchor-identity-and-collisions/README.md)  
**Proposed source:** `src/docsentinel/detectors/anchors.py`  
**Rule identity:** `Rule(code="DS104", profile="fast", title="Conflicting heading and explicit anchors", severity="warning")`.

## Required behavior and algorithm

1. Build anchors with DS101 heading_anchors/slugify rules, preserving generated suffixes; do not issue findings for ordinary repeated headings because GitHub assigns -1, -2 suffixes.
2. Index explicit `<a id=...>` and `<a name=...>` plus heading attribute IDs only if documented syntax supported; keep line, spelling and source kind.
3. Report repeated explicit identifiers and explicit-vs-generated collisions with stable line, while normal duplicate heading slugs remain valid.
4. Distinguish HTML ID case sensitivity and HTML name behavior; do not lowercase literal explicit IDs.
5. One finding per offending later identifier in stable document/line order; no global collisions between independent documents.

## Configuration additions and defaults

- `anchor_collision_policy = "explicit" (default): reject repeated explicit HTML id/name definitions and explicitly shadowed generated anchors only when renderer policy can prove ambiguity`
- `anchor_renderer = "github" (default): use DS101-compatible GitHub slugger and duplicate-heading suffix rules; other renderers deferred`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `doc_sentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Never flag two identical headings without an explicit conflicting ID.
- Ignore anchor-shaped strings in code fences, inline code, and HTML comments; do not reinterpret external URI fragments.
- Do not treat same anchor identifier in two different documents as duplicate.

## Relationship to previously shipped or planned rules

- DS101 owns link resolution, DS104 owns collisions; shared anchor inventory must agree on suffixed headings.
- M4 DS111 may expose frontmatter IDs, but HTML anchors are not document IDs (DS114).

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS104` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS104` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
