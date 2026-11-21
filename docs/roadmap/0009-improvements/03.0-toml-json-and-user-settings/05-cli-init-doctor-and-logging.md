# Task 05 — CLI: `--no-user-settings`, `init --user`, `doctor` sources, logging

**Parent story:** [Story 03.0](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md)  
**Role:** Python Expert  
**Depends on:** Task 04.

## Inputs

- Story README "CLI reference", "Logging"; decision S10.
- The Task 02 threat model,
  [threat-model-0009-user-settings-2026-11-17.md](/docs/security/threat-model-0009-user-settings-2026-11-17.md):
  R3, U4, U11, U15, U16 and amendments A8, A9 and A10 (link it in the briefing).
- `/src/docsentinel/cli.py`: `_build_parser()`, `_run_init()`, `_run_scan()`, `_run_baseline()`,
  the `doctor` branch and its helper lines.

## Steps

1. Add `--no-user-settings` to `scan`, `baseline` and `doctor`; pass `user_settings=False` to the
   loader.
2. `init --user`: resolve the path with `user_settings_path()`; refuse when user settings are `off`
   or the home is unknown (exit `2`); run the R3 directory check and refuse first (exit `2`, same
   phrase as the load gate) before creating anything; create each missing directory with
   `os.mkdir(path, 0o700)`; open the file with `O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW` (where
   available), mode `0o600`, then `fchmod(0o600)` on the descriptor so the umask cannot change it
   (A8, U15); write the starter object from the story; never overwrite or follow an existing
   symlink (exit `2` naming the file in tilde form); keep the `--yes` and interactive confirmation
   behaviour of `init`. `--user` and `--project-root` together are an argparse error.
3. `doctor`: print the user settings line, the project config line and (from Story 01.0) the
   reference-scope line, using `load_config_with_sources()` for the current directory; a
   `ConfigError` prints one neutralised error line and `doctor` still exits `0`, as the extension
   line does today.
4. `INFO` line `config: user settings <state>[ (<names>)], project <file name or none>` once per
   `scan` and `baseline` run, after validation succeeds (so a config error stays the first stderr
   line). The names are the user-layer option names, sorted, at most 20 then `and N more`, never
   values (A10, U16), for example
   `config: user settings loaded (ignore, reference_scope), project docsentinel.toml`.
5. Help texts mention the settings path and `DOCSENTINEL_SETTINGS`.
6. Set `DOCSENTINEL_SETTINGS: off` at job level in `/.github/workflows/ci.yml`, on every job that
   runs `docsentinel` (required, not optional; A9, U4).
7. Report a `Docs impact:` line (C).

## Files

`/src/docsentinel/cli.py`, `/.github/workflows/ci.yml`.

## Verification

- test_user_settings_cli_ds101_ds103.py (Task 06) green with `-q`.
- Manual: `DOCSENTINEL_SETTINGS=<tmp>/s.json uv run docsentinel init --user --yes`, then
  `uv run docsentinel doctor`.

## Acceptance

- [ ] `init --user` creates the file once, with the stated modes, and refuses a second time.
- [ ] `doctor` lines match the story exactly.
- [ ] No absolute home path appears in `INFO` or `doctor` output.
- [ ] Every CI job that runs `docsentinel` sets `DOCSENTINEL_SETTINGS: off` at job level.
