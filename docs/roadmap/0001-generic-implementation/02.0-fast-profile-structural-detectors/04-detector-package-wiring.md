# Task 04 - Detector Package Wiring & End-to-End Fast Profile Test

**Story:** [02.0 - Fast-Profile Structural Detectors](README.md)
**Depends on:** Tasks 01-03 (all three detector modules exist and self-register their `Rule` at
import time, per Milestone 0001 Story 01.0 Task 01's `register_rule` pattern)

## Purpose

A `Rule`/`Analyzer` pair registering itself at import time only matters if something actually
imports the module. This task makes that automatic (importing `docsentinel.engine` must be
enough to activate every shipped `fast` detector - a caller should never need to know the
individual detector module names) and proves the whole chain end-to-end, then retires the last
pieces of M0-era wording that are no longer true.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/__init__.py` | Modify (was created empty in Task 01) - import every detector submodule for its registration side effect |
| `src/docsentinel/engine.py` | Modify - import `docsentinel.detectors` so registration happens before `ANALYZERS`/`RULES` are ever read |
| `tests/test_fast_profile_end_to_end.py` | Create |
| `docs/architecture/README.md` | Modify |
| `docs/security/README.md` | Modify - threat-model update (see below) |

## Symbols / fields

`src/docsentinel/detectors/__init__.py`:

```python
"""Importing this package registers every shipped detector's Rule and Analyzer."""

from docsentinel.detectors import comments, links, paths

__all__ = ["comments", "links", "paths"]
```

(Plain re-export for the side effect - no new symbols beyond the submodules themselves. The
`__all__` entries exist so a linter doesn't flag the imports as unused; the real purpose is the
import's side effect, not the names.)

`src/docsentinel/engine.py`: add `from docsentinel import detectors as _detectors  # noqa: F401`
(or equivalent explicit-side-effect-import style already used elsewhere in this codebase - check
`docs/dev/python_style_rules.md` for this project's convention on intentionally-unused imports
before picking the exact suppression comment) near the top of the module, *before* `ANALYZERS`
registration of each detector's entry: each detector module itself must still write into
`ANALYZERS[code] = detect` at its own module level (next to its `register_rule` call) - Task 04
does not centralize that mapping, it only guarantees the modules get imported.

## Behavior change

- `ANALYZERS` now has three real entries (`"DS101"`, `"DS102"`, `"DS103"`) the moment
  `docsentinel.engine` is imported - no explicit plugin-loading step, no config flag needed to
  "turn on" `fast` detectors (they are always on for `profile="fast"`; `select`/`ignore` from
  Milestone 0001 Story 01.0 Tasks 02-03 is the only way to narrow them).
- `ScanResult.notice` for `profile="fast"` now reads the "N fast rule(s) evaluated" wording from
  Story 01.0 Task 03's Decision §5, replacing the "not implemented in M0" wording for `fast`
  specifically - `standard`/`deep` keep the original wording (still true - this milestone ships
  nothing for either).

## Tests (`tests/test_fast_profile_end_to_end.py`)

Build one `tmp_path` fixture tree exercising all three detectors together:
- a Markdown file with one dangling link (triggers `DS101`),
- a stray `<!-- comment -->` in a different file (triggers `DS102`),
- a bare `` `nonexistent/path.py` `` code span in a third file (triggers `DS103`),
- and one clean file with none of the above.

Tests:
- `test_default_fast_scan_reports_all_three_rule_findings` - `scan(tmp_path)` (default
  `profile="fast"`) returns exactly one finding per planted issue, correctly attributed by
  `rule` and `path`.
- `test_clean_tree_reports_zero_findings_with_evaluated_notice` - the clean file alone: zero
  findings, but `notice` says rules were evaluated (not "not implemented") and
  `enabled_rules == ("DS101", "DS102", "DS103")`.
- `test_ignore_narrows_the_active_set` - `Config(ignore=("DS102",))` on the same tree: the
  comment finding disappears, the other two remain.
- `test_standard_and_deep_profiles_still_report_pending` - same tree, `profile="standard"` and
  `profile="deep"`: zero findings, `pending` still carries the original "not implemented"
  message for each (regression guard against Task 04 accidentally making this milestone's fast
  detectors leak into the other profiles).
- `test_cli_scan_exit_code_reflects_real_findings` - invoke `cli.main(["scan", str(tmp_path)])`
  directly; assert it returns `1` (findings present) for the planted-issue tree and `0` for the
  clean one - the first time this project's CLI exit code has ever meant something real.

## Docs updates

`docs/architecture/README.md`: replace "No detection analyzers are registered in M0." with a
short paragraph naming the three `fast` rules now registered (`DS101`/`DS102`/`DS103`, one line
each) and reaffirming that `standard`/`deep` remain unimplemented - do not let the new paragraph
imply more than Milestone 0001 actually ships.

`docs/security/README.md`: the existing M0 threat model's own "Mitigations and open gaps" /
Tampering section says "Today's impact is low because no detectors run; it becomes high once
detectors exist" - that condition is now true. Add a dated follow-up note (do not rewrite the
original SME-review block - append below it) flagging: detectors now read full document
*contents* (not just path/size as in M0), so a maliciously crafted Markdown file (e.g. an
extremely long single line defeating the regexes' backtracking, or a deeply nested fence
structure) becomes a new, in-scope DoS surface for `security-auditor` to assess before this
story is considered done - **this task does not resolve that itself**; it files the open item.

## Success criteria

- [ ] `import docsentinel.engine` alone (no explicit detector import) is sufficient for
      `ANALYZERS` to contain all three fast codes - proven by a test that does nothing but that
      import and inspects `ANALYZERS`.
- [ ] The full existing test suite (including every M0-era and Story 01.0 test) still passes
      unmodified in intent, even though several M0-era assertions about emptiness
      (`enabled_rules == ()`, "not implemented" notice) now only hold for `standard`/`deep`, not
      `fast` - update exactly those assertions, nothing else.
- [ ] `security-auditor` has been handed the new content-reading threat surface per the Docs
      updates section before this story is marked complete in `status.md`.

## Constraints

- Full type annotations; no bare `except:`.
- Do not introduce a plugin-discovery mechanism (entry points, directory scanning) for
  detectors - three hardcoded imports in `detectors/__init__.py` is the right amount of
  machinery for three detectors; revisit only if a future milestone's detector count makes the
  hardcoded list genuinely unwieldy.
