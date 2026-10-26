# Task 01 — implement DS105: Heading hierarchy and section levels

**Parent story:** [Story 03.0](/docs/roadmap/0005-deepening-test-case-stage-2/03.0-heading-hierarchy-validation/README.md)  
**Proposed source:** `src/docsentinel/detectors/headings.py`  
**Rule identity:** `Rule(code="DS105", profile="fast", title="Heading hierarchy and section levels", severity="warning")`.

## Required behavior and algorithm

1. Collect ATX heading tokens and supported setext headings once from shared Markdown block scanner; each token retains source line and level.
2. Flag level jumps larger than one relative to preceding actual heading; first heading must match policy unless exempt.
3. Headers inside code, comments, HTML blocks, or YAML frontmatter are not heading tokens.
4. Evaluate each document independently; line uses offending heading, not predecessor.
5. Multiple H1s are permitted by default; optional policy warns on subsequent H1s.

## Configuration additions and defaults

- `heading_level_policy = "no-skips" (default)`
- `first_heading_level = 1 (default, configurable 1..6)`
- `multiple_h1_policy = "allow" (default; \`warn\` opt-in)`
- `setext_heading_support = true (default)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `docsentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Nested lists with `#` inline text are not headings.
- A legitimate H3 after H2 is clean; raising or reducing heading levels is allowed.
- Skip special Markdown heading syntax not supported by the declared scanner dialect, with explicit compatibility documentation.

## Relationship to previously shipped or planned rules

- Use same heading scanner as DS104 and DS106; keep DS101 generated-anchor behavior unchanged.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS105` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS105` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
