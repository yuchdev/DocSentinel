# Task 02 - Config Conventions (`pyproject.toml` / `doc_sentinel.toml`, `select`/`ignore`)

**Story:** [01.0 - Rule Registry & Config Conventions](README.md)
**Depends on:** [01 - Rule registry](01-rule-registry.md) (imports `rules.RULES` for shape
validation context, though cross-referencing live codes is Task 03's job, not this one's)

## Purpose

`CLAUDE.md` requires DocSentinel to configure like every Pythonic static analyzer: a
`[tool.doc_sentinel]` table in `pyproject.toml`, **or** a separate `doc_sentinel.toml`, each
document addressable via `include`/`exclude`, each rule addressable via `select`/`ignore`,
defaulting to include-all/select-all/exclude-nothing/ignore-nothing. Today's `config.py` only
reads a `docsentinel.toml` file with a `[docsentinel]` table and no `select`/`ignore` at all.
This is a **breaking rewrite** of `config.py`, not an additive change - DocSentinel is
pre-release (`0.1.0`, M0), so there is no deployed config to migrate, and `CLAUDE.md`'s "no
backwards-compatibility shims" stance means the old `docsentinel.toml`/`[docsentinel]` shape is
replaced outright, not kept alongside the new one.

## Decision this task implements (record precisely - do not improvise at implementation time)

1. **Discovery order**, mirroring `ruff`'s own file-vs-pyproject precedent (the closest
   well-known "Pythonic static analyzer" to imitate):
   - If `doc_sentinel.toml` exists at `root`, use it **and ignore `pyproject.toml` entirely**,
     even if the latter also has a `[tool.doc_sentinel]` table.
   - Else, if `pyproject.toml` exists at `root` and has a `[tool.doc_sentinel]` table, use that.
   - Else, `Config()` defaults.
2. **Shape of each file**:
   - `doc_sentinel.toml` has its keys **at the top level** - no wrapper table - exactly like
     `ruff.toml` has `select = [...]` directly, not `[ruff]\nselect = [...]`.
   - `pyproject.toml`'s `[tool.doc_sentinel]` table has the same keys, nested one level under
     `[tool]`, per the standard `pyproject.toml` convention every other tool already in this
     repo's dependency tree (`ruff`, `pytest`, `hatchling`) uses.
3. **An explicit `--config PATH`** (the existing `path` parameter) bypasses discovery: if
   `PATH.name == "pyproject.toml"`, parse the `[tool.doc_sentinel]` table; otherwise parse
   top-level keys directly. This keeps `--config some/other/doc_sentinel.toml` and
   `--config some/other/pyproject.toml` both meaningful.
4. **New fields**: `select: tuple[str, ...] = ()`, `ignore: tuple[str, ...] = ()`, alongside the
   existing `include`, `exclude`, `profile`.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/config.py` | Rewrite (`load_config`, `Config`) |
| `tests/test_scan.py` | Modify - replace the four existing `docsentinel.toml`/`[docsentinel]` config tests (lines ~70-98 as of this writing: the custom-profile load, the three malformed-content cases, and the bad-encoding case) with the new file/table shape |
| `tests/test_config.py` | Create - new tests move here rather than growing `test_scan.py` further (that file is about `scan()` end-to-end, not config parsing in isolation) |

## Symbols / fields

`src/docsentinel/config.py`:

| Symbol | Kind | Fields / signature | Notes |
|--------|------|---------------------|-------|
| `Config` | `@dataclass(frozen=True)` | `include: tuple[str, ...] = ("*.md", "**/*.md")`, `exclude: tuple[str, ...] = (".git", ".venv", "node_modules")`, `profile: str = "fast"`, `select: tuple[str, ...] = ()`, `ignore: tuple[str, ...] = ()` | Field order matters for the existing positional-construction call in `cli.py` (`Config(settings.include, settings.exclude, args.profile)`) - that call site must be updated to keyword args in Task 04, or updated here if Task 04 hasn't landed yet; do not leave a positional call relying on field order. |
| `load_config(root: Path, path: Path \| None = None) -> Config` | function | same signature | Implements the Decision's discovery order above. |
| `_load_toml_table(source: Path, *, wrapped: bool) -> dict[str, object]` | private helper | - | `wrapped=True` digs into `data["tool"]["doc_sentinel"]`; `wrapped=False` returns `data` itself. Shared by both the pyproject and standalone-file code paths so the key-validation logic (next section) is written once. |

## Validators (raise `ConfigError` - unchanged exception type)

- Standalone file: top-level keys outside `{"include", "exclude", "profile", "select", "ignore"}`
  → `ConfigError(f"Unknown config options: {...}")` (same message shape as today).
- `pyproject.toml`: a `[tool.doc_sentinel]` value that is not a table, or unknown keys inside it
  → same error shape.
- `pyproject.toml` with **no** `[tool]` table, or `[tool]` with no `doc_sentinel` key → falls
  through to `Config()` defaults (not an error - most projects' `pyproject.toml` won't mention
  DocSentinel at all).
- `include`/`exclude`: unchanged rule - must be a list of nonempty strings.
- `select`/`ignore`: must be a list of strings; each string must match `^DS\d*$` (a full code
  like `DS101`, or a prefix like `DS1`/`DS`) - a malformed entry (`"not-a-code"`, `""`, a non-DS
  prefix) raises `ConfigError`. **Do not** cross-reference against `rules.RULES` here - a
  well-formed selector for a code that doesn't exist *yet* (e.g. `ignore = ["DS201"]` written in
  anticipation of milestone 0002's rules) must still load cleanly; Task 03 decides what an
  unmatched selector *does* at resolution time, not whether it's a legal config.
- `profile` validation is unchanged (`fast`/`standard`/`deep`).

## Tests

`tests/test_config.py` (new):
- `test_defaults_are_include_all_select_all_exclude_ignore_nothing` - `Config()` has
  `select == ()` and `ignore == ()`, and the existing `include`/`exclude` defaults.
- `test_standalone_doc_sentinel_toml_top_level_keys` - a `doc_sentinel.toml` with top-level
  `select = ["DS1"]` (no wrapper table) loads correctly.
- `test_pyproject_tool_doc_sentinel_table` - a `pyproject.toml` with `[tool.doc_sentinel]`
  containing `ignore = ["DS101"]` loads correctly when no `doc_sentinel.toml` exists.
- `test_standalone_file_wins_over_pyproject` - both files exist, with *different* `profile`
  values; assert the standalone file's value is the one returned.
- `test_pyproject_without_tool_doc_sentinel_table_is_defaults` - a `pyproject.toml` present but
  with only `[project]` (no `[tool.doc_sentinel]`) → `Config()` defaults, no error.
- `test_malformed_select_entry_raises` - `select = ["not-a-code"]` → `ConfigError`.
- `test_select_entry_for_unregistered_rule_still_loads` - `select = ["DS999"]` (well-formed,
  matches no real rule) loads without error - asserts the "shape-only" validation boundary.
- `test_explicit_config_path_pyproject_vs_standalone` - `--config`-style explicit `path` pointed
  at a `pyproject.toml` parses the wrapped table; pointed at any other filename parses top-level
  keys.

`tests/test_scan.py` (modified): rename/rewrite the four tests currently keyed to
`docsentinel.toml`/`[docsentinel]` (see Files above) to use `doc_sentinel.toml`/top-level-keys
instead, keeping their original intent (custom profile loads; malformed TOML, wrong profile
value, non-list include, unknown key, and bad encoding all raise `ConfigError`).

## Success criteria

- [ ] No code path still reads a file literally named `docsentinel.toml` or a table literally
      named `[docsentinel]` - that shape is fully retired, not kept as a fallback.
- [ ] `load_config` with neither file present returns `Config()` unchanged from today's defaults
      plus the two new empty tuples.
- [ ] Precedence (standalone file beats `pyproject.toml`) is exercised by an actual test with
      both files on disk, not just asserted in prose.

## Constraints

- Full type annotations; `ConfigError` stays the single exception type this module raises (no
  new exception classes).
- No bare `except:` - the existing `except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError)`
  pattern extends to both file shapes unchanged.
- Keep `_load_toml_table` free of any dependency on `rules.py` - shape validation only, per the
  Validators section above; Task 03 is where `rules.RULES` gets consulted.
