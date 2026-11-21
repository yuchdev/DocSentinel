# Story 03.0 — TOML and JSON configuration; user-level settings

**Category:** configuration loading · **Touched sources:** `/src/docsentinel/config.py`,
`/src/docsentinel/cli.py`, `/src/docsentinel/engine.py` (no behaviour change beyond calling the
new loader), `/tests/conftest.py` (test isolation)  
**Parent:** [Milestone 0009 plan](/docs/roadmap/0009-improvements/plan.md) (contracts C1, C6, C7,
C8).  
**Depends on:** [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md)
(soft: serial edits of the config and CLI modules; `reference_scope` is a typical user-level key).  
**Security-sensitive:** yes (a new trusted input source and a new parser); Task 02 runs before
code.

## Goal

Accept configuration as TOML or JSON, and let a user keep personal defaults in one JSON file,
`$HOME/.local/share/docsentinel/settings.json`, layered under every project's configuration,
without letting that file weaken a repository's checks.

## Tasks

| Task | Deliverable | Role | Status |
|---|---|---|---|
| [01](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/01-adr-layered-configuration.md) | ADR for layered configuration and JSON support | Architect | ✅ Complete |
| [02](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/02-threat-model-user-settings.md) | Threat model for the user settings file and the JSON parser | Security Auditor | ✅ Complete |
| [03](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/03-strict-json-loader-and-shared-validation.md) | Strict JSON loader; one validation path for TOML and JSON; `--config FILE.json` | Python Expert | ✅ Complete |
| [04](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/04-user-settings-layer.md) | User settings discovery, key policy, permission check, layering, `ConfigSources`, test isolation | Python Expert | ✅ Complete |
| [05](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/05-cli-init-doctor-and-logging.md) | `--no-user-settings`, `init --user`, `doctor` config sources, logging lines | Python Expert | ✅ Complete |
| [06](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/06-tests.md) | Unit, mock and integration tests, including message parity between TOML and JSON | Testing Expert | ✅ Complete |
| [07](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/07-docs-and-release-notes.md) | Configuration reference, CLI tutorial, library guide, logging spec rows, README, release-notes proposal | Docs Writer | ✅ Complete |

## Scope

- A strict JSON reader producing the same option mapping as the TOML reader, validated by the same
  code.
- User settings: location, environment override, key policy, permission check, layering.
- `--config FILE.json` for an explicit project-level JSON file.
- `--no-user-settings` on `scan`, `baseline` and `doctor`; `init --user`; `doctor` lines.

## Non-goals

- Automatic discovery of a project-level docsentinel.json (plan D11).
- Comments, trailing commas or JSON5; YAML.
- Merging list values across layers (each key is replaced as a whole).
- Per-repository sections inside the user file.

## Design

### Decisions

| # | Decision | Rationale |
|---|---|---|
| S1 | Project discovery is unchanged: docsentinel.toml, its alias doc_sentinel.toml (both together stay a `ConfigError`), else `[tool.doc_sentinel]` in pyproject.toml | No new ambiguity; existing projects unaffected |
| S2 | JSON is read for the user settings file and for an explicit `--config` path whose suffix is `.json` (case-insensitive) | Covers the owner's JSON location and tools that generate JSON, without a third discovered name |
| S3 | User settings live at `$XDG_DATA_HOME/docsentinel/settings.json` when `XDG_DATA_HOME` is set and absolute, else `$HOME/.local/share/docsentinel/settings.json` (plan D16) | The owner's path is exactly the XDG default |
| S4 | `DOCSENTINEL_SETTINGS` overrides the location with an absolute path, or disables user settings with the exact value `off`; an empty value counts as unset; any other relative value is a `ConfigError` | Hermetic CI and tests; no current-directory surprises |
| S5 | Precedence: defaults, then user settings, then project config, then CLI flags (plan C1); a whole key value is replaced, never merged | Predictable and easy to explain |
| S6 | User settings may not set repository-relative keys (plan C6); such a key exits `2` | A personal baseline, exclude or link root would silently change every repository's results |
| S7 | JSON parsing is strict (plan C7) and feeds the same validators, so error text is identical; errors from the user file are prefixed with the file path in tilde form | Same rules, clear origin |
| S8 | User settings apply wherever `load_config()` discovers configuration: CLI, library and pytest plugin (plan D12); an injected `Config` still bypasses all files | One engine, same results |
| S9 | Rules R1-R7 of the threat model [threat-model-0009-user-settings-2026-11-17.md](/docs/security/threat-model-0009-user-settings-2026-11-17.md#permission-rule-ruling-on-d14): final target and the two holding directories owned by the effective user or root, no group/other write (sticky directories allowed), root-run accepts only root-owned, any violation is a `ConfigError` (exit `2`), skipped on non-POSIX (plan D14, ratified) | It is trusted input; the same model as `ssh` |
| S10 | `docsentinel init --user` writes a starter settings file; no `init --format json` (plan D15) | Project JSON is not discovered, so a project JSON scaffold would mislead |

### Files and formats

| Layer | Location | Format | When read |
|---|---|---|---|
| User settings | per S3 or `DOCSENTINEL_SETTINGS` | JSON | always, unless `off` or `--no-user-settings`; a missing file at the default location is skipped |
| Project, standalone | docsentinel.toml or doc_sentinel.toml at the scan root | TOML | discovery (unchanged) |
| Project, pyproject | `[tool.doc_sentinel]` in pyproject.toml at the scan root | TOML | discovery when no standalone file (unchanged) |
| Project, explicit | `--config FILE` | TOML, or JSON for a `.json` suffix | replaces discovery (unchanged rule); user settings still apply beneath it |

JSON shape: one object whose keys are the option names, exactly as at the top level of
docsentinel.toml. `telemetry_domains` is an array of objects with `glob` and `domain`.

```json
{
  "profile": "fast",
  "reference_scope": "strict",
  "report_show_clean_documents": true,
  "max_grade_level": 16.0
}
```

### Settings path and environment

| Condition | Result |
|---|---|
| `DOCSENTINEL_SETTINGS=off` or `--no-user-settings` | user settings disabled |
| `DOCSENTINEL_SETTINGS` absolute path | that file; missing or unreadable is a `ConfigError` (the invoker asked for it) |
| `DOCSENTINEL_SETTINGS` relative, or contains control characters | `ConfigError` |
| `DOCSENTINEL_SETTINGS` unset or empty, `XDG_DATA_HOME` absolute | the docsentinel settings file under `XDG_DATA_HOME`; missing is skipped |
| `XDG_DATA_HOME` unset, empty or relative | the file under `$HOME/.local/share`; missing is skipped |
| home directory unknown, or `HOME` relative | `no-home`: user settings skipped, `DEBUG` line |
| default-location file a dangling symlink, or `os.stat()` fails other than absent | `ConfigError` (`not readable`); never `missing` |

A relative `HOME` is `no-home`; the resolved settings path must be absolute before any filesystem
call (threat model A4, U3). `missing` only when `os.stat()` raises `FileNotFoundError` or
`NotADirectoryError` and `os.path.lexists()` is false; a dangling symlink or any other `OSError`
is a `ConfigError` (A5, U7).

The flag wins over the environment. The environment is read only in the config module's loader
entry point (one place, like the extension gate in the CLI).

### Strict JSON parsing

```python
MAX_JSON_CONFIG_BYTES: Final = 1_048_576

def load_json_options(source: Path) -> dict[str, object]:
    """Read one JSON config object, strictly; raise ConfigError on any deviation."""
```

1. `os.stat()` the path; a non-regular file is a `ConfigError`. Then open it once and treat
   `os.fstat()` on that descriptor as authoritative, reading from the same descriptor (threat model
   amendment A1, `/docs/security/threat-model-0009-user-settings-2026-11-17.md`).
2. Read at most `MAX_JSON_CONFIG_BYTES + 1` bytes; more is a `ConfigError` ("larger than 1 MiB").
3. Decode as strict UTF-8; a byte-order mark is a `ConfigError`.
4. `json.loads()` with an `object_pairs_hook` that refuses a duplicate key at any depth (the
   message names the key, bounded to 80 characters and neutralised), and a `parse_constant` that
   refuses `NaN`, `Infinity` and `-Infinity`. A `RecursionError` or `JSONDecodeError` becomes a
   `ConfigError` with the line and column only (no content echo).
5. The top level must be an object; a `null` anywhere is a `ConfigError` ("null is not allowed;
   omit the key").
6. Unknown keys raise the same `Unknown config options: ...` message as TOML.

Integers and floats map as in TOML (`5` is an int, `5.0` a float), so the existing numeric
validators keep their behaviour.

### Shared validation and layering

`load_config()` keeps its signature for existing callers and gains a keyword:

```python
def load_config(root: Path, path: Optional[Path] = None, *, user_settings: bool = True) -> Config: ...

@dataclass(frozen=True)
class ConfigSources:
    user: Optional[Path]        # loaded user settings file, or None
    user_state: str             # "loaded" | "missing" | "off" | "no-home"
    project: Optional[Path]     # loaded project file, or None
    project_kind: str           # "toml" | "pyproject" | "json" | "none"

def load_config_with_sources(
    root: Path, path: Optional[Path] = None, *, user_settings: bool = True
) -> tuple[Config, ConfigSources]: ...
```

1. Read the user mapping (if any). Refuse the C6 keys first. Validate the user mapping alone by
   building a `Config` from it through the existing code path; prefix any `ConfigError` message
   with `user settings <tilde path>: `.
2. Read the project mapping (TOML, pyproject table or JSON) as today.
3. Build the effective `Config` from `{**user, **project}` through the same code path. Project
   errors keep today's exact messages.
4. The CLI applies its flags with `dataclasses.replace()` as today.

`Config` gains no field; sources are reported through `ConfigSources` only, so `Config` equality
and every consumer are unchanged.

### User-level key policy

| Allowed (examples) | Refused (C6) |
|---|---|
| `profile`, `reference_scope`, `select`, `ignore`, thresholds (`max_grade_level`, `duplicate_similarity`, `min_information_score`, size limits), policy options of the fast rules, `deep_confirm`, `report_show_clean_documents`, `report_include_run_meta`, builtin `telemetry_extensions` | `baseline`, `include`, `exclude`, `docsig_paths`, `navigation_indexes`, `navigation_required`, `deprecated_references_file`, `report_templates_dir`, `link_root`, `telemetry_domains` |

`deep_confirm = true` in user settings confirms the heuristic deep profile for every repository the
user scans; this is the user's own consent, equivalent to exporting `DOCSENTINEL_DEEP_CONFIRM=1`
in a shell profile, and the docs say so. `python:` extensions stay refused in every file.

### CLI reference

| Command | Flag | Effect |
|---|---|---|
| `scan`, `baseline`, `doctor` | `--no-user-settings` | ignore the user settings file for this run |
| `scan`, `baseline` | `--config FILE.json` | explicit project config read as JSON (suffix rule) |
| `init` | `--user` | create the user settings file (parent directories mode `0o700`, file mode `0o600`, never overwritten, exit `2` if it exists or if user settings are `off`); honours `DOCSENTINEL_SETTINGS`; `--yes` as today |
| `doctor` | — | prints the config sources (below) |

`init --user` writes:

```json
{
  "profile": "fast",
  "reference_scope": "links"
}
```

`doctor` adds:

```text
user settings: ~/.local/share/docsentinel/settings.json (loaded, 3 options)
project config: docsentinel.toml (4 options)
reference scope: links (DS103 off)
```

### Logging

Per `/docs/specs/logging.md`; option names only, never values; the home directory shown as a
tilde.

| Level | Where | Text |
|---|---|---|
| `DEBUG` | config loader | `user settings <path>: loaded, options set: a, b` or `missing` or `disabled` |
| `DEBUG` | config loader | `loading config <path> (json)` beside the existing TOML line |
| `INFO` | CLI, once per `scan` and `baseline` | `config: user settings <state>[ (<names>)], project <file name or none>`; user-layer option names sorted, at most 20 then `and N more`, never values (threat model A10, U16) |
| `WARNING` | — | none: a bad user file is a `ConfigError` (exit `2`), logged once at `WARNING` by the CLI's existing failure path |

## Edge cases

- The user file is a directory, empty, `[]`, or contains `{"include": [...]}`: each is a
  `ConfigError` naming the user settings file.
- `{}` is valid and changes nothing.
- A project config sets a key the user also set: the project wins; `doctor` shows both sources.
- `--config` names pyproject.toml: unchanged wrapped behaviour; user settings still apply.
- Both TOML standalone names in one root: unchanged `ConfigError`; the user file is not a third
  name and never participates in that rule.
- A symlinked user file (dotfile managers): allowed; ownership and mode are checked on the final
  target.
- Windows: no ownership or mode check; the path rule is the same, under the user's home.
- Concurrency: the file is read once per `load_config()` call; no caching across calls.

## Security notes

- The user file is invoker-trusted, but its contents still pass every validator, and C6 keeps it
  from reaching repository paths or weakening containment.
- Parser hardening: size cap, strict UTF-8, duplicate keys, non-finite numbers, nesting errors.
- No secrets are expected in configuration; nothing from the file is logged except option names.
- The home path is PII; it appears in `INFO` and `doctor` output only in tilde form.
- Tests must never read the developer's real settings: `/tests/conftest.py` sets
  `DOCSENTINEL_SETTINGS=off` for every test, the same way it isolates the log directory.
- Task 02 decided the permission-check details and their tests: the threat model
  [threat-model-0009-user-settings-2026-11-17.md](/docs/security/threat-model-0009-user-settings-2026-11-17.md)
  (verdict PASS_WITH_FOLLOWUP) is a standing input for Tasks 03 to 07. Its rules R1-R7, threats
  U1-U16 and amendments A1-A12 are folded into those specs; follow-ups F2 and F3 (pre-existing
  TOML echo and size bounds) stay separate changes.

## Acceptance criteria

- [ ] With a user file setting `reference_scope = "strict"` and no project config, a scan runs
      DS103; a project config with `reference_scope = "links"` overrides it; `--reference-scope`
      overrides both.
- [ ] Each refused user-level key exits `2` with a message naming the key and the file.
- [ ] For every validator, the same invalid value gives the same message from TOML and JSON
      (parity test), apart from the user-file prefix.
- [ ] Duplicate keys, a BOM, `NaN`, `null`, a 1 MiB plus one byte file and deep nesting each exit
      `2` without echoing file content.
- [ ] `DOCSENTINEL_SETTINGS` and `XDG_DATA_HOME` rules behave as the table states.
- [ ] `init --user` creates the file with mode `0o600` and refuses to overwrite.
- [ ] `doctor` prints the source lines; the test suite never reads the real home directory.

## Test plan

| Layer | File (new) | Covers |
|---|---|---|
| Unit | test_json_config_loader.py in the unit tests folder | Strict parsing rules, size cap, top-level shape, null, unknown keys |
| Unit | test_config_message_parity.py | Every validator through TOML and JSON gives the same message |
| Unit | test_user_settings_policy.py | C6 refusals, allowed keys, precedence across layers |
| Mock | test_user_settings_location.py in the mock tests folder | Environment, XDG and home resolution with the environment and `Path.home()` patched; ownership and mode checks with `os.stat()` patched |
| Integration | test_user_settings_cli_ds101_ds103.py in the integration tests folder | CLI end to end over ds101 and ds103 assets with a settings file in `tmp_path` via `DOCSENTINEL_SETTINGS`: precedence, `--no-user-settings`, `--config` JSON, `init --user`, `doctor` lines, exit codes |

Configuration files are generated in the test body (per `/tests/assets/README.md`); document trees
reuse existing ds101 and ds103 asset cases.

## Docs to update

Triggers K, C, P and A of `/docs/dev/documentation_sync.md`:

- `/docs/user/reference/configuration.md` "How to set options": the four layers, JSON format, user
  settings path and environment, the refused keys;
- `/docs/user/tutorial/cli.md`: `init --user`, `--no-user-settings`, `--config FILE.json`,
  `doctor` lines;
- `/docs/user/tutorial/library.md`: `load_config(..., user_settings=False)` and
  `load_config_with_sources()`;
- `/docs/specs/logging.md`: the new lines (after the concurrent logging change has landed);
- `/README.md` configuration section; `/CLAUDE.md` config entry and Commands;
- `/docs/architecture/README.md` configuration layer; diagram follow-up from Task 01;
- a proposed `/RELEASE_NOTES.json` line.
