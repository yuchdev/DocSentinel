# Task 01 — implement DS116: Path traversal outside documentation root

**Parent story:** [Story 11.0](/docs/roadmap/0005-deepening-test-case-stage-2/11.0-repository-root-path-boundaries/README.md)  
**Proposed source:** `src/docsentinel/detectors/path_boundaries.py`  
**Rule identity:** `Rule(code="DS116", profile="fast", title="Path traversal outside documentation root", severity="error")`.

## Required behavior and algorithm

1. Normalize local target paths lexically, then reject any `..` that resolves outside supplied root.
2. Check both decoded and raw path; decode percent-escaping once to prevent %2e%2e root traversal bypass.
3. Reject absolute OS paths, drive-letter paths and UNC in locally interpreted documentation references unless explicitly treated as external literal examples.
4. Reject symlink traversal out of root using a safe, non-following containment check; never read outside target contents.
5. Validate Markdown links, image sources, explicitly referenced local assets and path-like code spans through shared resolver without changing DS101/DS103 public behavior.

## Configuration additions and defaults

- `root_escape_policy = "error" (default)`
- `decode_percent_paths = true (default; decode once and validate)`
- `windows_path_policy = "portable" (default; detect drive, UNC and rooted backslashes)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `doc_sentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Legitimate `../` navigation within scan root is permitted.
- External scheme URIs (`https:`, `mailto:`) are ignored.
- Root-relative `/docs/guide.md` Markdown links are allowed and resolve within configured scan root.

## Relationship to previously shipped or planned rules

- DS101/DS103 existence checks should not read an escaped target; DS116 owns explicit policy violation report.
- DS113 asset existence and DS112 nav resolution reuse safe resolver.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS116` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS116` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
