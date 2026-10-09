# Story 01.0 - Optional-Dependency Plumbing & Lazy Standard Loading

The architectural prerequisite for every other story in this milestone. `fast`'s detectors
(Milestone 0001) are stdlib-only and imported unconditionally in `detectors/__init__.py`;
`standard`'s are **not**. `scikit-learn`, `textstat`, and `docsig` are real, sometimes-heavy
dependencies that must never be required just to run `docsentinel scan --profile fast`, and must
never even be *imported* on the `fast` path.

This story delivers three things, in order:

1. An **optional dependency group** (`docsentinel[standard]`) so a plain `pip install docsentinel`
   has zero new transitive weight, and a typed, actionable error type for "the extra isn't here."
2. A **lazy loader** that imports the `standard` detector subpackage (and therefore its heavy
   dependencies) only when `profile="standard"` is actually requested - not at
   `docsentinel.engine` import time - and that converts a missing-extra `ImportError` into a clear
   `ExtraNotInstalledError` pointing the user at `pip install docsentinel[standard]` /
   `uv sync --extra standard`, instead of a raw `ModuleNotFoundError` traceback.
3. **Engine and CLI wiring** so `scan`, `rules`, and `doctor` all behave correctly whether or not
   the extra is installed - the error surfaces as exit code `2`, and `rules`/`doctor` degrade
   gracefully to a note rather than crashing.

No detector exists yet after this story - the `standard` subpackage's import list is empty.
Stories 02.0-04.0 each add their module to it.

## Tasks

| # | Task | Output |
|---|------|--------|
| 01 | [Optional dependency group & error type](01-optional-dependency-group.md) | `pyproject.toml` `[project.optional-dependencies] standard`; `src/docsentinel/errors.py` with `ExtraNotInstalledError` |
| 02 | [Lazy standard loader & engine wiring](02-lazy-loader-and-engine-wiring.md) | `src/docsentinel/detectors/standard/__init__.py` (empty subpackage), `src/docsentinel/detectors/loader.py`, `engine.scan()` conditional load |
| 03 | [CLI & docs awareness of the standard extra](03-cli-and-docs-awareness.md) | `rules`/`doctor` surface standard rules or the "install the extra" note; `scan --profile standard` error path; docs refresh |

Sequential - 02 imports 01's `ExtraNotInstalledError`; 03 exposes 02's loader behavior on the CLI.
</content>
