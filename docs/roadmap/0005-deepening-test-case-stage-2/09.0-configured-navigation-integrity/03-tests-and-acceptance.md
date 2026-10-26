# Task 03 — DS112 integration, profile and compatibility tests

**Parent story:** [Story 09.0](/docs/roadmap/0005-deepening-test-case-stage-2/09.0-configured-navigation-integrity/README.md)  
**Test file:** `tests/integration/test_detectors_configured_navigation_integrity_ds112.py`  
**Asset root:** `tests/assets/ds112/`

## Every named scenario is an integration test

1. Use `asset_case("ds112", scenario)` to materialize **each** scenario from Task 02 into a fresh `tmp_path`, passing only included Markdown documents into analyzer when needed (companion non-Markdown files are for reference resolution only).
2. Parametrize explicitly with a stable scenario-to-expectation mapping; do not derive expected findings from whatever the analyzer currently emits. Assert known row `outcome` (`clean`, `finding`, `error`) and associated details.
3. For `clean`: assert this rule was genuinely registered and executed, that its count is **zero**, and that optional feature selection was active when required.
4. For `finding`: assert one or more structured `DS112` findings with `severity='warning'`, correct offending path, one-based line if representable, useful evidence message and deterministic ordering; verify more-specific counts for repeated events.
5. For `error`: assert targeted `ConfigError`, safe filesystem error, or explicitly `pending/not-evaluated` state from shared contract; do not treat a dropped detector as a successful clean scan.
6. Verify `scan(root, config=Config(profile="fast", select=("DS112",), ...))`, CLI `--profile fast --format json`, and `docsentinel rules` list/execute `DS112`. Check select/ignore and baseline are correct.
7. Test that fast import/execution without standard/deep extras works. Prove no network requests and no execution of documentation content.
8. Regression-check shared behavior: old fast rules and relevant M4 rules as described by this story, especially source line offsets, escape handling, correct root resolution and scanner masking.

## Additional edge test dimensions

- Without configured indexes, mark this optional rule not applicable using M4 per-rule status rather than flag all docs.
- Do not flag missing targets in ordinary prose outside configured index.
- Navigation to external URLs is permitted but not considered a local required target.

Also test CRLF, invalid UTF-8, unreadable file, symlink/file paths and very long lines as appropriate; if inapplicable, write a one-sentence reason in test documentation. Check stable output across repeated scans and fresh roots.

## End-to-end commands

```sh
uv run pytest -p docsentinel.pytest_plugin tests/integration/test_detectors_configured_navigation_integrity_ds112.py
uv run pytest -p docsentinel.pytest_plugin tests/unit/ tests/integration/
uv run docsentinel rules
uv run docsentinel scan . --profile fast --format json
```

**Do not** force optional policy on repo-wide self-scan merely to obtain findings. Test opt-in policy with injected Config or per-case `docsentinel.toml`, maintaining existing app defaults.

## Acceptance

- [ ] All 14 cases are independently loaded and asserted, with expected 8 CLEAN, 5 FINDING and 1 ERROR.
- [ ] Broken Markdown asset content is committed; no fixture is only a Python string.
- [ ] No surprise skips, xfails or catches converting errors into zero findings.
- [ ] Relevant DS101–DS103/M4 tests and CLI/report/baseline suite stay green.
- [ ] Story status records path/test evidence and known supported dialect limits.
