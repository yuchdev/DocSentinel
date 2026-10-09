# Task 03 - CLI & Docs Awareness of the Standard Extra

**Story:** [01.0 - Optional-Dependency Plumbing & Lazy Standard Loading](README.md)
**Depends on:** [02 - Lazy loader & engine wiring](02-lazy-loader-and-engine-wiring.md); Milestone
0001 Story 01.0 Task 04 (the real `rules`/`doctor`/`init` CLI output) and Story 03.0 (the
`scan` exit-code wiring)

## Purpose

The loader (Task 02) does the right thing inside `scan()`. This task makes the three *other* CLI
surfaces behave correctly around it: `scan --profile standard` without the extra must fail with a
helpful message and exit `2` (not a traceback); and `rules` / `doctor` must be able to *describe*
the `standard` profile honestly whether or not the extra is installed - listing its rules when they
can be loaded, and printing a clear "install the extra to enable these" note when they cannot,
instead of either crashing or silently pretending `standard` has no rules.

## Decision this task implements

1. **`scan --profile standard` without the extra → exit `2`, no traceback.** This already works
   mechanically: Task 02 raises `ExtraNotInstalledError` (a `ValueError` subclass), and `cli.py`'s
   existing `except (ConfigError, ValueError, OSError)` prints `Scan failed: <message>` to stderr
   and returns `2`. This task's job is only to *verify* it end-to-end and confirm the printed
   message is the actionable one from Task 01, not to change the except clause.
2. **`rules` and `doctor` attempt a best-effort load, then degrade.** Both commands should call
   `ensure_standard_loaded()` inside a `try/except ExtraNotInstalledError`:
   - On success: list the `standard` rules (`rules_for_profile("standard")`) alongside `fast`'s,
     grouped by profile.
   - On `ExtraNotInstalledError`: print a one-line note (`"standard profile: install
     docsentinel[standard] to enable (DS2xx)"`) under the `fast` rules, and **return `0`** -
     listing/inspecting capabilities is not itself a failure; the user asked "what *could* run,"
     and the honest answer is "these, plus more if you install the extra."
3. **`doctor` reports extra availability as a capability line.** `doctor` is the "what can this
   install do" command; it gains a line stating whether the `standard` extra is importable
   (`standard profile: available` / `standard profile: not installed (pip install
   docsentinel[standard])`), computed via the same best-effort load.

The asymmetry is intentional and matches other linters: *running* a profile you can't run is an
error (exit `2`); *asking what profiles exist* is always answerable (exit `0`).

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/cli.py` | Modify - `rules`/`doctor` best-effort load + note; verify `scan` error path |
| `tests/test_scan.py` | Modify - CLI-level tests for the three surfaces |
| `docs/architecture/README.md` | Modify - document the `standard` extra + lazy-load boundary |
| `docs/roadmap/0002-standard-profile-detectors/status.md` | Modify - mark Story 01.0 status |

## Symbols / fields

`src/docsentinel/cli.py`:

| Symbol | Change |
|--------|--------|
| `_standard_rule_lines() -> list[str]` | New private helper: calls `ensure_standard_loaded()` in a `try/except ExtraNotInstalledError`; returns either the formatted `standard` rule lines (from `rules_for_profile("standard")`) or a single "install the extra" note line. Shared by `rules` and `doctor` so the degrade behavior is written once. |
| `rules` command body | Use `_standard_rule_lines()` in addition to the existing `fast` listing; still `return 0`. |
| `doctor` command body | Add a capability line derived from whether `_standard_rule_lines()` returned real rules or the note; still `return 0`. |

- Do not call `ensure_standard_loaded()` unconditionally at CLI startup - only inside `rules`,
  `doctor`, and (via `scan()`) the `standard` scan path. `docsentinel scan --profile fast` must
  still never touch the loader.

## Behavior change

- `docsentinel scan --profile standard` on a machine without the extra prints the Task 01 message
  (naming `pip install docsentinel[standard]` / `uv sync --extra standard`) to stderr and exits
  `2`. Previously (M0 / Milestone 0001) a `standard` scan simply reported "not implemented in M0"
  and exited `0`; from this milestone on, requesting `standard` either runs real rules or fails
  loudly - it never silently no-ops.
- `docsentinel rules` and `docsentinel doctor` now mention the `standard` profile in both the
  installed and not-installed cases.

## Tests (`tests/test_scan.py`)

- `test_cli_scan_standard_without_extra_exits_2_with_guidance` - patch `ensure_standard_loaded` to
  raise `ExtraNotInstalledError`; `main(["scan", str(tmp_path), "--profile", "standard"])` returns
  `2` and the captured stderr contains `docsentinel[standard]`.
- `test_cli_rules_lists_standard_when_extra_present` - with the loader patched to succeed and a fake
  `standard` rule registered via a fixture, `main(["rules"])` output contains that rule's code and
  returns `0`.
- `test_cli_rules_notes_missing_extra_and_still_exits_0` - loader patched to raise
  `ExtraNotInstalledError`; `main(["rules"])` output contains the "install docsentinel[standard]"
  note and returns `0` (listing capabilities is never a failure).
- `test_cli_doctor_reports_standard_availability` - two cases (loader succeeds / loader raises):
  `doctor` output contains `available` vs `not installed`, both returning `0`.
- `test_cli_scan_fast_profile_never_loads_standard` - `main(["scan", str(tmp_path)])` (default
  fast) with a sentinel on `ensure_standard_loaded` asserting it is never called.

## Docs updates

`docs/architecture/README.md`: add a short subsection under the profile boundaries describing that
`standard` detectors live behind the `docsentinel[standard]` optional dependency group, are imported
lazily only when `profile="standard"` is requested, and fail with an actionable error (not a
traceback) when the extra is absent. Reaffirm that `fast` imports nothing heavy and `deep` remains
Milestone 0003's unimplemented territory. Keep it factual - after this story the `standard`
*profile machinery* exists but *zero standard detectors* do yet; do not imply detectors ship here.

## Success criteria

- [ ] `docsentinel scan --profile standard` without the extra exits `2` and prints the actionable
      install guidance - verified by an end-to-end CLI test, not just asserted in prose.
- [ ] `docsentinel rules` and `docsentinel doctor` both return `0` whether or not the extra is
      installed, and both mention the `standard` profile in each case.
- [ ] No CLI command imports a heavy package on the `fast` path - the loader is the single choke
      point and `scan --profile fast` never reaches it.

## Constraints

- Full type annotations; no bare `except:` - the only handler added here is
  `except ExtraNotInstalledError`, caught narrowly for the degrade-to-note behavior.
- Do not change the `cli.py` `except (ConfigError, ValueError, OSError)` tuple around `scan` - the
  exit-code `2` behavior for `ExtraNotInstalledError` rides on its `ValueError` ancestry (Task 01),
  deliberately, so the exit-code contract stays in one place.
- `init`'s behavior is unchanged by this task; it still writes a starter config and never mentions
  the extra (installing dependencies is not the config file's job).
</content>
