# Task 06 — Fixtures and tests for reference scope, DS124 and mention escapes

**Parent story:** [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md)  
**Role:** Testing Expert  
**Depends on:** Task 04 (scanner) for unit tests; Task 05 for integration tests. Unit tests may be
written first and fail until the code lands.

## Inputs

- Story README "Test plan" (normative file list and case names) and "Acceptance criteria".
- Task 02 threat model: one test per mitigation.
- `/tests/assets/README.md` (asset layout, byte-exact cases, symlinks built in the test body) and
  `/tests/conftest.py` (the `asset_case` fixture and logging isolation).

## Steps

1. Create the asset cases listed in the story under the ds124 and ds103 asset folders, each a tiny
   documentation tree with real Markdown. Include a nested document (for the link-root fallback)
   and a `.git` marker created by the test where the case needs `link_root = "auto"` to find a
   repository root.
2. Unit tests (inline strings only): grammar, config validation, opt-in values and notice
   rendering (golden strings for DS110, DS112, DS115, DS118 copied from the current output).
3. Mock tests: patch `os.stat()` and `os.lstat()` to record calls; assert no call for home or
   absolute mentions and none outside the scan root (step 1) or link root (step 2).
4. Integration tests through `scan()` and the CLI: each asset case; scope precedence (default,
   config, CLI); `rules` and `doctor` lines; notice; `baseline --reference-scope strict` records
   DS103 fingerprints and a default-scope scan ignores them without error.
5. Escape cases with symlinks are built in the test body under `tmp_path`, as existing DS116 tests
   do; skip with a clear reason on platforms without symlink support.
6. Check lines, columns, `value`, `type`, severity and message of every finding.

## Files

New: test_at_reference_grammar.py, test_reference_scope_config.py and test_rule_opt_in_values.py
in the unit tests folder; test_at_reference_no_probe.py in the mock tests folder;
test_at_references_ds124.py, test_at_references_ds116_ds124.py, test_reference_scope_ds103.py
and test_reference_scope_cli_ds103_ds124.py in the integration tests folder; the asset cases.
Updated: `/tests/integration/test_rules_table.py` if needed.

## Verification

- `uv run pytest tests/unit tests/mock tests/integration -q -k "at_reference or reference_scope or ds124 or opt_in_values" -p docsentinel.pytest_plugin`
  is green.
- Full suite green once at story close.

## Acceptance

- [ ] Every case name in the story exists and is asserted.
- [ ] Every Task 02 mitigation has a named test.
- [ ] No unit test loads assets; every asset-loading file carries the rule-ID suffix.
