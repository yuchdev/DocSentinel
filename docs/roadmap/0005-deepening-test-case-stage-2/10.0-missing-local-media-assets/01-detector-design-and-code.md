# Task 01 — implement DS113: Missing local media and document assets

**Parent story:** [Story 10.0](/docs/roadmap/0005-deepening-test-case-stage-2/10.0-missing-local-media-assets/README.md)  
**Proposed source:** `src/docsentinel/detectors/assets.py`  
**Rule identity:** `Rule(code="DS113", profile="fast", title="Missing local media and document assets", severity="error")`.

## Required behavior and algorithm

1. Parse Markdown images (inline or reference-style) and supported HTML `<img src>`/`<source srcset>` as local asset references.
2. Resolve relative paths from containing document and repo-absolute paths from scan root; check target existence, containment and regular-file status.
3. Split srcset candidates without corrupting common data URIs, preserve relevant line and path.
4. Ignore external URL schemes, data URIs, fragment-only references, and templates explicitly exempted by policy.
5. When DS101 also notices a broken Markdown image, avoid changing DS101 baseline behavior; document how consumers may de-duplicate presentation without hiding either rule.

## Configuration additions and defaults

- `asset_extensions = ["png","jpg","jpeg","svg","webp","gif","pdf"] (default scope)`
- `check_html_asset_tags = true (default)`
- `check_markdown_images = true (default)`
- `check_srcset = true (default)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `doc_sentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Do not guess arbitrary filenames mentioned in prose (DS103 owns path-like code spans).
- Missing HTTP assets are not checked (no network in fast profile).
- Do not follow symlinks outside scan root; defer path-escape classification to DS116 if applicable.

## Relationship to previously shipped or planned rules

- DS101 may also flag link targets inside Markdown image syntax; tests must assert DS113-specific diagnostics.
- DS116 determines root escape security; an escaped missing asset must not be dereferenced.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS113` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS113` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
