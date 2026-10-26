# Task 01 — implement DS118: Documentation file and directory naming policy

**Parent story:** [Story 14.0](/docs/roadmap/0005-deepening-test-case-stage-2/14.0-documentation-path-naming-policy/README.md)  
**Proposed source:** `src/docsentinel/detectors/naming.py`  
**Rule identity:** `Rule(code="DS118", profile="fast", title="Documentation file and directory naming policy", severity="warning")`.

## Required behavior and algorithm

1. Evaluate discovered Markdown paths only, not arbitrary project source files or excluded directories.
2. Validate path components via portable ASCII naming policy: lowercase letters/digits and hyphen or underscore according to selected style.
3. Support explicit exemptions for canonical README.md/index.md and numeric ADR prefixes.
4. Report violation once per offending path component or document with stable path/line=None and suggested rename; never rename files.
5. Preserve source containment and Unicode behavior via explicit policy; do not lowercase paths in place on case-sensitive filesystems.

## Configuration additions and defaults

- `documentation_naming = "off" (default; \`kebab\` or \`snake\` enabled by explicit config)`
- `documentation_naming_allow = ["README.md", "index.md"] (default exemptions)`
- `documentation_naming_directories = true (default when enabled)`
- `documentation_naming_prefix_patterns = [] (optional validated ADR/release exceptions)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `docsentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Default disabled, to avoid breaking repositories that deliberately use title-cased filenames.
- Do not flag excluded documentation directories.
- Do not impose naming on sibling non-Markdown attachments unless explicitly configured.

## Relationship to previously shipped or planned rules

- DS115 handles deprecated names already in prose/links; DS118 only pathname format.
- DS101 will identify broken links after user renames; DS118 must not rewrite them.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS118` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS118` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
