# Task 04 — `--include`/`--exclude` flags and `scan()` keywords

**Parent story:** [Story 02.0](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/README.md)  
**Role:** Python Expert  
**Depends on:** Task 03.

## Inputs

- Story README "CLI reference", "Precedence", "Showing the effective selection", "Decisions" S1 to
  S4 and S9.
- `/src/docsentinel/engine.py` (`scan()`), `/src/docsentinel/cli.py` (`_build_parser()`,
  `_run_scan()`, `_run_baseline()`, the `doctor` branch), the Story 03.0 config-source helper.

## Steps

1. `/src/docsentinel/engine.py`: add keyword-only `include` and `exclude` (`Optional[Sequence[str]]`)
   to `scan()`. After settings are known and before discovery: if the target is a file and either
   is given, log the single-file `WARNING` and ignore them; otherwise call
   `normalize_invoker_selectors()`, then `dataclasses.replace()` the settings (include replaced,
   exclude appended, duplicates removed in first-occurrence order). Log the `INFO` selection line
   and the per-pattern `WARNING` for invoker include patterns with zero hits. Coordinate with the
   concurrent logging work in this module.
2. `/src/docsentinel/cli.py`: add `--include` and `--exclude` (`action="append"`, `metavar`
   PATTERN, help text stating "relative to the scan root") to `scan` and `baseline`; pass them to
   `scan()` only when given, as `--link-root` is passed. A `ConfigError` keeps the existing
   `Scan failed:` and `Baseline generation failed:` paths and exit `2`.
3. `doctor`: print the include and exclude counts and their source for the configuration of the
   current directory, using the Story 03.0 source information.
4. Docstrings for the new keywords; the `__init__` module docstring of the package mentions them
   if it lists `scan()` keywords.
5. Report a `Docs impact:` line (C, K, P).

## Files

`/src/docsentinel/engine.py`, `/src/docsentinel/cli.py`, possibly `/src/docsentinel/__init__.py`
(docstring only).

## Verification

- Integration tests test_discovery_selectors.py and test_cli_include_exclude_ds101.py (Task 05)
  green with `-q`.
- `uv run docsentinel scan . --exclude docs --format json` (to a scratch output file) exits `0` and
  reports no document under docs.

## Acceptance

- [ ] Flags on both commands; keywords on `scan()`; identical results through both paths.
- [ ] Merge semantics and precedence exactly as the story states.
- [ ] Logging and `doctor` lines as specified.

## Amendment (ADR 0006, 2026-11-18)

[ADR 0006](/docs/adr/0006-invoker-include-exclude-and-directory-selectors.md) Contracts 1, 4, 5 and
6 are authoritative. They refine the steps above:

- **Step 1, single-file target (O4, provisional).** The shape checks (type, empty sequence, a bare
  `str`/`bytes` refused (O5), at most 256 values, at most 1,024 characters) run for **every**
  target. Only after they pass does a single-file target log the S9 `WARNING` and ignore the
  keywords.
- **Step 1, INFO line.** In `exclude <m> pattern(s) (<c> configured, <i> invoker)`, `<i>` counts
  the invoker additions that were not already in the configured list (after deduplication).
  Missing-exclude `WARNING`s come from `InvokerSelection.unmatched_exclude`, logged here once.
- **Step 2, early CLI validation.** Before logging `scan started` (and `baseline started`), the CLI
  calls `normalize_invoker_selectors()` once and discards the result, so a bad value leaves
  `Scan failed:` (or `Baseline generation failed:`) as the first stderr line, as today. The raw
  lists are then passed to `scan()`, whose normalisation is idempotent.
- **Step 3, `doctor` source.** The source shown is the project file name when the key is in
  `ConfigSources.project_options`, else `default`; never a user-settings source (C6).

## Amendment (Task 02 security review, 2026-11-19)

The [threat model](/docs/security/threat-model-0009-invoker-selectors-2026-11-18.md) (verdict
PASS_WITH_FOLLOWUP) is a standing input; link it in the briefing. Its amendments A4 and A6 are
this task's, and are folded into
[ADR 0006](/docs/adr/0006-invoker-include-exclude-and-directory-selectors.md) Contracts 3, 5 and 6:

- **A4 (shared root spellings).** The engine and the CLI early call both pass
  `root_spellings=selector_root_spellings(directory, root)`. Here `directory` is the **canonical**
  root (`Path(root).resolve()` in the engine, `_resolve_root()` in the CLI) and `root` is the root
  argument as given.
  - Do not reuse `_origin_spellings()` and do not read `$PWD`.
  - The early call never passes the spelled root as `scan_root`.
- **A6, as owner ruling R1 (2026-11-19).** When `include` or `exclude` was given (not `None`) and
  the final inventory is empty, `scan()` raises `ConfigError`
  `the selection admitted no document; values are relative to the scan root`, with no value
  echoed. The CLI exits `2` through `Scan failed:` / `Baseline generation failed:`.
  - The per-pattern zero-hit `WARNING`s stay, and are logged first.
  - Config-only selection (both keywords `None`) keeps today's exit `0` for an empty inventory.
  - A single-file target never reaches this check.
- **M22.** The `INFO` selection line and the S9 single-file `WARNING` carry counts only. Every
  pattern echoed in a log record is `safe(pattern, 200)`.
- **Docs note for Task 06:** the new flags make the argparse abbreviations `--i` and `--ex`
  ambiguous, so argparse exits `2` on them.
- **Merge gate:** the threat model's BLOCK conditions apply to this change.
