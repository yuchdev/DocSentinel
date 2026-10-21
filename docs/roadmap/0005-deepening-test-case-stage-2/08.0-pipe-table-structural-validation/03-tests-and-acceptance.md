# Task 03 — DS117 integration, profile and compatibility tests

**Parent story:** [Story 08.0](/docs/roadmap/0005-deepening-test-case-stage-2/08.0-pipe-table-structural-validation/README.md)  
**Test file:** `tests/integration/test_detectors_pipe_table_structural_validation_ds117.py`  
**Asset root:** `tests/assets/ds117/`

## Every named scenario is an integration test

1. Use `asset_case("ds117", scenario)` to materialize **each** scenario from Task 02 into a fresh `tmp_path`, passing only included Markdown documents into analyzer when needed (companion non-Markdown files are for reference resolution only).
2. Parametrize explicitly with a stable scenario-to-expectation mapping; do not derive expected findings from whatever the analyzer currently emits. Assert known row `outcome` (`clean`, `finding`, `error`) and associated details.
3. For `clean`: assert this rule was genuinely registered and executed, that its count is **zero**, and that optional feature selection was active when required.
4. For `finding`: assert one or more structured `DS117` findings with `severity='warning'`, correct offending path, one-based line if representable, useful evidence message and deterministic ordering; verify more-specific counts for repeated events.
5. For `error`: assert targeted `ConfigError`, safe filesystem error, or explicitly `pending/not-evaluated` state from shared contract; do not treat a dropped detector as a successful clean scan.
6. Verify `scan(root, config=Config(profile="fast", select=("DS117",), ...))`, CLI `--profile fast --format json`, and `docsentinel rules` list/execute `DS117`. Check select/ignore and baseline are correct.
7. Test that fast import/execution without standard/deep extras works. Prove no network requests and no execution of documentation content.
8. Regression-check shared behavior: old fast rules and relevant M4 rules as described by this story, especially source line offsets, escape handling, correct root resolution and scanner masking.

## Additional edge test dimensions

- Do not treat prose containing pipes but lacking delimiter row as table.
- Pipe characters inside code spans or escaped with backslash do not delimit columns.
- Do not diagnose HTML tables; no HTML table parsing in fast profile.

Also test CRLF, invalid UTF-8, unreadable file, symlink/file paths and very long lines as appropriate; if inapplicable, write a one-sentence reason in test documentation. Check stable output across repeated scans and fresh roots.

## End-to-end commands

```sh
uv run pytest -p docsentinel.pytest_plugin tests/integration/test_detectors_pipe_table_structural_validation_ds117.py
uv run pytest -p docsentinel.pytest_plugin tests/unit/ tests/integration/
uv run docsentinel rules
uv run docsentinel scan . --profile fast --format json
```

**Do not** force optional policy on repo-wide self-scan merely to obtain findings. Test opt-in policy with injected Config or per-case `doc_sentinel.toml`, maintaining existing app defaults.

## Acceptance

- [ ] All 15 cases are independently loaded and asserted, with expected 9 CLEAN, 6 FINDING and 0 ERROR.
- [ ] Broken Markdown asset content is committed; no fixture is only a Python string.
- [ ] No surprise skips, xfails or catches converting errors into zero findings.
- [ ] Relevant DS101–DS103/M4 tests and CLI/report/baseline suite stay green.
- [ ] Story status records path/test evidence and known supported dialect limits.
