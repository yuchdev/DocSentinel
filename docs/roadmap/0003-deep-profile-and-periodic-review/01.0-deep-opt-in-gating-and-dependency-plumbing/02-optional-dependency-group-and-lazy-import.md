# Task 02 - Optional `deep` Dependency Group & Lazy-Import Boundary

**Story:** [01.0 - Deep Profile Opt-In Gating & Dependency Plumbing](README.md)
**Depends on:** [01 - Deep opt-in confirmation gate](01-deep-opt-in-confirmation-gate.md) (the
`pending` branching this task extends with a "deps missing" case)

## Purpose

`deep` detectors (Story 02.0) need spaCy and textacy, which are heavy, non-stdlib, and absent from
a default install. Two hard requirements fall out of DocSentinel's architecture: (1) those packages
must be an **optional** extra, so a `fast`/`standard` user never installs them; and (2) importing
`docsentinel.engine` - which every entry point does, including the `fast` pre-commit hook - must
stay cheap and must not fail when the extra is absent. This task adds the dependency group and the
lazy-import boundary, plus a single readiness probe that Task 03's `doctor` and Story 02.0's
detector both consult, so neither re-implements "is deep installed?" logic.

## Decision this task implements

1. **Optional extra**, in `pyproject.toml`:
   `[project.optional-dependencies] deep = ["spacy>=3.7", "textacy>=0.13"]`. Installed via
   `pip install docsentinel[deep]` / `uv sync --extra deep`. The spaCy **model**
   (`en_core_web_sm`) is deliberately **not** a pip dependency - it is a one-time
   `python -m spacy download en_core_web_sm` step (Task 03 documents it), because models are
   distributed out-of-band, not as PyPI wheels in this project's dependency tree.
2. **Lazy import is the law.** No module reachable from `import docsentinel.engine` may contain a
   top-level `import spacy` / `import textacy`. Story 02.0's detector module registers its `Rule`
   and `ANALYZERS` entry at import time (cheap, stdlib only) but imports spaCy/textacy **inside** the
   analyzer call, through this task's loader. So `import docsentinel.detectors.contradictions`
   succeeds even on a machine with no `deep` extra installed; the `ImportError` only ever surfaces
   when a confirmed `deep` scan actually tries to run.
3. **One readiness probe, two shapes:** a boolean "can I import the libs?" and a boolean "is the
   model present?", plus a combined "fully ready" that both must be true. The probe never raises -
   it reports; raising vs. reporting is the caller's choice (the engine reports via `pending`;
   `doctor` reports a line; the detector raises a clear, actionable message only at the point of
   actual use, never at import).
4. **"Deps missing" is honest `pending`, not a crash.** When `profile == "deep"` is **confirmed**
   (Task 01) but the probe says deps/model are unavailable, `engine.scan()` runs zero deep
   analyzers and emits a `pending` message naming the exact fix command - it does not raise, does
   not exit `2`, does not partially run. Inserted ahead of Task 01's "confirmed but nothing
   registered" branch (see Task 01 Decision §4's marked insertion point).
5. **Flag the de-duplication with Milestone 0002.** Milestone 0002 (`standard`, specced in
   parallel) very likely introduces its own optional-extra + lazy-import helper for its heavier
   dependencies. This task **cannot** confirm 0002's design from disk, so it writes its own
   `deep_support.py` and leaves an explicit `TODO(milestone-0002-dedup)` note (in the module
   docstring and this spec) so whoever lands both milestones collapses the two probes into one
   shared helper rather than maintaining parallel copies.

## Files

| Path | Action |
|------|--------|
| `pyproject.toml` | Modify - add `deep` optional-dependency group |
| `src/docsentinel/deep_support.py` | Create - lazy loaders + readiness probe |
| `src/docsentinel/engine.py` | Modify - "deps missing" `pending` branch for confirmed deep runs |
| `tests/test_deep_support.py` | Create |
| `tests/test_scan.py` | Modify - deps-missing gating test |

## Symbols / fields

`src/docsentinel/deep_support.py`:

| Symbol | Kind | Signature | Notes |
|--------|------|-----------|-------|
| `DEEP_EXTRA_HINT` | module-level `str` | - | The canonical install instruction string, reused everywhere: `"install the deep extra (pip install docsentinel[deep]) and the model (python -m spacy download en_core_web_sm)"`. One source of truth so every message matches. |
| `MODEL_NAME` | module-level `str` | - | `"en_core_web_sm"`. Pinned model name; referenced by the loader and by `doctor`. |
| `libraries_available() -> bool` | function | - | `True` iff `import spacy` and `import textacy` both succeed. Catches `ImportError` only; never raises. Does **not** import at module top level - the import happens inside this function body. |
| `model_available() -> bool` | function | - | `True` iff the spaCy model `MODEL_NAME` is installed (via `spacy.util.is_package(MODEL_NAME)` or an equivalent non-loading check - must **not** fully load the model, which is slow). Returns `False` (not raise) if spaCy itself is absent. |
| `deep_ready() -> bool` | function | - | `libraries_available() and model_available()`. The single "can a deep scan actually run?" predicate the engine and `doctor` share. |
| `load_pipeline() -> "spacy.language.Language"` | function | - | Imports spaCy, loads and returns the `MODEL_NAME` pipeline. Raises `RuntimeError(f"deep profile needs the model '{MODEL_NAME}': {DEEP_EXTRA_HINT}")` from the underlying `ImportError`/`OSError` if libs or model are missing - the **only** function here that raises, and only when a caller has already decided to actually run deep. The return annotation is a string forward-reference so this module needs no top-level `spacy` import for typing. |

`src/docsentinel/engine.py`: in the confirmed-`deep` branch, call `deep_support.deep_ready()`
before selecting deep analyzers; when `False`, emit `pending` =
`(f"deep profile confirmed, but its dependencies are unavailable - {deep_support.DEEP_EXTRA_HINT}",)`
and run nothing. `import docsentinel.deep_support` is safe at engine import time precisely because
`deep_support` has no top-level heavy imports.

## Tests

`tests/test_deep_support.py` (use `monkeypatch`/import-machinery stubs so these run on a machine
**without** the `deep` extra installed - the suite must stay green in a default CI environment):
- `test_libraries_available_true_when_importable` - with spaCy/textacy importable (or stubbed into
  `sys.modules`), returns `True`.
- `test_libraries_available_false_when_missing` - simulate `ImportError` (e.g. `monkeypatch`
  `builtins.__import__` or insert a sentinel that raises) → `False`, no exception propagates.
- `test_model_available_false_without_spacy` - spaCy absent → `model_available()` is `False`, not
  an error.
- `test_deep_ready_requires_both` - libs present but model absent → `deep_ready()` is `False`.
- `test_load_pipeline_raises_actionable_when_missing` - libs/model absent → `load_pipeline()`
  raises `RuntimeError` whose message contains `DEEP_EXTRA_HINT`.

`tests/test_scan.py` addition:
- `test_deep_confirmed_but_deps_missing_reports_pending` - register a fake deep rule, confirm deep,
  `monkeypatch` `deep_support.deep_ready` to return `False` → analyzer **not** invoked, zero
  findings, `pending` carries the deps-missing message with the install hint; no exception, exit
  path stays `0`.

## Success criteria

- [ ] `import docsentinel.engine` on a machine **without** the `deep` extra installed succeeds and
      is cheap - proven by a test that stubs spaCy/textacy out of `sys.modules` (or asserts they are
      not imported) and still imports the engine and the Story 02.0 detector module without error.
- [ ] No module reachable from `docsentinel.engine` has a top-level `import spacy`/`import textacy`
      - a grep-style assertion test (`"import spacy" not in` the engine/detector module source, or a
      `sys.modules` check after a clean import) guards this.
- [ ] `deep_ready()`, `libraries_available()`, `model_available()` never raise, for any
      installed/absent combination.
- [ ] A confirmed `deep` run with deps missing is a clean no-op-with-explanation (exit `0`,
      actionable `pending`), never a traceback or exit `2`.
- [ ] The `TODO(milestone-0002-dedup)` note is present in `deep_support.py`'s docstring so the
      parallel optional-extra helper gets collapsed when both milestones land.

## Constraints

- Full type annotations; no bare `except:` - catch exactly `ImportError` (and `OSError` for model
  load) where probing, nothing broader.
- The spaCy return type on `load_pipeline` is a **string forward-reference** annotation - do not add
  a top-level `import spacy` just to satisfy a type hint (that would defeat the whole boundary).
  Use `from __future__ import annotations` or a quoted annotation, matching this project's style.
- `DEEP_EXTRA_HINT` is the single source of the install-instruction wording; no other module
  hardcodes a second copy of that sentence.
