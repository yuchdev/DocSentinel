# Task 02 - Lazy Standard Loader & Engine Wiring

**Story:** [01.0 - Optional-Dependency Plumbing & Lazy Standard Loading](README.md)
**Depends on:** [01 - Optional dependency group & error type](01-optional-dependency-group.md);
Milestone 0001 Story 01.0 Task 03 (the `engine.scan()` body that resolves `profile_codes` from
`RULES` and builds the three `notice`/`pending` branches)

## Purpose

This is the heart of the story: make `standard`'s heavy detector modules load **only** when
`profile="standard"` is requested, never at `docsentinel.engine` import time, and turn a missing
extra into the actionable `ExtraNotInstalledError` from Task 01. After this task the `standard`
subpackage exists but is empty; it is the sanctioned home every later detector registers into.

## Decision this task implements

1. **A `standard` detector subpackage** at `src/docsentinel/detectors/standard/`. Its
   `__init__.py` imports each standard detector submodule for its registration side effect - exactly
   like `fast`'s `detectors/__init__.py` does for `comments`/`links`/`paths`. **It starts empty**
   (no submodules exist yet); Stories 02.0-04.0 each append one import line. Importing this package
   is what triggers `import sklearn` / `import textstat` / `import docsig` (transitively, via the
   submodules), so **nothing may import it eagerly** - not `detectors/__init__.py`, not `engine.py`
   at module scope.
2. **A stdlib-only loader module** at `src/docsentinel/detectors/loader.py`. It must import nothing
   heavy at module scope (so it is safe for `engine.py` to import eagerly). It does the deferred
   import inside a function, under a `try/except ImportError`.
3. **Distinguish a missing extra from a real bug.** A bare `except ImportError` would mask a genuine
   `ImportError` *inside* our own detector code (a typo, a bad relative import) as "extra not
   installed." The loader inspects the caught error's `.name`: if the missing top-level module is
   one of the extra's known packages (`{"sklearn", "textstat", "docsig"}`), convert to
   `ExtraNotInstalledError`; otherwise **re-raise the original** - that is our bug, not the user's
   environment.
4. **Idempotent + cached success.** Once loaded, a module-level flag short-circuits repeat calls so
   a multi-document scan doesn't re-run the import machinery per call. A *failed* load is **not**
   cached (so installing the extra and re-invoking in the same process - e.g. a long-lived test
   session - can succeed on a later call).
5. **Engine calls the loader conditionally.** `engine.scan()` calls `ensure_standard_loaded()`
   exactly when `settings.profile == "standard"`, *before* it computes `profile_codes` from
   `RULES`, so the `standard` rules are registered by the time the resolver runs. `fast` and `deep`
   runs never call it, so `fast` never imports a heavy module. (`deep` is Milestone 0003's problem;
   this task does not touch its branch.)

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/standard/__init__.py` | Create (empty import list + docstring) |
| `src/docsentinel/detectors/loader.py` | Create |
| `src/docsentinel/engine.py` | Modify - conditional `ensure_standard_loaded()` call in `scan()` |
| `tests/test_standard_loader.py` | Create |
| `tests/test_scan.py` | Modify - add the profile-gated-load regression tests |

## Symbols / fields

`src/docsentinel/detectors/standard/__init__.py`:

```python
"""Importing this package registers every shipped STANDARD-profile detector.

Heavy: importing this module imports scikit-learn / textstat / docsig transitively.
Never import it eagerly - go through docsentinel.detectors.loader.ensure_standard_loaded().
Detector stories (Milestone 0002, Stories 02.0-04.0) each append one submodule import below.
"""

# Detector submodules are appended here as each story lands, e.g.:
#   from docsentinel.detectors.standard import complexity  # DS201 (Story 02.0)
# __all__ grows in lockstep.

__all__: list[str] = []
```

`src/docsentinel/detectors/loader.py`:

| Symbol | Kind | Signature | Notes |
|--------|------|-----------|-------|
| `_STANDARD_PACKAGES` | module-level `frozenset[str]` | `frozenset({"sklearn", "textstat", "docsig"})` | The top-level import names of the `standard` extra's three packages (note: `scikit-learn` imports as `sklearn`). Used to classify an `ImportError` as "missing extra" vs. "our bug." |
| `_standard_loaded` | module-level `bool` | initial `False` | Success cache (see Decision §4). |
| `ensure_standard_loaded() -> None` | function | - | Imports `docsentinel.detectors.standard` under `try/except ImportError`; on success sets `_standard_loaded = True`; on an extra-package `ImportError` raises `ExtraNotInstalledError("standard", exc)`; on any other `ImportError` re-raises unchanged. No-ops if already loaded. |

Loader body (precise, so it is not improvised):

```python
def ensure_standard_loaded() -> None:
    global _standard_loaded
    if _standard_loaded:
        return
    try:
        import docsentinel.detectors.standard  # noqa: F401  (side-effect import)
    except ImportError as exc:
        if exc.name in _STANDARD_PACKAGES:
            raise ExtraNotInstalledError("standard", exc) from exc
        raise
    _standard_loaded = True
```

`src/docsentinel/engine.py` (`scan()` body addition, placed per Milestone 0001 Story 01.0 Task 03's
numbered steps):

- Between "resolve `settings`/`documents`" (step 1) and "compute `profile_codes`" (step 2), insert:
  ```python
  if settings.profile == "standard":
      ensure_standard_loaded()
  ```
  so the `standard` rules are in `RULES` before `profile_codes` filters it. Import
  `ensure_standard_loaded` at module scope from `docsentinel.detectors.loader` - the loader is
  stdlib-only, so this import stays cheap and does **not** pull in the heavy packages.

## Validators

- `ensure_standard_loaded()` raises exactly `ExtraNotInstalledError` (Task 01) when a *known extra*
  package is missing, and re-raises the original `ImportError` otherwise. It never swallows an
  error silently (that would violate the honesty rule - a `standard` scan must not quietly become a
  no-op).
- `exc.name` is Python's `ImportError.name` attribute (populated for `ModuleNotFoundError`); if a
  caught `ImportError` has `name is None` (rare, e.g. a malformed `from x import y` failure), treat
  it as "our bug" and re-raise - do not guess it is a missing extra.

## Tests

`tests/test_standard_loader.py`:
- `test_loader_module_imports_without_heavy_deps` - importing `docsentinel.detectors.loader` must
  not import `sklearn`/`textstat`/`docsig`; assert none of those three keys appear in `sys.modules`
  **as a result of** importing the loader (snapshot `sys.modules` before/after in a subprocess, or
  monkeypatch `builtins.__import__` to fail on those names and assert the loader import still
  succeeds). This is the "loader stays light" guarantee.
- `test_ensure_standard_loaded_raises_actionable_error_when_extra_missing` - simulate the extra
  being absent (monkeypatch `sys.modules` so `import docsentinel.detectors.standard` raises
  `ModuleNotFoundError(name="sklearn")`, or `builtins.__import__` to raise it); assert
  `ensure_standard_loaded()` raises `ExtraNotInstalledError` whose message contains
  `docsentinel[standard]`.
- `test_ensure_standard_loaded_reraises_unrelated_import_error` - make the subpackage import raise
  `ModuleNotFoundError(name="docsentinel.detectors.standard.typo")` (an *internal* name, not in
  `_STANDARD_PACKAGES`); assert the raised error is **not** `ExtraNotInstalledError` (our-bug
  errors are not disguised as a user setup problem).
- `test_ensure_standard_loaded_is_idempotent_on_success` - with the extra importable (or stubbed to
  import cleanly), call twice; assert the underlying import side effect happens only once (patch the
  submodule import and count calls) and no error is raised.
- `test_failed_load_is_not_cached` - first call raises `ExtraNotInstalledError`; then make the
  import succeed; a second call succeeds - proving a failure did not poison the cache.

`tests/test_scan.py` additions:
- `test_fast_scan_does_not_import_standard_subpackage` - run `scan(tmp_path)` with default
  `profile="fast"` and assert `docsentinel.detectors.standard` is **not** in `sys.modules` and
  `ensure_standard_loaded` was not called (patch it with a sentinel that records calls). The core
  guarantee of the whole milestone.
- `test_standard_scan_calls_loader` - `scan(tmp_path, config=Config(profile="standard"))` calls
  `ensure_standard_loaded()` exactly once (patched sentinel) before resolving rules.
- `test_standard_scan_without_extra_raises_actionable_error` - with the loader patched to raise
  `ExtraNotInstalledError`, `scan(..., profile="standard")` propagates it (the engine does not
  swallow it); a companion CLI-level assertion of the resulting exit code `2` lives in Task 03.

## Success criteria

- [ ] `import docsentinel.engine` in an environment **without** the `standard` extra succeeds and
      imports none of `sklearn`/`textstat`/`docsig` - proven by a test that imports the engine with
      those modules blocked and still runs a `fast` scan.
- [ ] `scan(..., profile="standard")` without the extra raises `ExtraNotInstalledError` (not a bare
      `ModuleNotFoundError`), and `scan(..., profile="fast")` never triggers the loader at all.
- [ ] The `standard` subpackage `__init__.py` has an empty import list after this task (no detector
      exists yet) - it imports cleanly and registers nothing.
- [ ] A genuine `ImportError` inside a (future) standard detector module surfaces as itself, not
      masked as `ExtraNotInstalledError`.

## Constraints

- Full type annotations. No bare `except:` - the only handler is `except ImportError as exc`, and
  it either converts or re-raises; nothing is swallowed.
- The loader must not import `config.py`, `engine.py`, or any heavy package at module scope - only
  `docsentinel.errors` (for `ExtraNotInstalledError`). Keep it a leaf.
- Do not introduce an entry-point / plugin-discovery mechanism for standard detectors. A hardcoded
  import list in `detectors/standard/__init__.py` is the right machinery, consistent with
  Milestone 0001's explicit decision for `fast` (`detectors/__init__.py`).
- `_standard_loaded` is process-wide mutable state; tests that drive it must reset it in teardown
  (a fixture that saves/restores `loader._standard_loaded`), following the same global-state
  isolation discipline Milestone 0001 established for `RULES`/`ANALYZERS`.
</content>
