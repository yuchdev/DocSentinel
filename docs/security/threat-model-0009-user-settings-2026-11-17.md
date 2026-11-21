# Threat Model - Milestone 0009 Story 03.0 User Settings and Strict JSON Config - 2026-11-17

Pre-implementation threat model for
[Story 03.0](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md)
([Task 02](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/02-threat-model-user-settings.md)):
the user settings file (layer 2 of plan contract C1), its location resolver and environment
(`DOCSENTINEL_SETTINGS`, `XDG_DATA_HOME`, `HOME`), the POSIX permission gate (plan decision D14),
the C6 refused-key policy, the strict JSON reader (C7) shared with `--config FILE.json`, the
`init --user` scaffold, and the `doctor`/logging surfaces. No code for this story exists yet. The
design under review is the story README and
[ADR 0005](/docs/adr/0005-layered-configuration-user-settings-json.md) (status Proposed). This
model is a standing input for Tasks 03, 04, 05 and 06; each of their briefings must link it.
Mitigation numbers M1, M2, ... and amendment numbers A1, A2, ... are local to this file.

Relevant weaknesses: CWE-276/CWE-732 (incorrect default or critical-resource permissions),
CWE-283 (unverified ownership), CWE-59 (link following), CWE-367 (TOCTOU), CWE-426/CWE-427
(untrusted search path), CWE-400/CWE-674/CWE-1333 (resource exhaustion, uncontrolled
recursion), CWE-248 (uncaught exception), CWE-20 (improper input validation), CWE-209/CWE-532
(information exposure through error messages and logs), CWE-117 (log injection), CWE-693
(protection-mechanism failure); OWASP A01:2021 Broken Access Control, A04:2021 Insecure Design,
A05:2021 Security Misconfiguration. Python's integer-string limit is the CPython fix for
CVE-2020-10735 (gh-95778, default 4300 digits; verified).

## Assets & trust boundaries

Assets:

- **The gate signal of every repository the user scans.** Exit codes 0/1/2 and "never a silent
  clean result". A user-level `ignore = ["DS"]`, `select = []`-style narrowing, a raised
  threshold, `root_escape_policy = "off"`, `missing_asset_policy = "off"` or `deep_confirm = true`
  changes results on every repository that does not set the same key itself.
- **The integrity of the user's own preferences** (a stricter `reference_scope = "strict"` that
  silently disappears is a weakening too).
- **Repository bounds** (scan selection, baseline, link root, configured index/mapping/template
  paths): must stay under repository control (C6).
- **The home path** (account name, PII) and file content: must not reach stderr, logs, reports
  or CI output except in tilde form and names-only form.
- **Availability** of `scan`, `baseline` and `doctor` (a bad file must exit `2`, never hang,
  never crash with a traceback, never exit `1` as if findings existed).
- **Test hermeticity**: the suite must never read the developer's real file.

Actors:

| ID | Actor | Capabilities |
|---|---|---|
| A1 | Owner (invoker) | Writes the settings file, the environment and argv. Trusted for their own runs. |
| A2 | Another local user on the same host | Cannot write the owner's private files. May write shared or mis-permissioned directories (umask 002, a shared `XDG_DATA_HOME`, `/tmp`). |
| A3 | Malicious repository | Controls the project config (TOML or a JSON named by the invoker), every committed file and symlink, and possibly environment-setting mechanisms the owner opted into (direnv `.envrc`, pytest-env, tox `setenv`, IDE workspace settings, Makefiles). Cannot write the owner's home directly. |
| A4 | CI runner | GitHub-hosted (ephemeral HOME) or self-hosted (persistent HOME shared by consecutive jobs, possibly from forks). |
| A5 | Dotfile manager | Replaces the file with a symlink into a dotfiles checkout (owner-owned) or a read-only store (Nix home-manager: root-owned, mode 0444, in a root-owned 0555 directory). |

Trust boundaries:

1. Environment (`DOCSENTINEL_SETTINGS`, `XDG_DATA_HOME`, `HOME`) to the location resolver.
2. The resolved path to the filesystem (permission gate, open, read): symlink following,
   ownership, TOCTOU.
3. Bytes to `json.loads()` to the decoded mapping (parser DoS, smuggling, number semantics).
4. Decoded mapping to the C6 filter and the shared builder (`_build_config`), and then to the
   effective `Config` (layer ordering).
5. `ConfigError` text, `ConfigSources`, `doctor` lines and log records to stderr, the per-run log
   file and CI logs (disclosure, injection).
6. Test process environment to the resolver (hermeticity).

Key structural observation: because of C6, **the user tier has no capability the project tier
lacks** (every allowed user key can also be set by a project config, which wins). A file that
reaches layer 2 can therefore never gain more than a repository already has over its own scan.
What it gains is **breadth and persistence**: it applies to every repository that does not set
the key, and it survives across runs. The gate protects that breadth.

## Evidence (confirmed in a scratch directory, not assumed)

Python 3.12.13, the project interpreter:

| Probe | Result | Consequence |
|---|---|---|
| `json.loads` of a 100,000-digit integer | `ValueError` ("Exceeds the limit (4300 digits) ..."), **not** `JSONDecodeError` | Task 03 must catch plain `ValueError` (M14) |
| Same, with `-X int_max_str_digits=0` (limit disabled by the invoker) | a 1 MiB integer parses in 0.89 s | bounded by the 1 MiB cap; acceptable |
| `json.loads("1e400")` | `inf`; `parse_constant` is **not** called | C7 "Infinity rejected" is bypassable (U8) |
| a 400-digit integer as `max_grade_level` in today's TOML | uncaught `OverflowError` in `float()`, traceback, **exit 1** | pre-existing CWE-248 with a misleading exit code (U8) |
| `max_grade_level = nan` in today's TOML | accepted (`nan <= 0` is false) | pre-existing validation gap (U8) |
| a 5,001-digit integer in a repository's TOML, then `docsentinel doctor` | raw `ValueError` traceback (doctor catches only `ConfigError`, `OSError`) | pre-existing; JSON must not inherit it (M14, F1) |
| nesting `[` x 3,000 | C scanner parses it | the parser alone does not bound depth below the Python recursion limit |
| nesting `[` x 100,000 | `RecursionError` | must map to `ConfigError` (M13) |
| recursive Python walk over a 1,400-deep parsed value | `RecursionError` | the `null` walk must be iterative (M13) |
| `json.loads(bytes)` of UTF-16 | decoded silently | never pass bytes to `json.loads` (M12) |
| UTF-8 BOM in a `str` | `JSONDecodeError` "Unexpected UTF-8 BOM" | explicit BOM check still required for the fixed phrase |
| `{"ignore":1,"ignore":2}` with a pairs hook | duplicate detected on decoded keys | escaped-duplicate smuggling is covered by the hook (U9) |
| `HOME=.` / `HOME=rel/dir` | `Path.home()` returns a **relative** path | the default location becomes CWD-relative, i.e. repository-controlled (U3) |
| `HOME=` (empty) | `Path.home()` returns `/` | absolute; the gate still applies |

## Permission rule (ruling on D14)

D14 is **ratified with refinements**. The rule applies to the user settings file only (default
location and a `DOCSENTINEL_SETTINGS` path alike), never to a project `--config` file.

| # | Rule |
|---|---|
| R1 | **Platform.** The ownership and mode checks run when `os.name == "posix"` (Linux, macOS, BSD, WSL, Cygwin). Elsewhere they are skipped with one `DEBUG` line `user settings: permission check skipped (non-POSIX)`; the regular-file, size and parse checks still apply. |
| R2 | **File, final target.** The decision is made on `os.fstat()` of the **opened descriptor** (symlinks followed to the final target, so a dotfile-manager link is allowed). The target must be a regular file; `st_uid` must be `os.geteuid()` or `0`; `st_mode & (S_IWGRP | S_IWOTH)` must be `0`. Read bits are not checked (the file holds no secrets). |
| R3 | **Directories.** Two directories are checked with `os.stat()`: the directory holding the configured path (where a symlink, if any, lives) and the directory holding the final target (`dirname(realpath(path))`; the same directory when there is no symlink). Each must be owned by `os.geteuid()` or `0`, and must either have no group/other write bit or have the sticky bit (`S_ISVTX`, as `/tmp`). Ancestors above these two are **not** checked (residual, U1). |
| R4 | **Root-owned accepted.** `st_uid == 0` is accepted for the file and both directories (Nix home-manager, admin-managed files; root can already change anything). When the process runs as root (`geteuid() == 0`) only root-owned objects pass, so `sudo` with a preserved `HOME` refuses the user's file instead of reading it as root. |
| R5 | **Error, never warning.** Any violation is a `ConfigError` (exit `2`), prefixed `user settings <tilde path>: ` per Contract 5. No warning mode, no override flag or variable; the escape hatches are fixing the mode (`chmod go-w`), `--no-user-settings` or `DOCSENTINEL_SETTINGS=off`. |
| R6 | **Messages.** Fixed phrases, no uid, no owner name, no mode digits of other objects, never the symlink target: `owned by another user`, `writable by group or others (run chmod go-w on it)`, `its directory is owned by another user or writable by others`. |
| R7 | **Order.** Directory checks (R3), then `os.stat()` pre-check (regular file, so a device or FIFO is never opened), then `os.open(O_RDONLY | O_NONBLOCK | O_NOCTTY)`, then `os.fstat()` (R2, authoritative), then a bounded read from the same descriptor. One open, one read, closed in `finally`. |

Rationale for R3: in a directory another user can write, that user cannot edit the owner's
file, but can rename over it with a symlink to any owner-owned or root-owned file, for example
an attacker-authored JSON object inside the owner's clone of a repository the attacker
contributes to. R2 alone passes that file (owner-owned, mode 0644). Checking the directory that
holds the link closes the swap; checking the target's directory closes the same swap one hop
later. The sticky exception keeps `DOCSENTINEL_SETTINGS=/tmp/...` usable in CI, because a sticky
directory forbids renaming another user's entry.

## Findings

### [HIGH] U1 A foreign-writable or foreign-owned settings file silently weakens every scan

- Vector / evidence: S9 and ADR Contract 3 step 2 check only the final target's owner and
  `S_IWGRP`/`S_IWOTH`, and leave directories, root-owned files and error-versus-warning open.
  A2 with write access to the file or to a directory on its path (umask 002 setups, a shared
  `XDG_DATA_HOME`, a `DOCSENTINEL_SETTINGS` under a shared directory) plants
  `{"ignore": ["DS"]}` or `{"profile": "deep", "deep_confirm": true}` or a raised threshold.
  Every allowed key applies to every repository that does not set it (README key policy table).
- Impact: silent clean results on all of the owner's local scans (CWE-732, CWE-283); a gate
  that reads green while checking nothing (CWE-693).
- Mitigation: M1 = R1-R7 above. M2: the INFO line and `doctor` show that a user layer applied
  (already designed); see U16 for naming the options.
- Tests (Task 06, mock, `test_user_settings_location.py`, `os.stat`/`os.fstat`/`os.geteuid`
  patched): `test_gate_refuses_file_owned_by_other_user`, `test_gate_refuses_group_writable_file`,
  `test_gate_refuses_world_writable_file`, `test_gate_accepts_owner_file_mode_0644`,
  `test_gate_accepts_root_owned_file`, `test_gate_as_root_refuses_user_owned_file`,
  `test_gate_checks_symlink_final_target_not_link`, `test_gate_refuses_writable_dir_holding_symlink`,
  `test_gate_refuses_writable_dir_holding_target`, `test_gate_accepts_sticky_world_writable_dir`,
  `test_gate_refuses_dir_owned_by_other_user`, `test_gate_skipped_on_non_posix`,
  `test_gate_messages_fixed_phrases_no_uid_no_target`. Integration (real chmod in `tmp_path`,
  POSIX only): `test_cli_group_writable_settings_exits_2`.

### [MEDIUM] U2 TOCTOU between the permission check and the read; FIFO or device swap

- Vector / evidence: ADR Contract 3 steps 2 and 3 are separate calls (`os.stat()` gate, then
  `load_json_options()` which stats and opens again). Between them, anyone able to rename in the
  directory swaps the checked file for another, or for a FIFO, which blocks `open()` forever
  (CWE-367, CWE-400). `load_json_options(source: Path)` takes a path, so it cannot share a
  descriptor with the gate as specified.
- Impact: gate bypass (U1 by race), or a hung `scan`/pre-commit.
- Mitigation: M3 = R7. The user layer opens once and decides on `fstat()` of that descriptor; the
  JSON bytes are read from the same descriptor. `load_json_options(source)` keeps its public
  signature and also uses the open-once path (pre-stat, `O_NONBLOCK` open, `fstat` regular-file
  check, bounded read), with the ownership check applied only by the user layer (amendment A1).
- Tests: `test_gate_decision_uses_fstat_of_opened_descriptor` (mock: `os.stat` reports a safe
  file, `os.fstat` an unsafe one; refused), `test_fifo_settings_file_refused_without_blocking`
  (integration, real `os.mkfifo`, POSIX only, with a pytest timeout guard),
  `test_json_loader_reads_once_from_one_descriptor` (unit, `os.open` call count 1).

### [MEDIUM] U3 A relative home turns "user settings" into a repository file

- Vector / evidence: confirmed that `HOME=.` or a relative `HOME` makes `Path.home()` relative,
  so the default location becomes CWD-relative. A3 commits that path in its tree; when the owner
  runs a scan with that directory as CWD (including scanning another, trusted repository from
  there), the repository's file is read as layer 2. It is owner-owned, so R2 passes
  (CWE-426/CWE-427).
- Impact: cross-repository injection of allowed keys into scans of other trees.
- Mitigation: M4. The resolver requires an absolute home; a relative home is state `no-home`
  (`DEBUG` line). The resolved settings path is asserted absolute before any filesystem call. A
  relative `XDG_DATA_HOME` is already ignored (S3) and a relative `DOCSENTINEL_SETTINGS` is
  already a `ConfigError` (S4).
- Tests: `test_relative_home_is_no_home`, `test_empty_xdg_and_relative_xdg_fall_back_to_home`,
  `test_relative_settings_env_is_config_error_value_not_echoed` (mock).

### [MEDIUM] U4 Persistent settings on a self-hosted CI runner poison later jobs

- Vector / evidence: A4. A job running untrusted code (a fork PR on a self-hosted runner) writes
  the default settings file under the runner's persistent home. It is owned by the runner user
  with mode 0600, so R2 passes, and every later job, including the protected branch, inherits
  `{"ignore": ["DS"]}`. ADR 0005 marks `DOCSENTINEL_SETTINGS=off` in CI as "Recommended" and
  Task 05 calls the CI line optional.
- Impact: a green merge gate across jobs (CWE-693).
- Mitigation: M5. `.github/workflows/ci.yml` sets `DOCSENTINEL_SETTINGS: off` at job level
  (required, not optional; unlike the python-extension gate, `off` only removes trust, so
  job-wide is the safe direction). The CI, pre-commit and library docs tell CI users to do the
  same, and name self-hosted runners explicitly.
- Tests: `test_ci_workflow_sets_settings_off` (integration, parses the workflow YAML text for
  the variable on every job that runs `docsentinel`), plus docs review in Task 07.

### [MEDIUM] U5 C6 bypass, repository paths or code execution through the user tier

- Vector / evidence: a user file naming a C6 key (by plain or escaped spelling), or a
  `telemetry_extensions` entry with `python:`; a project config trying to name the settings
  path.
- Impact: a personal file changing which documents every repository scans, its baseline or its
  bounds; code execution from a file.
- Mitigation: M6. C6 refusal runs on the **decoded** keys, before any value validation, and lists
  every refused key (ADR Contract 4). `python:` stays refused by the existing validator at every
  level. No configuration key names or influences the settings location: only the environment
  and the flag/keyword do, and an unknown key such as `user_settings` in a project file is the
  existing `Unknown config options` error. The drift test keeps the frozenset equal to C6 and a
  subset of `_CONFIG_OPTIONS`.
- Tests: `test_each_c6_key_refused_naming_key_and_file` (parametrised over the ten keys),
  `test_escaped_c6_key_refused`, `test_c6_refusal_precedes_value_validation`,
  `test_user_python_extension_refused`, `test_refused_keys_drift_matches_c6`,
  `test_project_config_cannot_name_settings_path` (unit).

### [MEDIUM] U6 Parser denial of service: size, nesting, huge integers, encodings

- Vector / evidence: Evidence table rows 1-2 and 6-10.
- Impact: hangs, memory spikes, tracebacks (CWE-400, CWE-674, CWE-248).
- Mitigation: M11 bounded read of `MAX_JSON_CONFIG_BYTES + 1` from the descriptor. M12 decode to
  `str` with strict UTF-8 first and pass only `str` to `json.loads` (no UTF-16/32
  auto-detection). M13 `RecursionError` maps to `nested too deeply`, and the `null` walk is
  iterative (an explicit stack), so a value the C scanner accepts can never overflow a Python
  walk. M14 `ValueError` that is not a `ConfigError` (the integer-string limit, `JSONDecodeError`)
  maps to a fixed phrase; the integer limit gets its own phrase `number out of range`. The
  `except` order is `ConfigError` (re-raise unchanged), `RecursionError`, `ValueError`, so a
  hook's own message is never rewritten as "invalid JSON". Python's limit is relied on, not
  re-implemented; if the invoker disables it, the 1 MiB cap bounds the cost (0.89 s measured).
- Tests: `test_json_size_exactly_1mib_accepted`, `test_json_size_1mib_plus_one_refused`,
  `test_json_deep_nesting_100k_refused_as_nested_too_deeply`,
  `test_json_null_walk_iterative_at_depth_3000` (parses, contains `null` at depth 3000, refused
  with the `null` phrase, no `RecursionError`), `test_json_100k_digit_integer_is_config_error`,
  `test_json_utf16_file_refused_as_not_utf8`, `test_hook_config_error_not_rewrapped` (unit,
  `test_json_config_loader.py`).

### [MEDIUM] U7 Silent fail-open when the default-location file cannot be read

- Vector / evidence: the story treats a missing default file as "skipped". If the resolver maps
  every `OSError` (a dangling dotfile symlink, `EACCES`, `ELOOP`) to `missing`, the owner's
  stricter settings disappear with no signal.
- Impact: silent weakening (fail-open, principle 5).
- Mitigation: M7. `missing` only when `os.stat()` raises `FileNotFoundError` or
  `NotADirectoryError` **and** `os.path.lexists()` is false. A dangling symlink, a permission
  error, a loop or any other `OSError` is a `ConfigError` (`Cannot read JSON config: not
  readable`). A `DOCSENTINEL_SETTINGS` path is never `missing` (S4).
- Tests: `test_default_location_absent_is_missing`, `test_default_location_dangling_symlink_is_error`,
  `test_default_location_permission_denied_is_error`, `test_env_path_absent_is_error` (mock).

### [MEDIUM] U8 Non-finite and overflowing numbers bypass C7 and crash the builder

- Vector / evidence: Evidence rows 3-5. `1e400` parses to `inf` without calling
  `parse_constant`. A 400-digit integer reaches `float(max_grade_level)` and raises an uncaught
  `OverflowError` (today, from TOML: traceback and exit 1, read by callers as "blocking
  findings"). `max_grade_level = nan` is accepted from TOML today and silences DS201.
- Impact: contract C7 violated; CWE-248 with a misleading exit code; a parity break if JSON
  refuses what TOML accepts.
- Mitigation: M8. JSON: a `parse_float` hook refuses a non-finite result (`NaN and Infinity are
  not allowed`). Shared builder (both formats): every float-valued option requires a finite,
  float-convertible value, and `OverflowError` maps to the option's **existing** message (for
  example `max_grade_level must be a positive number`). This changes TOML behaviour only for
  `nan`, `inf` and out-of-range values, which today are a silent gap or a crash; it is an allowed
  exception to Task 03's "behaviour identical" rule (amendment A6).
- Tests: `test_json_1e400_refused`, `test_json_negative_1e400_refused`,
  `test_numeric_overflow_int_is_config_error_both_formats`,
  `test_toml_nan_and_inf_refused_with_existing_message`, plus the parity test covers both formats.

### [LOW] U9 Duplicate-key smuggling, BOM, null, surrogates

- Vector / evidence: JSON is last-wins by default; TOML forbids duplicates. A file with two
  `ignore` keys (one escaped) would show a reviewer the first and apply the second.
- Mitigation: M9. `object_pairs_hook` refuses a duplicate at any depth on decoded keys; the
  message names the key bounded to 80 characters and neutralised. Explicit BOM check before
  parsing. `null` refused anywhere. Lone surrogates in strings reach validators as `str`; every
  echo goes through `safe()`/`neutralize_text`, which already neutralise U+D800-U+DFFF.
- Tests: `test_duplicate_key_top_level`, `test_duplicate_key_nested`,
  `test_duplicate_key_escaped_spelling`, `test_bom_refused`, `test_null_top_level_and_nested`,
  `test_duplicate_key_name_bounded_and_neutralised` (unit).

### [LOW] U10 Repository-influenced environment points `DOCSENTINEL_SETTINGS` at a committed file

- Vector / evidence: A3 through direnv, pytest-env, tox `setenv` or IDE settings the owner
  accepted. The committed file is owner-owned, so R2/R3 pass.
- Impact: bounded. By the structural observation above, the file gains nothing a project config
  of the same repository could not already set; it cannot name paths (C6). The residual is that
  it also applies when scanning another tree from that shell. That is the same trust the owner
  gave the repository's environment hooks.
- Mitigation: M10, accepted residual, documented in the configuration reference ("a tool that
  sets `DOCSENTINEL_SETTINGS` for you is trusted with your settings").
- Tests: covered by U5 tests (C6 still applies to an env-named file):
  `test_env_named_file_still_c6_restricted`.

### [LOW] U11 Disclosure: home path, file content, environment value, repr

- Vector / evidence: Contract 5 already makes `load_json_options()` messages path-free and keeps
  the bad `DOCSENTINEL_SETTINGS` value out of messages. Remaining gaps: (a) the tilde rule
  compares lexically with `Path.home()` only, so a path given through the home's real path (for
  example a symlinked `/home`) prints in full; (b) `ConfigSources.__repr__` contains the absolute
  path and would leak it if ever logged with `%r` or put in the report context; (c) existing
  validators echo values (`allowed_fence_languages` with `!r`, the full unknown-key list) without
  a length bound, for TOML today and for JSON by parity.
- Mitigation: M15. The tilde helper matches both `Path.home()` and `os.path.realpath()` of it,
  and the result goes through `safe()`. `ConfigSources` is never logged as an object and never
  enters `ReportModel` or a template context; `doctor` and the INFO line render it through the
  tilde helper and the file **name** only. Option values are never logged. (c) is follow-up F2.
- Assessment of the ADR 0005 refinements: path-free inner messages of `load_json_options()`
  (agreed: the prefix is the single place a path appears, in tilde form); the
  `DOCSENTINEL_SETTINGS` value not echoed for a bad value (agreed: it may hold an absolute home
  path; note that a *valid* absolute path outside home is still shown as given by the prefix,
  which is acceptable because the invoker chose it); `user_options`/`project_options` names only
  (agreed: names are schema-bounded by the unknown-key check, carry no values, and let `doctor`
  avoid a second read, which would also reopen U2).
- Tests: `test_tilde_form_for_home_and_its_realpath`, `test_no_absolute_home_in_info_or_doctor`
  (integration, asserts the `tmp_path`-based fake home never appears in stderr/stdout),
  `test_config_error_never_echoes_file_content` (unit, a sentinel string in the file never
  appears in any message), `test_config_sources_not_in_report_context` (unit).

### [LOW] U12 The test suite reads the developer's real settings file

- Vector / evidence: library and plugin now inherit layer 2. A test that deletes
  `DOCSENTINEL_SETTINGS` to exercise the default location, and forgets to patch the home, reads
  the developer's real file.
- Mitigation: M16. The autouse fixture in `/tests/conftest.py` sets `DOCSENTINEL_SETTINGS=off`
  **and** points `XDG_DATA_HOME` at an empty per-test temporary directory (second layer), set and
  restored by hand like the log isolation. Default-location tests patch `Path.home()` to
  `tmp_path` as well.
- Tests: `test_isolation_settings_off` (guard: `user_settings_path()` reports `off`),
  `test_isolation_default_location_is_temporary` (guard: with `DOCSENTINEL_SETTINGS` removed the
  resolved path lies under the temporary `XDG_DATA_HOME`).

### [LOW] U13 Environment read in several places; flag precedence

- Mitigation: M17. `DOCSENTINEL_SETTINGS`, `XDG_DATA_HOME` and `HOME` (via `Path.home()`) are
  read only in the private resolver in `config.py`. `user_settings=False` and
  `--no-user-settings` return `off` before reading the environment, so a malformed value cannot
  fail a run that opted out.
- Tests: `test_settings_env_read_only_in_resolver` (unit, AST scan of `src/docsentinel` for the
  two variable names and `os.environ` access), `test_user_settings_false_never_reads_env`
  (mock: relative garbage in the variable, no error).

### [LOW] U14 Non-POSIX platforms and ACLs

- Vector / evidence: Windows has no meaningful `st_uid`/mode; macOS and Linux ACLs can grant
  write without a mode bit; WSL drvfs mounts under `/mnt/c` report 0777 and are refused.
- Mitigation: accepted residual. R1 skip with a `DEBUG` line on non-POSIX; the profile directory
  ACLs protect the default location on Windows. ACLs are not inspected (same as OpenSSH
  StrictModes). The WSL false positive is documented with the fix (keep the file in the Linux
  home). Test: `test_gate_skipped_on_non_posix` (U1).

### [LOW] U15 `init --user` creation

- Vector / evidence: `os.makedirs(..., mode=0o700)` applies the mode only to the leaf; under
  umask 002 the intermediate directories come out 0775; a pre-existing symlink at the target
  must not be followed; a directory failing R3 would produce a file the next load refuses.
- Mitigation: M18. Create each missing directory with its own `os.mkdir(path, 0o700)`; create the
  file with `O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW` (where available) and mode `0o600`, then
  `fchmod(0o600)` on the descriptor so a restrictive or permissive umask cannot change it; run the
  R3 directory check first and refuse with exit `2` (same phrase) before creating anything.
- Tests: `test_init_user_creates_0600_file_and_0700_dirs_under_umask_002`,
  `test_init_user_refuses_existing_symlink`, `test_init_user_refuses_unsafe_directory`,
  `test_init_user_twice_exits_2` (integration).

### [LOW] U16 Repudiation and reproducibility: which settings changed this result

- Vector / evidence: reports do not record the user layer (ADR consequence). The INFO line only
  says `user settings loaded`.
- Mitigation: M19. The INFO line names the user-layer options (names only, sorted, bounded to
  the first 20, then `and N more`), for example
  `config: user settings loaded (ignore, reference_scope), project docsentinel.toml`. The per-run
  log file records the same at DEBUG (already designed). Recording it in reports stays out of
  scope.
- Tests: `test_info_config_line_names_user_options_not_values` (integration).

### Not applicable / no finding

- **Secrets.** Configuration holds no credentials; nothing in `.mcp.json` is touched.
- **Shell or SQL injection.** No shell-out, no database; values only reach typed validators.
- **Prompt injection.** No AI backend in this path.
- **`DOCSENTINEL_PROD_CONFIRMED`-style guard.** Not applicable; `deep_confirm` at user level is
  the owner's standing consent (ADR Contract 4) and deep findings stay advisory-only.

## Follow-ups (pre-existing, outside the story's acceptance)

- **F1** `_load_toml_table()` lets the integer-string `ValueError` escape as a plain
  `ValueError`; `doctor` then crashes with a traceback on a repository's TOML. Fix in Task 03,
  which refactors that reader anyway: map `ValueError` to `Cannot read <path>: number out of
  range`. Owner: python-expert; test `test_doctor_survives_oversized_toml_integer`.
- **F2** Bound value and key echoes in existing validators (`allowed_fence_languages` `!r`, the
  unknown-key list) to 80 characters per item and the first 20 items, in TOML and JSON together
  so parity holds. Owner: python-expert, separate change.
- **F3** The TOML reader has no size cap for project files; apply the same 1 MiB bounded read.
  Separate change.

## Mitigation-to-test map

| Mitigation | Implements | Test file (Task 06) |
|---|---|---|
| M1 (R1-R7), M3 | Task 04 (gate), Task 03 (open-once reader) | mock test_user_settings_location.py; unit test_json_config_loader.py; integration test_user_settings_cli_ds101_ds103.py |
| M4, M7, M10, M17 | Task 04 | mock test_user_settings_location.py |
| M5 | Task 05 (workflow line), Task 07 (docs) | integration test_user_settings_cli_ds101_ds103.py |
| M6 | Task 04 | unit test_user_settings_policy.py |
| M8, M9, M11-M14 | Task 03 | unit test_json_config_loader.py, test_config_message_parity.py |
| M15 | Tasks 03-05 | unit and integration as named in U11 |
| M16 | Task 04 (conftest) | guards in mock test_user_settings_location.py |
| M18, M19 | Task 05 | integration test_user_settings_cli_ds101_ds103.py |

## Required spec amendments

Apply before the named task starts; the ADR amendments before ADR 0005 moves to Accepted.

- **A1 (ADR 0005 Contract 3, steps 2-3; Task 03 step 2; Task 04 step 3).** Replace the separate
  gate `os.stat()` and read with one open: directory checks, `os.stat()` regular-file pre-check,
  `os.open(O_RDONLY | O_NONBLOCK | O_NOCTTY)`, `os.fstat()` on the descriptor (authoritative
  regular-file, owner and mode check), bounded read from the same descriptor.
  `load_json_options(source)` keeps its signature and uses the same open-once helper without the
  ownership check.
- **A2 (ADR 0005 Contract 3 step 2, story S9, plan D14).** Replace "Task 02 rules on ..." with:
  "Rules R1-R7 of the threat model threat-model-0009-user-settings-2026-11-17.md: final target
  and the two holding directories owned by the effective user or root, no group/other write
  (sticky directories allowed), root-run accepts only root-owned, any violation is a
  `ConfigError` (exit 2), skipped on non-POSIX." Mark D14 ratified.
- **A3 (ADR 0005 Contract 5 reason list).** Add `number out of range` (integer-string limit and
  float overflow), `not readable` (any `OSError` other than an absent default file), and the
  three R6 gate phrases. Add: "a `ConfigError` raised inside a hook propagates unchanged".
- **A4 (story "Settings path and environment"; ADR Contract 3 step 1; Task 04 step 2).** "A
  relative `HOME` is `no-home`; the resolved settings path must be absolute before any
  filesystem call."
- **A5 (same places).** "`missing` only when `os.stat()` raises `FileNotFoundError` or
  `NotADirectoryError` and `os.path.lexists()` is false; a dangling symlink or any other
  `OSError` is a `ConfigError`."
- **A6 (Task 03 steps 1-2).** Add: "pass only `str` to `json.loads`; `parse_float` refuses a
  non-finite result; the `null` walk is iterative; `except` order `ConfigError` (re-raise),
  `RecursionError`, `ValueError`. Float-valued options require a finite, float-convertible value
  and map `OverflowError` to the option's existing message, in TOML and JSON (allowed exception
  to 'behaviour identical'; it fixes the TOML `nan` and overflow crash). `_load_toml_table()`
  maps the integer-limit `ValueError` to `ConfigError` (F1)."
- **A7 (Task 04 steps 4 and 6).** Add: "the tilde helper also matches the real path of the home;
  `ConfigSources` is never logged as an object and never enters a report context; the autouse
  fixture also points `XDG_DATA_HOME` at an empty temporary directory."
- **A8 (Task 05 step 2).** Replace the directory and file creation text with: "create each
  missing directory with `os.mkdir(path, 0o700)`; run the R3 directory check and refuse first;
  open with `O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW`, mode `0o600`, then `fchmod(0o600)`."
- **A9 (Task 05 new step; ADR "Affected components" CI row).** "Set `DOCSENTINEL_SETTINGS: off`
  at job level in the CI workflow (required, not optional)."
- **A10 (Task 05 step 4; story Logging table).** INFO text becomes
  `config: user settings <state>[ (<names>)], project <file name or none>`, names sorted, at most
  20 then `and N more`, never values.
- **A11 (Task 06 steps 1, 4, 5, 6).** Add every test named in U1-U16 and F1 above; the gate tests
  patch `os.fstat` and `os.geteuid` as well as `os.stat`; the FIFO and chmod tests are POSIX-only
  with a timeout.
- **A12 (Task 07).** Document R1-R7 with the `chmod go-w` fix, the WSL drvfs note, the
  self-hosted runner advice (U4), and that a tool setting `DOCSENTINEL_SETTINGS` is trusted with
  the user's settings (U10).

## Verdict: PASS_WITH_FOLLOWUP

Story 03.0 close review (2026-11-18, last section): **PASS_WITH_FOLLOWUP**. No merge-gate
condition holds; C-1 (doc wording) is required before close, everything else open is optional.

There is no CRITICAL finding. C6 already ensures the user tier has no capability the project
tier lacks, so no finding is an elevation; the risks are breadth (U1, U4), races (U2), a
CWD-relative home (U3) and parser and number edge cases (U6, U8). All are mitigated in design,
provided amendments A1-A11 land before Tasks 03-06 start and A12 before Task 07.

Merge-gate conditions for the human reviewer and the merge-blocking hook. Any of the following
in a Story 03.0 change is a **BLOCK** and must be kept out of `master`:

- the user file is read without the R2 check on `fstat()` of the descriptor it is read from, or
  a violation only warns;
- a refused C6 key or a `python:` extension from the user file reaches `Config`;
- a relative home or a relative `DOCSENTINEL_SETTINGS` causes any filesystem access;
- any `ConfigError`, log line, `doctor` line or INFO line contains file content, an option value,
  the `DOCSENTINEL_SETTINGS` value of a refused setting, or the absolute home path;
- a JSON config input produces an uncaught exception, a hang, or an exit code other than `2`;
- the test suite can resolve the developer's real settings file.

ADR 0005 may move to Accepted on this verdict once the owner signs off and A1-A5 are folded in.

## Task 03 implementation review (2026-11-17)

Scope: uncommitted `src/docsentinel/config.py` (`MAX_JSON_CONFIG_BYTES`, `_read_config_once`,
`_parse_json_options`, `load_json_options`, `_read_project_options`, `_finite_number`, F1 in
`_load_toml_table`). Evidence: the implementer's 67 probes (all pass) plus independent probes
(cap boundaries, duplicate-key echo, lone surrogate and NUL strings through `scan`/`baseline`,
huge integers in int-valued options, a 5,000-character unknown key).

### Mitigation check

| Item | Result | Evidence |
|---|---|---|
| U2 / R7 / A1 | Met | `config.py:812-859`: `os.stat` pre-check, one `os.open` with `O_NONBLOCK`/`O_NOCTTY` (`:121`), `os.fstat` regular-file check, then `check_descriptor(status)` (`:846`) before any read, bounded read from the same descriptor, `os.close` in `finally` (`:859`). The descriptor is created immediately before the `try`, so no leak path; Python descriptors are non-inheritable (PEP 446). The hook runs on the read descriptor's `fstat`, so Task 04's R2 decision is authoritative. FIFO, FIFO swap and directory refused without blocking. |
| U6 / M11-M14 | Met | Exactly 1,048,576 bytes accepted; cap+1 (including one trailing newline) refused. Strict UTF-8, BOM check, `str`-only `json.loads`; `except` order `ConfigError`, `RecursionError`, `JSONDecodeError`, `ValueError` (`:955`); iterative `null` walk (`:900`). `MemoryError` is not mapped; unreachable in practice under the 1 MiB cap (accepted). |
| U8 / A6 | Met | `parse_float` refuses overflow; `_finite_number` (`:985`) maps `bool`, `nan`, `inf` and `OverflowError` to `None`, so each float option keeps its existing message in TOML and JSON. Int-valued options with a 400-digit integer scan without error (no float conversion). |
| U9 | Met | Duplicate keys refused at any depth on decoded keys, including escaped spellings; echo bounded to 80 characters and neutralised by `safe()` (`:873`; RLO and ESC rendered as escapes). |
| U11 | Met for Task 03 | `load_json_options` messages are fixed phrases with line/column only; no content echo found. DEBUG lines (`:1022`, `:1040`) log the project path through `safe()` and option names only. |
| F1 | Met | `:785` maps the integer-limit `ValueError` after the `TOMLDecodeError`/`UnicodeDecodeError` clause; `doctor` survives. |
| TOML trust behaviour | Unchanged | Discovery, the `pyproject.toml` wrap and messages are as before; the only TOML deltas are A6 and F1 (sanctioned). |

### Findings

#### [LOW] T03-1 Lone surrogates are a new input class reachable only through JSON

- Vector / evidence: TOML cannot express a lone surrogate; JSON `"\ud800"` can. In `baseline`,
  `deprecated_references_file` or `report_templates_dir` it raises `UnicodeEncodeError` at the
  first filesystem call. The CLI still exits `2` with a neutralised generic codec message (it
  catches `ValueError`), but `docsentinel.scan()` library callers get a `ValueError` that is not a
  `ConfigError` (CWE-176, CWE-248 for library callers).
- Impact: a misleading message and a parity gap between TOML and JSON; no gate bypass, no hang.
- Mitigation: refuse a lone surrogate in any JSON key or string during the iterative walk
  (`_json_contains_null` or a sibling) with a fixed phrase such as `not valid Unicode`.
  Owner: python-expert; test `test_json_lone_surrogate_refused` (testing-expert). Required before
  Task 04 reuses the parser for the user settings file.

#### [LOW] T03-2 Unknown-key echo is unbounded (pre-existing F2, newly reachable from JSON)

- Vector / evidence: `config.py:765`; a 5,000-character key gives a 5,043-character `Scan failed:`
  line. It is neutralised (RLO rendered as `\u202e`), so there is no injection, only noise
  (CWE-117 mitigated, CWE-400 cosmetic).
- Mitigation: land F2 (80 characters per item, first 20 items) in TOML and JSON together.

#### [LOW] T03-3 Notes for Task 04 (no code change in Task 03)

- An `OSError` raised inside `check_descriptor` is rewritten to `not readable`. The hook must
  raise only `ConfigError`, and the R3 directory checks must run before `_read_config_once`.
- The pre-stat-to-open window still lets a renamer substitute a device node, which is then opened
  (non-blocking, no controlling terminal) before `fstat` refuses it. For the user file, R3 closes
  this; for a project `--config` the invoker chose the path. Accepted residual.
- Do not route the user settings path through `_read_project_options` DEBUG logging; log it in
  tilde form (U11, A7).
- F3 is still open: a project TOML `--config` that names a FIFO blocks `tomllib`. Reusing
  `_read_config_once` for TOML would close it.

### Verdict: PASS_WITH_FOLLOWUP

No CRITICAL or HIGH finding, and no merge-gate condition is hit: every malformed JSON input probed
exits `2` without a traceback or content echo, and the descriptor hook is placed where Task 04
needs it. T03-1 must be fixed before Task 04 merges. T03-2 (F2) and F3 remain follow-ups.

## Task 04 implementation review (2026-11-17)

Scope: uncommitted `src/docsentinel/config.py` (`user_settings_path`, `_home_directory`,
`_tilde_path`, `_user_settings_exist`, `_owner_trusted`, `_check_user_settings_directories`,
`_check_user_settings_descriptor`, `_read_user_options`, `_load_user_layer`,
`load_config_with_sources`, `ConfigSources`), `src/docsentinel/__init__.py`, `tests/conftest.py`.
Evidence: the implementer's 87 probes plus 45 independent probes on real files, modes, symlinks
and a FIFO in a scratch directory (`os.geteuid`, `os.fstat` patched where another owner or a
`stat`/`fstat` split was needed; `os.stat`/`os.open`/`os.path.lexists` spied for the zero-access
cases). The developer's real settings file was not modified (its `stat` was unchanged after the run).

### Mitigation check

| Item | Result | Evidence |
|---|---|---|
| R2 / U2 | Met | The only read of the user file is `_read_config_once(path, check_descriptor=_check_user_settings_descriptor)` (`config.py:1316`); the decision runs on `fstat` of the read descriptor. A probe where `os.stat` reported a clean file and `os.fstat` a world-writable one was refused (`writable by group or others`). The hook raises only `ConfigError` (T03-3). |
| R3 | Met for the two directories, gap for chains | A link or target in a world-writable non-sticky directory, and a symlinked parent directory that points into one, are refused. A sticky directory is accepted. Gap: see T04-1. |
| R4 | Met | `_owner_trusted` (`:1248`) accepts `{geteuid(), 0}`. When `euid` is 0 this is `{0}` only, so a user-owned directory or file is refused. |
| R1, R5, R6, R7 | Met | `os.name` gate with a DEBUG line; errors only, never warnings; the three fixed phrases with no uid, mode or target; order R3, pre-stat, open, fstat, read. |
| U3 / A4 | Met | `HOME` set to `.`, `rel/dir`, an empty string, `/` or `//`, and a relative or ESC-bearing `XDG_DATA_HOME`, all give `no-home` with **zero** `stat`/`open`/`lexists` calls on any settings path. A relative, RLO-bearing or surrogate-escaped `DOCSENTINEL_SETTINGS` is a `ConfigError` before any filesystem call, and the value is not echoed. |
| U7 / A5 | Met | An absent default file gives `missing`. A dangling symlink, `EACCES` on the directory, a symlink loop and an absent `DOCSENTINEL_SETTINGS` file all give `not readable` (`:1240-1244`). A FIFO gives `not a regular file` without blocking. |
| U5 / C6 | Met | `baseline`, and `link_root` carrying a wrong-typed value, are refused by name before any value validation (`:1320`). The escaped spelling `\u0062aseline` was refused as well (see T04-3 for the phrase). Case, fullwidth, zero-width and dotless-i variants are not known options and fail as `Unknown config options`, so they never reach `Config`. A `python:` extension is refused. No project key can name the location (`user_settings` is an unknown option); `root` and `path` are not inputs to `_load_user_layer`. |
| U11 | Met for messages | The prefix shows the tilde form for the home and for the home's real path; an invalid value gives the validator's phrase (the sentinel value was not echoed for `profile`); `ConfigError` is logged by the CLI without `exc_info`. Residual: T04-2. |
| U12 / U13 | Met | The autouse fixture sets `DOCSENTINEL_SETTINGS=off` and points `XDG_DATA_HOME` at an empty per-test directory, saves both and restores both in `finally`. No test builds a subprocess environment from scratch. `user_settings=False` returns before the environment is read (garbage value, no error). Outside `config.py`, no `src/` module reads the variables. |
| Deviations | Accepted | Treating a `/` home as `no-home` is stricter than the evidence table and is correct, because `/.local/share` is not a real home. Reporting an absent `DOCSENTINEL_SETTINGS` file as `not readable` uses the A3 phrase and fails closed (S4). |

### Findings

#### [MEDIUM] T04-1 R3 skips the directories that hold intermediate links in a symlink chain

- Vector / evidence: `config.py:1271-1272` checks only `dirname(path)` and
  `dirname(realpath(path))`. Probe: `safe/l7.json -> ../ww/mid -> ../clone/evil.json`, with
  `ww` mode 0777 and not sticky, **loaded** the owner-owned `evil.json` (`ignore = ["DS"]`). A
  directory-level chain `safe/dlink -> ../ww/dmid -> ../clone` loaded it too. Another user who can
  write `ww` replaces `mid` and sends the read to any file the owner owns in a safe directory. No
  race is needed. This is the swap from the R3 rationale, moved one hop along the chain
  (CWE-59, CWE-732).
- Impact: U1 by redirection. It needs the owner to have set up a chain that passes through a
  foreign-writable directory, which is unusual. Nix and home-manager chains pass through
  root-owned sticky `/nix/store` and still pass. The implementation follows the letter of R3;
  the gap is in the rule.
- Mitigation: tighten R3. Walk the chain with `os.lstat`/`os.readlink`, at most 40 hops, and
  apply the directory rule to the directory that holds every link: the configured path, each
  intermediate link, and each symlinked directory component met while resolving below the
  configured path's own directory. Then check the final target's directory. A hop over the limit
  is `not readable`. Tests: `test_gate_refuses_chain_through_writable_dir` (file chain and
  directory chain) and `test_gate_accepts_chain_through_sticky_root_dir`. Owners: python-expert
  (fix), testing-expert (tests). This is required before Story 03.0 closes. It does not block
  this task's merge.

#### [LOW] T04-2 The exception chain carries the absolute path

- Vector / evidence: `:1241`, `:1244`, `:1277` and `:888`/`:905` use `raise ... from exc`. The
  `__cause__` is the `OSError`, whose text holds the full untilded path (probe:
  `FileNotFoundError`, absolute path present). The CLI does not log it, but a library caller,
  or the pytest plugin when `load_config` fails inside a test, prints the chained traceback.
  The absolute home path then reaches CI logs (CWE-209, U11).
- Mitigation: in the user layer, raise the `ConfigError` with `from None`, as the scan-root
  resolver in `cli.py` already does, or replace the cause with a path-free one. Test:
  `test_user_settings_error_cause_has_no_absolute_path`.

#### [LOW] T04-3 `null` and unknown-key checks run before the C6 refusal

- Evidence: `{"baseline": 5, "include": null}` is refused with the `null` phrase, not as a
  C6 refusal (`:1016-1017` run before `:1320`). The C6 key still never reaches `Config`, so the
  merge gate is not affected. The message names the wrong problem only. The pre-existing F2
  echo bound remains open for unknown keys, which now come from the user file too.
- Mitigation: none required. Optionally, run the C6 intersection on the decoded keys before
  `_json_check_values`.

### Verdict: PASS_WITH_FOLLOWUP

No CRITICAL or HIGH finding, and none of the merge-gate conditions holds. Every read is gated on
the read descriptor's `fstat`. A violation is an error. C6 keys and `python:` never reach
`Config`. Relative or control-bearing locations cause zero filesystem access. No message
contains file content, a refused environment value or an untilded home path. The suite cannot
resolve the real file. T04-1 must be fixed before Story 03.0 closes. T04-2 should land with
Task 05, which adds the `doctor` and INFO rendering.

### Re-check (2026-11-17, after the T04-1 and T04-2 fixes)

Scope: `_user_settings_link_directories` (`config.py:1263`) and the `from None` changes
(`:892`, `:909`, `:1245`, `:1248`, `:1299`, `:1332`, `:1409`). All 45 earlier probes were re-run,
plus 13 probes aimed at the walker.

- **T04-1 closed.** Both chain repros are now refused with the directory phrase: a file chain
  and a directory chain through a world-writable intermediate directory. Also refused: `..`
  after a directory link that lands in a writable directory, and a link whose target directory
  is itself a link held in a writable directory. Accepted, as they should be: relative links,
  `..` after a link into a safe directory, and `/tmp` on macOS (a root-held link to the sticky
  `/private/tmp`). A link loop fails closed.
- **T04-2 closed.** No `__cause__` remains, the context is suppressed, and no absolute path
  appears in the chain.
- **TOCTOU between the walk and the open:** every directory that holds a link has been
  checked, so another user cannot rename an entry in it. The final `fstat` (R2) still decides
  the file. Residual: T04-4.
- **Note (no action):** chains of 40 and 41 links give `not readable` rather than `too many
  symbolic links`. The earlier `os.stat` hits the kernel's own limit first (32 on macOS). This
  fails closed; only the message differs.

#### [MEDIUM] T04-4 A link owned by another user in a sticky directory is followed

- Vector / evidence: the sticky exception checks the directory but not who owns the link in
  it. With `os.lstat` reporting uid 4242 for `sticky/s.json -> clone/evil.json`, the file
  **loaded** `ignore = ["DS"]`. The same happened through a directory link in the sticky
  directory. On a shared host, another user can plant a symlink at a `DOCSENTINEL_SETTINGS`
  path under `/tmp` before the owner creates the file, and send the read to any owner-owned
  JSON file in a safe directory. Linux `fs.protected_symlinks=1` blocks this; macOS and BSD
  have no such protection (CWE-59, CWE-377).
- Mitigation: in the walker, when the directory holding a link has a group or other write bit
  (allowed only because it is sticky), require the link's `lstat().st_uid` to pass
  `_owner_trusted`. This is the `protected_symlinks` rule. Otherwise raise `its directory is
  owned by another user or writable by others`. Tests:
  `test_gate_refuses_foreign_link_in_sticky_dir` (file link and directory link) and
  `test_gate_accepts_own_link_in_sticky_dir`. Owners: python-expert, testing-expert. This is
  required before Story 03.0 closes. It does not block the Task 04 merge: the default location
  never passes through a sticky directory, and the sticky exception was a deliberate design
  choice in R3.

### Re-check verdict: PASS_WITH_FOLLOWUP

T04-1 and T04-2 are closed. No merge-gate condition is hit. T04-4 (new) and T04-3 remain as
follow-ups.

Re-check 2 (2026-11-18): **T04-4 closed.** A symlink owned by another user in a sticky directory, whether a file link or a directory link, is now refused with the directory phrase. The `/tmp` root-held link, the owner's own file in a sticky directory and all earlier walker and gate probes are unchanged. No new finding. Verdict stays **PASS_WITH_FOLLOWUP**: only the optional T04-3 remains.

## Task 05 implementation review (2026-11-18)

Scope: uncommitted `src/docsentinel/cli.py` (`_run_init_user`, `_missing_directories`,
`_init_user_refused`, `--no-user-settings` on `scan`/`baseline`/`doctor`,
`_doctor_config_source_lines`, `_config_sources_text`, the shared `doctor` load), the
`final_is_directory` keyword of `_user_settings_link_directories` and
`_check_user_settings_directories` in `src/docsentinel/config.py`, and
`.github/workflows/ci.yml`. Evidence: 30 subprocess probes with `HOME`, `XDG_DATA_HOME`,
`DOCSENTINEL_SETTINGS` and `DOCSENTINEL_LOG_DIR` pointed at a scratch directory, plus 7
in-process probes with `os.mkdir`, `os.open` and `os.fdopen` patched to simulate races and
failures. The developer's real settings file was not touched (its inode, size and mtime were
the same after the run).

### Mitigation check

| Item | Result | Evidence |
|---|---|---|
| U15 / A8 modes | Met | Under umask 002, 000, 022 and 077, every created directory is `0700` and the file is `0600`. This holds for nested `DOCSENTINEL_SETTINGS` paths and for the default `~/.local/share/docsentinel` path. A umask can only remove bits from `os.mkdir(..., 0o700)`, and `fchmod` resets the file mode. A pathological umask of `0o200` produces a `0500` directory, after which creation fails with exit 2 (fail-closed). |
| U15 R3 before creation | Met | A `0777` non-sticky deepest existing directory is refused with the R3 phrase, and nothing is created. A symlinked component that points into a `0777` directory is refused, and nothing is created in the target. The user's own link into the user's own `0700` directory is accepted. A sticky `1777` ancestor is accepted, and the directories created under it are `0700`. |
| No overwrite, no follow | Met | A pre-planted symlink at the file path is refused with `already exists` and exit 2, whether it points at an owner file or dangles. The victim is unchanged, and no dangling target is created. A symlink planted between the last `mkdir` and the `open` fails with `EEXIST` (`O_CREAT|O_EXCL`), and the victim is unchanged. A second run exits 2. |
| TOCTOU, check to create | Met (fail-closed) | The window includes the interactive prompt, so it is unbounded. A symlink or directory planted at the first missing component after the R3 check makes `os.mkdir` raise `FileExistsError`, and the run exits 2. No entry can be swapped later: each directory we create is ours and `0700`, and R3 already established that the deepest existing directory is not writable by others, or is sticky (no foreign renames). In that sticky case, T04-4 refuses a foreign link. |
| Partial failure | Met for the file | When a write fails after `O_EXCL` succeeded, the file is unlinked, so no half-written file remains for the next load to refuse. Directories created before a failure are kept (empty, `0700`), which is harmless. See T05-1. |
| U3 / A4, refused env | Met | `HOME=.` gives `the home directory is unknown` and creates nothing in the CWD. `off` is refused. A relative, ESC-bearing or RLO-bearing `DOCSENTINEL_SETTINGS` is refused, and the value never appears on stderr or in the log file. `--user --project-root` is an argparse error. With `--no-user-settings`, a garbage value is never read (exit 0). |
| U11 no absolute home | Met | For a real home and for a symlinked home (realpath match), stdout, stderr and the per-run log show only `~/.local/share/docsentinel/settings.json`. The OSError reason is `strerror` only, so it holds no path. An invoker-chosen `DOCSENTINEL_SETTINGS` or `XDG_DATA_HOME` outside home is shown as given, which U11 accepts. |
| U16 / A10 INFO line | Met | A valid 57-option user file gives `config: user settings loaded (<20 sorted names> and 37 more), project none` (518 characters). Neither `DS999` nor `13.37` appears in stderr, the log or `doctor`. The names come from a validated file, so an unknown key never reaches the line. `off` and `--no-user-settings` give `user settings off`. |
| Injection through names or errors | Met | A user file whose unknown key holds an OSC title sequence (`ESC ] 0;pwn BEL`) is rendered `\x1b]0;pwn\x07` in `doctor`, in `Scan failed:` and in the log file. No raw ESC or BEL appears. |
| U4 / A9 CI | Met | `DOCSENTINEL_SETTINGS: "off"` is set at job level on `test`, the only job that runs `docsentinel` (`release.yml` only runs `uv build`). The value is quoted, so it parses as the string `'off'`. Unquoted YAML 1.1 `off` would parse as `False`, which Actions would pass as `false`, and that is a relative path that fails every scan. |

### Findings

#### [LOW] T05-1 A raced or `..` intermediate directory is reported as "settings file already exists"; created directories are kept on failure

- Vector / evidence: `cli.py:615` maps every `FileExistsError` raised before the file was
  created to `<path> already exists; not overwriting it`, and that includes an `os.mkdir` of an
  intermediate directory (`cli.py:599-600`). Probes: a component planted after the R3 check, and
  `DOCSENTINEL_SETTINGS=/x/p7/a/../b/settings.json` (`_missing_directories` lists `a/..`, which
  `mkdir` reports as existing). Both exit 2, but the message is false, and in the `..` case `a`
  is left behind. A failure partway leaves the earlier `0700` directories in place.
- Impact: fail-closed, with no security effect. The message misleads the user (CWE-209 does not
  apply, because nothing leaks).
- Mitigation (optional): only map `FileExistsError` from the final `os.open` to `already exists`.
  Report an intermediate one as `Cannot create user settings <tilde>: a directory on the path
  appeared or is not creatable`. Optionally, refuse a `DOCSENTINEL_SETTINGS` holding `.` or `..`
  components for `init --user`, or `rmdir` the directories this run created, in reverse order,
  on failure. Test: `test_init_user_raced_intermediate_dir_exits_2`.

#### [LOW] T05-2 `doctor` prints the same unbounded configuration error on four lines

- Vector / evidence: `cli.py:200`, `:341`, `:361` and `:392` each print
  `neutralize_text(str(error))` without a length bound. Probe: a user file with 2,000 unknown
  keys of 55 characters gave 457 KB of `doctor` stdout in 4 lines of 114 KB each. A project
  `docsentinel.toml` from an untrusted checkout can do the same. Spec step 3 says "one
  neutralised error line". The template and extension lines already did this before Task 05,
  and Task 05 adds the sources line, which makes four. This amplifies the pre-existing F2 / T03-2
  (CWE-400, CWE-117 mitigated by neutralisation).
- Impact: terminal or log flooding only. Output stays neutralised, so no injection.
- Mitigation (optional, fold into F2): render the error once through `safe(error, limit=...)`
  (for example 500), print it on the `config sources: error:` line, and make the other three
  lines `unavailable (see config sources)`. Test: `test_doctor_config_error_one_bounded_line`.

#### [INFO] T05-3 `init --user` is stricter than the load gate for the deepest existing ancestor

- Evidence: `cli.py:584` applies R3 to the deepest existing directory. On a first run that is
  often `~` or `~/.local`, so a group-writable home refuses `init --user`. The load gate would
  accept a file in a `0700` `docsentinel` directory there, because R3 does not check ancestors
  (residual U1).
- Impact: none for security. This is the right direction: a group-writable home lets group
  members rename `~/.local`.
- Mitigation (optional): mention it in the Task 07 user documentation next to the `chmod go-w`
  advice (A12).

#### [INFO] T05-4 The confirmation prompt shows a path cut to 200 characters

- Evidence: `shown = _tilde_path(path)` (`cli.py:578`) goes through `safe()`, so a path longer
  than 200 characters ends in `...` in `Create <path>? [Y/n]` (`:591`) and `Created <path>`
  (`:620`).
- Impact: for a very long `DOCSENTINEL_SETTINGS` path, the user confirms a path they cannot fully
  see. The invoker set that path, so there is no cross-trust effect.
- Mitigation (optional): use `neutralize_text` without the cap for the prompt and the `Created`
  line, and keep `safe()` for log records.

Not a finding: a `ValueError` from `os.mkdir` or `os.open` (for example an embedded NUL) would
escape `_run_init_user`, but `user_settings_path` refuses Cc/Cf/Cs/Zl/Zp in every source path,
so it cannot be reached.

### Verdict: PASS

There is no CRITICAL, HIGH or MEDIUM finding, and no merge-gate condition is hit. Creation is
umask-independent and runs R3 before anything is created. No race found by the probes follows a
symlink: every one fails closed with exit 2, and a failed write leaves no file. No absolute home
path, option value or refused `DOCSENTINEL_SETTINGS` value reaches stderr, the log file or
`doctor`. Option names are schema-validated, bounded to 20 and neutralised. CI disables the user
layer with a correctly quoted `"off"` on its only `docsentinel` job. T05-1 and T05-2 are
optional follow-ups (T05-2 goes with F2). The optional T04-3 remains open.

## Story 03.0 close review (2026-11-18)

Scope: the whole Story 03.0 surface as it stands in the uncommitted tree, end to end:
`src/docsentinel/config.py` (strict JSON reader, user layer, R1-R7 gate and link walker, C6),
`src/docsentinel/cli.py` (`init --user`, `--no-user-settings`, `doctor`, the INFO `config:` line),
`src/docsentinel/engine.py` and `pytest_plugin.py` (implicit layer-2 consumers),
`.github/workflows/ci.yml`, the five new test files, and the user docs
(`docs/user/reference/configuration.md`, `docs/user/tutorial/cli.md`,
`docs/user/tutorial/library.md`, `docs/test/user-settings.md`). Previously accepted items (F2, F3,
T04-3, T05-1 to T05-4) were checked only for change; none changed.

Evidence: a code read of every function on the path, a test-name diff of this file against the
suite, a read of the key test bodies, and about 30 subprocess probes run with `env -i`, with `HOME`
and `DOCSENTINEL_LOG_DIR` pointed at a scratch directory. The developer's real settings file was
not read or changed. Its inode, size and mtime were the same before and after the run.

### Integration check

| Item | Result | Evidence |
|---|---|---|
| Single read path | Met | `load_config_with_sources` is the only caller of `_load_user_layer`. The user file is read only through `_read_user_options` (`config.py:1384-1395`): R3 walk, then `_read_config_once` with the R2 hook, then parse, then C6, then `_build_config` alone. `engine.scan(config=None)` and the pytest fixture reach it through `load_config` (`engine.py:364`). No other `src/` module calls a config loader. |
| CLI consumers | Met | `scan`, `baseline` and `doctor` each load once with `user_settings=not args.no_user_settings` (`cli.py:915`, `:969`, `:1034`). They pass the resulting `Config` into `scan()`, so the engine never loads the user layer a second time. A relative `DOCSENTINEL_SETTINGS` with `--no-user-settings` exits on findings only (1), without the error; without the flag it exits 2 and does not echo the value. |
| Layer precedence | Met | The user mapping is validated alone and then merged under the project mapping (`:1470`). CLI `--profile`/`--select`/`--ignore`/`--reference-scope` replace on top. The `docsentinel-fast` pre-commit hook pins `--profile fast`, so a user `profile` cannot change the hook's profile. |
| Weakening is never silent | Met | User files `{"profile":"deep"}`, `{"profile":"deep","deep_confirm":true}` and `{"ignore":["DS"]}` each exit 0 on a tree with a dangling link. Each report states why (`Profile: deep` plus `Pending: ...`, or `All fast rules were excluded by select/ignore`), and the INFO line names the user options. This is the owner's own choice, and the gate keeps A2 out (U1). |
| Hostile user files in `doctor` | Met | Top-level array, 100,000-digit integer, 400-digit float option, boolean for an int option, `NaN`, `-1e400`, 100,000-deep nesting, lone-surrogate key, an OSC/BEL key and a `python:` extension: each gives one `config sources: error:` line (or `Scan failed:`), exit 0 for `doctor` and 2 for `scan`, with no traceback. The OSC key is rendered `\x1b]0;pwn\x07`, and no raw ESC byte appears in stdout or stderr. |
| U11 at close | Met | Across `scan -v`, `baseline -v`, `doctor` and a refused `scan`, stderr and the per-run log files hold the settings path only as `~/.local/share/docsentinel/settings.json`, and the fake home's absolute path appears 0 times. Option values are never printed. The scan-root path in DEBUG discovery lines is pre-existing and is not the settings file. |
| U4 / A9 CI | Met | `ci.yml` sets `DOCSENTINEL_SETTINGS: "off"` on job `test`, the only job that runs `docsentinel` or the pytest plugin. `test_ci_workflow_sets_settings_off` scans every workflow and asserts it checked `ci.yml:test`, so it cannot pass vacuously. |
| ADR 0005 amendments | Folded in | A1-A5 (fstat decision, R1-R7, relative `HOME`, `lexists`, the A3 reason phrases) are in the ADR text. No "Recommended" CI wording remains. The status is still `Proposed`, pending owner sign-off. |

### Mitigation-to-test map (A11) at close

Every test named in U1-U16, F1, T03-1, T04-1, T04-2 and T04-4 exists in the five Story 03.0
files. The only names this file mentions that are missing are the two tests of the optional
T05-1 and T05-2 (`test_init_user_raced_intermediate_dir_exits_2`,
`test_doctor_config_error_one_bounded_line`). Spot reads confirm the tests are substantive:

- The R2 hook test splits `os.stat` from `os.fstat` and asserts one open and `fstat` on that
  descriptor.
- The root-run test refuses a user-owned file and then accepts a root-owned one.
- The chain and sticky-link tests first prove the file loads, and only then make the directory
  writable or the link foreign.
- The relative-home test spies `stat`/`lstat`/`open` and asserts zero calls on a settings path.
- The FIFO and chmod tests use real objects behind a timeout guard.
- The T04-2 test formats the whole traceback and asserts the home path is absent.
- The U11 integration test covers a symlinked home and the log file.
- The isolation guards assert that `off` is set, that `XDG_DATA_HOME` is empty and outside the
  real home, and that the resulting state is `missing`.

Helpers that clear `DOCSENTINEL_SETTINGS` or `XDG_DATA_HOME` (the `home` fixture,
`UserHome.use_default_location`) always set `HOME` to a temporary directory first, so no test can
resolve the developer's real file.

### Findings

#### [LOW] C-1 The configuration reference says the gate names the directory to fix (required, docs)

- Vector / evidence: `docs/user/reference/configuration.md:115-116`: "Fix it with `chmod go-w` on
  the file (or the directory named)". The R3 phrase (`config.py:169`, raised at `:1348` and
  `:1351`) never names a directory, by design (R6). With a symlink chain, the failing directory
  can be any link-holding directory on the way. `chmod` also cannot fix `owned by another user`
  or a foreign link in a sticky directory.
- Impact: misleading remediation advice. A user may `chmod` the wrong directory and conclude the
  gate is broken. No bypass.
- Mitigation: reword, for example: "For `writable by group or others`, run `chmod go-w` on the
  file. For the directory message, run it on the directory that holds the file, and on each
  directory that holds a symbolic link on the way to it (the message does not say which). For an
  ownership problem, recreate the file as yourself." Owner: docs-updater (with the story's docs
  pass). No test needed.

#### [LOW] C-2 The self-hosted runner advice could read as sufficient (optional, docs)

- Vector / evidence: `docs/user/tutorial/cli.md:517-521` and `configuration.md:131-134`. Setting
  `off` closes this one persistence path. A self-hosted runner that executes fork code can still
  be poisoned in other ways: shell rc files, tool caches, or the installed `docsentinel` itself.
- Mitigation: add one sentence: "This closes one persistence path only; do not run untrusted fork
  pull requests on a self-hosted runner that also runs protected jobs." This matches GitHub's own
  guidance for self-hosted runners.

#### [INFO] C-3 WSL and YAML-quoting nuances (optional, docs)

- `configuration.md:122`: mode `0777` under `/mnt/c` holds for the default drvfs mount options.
  With the `metadata` option, the real modes apply. Say "by default".
- `configuration.md:131`: the reference gives `DOCSENTINEL_SETTINGS=off` without the YAML
  quoting that the `cli.md` example uses. A YAML 1.1 parser (several CI systems) turns an unquoted
  `off` into `false`. That value is relative, so every run exits 2. This fails closed, with no
  security effect. Recommend `"off"`.

#### [INFO] C-4 Manual checklist step 14 inherits a refused file (optional, test docs)

- `docs/test/user-settings.md:36` expects exit 0, but steps 10-11 leave the
  `DOCSENTINEL_SETTINGS` file invalid or refused, so step 14 exits 2 unless the tester restores a
  valid file. This fails closed and only affects the checklist's usability. Add "restore a valid
  file (step 4)" before step 14, or run it with `--no-user-settings`.

Not a finding: a probe first appeared to show a raw ESC/BEL in `doctor` output. That came from
zsh's builtin `echo` expanding `\x1b` in the probe harness. Written directly to a file, the output
holds the escaped text and no raw control byte.

### Merge-gate conditions at close

None holds:

- Every read is decided on `fstat` of the read descriptor.
- A violation is always an error.
- No C6 key or `python:` spec from the user file reaches `Config`.
- A relative home or a relative `DOCSENTINEL_SETTINGS` causes zero filesystem access.
- No message, log line, `doctor` line or INFO line contains file content, an option value, a
  refused environment value or the absolute home path. F2's accepted `allowed_fence_languages`
  echo is the only value echo, and it is unchanged.
- Every hostile JSON input exits 2 (`doctor`: 0 with one error line), with no traceback or hang.
- The suite cannot resolve the real file.

### Verdict: PASS_WITH_FOLLOWUP

There is no CRITICAL, HIGH or MEDIUM finding, and the pieces compose without regressions since
the Task 03-05 reviews. Story 03.0 may close once C-1 (a doc wording fix) lands with the story's
docs pass. These stay open as optional follow-ups: F2 (with T03-2 and T05-2), F3, T04-3, T05-1,
T05-4, C-2, C-3 and C-4. ADR 0005 may move to Accepted on this verdict once the owner signs off.

**Disposition (2026-11-18, story close):** C-1 (required) and C-2, C-3, C-4 were applied as wording fixes in `docs/user/reference/configuration.md`, `docs/user/tutorial/cli.md` and `docs/test/user-settings.md`. Story 03.0 is closed.
