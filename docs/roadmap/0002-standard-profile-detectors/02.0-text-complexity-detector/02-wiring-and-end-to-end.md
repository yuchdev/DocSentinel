# Task 02 - Package Wiring & End-to-End Standard Profile Test

**Story:** [02.0 - Text Complexity Detector](README.md)
**Depends on:** [01 - Complexity detector & grade threshold](01-complexity-detector.md); Milestone
0002 Story 01.0 Task 02 (the empty `standard` subpackage + loader)

## Purpose

`DS201` registers itself at import time - but only if something imports its module. This task adds
that import to the `standard` subpackage and proves the whole chain end-to-end: with the extra
installed, `scan(..., profile="standard")` lazily loads the subpackage, registers `DS201`, and
returns real findings; `select`/`ignore` narrow it; and `fast` still never touches any of it. This
is also the first end-to-end proof that Story 01.0's lazy-load design actually delivers a working
detector.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/standard/__init__.py` | Modify - add the `complexity` import line |
| `tests/test_standard_profile_end_to_end.py` | Create |
| `docs/architecture/README.md` | Modify - record `DS201` as the first standard rule |

## Symbols / fields

`src/docsentinel/detectors/standard/__init__.py` - add:

```python
from docsentinel.detectors.standard import complexity  # DS201 (Story 02.0)

__all__ = ["complexity"]
```

(Plain side-effect import, mirroring `fast`'s `detectors/__init__.py`. The import triggers
`complexity.py`'s module-level `register_rule(DS201)` and its `ANALYZERS["DS201"] = detect`
assignment. Later detector stories append to both the import and `__all__`.)

- Confirm `complexity.py` performs its own `ANALYZERS["DS201"] = detect` at module level, next to its
  `register_rule` call - exactly as Milestone 0001's fast detectors do. This wiring task does not
  centralize the mapping; it only guarantees the module gets imported (via the loader).

## Behavior change

- With `docsentinel[standard]` installed, `scan(root, config=Config(profile="standard"))` now:
  lazily imports `docsentinel.detectors.standard` (Story 01.0 loader), which registers `DS201`;
  resolves `active_codes = ("DS201",)` (modulo `select`/`ignore`); runs it; and returns a
  `ScanResult` whose `notice` reads "1 standard rule(s) evaluated" (the Milestone 0001 Story 01.0
  Task 03 "evaluated" wording), **not** the old "standard detectors are not implemented in M0"
  `pending` message. That old `pending` message for `standard` is now only correct when the extra is
  absent - at which point the run fails with `ExtraNotInstalledError` before reaching that branch, so
  the message is effectively retired for `standard` once this story ships.
- `fast` and `deep` scans are entirely unaffected.

## Tests (`tests/test_standard_profile_end_to_end.py`)

These tests require the `standard` extra; mark them so they are skipped (not failed) when it is
absent - `pytest.importorskip("textstat")` / `pytest.importorskip("sklearn")` at module top, or a
dedicated `standard_extra` marker registered in `conftest.py` (decide which, matching whatever
skip-when-dependency-absent convention the repo's `tests/` already uses; if none exists yet,
`importorskip` is the lighter choice).

Build a `tmp_path` tree with: one Markdown file of deliberately dense prose (triggers `DS201`), and
one plainly-written file (clean).

- `test_standard_scan_reports_complexity_finding` - `scan(tmp_path, config=Config(profile="standard"))`
  returns exactly one `DS201` finding, attributed to the dense file by `path`.
- `test_standard_scan_notice_says_evaluated_not_pending` - the clean-file-only tree under
  `profile="standard"`: zero findings, `notice` contains "evaluated", `enabled_rules == ("DS201",)`,
  and `pending` does **not** contain "not implemented".
- `test_ignore_narrows_standard_set` - `Config(profile="standard", ignore=("DS201",))` on the dense
  tree: zero findings, and the filtered-out `pending` message (Milestone 0001 Story 01.0 Task 03
  Decision §5) rather than "evaluated" or "not implemented".
- `test_importing_engine_does_not_register_ds201` - with a fresh import state, importing
  `docsentinel.engine` (no scan) leaves `DS201` **absent** from `RULES`/`ANALYZERS` - it only
  appears after a `standard` scan (or an explicit `ensure_standard_loaded()`). Guards the lazy
  contract from regressing into eager import.
- `test_cli_standard_scan_exit_code_reflects_warning_severity` - `main(["scan", str(tmp_path),
  "--profile", "standard"])` on the dense tree exits `0` by default (DS201 is a `warning`) and `1`
  with `--strict` (Milestone 0001 Story 03.0 Task 01 semantics) - the first proof the severity/exit
  wiring composes with a `standard` detector.

## Docs updates

`docs/architecture/README.md`: add `DS201` (text complexity, `textstat`, `warning`) to the list of
registered rules, in a `standard`-profile subsection distinct from the `fast` rules. State plainly
that `standard` detectors load only behind the `docsentinel[standard]` extra and that `DS202`-`DS204`
remain to be added by later stories of this milestone. Do not imply more than Story 02.0 ships.

## Success criteria

- [ ] A single `scan(..., profile="standard")` (extra installed) is sufficient to register and run
      `DS201` - no explicit detector import by the caller, proven by `test_importing_engine_does_not_
      register_ds201` plus a positive scan test.
- [ ] The full existing suite still passes - in particular any Milestone 0001 test asserting
      `standard` always produces the "not implemented" `pending` message must be updated to reflect
      that `standard` now either runs rules (extra present) or raises `ExtraNotInstalledError` (extra
      absent); update exactly those assertions, nothing else.
- [ ] `DS201` end-to-end findings flow through `--strict` and (by construction) through the baseline
      mechanism, with no code added here for either.

## Constraints

- Full type annotations; no bare `except:`.
- Do not add a plugin-discovery mechanism - one import line in `detectors/standard/__init__.py` per
  detector, consistent with Story 01.0's decision and Milestone 0001's `fast` precedent.
- Keep the `importorskip`/marker guard on these tests so the default (no-extra) test lane stays
  green - CI's `standard`-extra lane (Story 05.0) is where they actually execute.
</content>
