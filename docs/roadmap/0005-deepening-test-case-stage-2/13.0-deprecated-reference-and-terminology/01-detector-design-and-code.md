# Task 01 — implement DS115: Deprecated names and migrated references

**Parent story:** [Story 13.0](/docs/roadmap/0005-deepening-test-case-stage-2/13.0-deprecated-reference-and-terminology/README.md)  
**Proposed source:** `src/docsentinel/detectors/deprecated_refs.py`  
**Rule identity:** `Rule(code="DS115", profile="fast", title="Deprecated names and migrated references", severity="warning")`.

## Required behavior and algorithm

1. Load a versioned, root-contained TOML mapping with explicit `[[replacement]]` entries (old, new, kind, optional scope); validate conflicting keys and target types.
2. Match obsolete path references and identifiers only where explicit mapping applies; support Markdown links, path-like code spans and prose terms per kind.
3. Use token boundaries rather than naive substring replacement: old `APIv1` must not match `APIv10`.
4. Exclude code fences and quoted historical migration examples by explicit exemption policy, not by guessing date semantics.
5. Emit old token, suggested replacement and mapping provenance, without modifying source automatically.

## Configuration additions and defaults

- `deprecated_references_file = "" (default: disabled until mapping supplied)`
- `deprecated_check_prose = true (default)`
- `deprecated_check_links = true (default)`
- `deprecated_case_sensitive = true (default)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `docsentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Absent mapping means check not applicable, not a universal obsolete-term heuristic.
- Keep archival/historical examples exempt by supported allowlist or path exclude.
- A replacement may point to a new path not existing yet; DS115 reports only registered obsolete occurrence, not its target existence.

## Relationship to previously shipped or planned rules

- DS205 canonical terminology from M4 is not necessarily deprecated; DS115 requires explicit deprecated mapping.
- DS101 checks existence; a legacy path can exist yet still be prohibited.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS115` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS115` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
