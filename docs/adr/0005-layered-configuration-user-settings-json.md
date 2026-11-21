# 0005 - Layered Configuration: User Settings JSON under Project TOML

> **Status:** Accepted (2026-11-20, owner)
>
> **Date:** 2026-11-17
>
> **Supersedes:** _(none)_
>
> **Superseded by:** _(none)_

## Context and Problem Statement

DocSentinel reads configuration from one place per scan. That place is either a standalone
docsentinel.toml (or its alias doc_sentinel.toml) at the scan root, the `[tool.doc_sentinel]` table
of pyproject.toml, or an explicit `--config` file. Without any of these, it uses the built-in
defaults. `load_config(root, path=None)` in `/src/docsentinel/config.py` does all of this, and
`_load_toml_table()` is the only reader. Configuration is per project and TOML only. A user has no
place for personal defaults, so every repository repeats the same preferences. Tools that emit JSON
have no way in either
([Milestone 0009 plan, P4](/docs/roadmap/0009-improvements/plan.md#problem-inventory-observed-2026-11-13)).

The question is how to add a personal, machine-level layer and a JSON format without three
problems:

- a second validation path whose error text drifts from the TOML one;
- a third discovered project file name with new ambiguity rules;
- a way for a personal file to change *which* files a repository checks, or to weaken its
  containment bounds.

## Decision Drivers

- **One engine** (plan principle 1). The CLI, the library (`docsentinel.scan`), and the pytest
  plugin must resolve configuration the same way, through `load_config()`.
- **One validator.** JSON must reach exactly the validators TOML reaches. The same invalid value
  gives the same message, apart from the user-file prefix (plan C7).
- **Trust follows the source** (plan C8). The repository's config is untrusted. The user file is
  invoker input, but it still may not name repository-relative paths (plan C6).
- **Fail closed on input** (principle 5). A bad settings file, a bad environment value or a refused
  key exits `2`. It is never silently dropped.
- **No silent behaviour change for existing projects.** Discovery, its precedence and today's error
  messages stay byte-identical. A user file is opt-in, because it applies only if it exists.
- **Reproducibility.** CI, tests and anyone reading a report must be able to rule out a personal
  layer.
- **Privacy.** The home path is PII (the account name). It appears only in tilde form, and option
  values are never logged.
- **Stdlib only** (principle 6). `json` and `tomllib`, with no new dependency.

## Considered Options

1. **(a) A user JSON file layered under the project config, with restricted keys.** One JSON
   file at the XDG data location is layered as defaults, then user settings, then project config,
   then CLI flags. Repository-relative keys are refused at user level. Project discovery is
   unchanged, and JSON is read for a project file only through an explicit `--config FILE.json`.
2. **(b) A user file that may set every key.** Same location and layering, but no key policy.
3. **(c) No user layer; one environment variable per key** (for example
   `DOCSENTINEL_REFERENCE_SCOPE`). Personal defaults live in a shell profile.
4. **(d) Option (a), plus automatic discovery of a project-level docsentinel.json** as a third
   standalone name.

## Decision Outcome

Chosen option: **(a)**. It is the only option that gives personal defaults and JSON input without
a new discovery name (unlike (d)) or a second validation path (unlike (c)). It also keeps a
personal file from changing which files a repository checks, or where its bounds lie (unlike (b)).

### Decisions recorded

Story decisions, from the
[Story 03.0 README](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md#decisions),
adopted verbatim:

| # | Decision |
|---|---|
| S1 | Project discovery is unchanged: docsentinel.toml, its alias doc_sentinel.toml (both together stay a `ConfigError`), otherwise `[tool.doc_sentinel]` in pyproject.toml. |
| S2 | JSON is read for the user settings file and for an explicit `--config` path whose suffix is `.json` (case-insensitive). |
| S3 | User settings live under `XDG_DATA_HOME` when it is set and absolute, otherwise under `$HOME/.local/share`. The file is the docsentinel directory's settings.json. |
| S4 | `DOCSENTINEL_SETTINGS` overrides the location with an absolute path. The exact value `off` disables user settings. An empty value counts as unset. Any other relative value is a `ConfigError`. |
| S5 | Precedence: defaults, user settings, project config, CLI flags (C1). A whole key value is replaced, never merged. |
| S6 | User settings may not set repository-relative keys (C6). Such a key exits `2`. |
| S7 | JSON parsing is strict (C7) and feeds the same validators. Errors from the user file are prefixed with its path in tilde form. |
| S8 | User settings apply wherever `load_config()` discovers configuration: the CLI, the library and the pytest plugin (D12). An injected `Config` still bypasses all files. |
| S9 | On POSIX the user file passes rules R1-R7 of the [threat model](/docs/security/threat-model-0009-user-settings-2026-11-17.md#permission-rule-ruling-on-d14): final target and the two holding directories owned by the effective user or root, no group/other write (sticky directories allowed), root-run accepts only root-owned, any violation is a `ConfigError` (exit `2`), skipped on non-POSIX (D14). |
| S10 | `docsentinel init --user` writes a starter settings file. There is no `init --format json` (D15). |

Milestone decisions D11 to D16, from the
[plan's open decisions](/docs/roadmap/0009-improvements/plan.md#open-decisions-for-owner), were
adopted as recommended on 2026-11-14 (see
[status.md](/docs/roadmap/0009-improvements/status.md)). This ADR rests on all of them:

| # | Decision (adopted) |
|---|---|
| D11 | JSON is accepted for user settings and an explicit `--config FILE.json`. A project-level JSON file is never discovered automatically. |
| D12 | User settings apply to the CLI, the library and the pytest plugin. `DOCSENTINEL_SETTINGS=off` or `--no-user-settings` turns them off. |
| D13 | User settings refuse repository-relative keys. `select` and `ignore` are allowed. |
| D14 | On POSIX, a settings file that is group-writable, world-writable or owned by another user is refused with exit `2`. **Ratified 2026-11-17** with refinements by the Task 02 threat model, rules R1-R7 (holding directories checked, root-owned accepted, error only). |
| D15 | `init --user` creates the settings file. There is no `init --format json`. |
| D16 | The location honours an absolute `XDG_DATA_HOME`, otherwise `$HOME/.local/share`. |

### Contract 1: precedence chain (plan C1)

From lowest to highest. Each layer replaces a key's value as a whole. Lists are never merged across
layers, with one exception: the `--exclude` flag of Story 02.0 appends (C5).

| Layer | Source | Read by | Keys |
|---|---|---|---|
| 1 | `Config()` defaults | `config.py` | all |
| 2 | User settings JSON (S3, S4) | `load_config_with_sources()` | all except the C6 set |
| 3 | Project config. Discovered: standalone TOML, or the pyproject table (S1). Explicit: `--config FILE`, read as TOML, or as JSON for a `.json` suffix (S2). An explicit file replaces discovery only, never layer 2. | `load_config_with_sources()` | all |
| 4 | CLI flags and `scan()` keywords (`--profile`, `--select`, `--ignore`, `--baseline`, `--reference-scope`, `--link-root`, and later `--include`/`--exclude`) | `cli.py` via `dataclasses.replace()`; `engine.scan()` | per flag |

The effective `Config` is built from `{**user_mapping, **project_mapping}` and then layer 4.

- **Injection.** A `Config` passed as `scan(config=...)` bypasses layers 1 to 3 exactly as today.
  Its values are used verbatim, and no file and no environment variable is read. Layer-4 keywords
  still apply on top of it.
- **Disabling layer 2.** `DOCSENTINEL_SETTINGS=off`, `--no-user-settings` (on `scan`, `baseline` and
  `doctor`), or `load_config(..., user_settings=False)`. The flag and the keyword win over the
  environment, so `user_settings=False` never reads `DOCSENTINEL_SETTINGS`.
- **Environment.** `DOCSENTINEL_SETTINGS`, `XDG_DATA_HOME` and `HOME` (through `Path.home()`) are
  read in exactly one place: the private location resolver called by `load_config_with_sources()`.
  No other module reads them.

### Contract 2: public signatures (`/src/docsentinel/config.py`)

These signatures are described here, not implemented. They follow the coding standard in
`/docs/dev/python_coding_standard.md`: `Optional[T]`, never `T | None`, full annotations and
reStructuredText docstrings.

```python
MAX_JSON_CONFIG_BYTES: Final = 1_048_576

USER_SETTINGS_REFUSED_KEYS: Final[frozenset[str]] = frozenset({
    "baseline", "include", "exclude", "docsig_paths", "navigation_indexes",
    "navigation_required", "deprecated_references_file", "report_templates_dir",
    "link_root", "telemetry_domains",
})

@dataclass(frozen=True)
class ConfigSources:
    user: Optional[Path]                  # the loaded user settings file, or None
    user_state: str                       # "loaded" | "missing" | "off" | "no-home"; plain str
    project: Optional[Path]               # the loaded project file, or None
    project_kind: str                     # "toml" | "pyproject" | "json" | "none"; plain str
    user_options: tuple[str, ...] = ()    # option NAMES set by the user file, sorted; never values
    project_options: tuple[str, ...] = () # option NAMES set by the project file, sorted; never values

def load_json_options(source: Path) -> dict[str, object]:
    """Read one JSON config object strictly; raise ConfigError on any deviation."""

def load_config_with_sources(
    root: Path, path: Optional[Path] = None, *, user_settings: bool = True
) -> tuple[Config, ConfigSources]:
    """Resolve layers 1 to 3 and report where each came from."""

def load_config(root: Path, path: Optional[Path] = None, *, user_settings: bool = True) -> Config:
    """Return load_config_with_sources(root, path, user_settings=user_settings)[0]."""
```

- **`load_config()`.** Existing positional calls such as `load_config(root)` and
  `load_config(root, path)` keep working. With no user file present, their result is identical to
  today's. `Config` gains **no field**. Sources travel only in `ConfigSources`, so `Config`
  equality, hashing and every consumer stay unchanged.
- **`ConfigSources` state table:**

  | `user_state` | Meaning | `user` |
  |---|---|---|
  | `"loaded"` | A file was read and validated. `{}` counts. | the path, as resolved by S3 or S4 (not symlink-resolved) |
  | `"missing"` | No file at the default location (`os.stat()` raises `FileNotFoundError` or `NotADirectoryError` and `os.path.lexists()` is false; Contract 3 step 1) | `None` |
  | `"off"` | `DOCSENTINEL_SETTINGS=off`, `--no-user-settings`, or `user_settings=False` | `None` |
  | `"no-home"` | `Path.home()` failed or returned a relative path, and no override is set (`DEBUG` line) | `None` |

  `project_kind` is `"toml"` for a standalone file or an explicit non-pyproject, non-JSON file. It
  is `"pyproject"` for pyproject.toml, discovered or explicit, even when the table is absent. It is
  `"json"` for an explicit `.json` file, and `"none"` with `project=None` when no file was found.
  A missing file named by `DOCSENTINEL_SETTINGS` is not a state. It is a `ConfigError` (S4).
- **`user_options` and `project_options`** are an addition to the story README sketch. They let
  `doctor` print `(loaded, 3 options)` and show a key set at both levels, without reading the file
  a second time. They hold names only, so they carry no values and no PII.
- **`load_json_options(source)`** follows the
  [Strict JSON parsing](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md#strict-json-parsing)
  steps in order:
  1. Open once through the shared open-once helper of Contract 3 step 2 (threat model A1), without
     the ownership and mode check: `os.stat()` pre-check (a non-regular file is refused and never
     opened), `os.open(O_RDONLY | O_NONBLOCK | O_NOCTTY)`, then `os.fstat()` of the descriptor
     (authoritative regular-file check).
  2. Read at most `MAX_JSON_CONFIG_BYTES + 1` bytes from that same descriptor; a longer file is
     refused.
  3. Decode as strict UTF-8; a byte-order mark is refused. Only the decoded `str` is passed to
     `json.loads()`, never bytes.
  4. `json.loads()` with an `object_pairs_hook` that refuses a duplicate key at any depth, a
     `parse_constant` that refuses `NaN`, `Infinity` and `-Infinity`, and a `parse_float` that
     refuses a non-finite result (`1e400`). The `except` order is `ConfigError` (re-raised
     unchanged), `RecursionError`, then `ValueError` (`JSONDecodeError` and the integer-string
     limit).
  5. The top level must be an object, and `null` anywhere is refused; the `null` walk is iterative.
  6. Unknown keys get the TOML reader's exact `Unknown config options: <sorted, comma-joined>`.

  It reads exactly once and does not cache. `5` stays an `int` and `5.0` a `float`, as in TOML. The
  function stays in `docsentinel.config`. It is not re-exported from `docsentinel`.
- **Shared validation.** Task 03 extracts the body of today's `load_config()` that turns an options
  mapping into a `Config` into one private builder (proposed name `_build_config(options)`).
  `_load_toml_table()`, `load_json_options()` and the layering step all reach `Config` only through
  it. No validator is duplicated or forked by format.
- **Public API.** `docsentinel.__init__` adds `ConfigSources` and `load_config_with_sources` to its
  exports, beside `load_config`, `Config` and `ConfigError`.

### Contract 3: the layered load, step by step

1. **Locate (layer 2).** If `user_settings` is false, the state is `"off"`. Otherwise read the
   environment once and apply the
   [Settings path and environment](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md#settings-path-and-environment)
   table. A relative `HOME` is `"no-home"`; the resolved settings path must be absolute before any
   filesystem call (threat model A4, U3). The state is `"missing"` only when `os.stat()` raises
   `FileNotFoundError` or `NotADirectoryError` and `os.path.lexists()` is false; a dangling
   symlink or any other `OSError` is a `ConfigError` (A5, U7). A file named by
   `DOCSENTINEL_SETTINGS` that is missing or unreadable is a `ConfigError`.
2. **Gate.** Rules R1-R7 of the
   [threat model](/docs/security/threat-model-0009-user-settings-2026-11-17.md#permission-rule-ruling-on-d14):
   final target and the two holding directories owned by the effective user or root, no
   group/other write (sticky directories allowed), root-run accepts only root-owned, any violation
   is a `ConfigError` (exit `2`), skipped on non-POSIX (A2). The gate and the read share one open
   (A1, U2): the R3 directory checks, an `os.stat()` regular-file pre-check (a FIFO or device is
   never opened), `os.open(O_RDONLY | O_NONBLOCK | O_NOCTTY)`, then `os.fstat()` on the
   descriptor as the authoritative regular-file, owner and mode check (R2).
3. **Read** the bounded bytes from that same descriptor and parse them with the
   `load_json_options()` rules (Contract 2); one open, one read, closed in `finally` (R7).
   `load_json_options(source)` keeps its signature and uses the same open-once helper without the
   ownership check.
4. **Refuse C6** keys before any value validation.
5. **Validate the user mapping alone** through `_build_config()`, so a bad user value is attributed
   to the user file.
6. **Read the project mapping** (TOML, pyproject table or JSON) exactly as today. The rule that
   rejects both standalone names is unchanged, and the user file never takes part in it.
7. **Build the effective `Config`** from `{**user, **project}` through `_build_config()`. Every
   validator is per key, so a failure at this step comes from a project value and keeps today's
   unprefixed message. Task 03 adds a test that guards this per-key property. If a cross-key
   validator is ever added, this ADR must be amended.
8. **Log** the `DEBUG` lines (option names only), then return `(config, sources)`.

### Contract 4: refused-key set (plan C6)

`USER_SETTINGS_REFUSED_KEYS` is exactly the C6 list: `baseline`, `include`, `exclude`,
`docsig_paths`, `navigation_indexes`, `navigation_required`, `deprecated_references_file`,
`report_templates_dir`, `link_root`, `telemetry_domains`.

- Every other key in the configuration schema is allowed at user level, `select`, `ignore` and
  `deep_confirm` included (D13). A user-level `deep_confirm = true` is the user's own standing
  consent, like exporting `DOCSENTINEL_DEEP_CONFIRM=1`, and the docs say so.
- `telemetry_extensions` is allowed, but only with `builtin:` entries, at every level. A `python:`
  entry stays a `ConfigError` from the existing validator.
- A refused key is never silently dropped. The message lists every refused key present in the file,
  sorted, and names the file through the prefix rule:
  `user settings <tilde path>: repository-relative options cannot be set in user settings: <k1>, <k2>`.
- A drift test keeps the frozenset equal to the C6 list and a subset of the option-name set
  `_CONFIG_OPTIONS`. A new repository-relative key must be added to the frozenset in the same
  change.

### Contract 5: error-prefix rule

| Origin | Message shape |
|---|---|
| Any `ConfigError` raised in steps 1 to 5 for an existing or explicitly named user file (gate, read, parse, C6, validation) | `user settings <tilde path>: <inner message>` |
| A bad `DOCSENTINEL_SETTINGS` value (relative path, control character) | `DOCSENTINEL_SETTINGS must be an absolute path or "off"`. The value is never echoed. |
| A project TOML file (discovered or explicit) | Exactly today's text, with no prefix |
| A project JSON file (`--config FILE.json`) | The same validator text as TOML, with no prefix |

- **Tilde path.** If the path is lexically under `Path.home()` or under `os.path.realpath()` of it
  (threat model U11, M15), the home part is replaced with `~`.
  Otherwise the path is shown as given. Either way it passes through `safe()` (neutralised and
  bounded). The symlink target is never shown.
- **Inner messages of `load_json_options()`** contain no path. File-level failures read
  `Cannot read JSON config: <reason>`. The reason is a fixed phrase: `not a regular file`,
  `larger than 1 MiB`, `not valid UTF-8`, `starts with a byte-order mark`, `duplicate key <k>`,
  `NaN and Infinity are not allowed`, `null is not allowed; omit the key`,
  `the top level must be an object`, `nested too deeply`, `number out of range` (the
  integer-string limit and float overflow), `not readable` (any `OSError` other than an absent
  default file), or `invalid JSON at line L, column C`. A duplicate key name is bounded to 80
  characters and neutralised. No file content or `JSONDecodeError` document text is ever echoed.
  A `ConfigError` raised inside a hook propagates unchanged; it is never rewritten as invalid
  JSON (threat model A3).
- **Gate phrases (R6).** A permission-gate violation uses one fixed phrase after the
  `user settings <tilde path>: ` prefix: `owned by another user`,
  `writable by group or others (run chmod go-w on it)`, or
  `its directory is owned by another user or writable by others`. No uid, owner name, mode digits
  of other objects or symlink target is shown.

  This keeps the absolute home path out of every user-file message, which carries only the tilde
  prefix. For an explicit project JSON file the invoker named the path, and the `DEBUG` line
  `loading config <path> (json)` records it. Task 03 pins the exact strings in tests.
- **Parity.** For every validator, the inner message from JSON equals the TOML message
  (`test_config_message_parity.py`).

### Logging (per `/docs/specs/logging.md`)

| Level | Where | Text |
|---|---|---|
| `DEBUG` | config loader | `user settings <tilde path>: loaded, options set: a, b`, or `user settings: missing`, `user settings: disabled` (state `"off"`), `user settings: no home directory` |
| `DEBUG` | config loader | `loading config <path> (json)`, beside the existing TOML line |
| `INFO` | CLI, once per `scan` and `baseline` | `config: user settings <state>[ (<names>)], project <file name or none>`; names sorted, at most 20 then `and N more`, never values (threat model A10, U16) |

There is no `WARNING` from the loader. A bad user file is a `ConfigError`, and the CLI's existing
failure path logs it once at `WARNING`. Option values are never logged.

### Affected components and migration path

| Component | Change | Migration for callers |
|---|---|---|
| Config loader, `/src/docsentinel/config.py` | `load_json_options()`, `MAX_JSON_CONFIG_BYTES`, `USER_SETTINGS_REFUSED_KEYS`, `ConfigSources`, `load_config_with_sources()`, a `user_settings` keyword on `load_config()`, the shared builder, the location resolver and the permission gate | None. The signature is a superset, and the result is identical when no user file exists. |
| Engine, `/src/docsentinel/engine.py` | None in code. `scan()` keeps calling `load_config(directory)` and so inherits layer 2. No new `scan()` keyword. | A library caller that needs a hermetic scan passes `config=load_config(root, user_settings=False)`, or sets `DOCSENTINEL_SETTINGS=off`. |
| CLI, `/src/docsentinel/cli.py` | `--no-user-settings` on `scan`, `baseline` and `doctor`; `.json` suffix routing for `--config`; `init --user`; `doctor` source lines; the `INFO` config line. The three `doctor` helpers that call `load_config(Path.cwd())` today share one `load_config_with_sources()` result and keep their report-the-error-inline behaviour. | Scripts that parse `doctor` see two new lines. |
| Pytest plugin, `/src/docsentinel/pytest_plugin.py` | No code change. The `docsentinel_scan` fixture inherits layer 2 through `scan()` (D12). | A downstream suite that wants hermetic results sets `DOCSENTINEL_SETTINGS=off` (documented). |
| Library callers (`docsentinel` package) | New exports `ConfigSources` and `load_config_with_sources` | None |
| Test suite, `/tests/conftest.py` | An autouse fixture sets `DOCSENTINEL_SETTINGS=off` for every test, like the log-directory isolation. Tests that exercise layer 2 point the variable at a file in `tmp_path`. | None |
| CI, `/.github/workflows/ci.yml` | Required: set `DOCSENTINEL_SETTINGS: off` at job level on every job that runs `docsentinel` (threat model A9, U4: a persistent self-hosted runner home could carry a settings file between jobs). `off` only removes trust, so job-wide is the safe direction. | CI users set the same; the docs name self-hosted runners |
| Pre-commit hooks, report templates, JSON schemas, `Config`, `ScanResult` | Unchanged | None |
| Existing projects | Unchanged discovery, precedence and messages | **None.** A user file is opt-in, because it applies only if it exists. |

### Consequences

- Good: personal defaults live in one file and apply to every repository, with the project config
  still winning. CLI, library and plugin agree.
- Good: JSON and TOML share one builder and one set of messages. A parity test makes drift visible.
- Good: the C6 set means a personal file can never change which documents a repository scans, its
  baseline, or its containment bounds.
- Good: no new discovery name and no change for existing projects. `Config` and `ScanResult` are
  unchanged.
- Bad: **reproducibility across machines gets harder.** The same commit can give different results
  on two machines, for example with `reference_scope = "strict"` or a higher `max_grade_level` at
  user level. This is mitigated by `DOCSENTINEL_SETTINGS=off` in CI and in the test suite, by
  `--no-user-settings`, by the `INFO` config line, and by the `doctor` source lines. A report
  still does not record that a user layer applied. Recording it is out of scope here, because it
  would change the report schema.
- Bad: library and plugin callers now depend on the environment and the home directory unless they
  inject a `Config` or opt out. The test suite must isolate itself, and forgetting to do so reads
  the developer's real file.
- Bad: a user-level `deep_confirm = true` silently confirms deep scans everywhere for that user.
  This is deliberate standing consent, and it is documented.
- Bad: two parsers (TOML and JSON) and a POSIX permission gate add attack surface and test burden.
  The Task 02
  [threat model](/docs/security/threat-model-0009-user-settings-2026-11-17.md) covers them
  (verdict PASS_WITH_FOLLOWUP).
- Neutral: `--config FILE.json` is accepted, but `init` never scaffolds project JSON (D15).

## Pros and Cons of the Options

### (a) User JSON under project config, restricted keys (chosen)

- Good: it meets every driver. One loader, one builder, no new discovery name, and repository bounds
  stay under repository control.
- Good: the location is the XDG default, which is also the owner's requested path.
- Bad: users must learn which ten keys are refused. Mitigation: the error message names them.
- Bad: cross-machine reproducibility needs an explicit opt-out in CI and tests.

### (b) User file with all keys

- Good: simplest to explain and implement, with no key policy and no refusal messages.
- Bad: a personal `exclude`, `include`, `baseline` or `link_root` silently changes every
  repository's results and bounds. A clean scan could hide checks the repository relies on. This
  breaks "never a silent clean result" and C8.
- Bad: repository-relative paths in a machine-wide file have no single meaning across repositories.

### (c) No user layer, one environment variable per key

- Good: no new file, no parser, no permission gate. Environment variables are already invoker input.
- Bad: all 67 option names would each need an environment twin, with string-to-type coercion
  for lists, floats and the `telemetry_domains` table. That is a second validation path, which
  breaks the one-validator driver.
- Bad: shell profiles are per shell, not per user, so IDEs and pytest runners see different
  values. Values also appear in `ps` output and in CI logs more easily.
- Bad: no JSON input for tools that generate configuration.

### (d) Option (a) plus automatic discovery of a project docsentinel.json

- Good: tools could drop a JSON file into a repository without the `--config` flag.
- Bad: a third standalone name needs new ambiguity rules (TOML and JSON both present) and a new
  `init` mode. That is the ambiguity D11 avoids, for no stated need.
- Bad: it widens the untrusted parser surface to every scanned repository, not only invoker-named
  files.
- Neutral: it can be reopened later without breaking (a): the reader and the builder are already
  shared.

## Validation / Rollout

- `python scripts/check_doc_links.py docs/adr docs/roadmap` reports 0 problems.
- The acceptance criteria of
  [Story 03.0](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md#acceptance-criteria),
  in particular precedence across all four layers, an exit `2` that names the key and the file for
  each refused key, TOML-to-JSON message parity, and a suite that never reads the real home
  directory.
- The ADR moves to `Accepted` once the owner signs off and the Task 02 Security Auditor verdict is
  PASS or PASS_WITH_FOLLOWUP. Any Task 02 amendment to the gate or the messages is folded in here
  first. The verdict is PASS_WITH_FOLLOWUP (2026-11-17); amendments A1-A5 and A9 of the
  [threat model](/docs/security/threat-model-0009-user-settings-2026-11-17.md#required-spec-amendments)
  are folded in, so only the owner sign-off remains.

Follow-up tasks:

| Task | Owner | Deliverable |
|---|---|---|
| [02](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/02-threat-model-user-settings.md) | Security Auditor | Threat model for the user file, the environment and the JSON parser. It rules on the permission gate details. Runs before any code. |
| [03](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/03-strict-json-loader-and-shared-validation.md) | Python Expert | `load_json_options()`, the shared builder, `--config FILE.json` routing, and Contract 5 inner messages |
| [04](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/04-user-settings-layer.md) | Python Expert | Location resolver, gate, Contract 3 and 4, `ConfigSources`, `load_config_with_sources()`, exports, conftest isolation |
| [05](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/05-cli-init-doctor-and-logging.md) | Python Expert | `--no-user-settings`, `init --user`, the `doctor` source lines (from `ConfigSources`, tilde form only), the logging lines, and the required job-level CI environment line |
| [06](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/06-tests.md) | Testing Expert | The story test plan, plus drift tests for `USER_SETTINGS_REFUSED_KEYS` and the per-key validator property (Contract 3, step 7) |
| [07](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/07-docs-and-release-notes.md) | Docs Writer | Configuration reference, CLI and library tutorials, logging spec, README, CLAUDE.md, architecture prose, release-notes proposal |

**Diagram follow-up for `diagram-creator`.** Run it after Tasks 04 and 05 land, because
`/docs/diagrams/` shows the as-built package:

- `/docs/diagrams/component/overview/component-overview.puml`: add a `User settings JSON` file
  input (S3/S4 location) and an explicit `--config FILE.json` to the configuration-files database,
  with an edge from `config.py` labelled `read (layer 2, C6-restricted)`. Add an environment input
  (`DOCSENTINEL_SETTINGS`, `XDG_DATA_HOME`) read only by `config.py`. Extend the `config.py` label
  with `load_config_with_sources, ConfigSources`, and the API label with the new exports. Re-render
  the `.svg` and `.png`.
- New: `sequence/config-layered-load`. Participants: CLI, library or plugin, `engine.scan`,
  `load_config_with_sources`, location resolver, permission gate, `load_json_options`,
  `_load_toml_table`, `_build_config`. It shows Contract 3 steps 1 to 8, the C6 refusal and the
  prefix branch, and the injected-`Config` bypass. Add it to `/docs/diagrams/README.md`.
- `/docs/diagrams/component/detectors/component-detectors.puml` and
  `/docs/diagrams/component/reporting/component-reporting.puml`: no change.
- `/docs/architecture/README.md` has no Mermaid diagram. Task 07 updates its Configuration section
  prose to the four layers.

## Links

- **Roadmap story/task:**
  [Story 03.0](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md),
  [Task 01](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/01-adr-layered-configuration.md),
  [Milestone 0009 plan, shared contracts](/docs/roadmap/0009-improvements/plan.md#shared-contracts-authoritative)
- **Supporting specs:** [configuration reference](/docs/user/reference/configuration.md),
  [logging](/docs/specs/logging.md), [architecture](/docs/architecture/README.md),
  [coding standard](/docs/dev/python_coding_standard.md),
  [threat model 0009 user settings](/docs/security/threat-model-0009-user-settings-2026-11-17.md)
- **Related ADRs:**
  [0004 - Reference Scope and @-Document References](/docs/adr/0004-reference-scope-and-at-document-references.md)
  (`reference_scope` is a typical user-level key)
- **Diagrams:** [diagram index](/docs/diagrams/README.md); the follow-up is above
