# Task 04 — User settings layer

**Parent story:** [Story 03.0](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md)  
**Role:** Python Expert  
**Depends on:** Task 03.

## Inputs

- Story README "Settings path and environment", "Shared validation and layering",
  "User-level key policy", "Edge cases"; decisions S3 to S6, S8, S9; plan C6; ADR 0005
  Contracts 3 to 5.
- The Task 02 threat model,
  [threat-model-0009-user-settings-2026-11-17.md](/docs/security/threat-model-0009-user-settings-2026-11-17.md):
  the permission rule R1-R7, U1-U3, U5, U7, U10-U14 and amendments A1, A4, A5 and A7 (link it in
  the briefing).
- `/src/docsentinel/config.py`, `/src/docsentinel/engine.py`, `/tests/conftest.py`.

## Steps

1. Constants: `USER_SETTINGS_ENV = "DOCSENTINEL_SETTINGS"`, `USER_SETTINGS_OFF = "off"`, and
   `USER_SETTINGS_REFUSED_KEYS` (the C6 set, a `frozenset`).
2. `user_settings_path() -> tuple[Optional[Path], str]` returning the path and a state per the
   story's table (`Path.home()` failures map to `no-home`). Environment is read here only. A
   relative `HOME` is `no-home`; the resolved settings path must be absolute before any
   filesystem call (A4, U3). `missing` only when `os.stat()` raises `FileNotFoundError` or
   `NotADirectoryError` and `os.path.lexists()` is false; a dangling symlink or any other
   `OSError` is a `ConfigError` (A5, U7).
3. A permission gate per rules R1-R7 of the threat model (A1, A2): on POSIX, the R3 checks on the
   directory holding the configured path and the directory holding its final target, then the
   Task 03 open-once helper (`os.stat()` regular-file pre-check,
   `os.open(O_RDONLY | O_NONBLOCK | O_NOCTTY)`, `os.fstat()` of the descriptor as the
   authoritative R2 owner and mode check, bounded read from the same descriptor). Owner is
   `os.geteuid()` or `0`; when running as root only root-owned objects pass (R4). Any violation is
   a `ConfigError` with an R6 fixed phrase, never a warning (R5). On non-POSIX the ownership and
   mode checks are skipped with one `DEBUG` line (R1).
4. Layering in `load_config_with_sources()` per the story's steps 1 to 3, with the user-file
   message prefix in tilde form; `load_config()` delegates and returns only the `Config`.
   `ConfigSources` as specified. The tilde helper also matches the real path of the home
   (`os.path.realpath(Path.home())`); `ConfigSources` is never logged as an object and never
   enters a report context (A7, U11).
5. `engine.scan()` keeps calling `load_config(directory)` when no `Config` is injected (so the
   library and pytest plugin get the user layer); no other engine change.
6. `/tests/conftest.py`: an autouse fixture sets `DOCSENTINEL_SETTINGS=off` for every test, next to
   the existing log-directory isolation, so no test reads the real home. The fixture also points
   `XDG_DATA_HOME` at an empty per-test temporary directory, set and restored by hand (A7, U12).
   Tests that exercise the layer set the variable to a file in `tmp_path`; default-location tests
   also patch `Path.home()` to `tmp_path`.
7. `DEBUG` lines per the story's logging table.
8. Report a `Docs impact:` line (K, P, A).

## Files

`/src/docsentinel/config.py`, `/src/docsentinel/engine.py` (only if a call site must change),
`/tests/conftest.py`.

## Verification

- test_user_settings_policy.py and test_user_settings_location.py (Task 06) green with `-q`.
- Full suite green on a machine that has a real settings file (proves isolation).

## Acceptance

- [ ] Precedence defaults, user, project, CLI holds in every path (CLI, library, pytest plugin).
- [ ] Each refused key exits `2` naming key and file; allowed keys apply.
- [ ] `off`, `--no-user-settings` (Task 05) and the environment path behave as the table states.
- [ ] The user file is never read without the R2 check on `fstat()` of the descriptor it is read
      from, and a relative home or `DOCSENTINEL_SETTINGS` causes no filesystem access (threat
      model merge-gate conditions).
