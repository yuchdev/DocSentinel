# Task 01 — implement DS106: Empty or contentless sections

**Parent story:** [Story 04.0](/docs/roadmap/0005-deepening-test-case-stage-2/04.0-contentless-section-detection/README.md)  
**Proposed source:** `src/docsentinel/detectors/sections.py`  
**Rule identity:** `Rule(code="DS106", profile="fast", title="Empty or contentless sections", severity="warning")`.

## Required behavior and algorithm

1. Build heading ranges; for each leaf section, inspect visible non-whitespace text and supported blocks between heading and next heading.
2. Skip HTML comments, fenced and indented empty code blocks, separators and blank lines; a nonempty fenced code block or table counts as content.
3. Structural parents with only nested child sections are not empty by default.
4. Flag the section heading location only once; trailing heading at EOF is a finding.
5. Do not confuse an empty frontmatter record with a body section.

## Configuration additions and defaults

- `empty_section_policy = "leaf" (default): check only sections without child sections`
- `placeholder_content_policy = "ignore" (default): HTML comments and whitespace do not count as content`
- `image_content_counts = true (default)`
- `empty_section_min_text_chars = 0 (default; positive values deferred to DS203 quality policy)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `docsentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- An image or local diagram alone is meaningful content when image_content_counts is true.
- A lone HTML comment is not publishable section content.
- Do not flag an empty document without headings as an empty *section*; metadata/other rules may handle it.

## Relationship to previously shipped or planned rules

- DS111 validates metadata; DS119 finds markers; DS106 checks visible section content regardless of both.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS106` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS106` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
