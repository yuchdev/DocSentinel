# Task 01 — implement DS109: Malformed or unclosed fenced code blocks

**Parent story:** [Story 06.0](/docs/roadmap/0005-deepening-test-case-stage-2/06.0-fenced-code-boundary-validation/README.md)  
**Proposed source:** `src/docsentinel/detectors/fences.py`  
**Rule identity:** `Rule(code="DS109", profile="fast", title="Malformed or unclosed fenced code blocks", severity="error")`.

## Required behavior and algorithm

1. Scan backtick and tilde fences with opener length >=3, indent <=3 and matching closing character.
2. Closing run must be at least opener length and may contain only permitted trailing whitespace.
3. Backtick opener info string may not contain backticks; reject malformed opener if identified as intentional fence.
4. Preserve exact line ranges for opening and EOF errors; do not treat shorter closure as completion.
5. Offer shared fence mask to other DS1xx analyzers; test linear-time behavior on very long or adversarial fenced input.

## Configuration additions and defaults

- `fence_dialect = "gfm-subset" (default)`
- `report_stray_closing_fence = false (default; unattached closers are not unambiguously erroneous)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `doc_sentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Indented code blocks (>=4 spaces) are not fenced openers.
- A tilde cannot close a backtick fence and vice versa.
- Content that happens to contain triple backticks in prose is not necessarily a fence if not a block opener.

## Relationship to previously shipped or planned rules

- DS101–103 already mask fences; migration must not regress inherited stripping semantics without explicit review.
- DS110 consumes parsed fence opener info without re-parsing differently.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS109` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS109` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
