# Task 01 — implement DS110: Missing language labels on code fences

**Parent story:** [Story 07.0](/docs/roadmap/0005-deepening-test-case-stage-2/07.0-code-fence-language-policy/README.md)  
**Proposed source:** `src/docsentinel/detectors/fence_languages.py`  
**Rule identity:** `Rule(code="DS110", profile="fast", title="Missing language labels on code fences", severity="warning")`.

## Required behavior and algorithm

1. Reuse DS109 fence scan to enumerate valid opening fences and info strings.
2. When enabled, report nonempty meaningful fenced code blocks with empty language marker.
3. Info first token names the language, e.g. python, bash, text, console, diff; treat whitespace-only info as absent.
4. Do not execute examples or validate syntax here (DS219 in M4).
5. Malformed fences are owned by DS109: DS110 must avoid double-reporting a fence never successfully closed.

## Configuration additions and defaults

- `require_fence_languages = false (default: only enabled with policy)`
- `allow_unlabelled_empty_fences = true (default)`
- `allowed_fence_languages = [] (empty means no vocabulary restriction; non-empty validated allowlist)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `doc_sentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Unlabeled fence is clean when policy is disabled.
- An intentionally empty demonstration fence is exempt when allow_unlabelled_empty_fences=true.
- Honor explicit `text`/`plaintext` as legitimate language labels.

## Relationship to previously shipped or planned rules

- DS109 supplies validity and spans. DS219 handles code syntax; DS110 handles only fence metadata.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS110` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS110` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
