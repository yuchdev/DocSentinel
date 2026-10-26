# Task 01 — implement DS108: Reference-style link definition integrity

**Parent story:** [Story 05.0](/docs/roadmap/0005-deepening-test-case-stage-2/05.0-reference-definition-integrity/README.md)  
**Proposed source:** `src/docsentinel/detectors/references.py`  
**Rule identity:** `Rule(code="DS108", profile="fast", title="Reference-style link definition integrity", severity="warning")`.

## Required behavior and algorithm

1. Parse full, collapsed and explicit reference links, image references, and definitions according to supported Markdown subset.
2. Normalize reference labels case-insensitively and collapse whitespace, but preserve original source positions.
3. Flag an explicit reference use with no matching definition and each duplicate definition after the first.
4. Unused definitions are off by default; when enabled, emit warnings for declarations never referenced.
5. Do not interpret footnotes `[^note]` as ordinary link refs; pairwise dedup and stable line attribution.

## Configuration additions and defaults

- `unused_reference_definitions = false (default; warnings only when true)`
- `duplicate_reference_definitions = "warn" (default)`
- `reference_label_normalization = "commonmark" (fixed unless dialect adapter registered)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `docsentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Do not flag shortcut bracket prose as a broken reference unless parser positively recognizes it as a link.
- Skip reference-looking material in fenced code, inline code, and comments.
- Skip escaped brackets and recognize multi-line definitions only within a documented supported dialect.

## Relationship to previously shipped or planned rules

- DS101 checks resolved targets after reference expansion; DS108 checks identifiers/definitions. No duplicate DS101 findings for merely undefined labels.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS108` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS108` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
