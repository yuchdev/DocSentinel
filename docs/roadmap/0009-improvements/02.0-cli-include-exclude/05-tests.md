# Task 05 — Tests for invoker selectors and directory matching

**Parent story:** [Story 02.0](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/README.md)  
**Role:** Testing Expert  
**Depends on:** Task 03 (unit and mock tests), Task 04 (integration tests).

## Inputs

- Story README "Test plan", "Selector grammar", "Edge cases", "Acceptance criteria".
- Task 02 review: one test per mitigation.
- `/tests/assets/README.md` and `/tests/conftest.py`.

## Steps

1. Unit: one parametrised test per normalisation-table row; bounds (257 values, a 1,025-character
   value); glob versus literal classification; the Windows rule through
   `backslash_is_separator=True`; empty sequence and `None`.
2. Unit: matcher table for include and exclude, globs unchanged against a recorded set of cases
   from the current behaviour.
3. Mock: record `os.lstat()` calls; a symlinked component that leaves the root is refused without
   any call outside the root.
4. Integration (trees built in the test body): pruning (patch or wrap `os.walk()` to prove an
   excluded directory is not entered), replace versus append, injected `Config` plus keywords,
   duplicates, single-file warning, zero-hit include warning, config literal directory exclude.
5. Integration over assets: create selection_excluded_directory and selection_included_directory
   under the ds101 asset folder; run the CLI `scan` and `baseline` with the flags; assert findings,
   exit codes, `Scan failed:` messages and the `doctor` lines.

## Files

New: test_invoker_selectors.py and test_selector_matching.py in the unit tests folder;
test_invoker_selectors_containment.py in the mock tests folder; test_discovery_selectors.py and
test_cli_include_exclude_ds101.py in the integration tests folder; the two asset cases.

## Verification

- `uv run pytest tests -q -k "selector or include_exclude" -p docsentinel.pytest_plugin` is green.

## Acceptance

- [ ] Every table row and edge case asserted; every Task 02 mitigation has a test.
- [ ] Asset-loading test files carry the `_ds101` suffix; unit tests load no assets.

## Amendment (ADR 0006, 2026-11-18)

Add one test per row of
[ADR 0006](/docs/adr/0006-invoker-include-exclude-and-directory-selectors.md) Contracts 1, 2 and 3,
plus these cases:

- Unit: a bare `str` (and `bytes`) keyword value raises `ConfigError` (O5).
- Unit: a single-component literal exclude that names nothing at the root is not listed in
  `unmatched_exclude` and logs no `WARNING` (O3).
- Unit: a **glob** exclude does **not** prune a directory by its relative path; for example
  `docs/v?` and `**/archive` still keep `docs/v1/a.md` and `docs/archive/a.md`, byte-identical to
  today (owner ruling on O1).
- Mock: a literal include reached through an in-root symlinked directory component exits `2`
  without following the link (O6, as ruled by Task 02).
- Integration: a bad `--include` on `scan` and on `baseline` leaves `Scan failed:` (or
  `Baseline generation failed:`) as the first stderr line, before any `scan started` line.
- Integration: a single-file target with an empty or oversized selector list still exits `2`
  (O4); with valid selectors it logs the S9 `WARNING` and ignores them.

## Amendment (Task 02 security review, 2026-11-19)

Adopt the [threat model](/docs/security/threat-model-0009-invoker-selectors-2026-11-18.md)'s
mitigation-to-test map **verbatim**: the names and files below. Mock tests record `os.lstat`,
`os.stat`, `os.readlink`, `os.path.realpath`, `os.path.abspath` (on selector values), `os.scandir`,
`os.listdir` and `Path.resolve`. They assert that every recorded path is the canonical root or lies
under it, compared separator-aware. Owner ruling R1 (2026-11-19) turns the M18 test into its
exit-`2` form.

Unit, `tests/unit/test_invoker_selectors.py`:

- M1: `test_dotdot_component_refused_relative`, `test_dotdot_in_absolute_value_refused_before_normpath`
- M2: `test_absolute_sibling_prefix_refused`, `test_absolute_inside_root_made_relative`,
  `test_absolute_equal_root_is_dot`, `test_absolute_glob_refused`
- M4: `test_tilde_and_env_vars_not_expanded`
- M9: `test_absolute_longest_root_spelling_wins`
- M10, M11: `test_windows_drive_forms_refused_on_posix`, `test_unc_and_device_forms_refused`,
  `test_leading_double_slash_refused_on_posix`, `test_backslash_refused_on_posix`,
  `test_backslash_is_separator_when_injected`,
  `test_rooted_backslash_refused_when_backslash_is_separator`,
  `test_windows_ads_and_trailing_dot_refused_when_backslash_is_separator`
- M12: `test_lookalike_separators_are_name_characters` (parametrised over U+2215, U+FF0F, U+2044,
  U+29F8, U+FF3C, U+FE68), `test_no_unicode_normalisation_applied`
- M13: `test_nul_and_controls_refused` (NUL, ESC, CR, LF, DEL, U+0085, U+202E, U+200B, U+2028,
  U+DC80)
- M14: `test_github_command_marker_refused_with_clear_message`
- M19: `test_shape_bounds`, `test_oversized_list_refused_before_item_processing`
- M21: `test_error_message_bounded_and_neutralised`, `test_error_message_says_relative_to_scan_root`

Unit, `tests/unit/test_selector_matching.py`:

- M12: `test_lookalike_separator_glob_does_not_match_slash`

Mock, `tests/mock/test_invoker_selectors_containment.py`:

- M3: `test_lstat_only_inside_root_for_escaping_relative_symlink`,
  `test_lstat_only_inside_root_for_escaping_absolute_symlink`,
  `test_symlink_escape_refused_for_include_and_exclude`
- M5: `test_no_filesystem_call_for_glob_values`
- M6, M7: `test_no_filesystem_call_for_absolute_outside_value`,
  `test_no_realpath_or_resolve_of_selector_value`
- M8: `test_root_spelling_requires_samefile`, `test_pwd_not_used_for_selector_spellings`
- M13: `test_no_filesystem_call_before_character_checks`
- M15: `test_include_through_inroot_symlinked_dir_refused`,
  `test_include_final_component_symlink_refused`,
  `test_exclude_through_inroot_symlink_listed_unmatched`, `test_symlink_loop_refused_bounded`
- M16: `test_literal_include_non_regular_refused` (an `lstat` that reports a FIFO)
- M17: `test_lstat_oserror_becomes_config_error_with_relative_echo`
- T9 (accepted): `test_config_literals_never_touch_filesystem`

Integration, `tests/integration/test_discovery_selectors.py`:

- M12: `test_lookalike_named_file_selected_only_by_exact_name`
- M18 / R1: `test_exclude_star_empty_inventory_exits_2`. Assert a `ConfigError` from `scan()` and
  exit `2` from the CLI. Also assert that config-only `exclude = ["*"]` still exits `0`.
- M18: `test_case_mismatched_literal_include_zero_hit_warning` (skipped unless the temporary file
  system is case-insensitive)
- M20: `test_pathological_globs_complete` (256 values of 1,024 characters over a small tree, with
  a generous time bound)

Integration, `tests/integration/test_cli_include_exclude_ds101.py`:

- M3: `test_cli_early_validation_uses_canonical_root`
- M6: `test_cli_absolute_outside_root_message_independent_of_existence`
- M8: `test_cli_and_engine_use_same_root_spellings`
- M21: `test_cli_refused_selector_first_stderr_line_is_scan_failed`,
  `test_cli_refused_selector_echo_neutralised`
- M22: `test_cli_warning_echo_bounded`, `test_selection_info_line_has_counts_only`

The M18 and M20 tests build their trees in the test body, so `test_discovery_selectors.py` stays
asset-free and needs no rule suffix. The tests that load the ds101 assets are in
`test_cli_include_exclude_ds101.py`.
