# Task 01 - Optional Dependency Group & Error Type

**Story:** [01.0 - Optional-Dependency Plumbing & Lazy Standard Loading](README.md)
**Depends on:** Milestone 0001 (nothing in this task touches a detector yet)

## Purpose

Before a single `standard` detector exists, two pieces of plumbing have to be in place: a
**packaging** declaration that makes `scikit-learn`/`textstat`/`docsig` an *opt-in* install, and a
**typed error** the loader (Task 02) can raise when a user asks for `standard` without that opt-in.
Doing packaging first means every later detector can `import sklearn` / `import textstat` /
`import docsig` freely, knowing the dependency is declared, while a base install stays lean.

## Decision this task implements

1. The three libraries are an **optional dependency group named `standard`**, never core
   dependencies. `pip install docsentinel` pulls in none of them; `pip install docsentinel[standard]`
   (or `uv sync --extra standard`) pulls in all three. This mirrors the `canonix_engine[lint]`
   extra precedent (`flakeforge` is an extra there, not a core dep) that this project's scaffold
   draws on.
2. The missing-extra error is a **new exception type**, `ExtraNotInstalledError`, subclassing
   `ValueError`. Subclassing `ValueError` is deliberate: the CLI's existing
   `except (ConfigError, ValueError, OSError)` boundary (see `cli.py`) then catches it and returns
   exit code `2` (config/scan failure) with **no change to the CLI's except clause** - a missing
   optional dependency is a setup/config failure, not a findings failure (`1`) and not a crash.
3. The error lives in a **new `src/docsentinel/errors.py` module**, not in `config.py`.
   `config.py` owns `ConfigError` (a config-*parsing* failure); an uninstalled extra is an
   *environment* failure, a different axis - giving it its own module avoids importing `config.py`
   just to raise it and keeps `config.py` dependency-free.

## Files

| Path | Action |
|------|--------|
| `pyproject.toml` | Modify - add `[project.optional-dependencies] standard = [...]` |
| `src/docsentinel/errors.py` | Create |
| `tests/test_errors.py` | Create |

## Symbols / fields

`pyproject.toml`:

```toml
[project.optional-dependencies]
standard = ["scikit-learn>=1.4", "textstat>=0.7", "docsig>=0.96"]
```

- Pin style matches the project's existing `>=`-floor convention for the two already-pinned deps
  (`flakeforge`, `release-saga`) - a floor, not a `==` lock, because these are advisory analysis
  tools, not output-defining ones. (Confirm against `pyproject.toml`'s existing pin style at
  implementation time and match it; if the repo actually uses `==` elsewhere for reproducibility,
  follow that instead - do not invent a third convention.)
- Do **not** add any of the three to `[project] dependencies` (the core list). The whole point of
  this story is that the base install stays stdlib-plus-nothing-heavy.

`src/docsentinel/errors.py`:

| Symbol | Kind | Fields / signature | Notes |
|--------|------|---------------------|-------|
| `ExtraNotInstalledError` | `class(ValueError)` | `__init__(self, extra: str, cause: ImportError) -> None` | Stores `self.extra` and `self.cause`; builds a `str` message of the exact shape below. |

Message shape (stable - the CLI prints it verbatim, and a test asserts on it):

```
The '<extra>' optional dependency group is required for this profile but is not installed.
Install it with:  pip install docsentinel[<extra>]   (or: uv sync --extra <extra>)
Underlying import error: <cause>
```

- `<extra>` is the constructor's `extra` argument (always `"standard"` in this milestone, but the
  type is generic so Milestone 0003's `deep` extra can reuse it).
- `<cause>` is `str(cause)` - the original `ModuleNotFoundError`'s message (e.g.
  `No module named 'sklearn'`), so the user still sees *which* package is missing, just wrapped in
  guidance instead of a bare traceback.

## Validators

- No input validation beyond type correctness - `errors.py` is pure data, no I/O.
- `ExtraNotInstalledError` must set its message via `super().__init__(message)` so `str(err)` and
  `args[0]` both yield the formatted message (standard exception ergonomics; a test checks
  `str(err)`).

## Tests (`tests/test_errors.py`)

- `test_extra_not_installed_is_a_value_error` - `issubclass(ExtraNotInstalledError, ValueError)` is
  `True` (this is the property the CLI's exit-code `2` path relies on; guard it so a refactor can't
  silently break the exit-code contract).
- `test_extra_not_installed_message_names_extra_and_install_command` - construct with
  `extra="standard"` and a dummy `ImportError("No module named 'sklearn'")`; assert the message
  contains `docsentinel[standard]`, `uv sync --extra standard`, and `No module named 'sklearn'`.
- `test_extra_not_installed_preserves_cause_attribute` - `err.extra == "standard"` and
  `err.cause is the_import_error` - the structured attributes are available for callers that want
  them, not only the formatted string.

## Success criteria

- [ ] `pip install docsentinel` (no extra) installs none of `scikit-learn`/`textstat`/`docsig` -
      verifiable by `import docsentinel.engine` succeeding in an env where those three are absent
      (this is proven end-to-end in Task 02's tests; this task only establishes the declaration).
- [ ] `ExtraNotInstalledError` is a `ValueError` subclass, so the existing CLI `except` tuple
      catches it with no edit to that tuple.
- [ ] `errors.py` imports nothing from `config.py`, `engine.py`, or any third-party package - it is
      a leaf module.

## Constraints

- Full type annotations on `__init__`. No bare `except:` (there is no exception handling here at
  all - this module only *defines* an exception).
- Do not widen the core dependency list. If `uv sync` / CI needs the extra to run this milestone's
  tests, that is configured in Story 05.0 (CI lane) and the test-collection guard in Task 02, not
  by promoting the extra to a hard dependency here.
</content>
