# Task 01 — implement DS112: Declared documentation navigation integrity

**Parent story:** [Story 09.0](/docs/roadmap/0005-deepening-test-case-stage-2/09.0-configured-navigation-integrity/README.md)  
**Proposed source:** `src/docsentinel/detectors/navigation.py`  
**Rule identity:** `Rule(code="DS112", profile="fast", title="Declared documentation navigation integrity", severity="warning")`.

## Required behavior and algorithm

1. Read only configured navigation index Markdown documents; inspect actual local links in list items (and optionally configured nav sections).
2. Check required targets appear exactly once when navigation_required is provided, and duplicates are reported once each at later link.
3. Detect nonexistent local destinations in designated navigation, distinguishing them from ordinary prose links.
4. Use DS107 graph for shared normalized path resolution when M4 landed; do not infer navigation by every Markdown hyperlink.
5. Missing/unreadable configured index is a clear config/readiness error, not silent clean result; never follow symlinks beyond root.

## Configuration additions and defaults

- `navigation_indexes = [] (default: empty disables policy; no guessed index)`
- `navigation_required = [] (default; explicit required doc targets)`
- `navigation_unique_targets = true (default)`
- `navigation_check_missing = true (default)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `doc_sentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Without configured indexes, mark this optional rule not applicable using M4 per-rule status rather than flag all docs.
- Do not flag missing targets in ordinary prose outside configured index.
- Navigation to external URLs is permitted but not considered a local required target.

## Relationship to previously shipped or planned rules

- DS101 validates general links; DS112 checks only declared navigation contract. DS107 handles graph reachability from index, not explicit required inclusion.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS112` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS112` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
