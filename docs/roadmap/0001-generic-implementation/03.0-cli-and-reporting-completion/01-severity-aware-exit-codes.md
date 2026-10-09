# Task 01 - Severity-Aware Exit Codes

**Story:** [03.0 - CLI & Reporting Completion](README.md)
**Depends on:** Milestone 0001 Story 02.0 (needs real findings with real severities to be
meaningful - `DS102`/`DS103` ship as `warning`, `DS101` as `error`)

## Purpose

Today's `cli.py` does `return 1 if result.findings else 0` - any finding at all fails the run,
with no way to land a `warning`-only change (e.g. a stray HTML comment) without either fixing it
immediately or disabling the rule outright via `ignore`. Every mature linter distinguishes "this
blocks the build" from "this is worth knowing." This task makes that distinction real.

## Decision

- **Default behavior**: exit `1` iff at least one finding has `severity == "error"`. A run with
  only `warning` findings exits `0` (and still prints them - visibility, not suppression).
- **`--strict`**: a new `scan` flag; when set, any finding (warning or error) causes exit `1`.
  Useful for a stricter CI lane without changing anyone's local/default experience.
- Exit code `2` (config/scan failure) is unaffected - this task only changes the `0`/`1` boundary.
- `Finding.severity` is currently an open `str` field with no enumeration anywhere in the
  codebase (`models.py` just types it `str = "warning"`). This task does not introduce an enum -
  keep it a string, but the CLI logic must treat exactly `"error"` as build-failing and
  everything else (today just `"warning"`) as non-failing by default. Document this precisely so
  a future severity value doesn't silently become either all-failing or all-silent by accident.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/cli.py` | Modify |
| `tests/test_scan.py` | Modify/add CLI exit-code tests |

## Symbols / fields

| Symbol | Change |
|--------|--------|
| `scan_parser.add_argument("--strict", action="store_true")` | New CLI flag, `scan` subcommand only. |
| `main`'s final return | Replace `return 1 if result.findings else 0` with a helper `_exit_code(result: ScanResult, *, strict: bool) -> int` so the logic is unit-testable without going through `main`'s full argv parsing. |
| `_exit_code(result: ScanResult, *, strict: bool) -> int` | New function in `cli.py`: `if strict: return 1 if result.findings else 0`; else `return 1 if any(f.severity == "error" for f in result.findings) else 0`. |

## Tests

- `test_exit_code_zero_for_warnings_only_by_default` - a `ScanResult` with only `warning`
  findings → `_exit_code(result, strict=False) == 0`.
- `test_exit_code_one_for_any_error_by_default` - one `error` finding among several `warning`s →
  `1`.
- `test_exit_code_strict_fails_on_warnings_too` - warnings-only result, `strict=True` → `1`.
- `test_exit_code_zero_when_no_findings_regardless_of_strict` - empty findings, both strict
  values → `0`.
- `test_cli_strict_flag_wired_end_to_end` - `main(["scan", str(tmp_path), "--strict"])` against a
  tree producing only `DS102` (warning) findings returns `1`; without `--strict`, `0`.

## Success criteria

- [ ] `_exit_code` has no dependency on `argparse` or `sys` - pure function over a `ScanResult`
      and a bool, callable from a unit test without invoking the CLI.
- [ ] Existing M0-era CLI tests that assumed "any finding → exit 1" are updated to either use
      `error`-severity findings or pass `--strict`, whichever matches their original intent.

## Constraints

- Full type annotations; no change to exit code `2`'s meaning or trigger conditions.
- Do not add a third "warnings fail, but only above some count" tier - exactly two modes
  (default: errors only; `--strict`: everything) per the Decision above. Keep it simple until a
  real use case demands more.
