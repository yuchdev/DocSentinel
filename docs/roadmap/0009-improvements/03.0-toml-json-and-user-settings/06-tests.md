# Task 06 — Tests for JSON configuration and user settings

**Parent story:** [Story 03.0](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md)  
**Role:** Testing Expert  
**Depends on:** Task 03 (loader tests), Task 04 (layer tests), Task 05 (CLI tests).

## Inputs

- Story README "Test plan", "Acceptance criteria", "Edge cases".
- The Task 02 threat model,
  [threat-model-0009-user-settings-2026-11-17.md](/docs/security/threat-model-0009-user-settings-2026-11-17.md):
  one test per mitigation; the named tests of U1-U16 and F1 and its mitigation-to-test map
  (amendment A11). Link it in the briefing.
- `/tests/conftest.py` (the new `DOCSENTINEL_SETTINGS=off` and `XDG_DATA_HOME` isolation),
  `/tests/assets/README.md`.

## Steps

1. Unit, JSON loader: valid object; duplicate key at top level and nested; BOM; invalid UTF-8;
   `NaN`, `Infinity`, `-Infinity`; `null` at top level and nested; a top-level array; 1 MiB exactly
   (accepted) and plus one byte (refused); deep nesting; a 100,000-digit integer; unknown key
   message equal to the TOML one. Threat-model tests (test_json_config_loader.py):
   `test_json_loader_reads_once_from_one_descriptor` (U2), `test_json_size_exactly_1mib_accepted`,
   `test_json_size_1mib_plus_one_refused`,
   `test_json_deep_nesting_100k_refused_as_nested_too_deeply`,
   `test_json_null_walk_iterative_at_depth_3000`, `test_json_100k_digit_integer_is_config_error`,
   `test_json_utf16_file_refused_as_not_utf8`, `test_hook_config_error_not_rewrapped` (U6),
   `test_json_1e400_refused`, `test_json_negative_1e400_refused` (U8), `test_duplicate_key_top_level`,
   `test_duplicate_key_nested`, `test_duplicate_key_escaped_spelling`, `test_bom_refused`,
   `test_null_top_level_and_nested`, `test_duplicate_key_name_bounded_and_neutralised` (U9),
   `test_config_error_never_echoes_file_content` (U11).
2. Unit, message parity: for each validator in the config module, one invalid value written as
   TOML and as JSON yields the same message. Threat-model tests (test_config_message_parity.py):
   `test_numeric_overflow_int_is_config_error_both_formats`,
   `test_toml_nan_and_inf_refused_with_existing_message` (U8).
3. Unit, policy: each C6 key refused with key and file named; a representative allowed key from
   each family applies; precedence user under project under CLI. Threat-model tests
   (test_user_settings_policy.py): `test_each_c6_key_refused_naming_key_and_file` (parametrised
   over the ten keys), `test_escaped_c6_key_refused`, `test_c6_refusal_precedes_value_validation`,
   `test_user_python_extension_refused`, `test_refused_keys_drift_matches_c6`,
   `test_project_config_cannot_name_settings_path` (U5), `test_env_named_file_still_c6_restricted`
   (U10), `test_config_sources_not_in_report_context` (U11), `test_settings_env_read_only_in_resolver`
   (U13, AST scan of `src/docsentinel`).
4. Mock, location: environment `off`, absolute, relative, empty; `XDG_DATA_HOME` absolute,
   relative, unset; `Path.home()` raising; the permission gate with `os.stat()`, `os.fstat()` and
   `os.geteuid()` patched (A11). Threat-model tests (test_user_settings_location.py):
   `test_gate_refuses_file_owned_by_other_user`, `test_gate_refuses_group_writable_file`,
   `test_gate_refuses_world_writable_file`, `test_gate_accepts_owner_file_mode_0644`,
   `test_gate_accepts_root_owned_file`, `test_gate_as_root_refuses_user_owned_file`,
   `test_gate_checks_symlink_final_target_not_link`, `test_gate_refuses_writable_dir_holding_symlink`,
   `test_gate_refuses_writable_dir_holding_target`, `test_gate_accepts_sticky_world_writable_dir`,
   `test_gate_refuses_dir_owned_by_other_user`, `test_gate_skipped_on_non_posix`,
   `test_gate_messages_fixed_phrases_no_uid_no_target` (U1, U14),
   `test_gate_decision_uses_fstat_of_opened_descriptor` (U2), `test_relative_home_is_no_home`,
   `test_empty_xdg_and_relative_xdg_fall_back_to_home`,
   `test_relative_settings_env_is_config_error_value_not_echoed` (U3),
   `test_default_location_absent_is_missing`, `test_default_location_dangling_symlink_is_error`,
   `test_default_location_permission_denied_is_error`, `test_env_path_absent_is_error` (U7),
   `test_tilde_form_for_home_and_its_realpath` (U11), `test_user_settings_false_never_reads_env`
   (U13).
5. Integration (CLI, settings file in `tmp_path` through `DOCSENTINEL_SETTINGS`, documents from the
   existing ds101 and ds103 asset cases): a user `reference_scope = "strict"` turns DS103 on; a
   project value overrides it; `--no-user-settings`; `--config` with a JSON file; `init --user`
   twice; `doctor` lines; exit codes and `Scan failed:` messages. Threat-model tests
   (test_user_settings_cli_ds101_ds103.py): `test_cli_group_writable_settings_exits_2` (U1, real
   chmod), `test_fifo_settings_file_refused_without_blocking` (U2, real `os.mkfifo`),
   `test_ci_workflow_sets_settings_off` (U4), `test_no_absolute_home_in_info_or_doctor` (U11),
   `test_init_user_creates_0600_file_and_0700_dirs_under_umask_002`,
   `test_init_user_refuses_existing_symlink`, `test_init_user_refuses_unsafe_directory`,
   `test_init_user_twice_exits_2` (U15), `test_info_config_line_names_user_options_not_values`
   (U16), `test_doctor_survives_oversized_toml_integer` (F1). The FIFO and chmod tests are
   POSIX-only (skip elsewhere) and run under a timeout guard (A11).
6. Guard tests (U12): with the autouse isolation in place, `user_settings_path()` reports `off`
   (`test_isolation_settings_off`); with `DOCSENTINEL_SETTINGS` removed, the resolved path lies
   under the temporary `XDG_DATA_HOME` (`test_isolation_default_location_is_temporary`). Both in
   test_user_settings_location.py.

## Files

New: test_json_config_loader.py, test_config_message_parity.py and test_user_settings_policy.py in
the unit tests folder; test_user_settings_location.py in the mock tests folder;
test_user_settings_cli_ds101_ds103.py in the integration tests folder.

## Verification

- `uv run pytest tests -q -k "json_config or message_parity or user_settings" -p docsentinel.pytest_plugin`
  is green.

## Acceptance

- [ ] Every acceptance criterion and Task 02 mitigation has a test; every test named in U1-U16
      and F1 of the threat model exists under that name.
- [ ] No test reads or writes the real home directory.
