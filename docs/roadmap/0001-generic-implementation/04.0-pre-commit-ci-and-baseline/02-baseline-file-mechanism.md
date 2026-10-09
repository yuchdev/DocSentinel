# Task 02 - Baseline File Mechanism

**Story:** [04.0 - Pre-commit, CI & Self-Scan Baseline](README.md)
**Depends on:** Milestone 0001 Story 02.0 (real findings to baseline); mirrors the
`flakeforge-baseline.json` pattern referenced in this project's own `CLAUDE.md`-adjacent
ecosystem precedent (Canonix Engine's `flakeforge` dependency, already pinned in
`pyproject.toml` though unused by DocSentinel's own code) - gate only *new* findings against a
captured snapshot, so turning a rule on does not force an instant fix-everything-or-disable-it
choice on a corpus with pre-existing issues.

## Purpose

The moment Story 02.0's detectors go live, this repo's own `docs/` surfaces real findings (the
illustrative ADR 0001's three dangling links, at minimum - confirmed by hand during that story's
Task 01). Without a baseline, enabling `DS101` in CI and pre-commit is an all-or-nothing switch:
either every pre-existing issue gets fixed in one disruptive sweep, or the rule can't be turned
on yet. A baseline lets the rule be enabled today, with the fix-up tracked as its own shrinking
backlog.

## Decision

- Baseline format: a JSON object mapping a **stable finding fingerprint** to `true` (presence is
  the only signal needed; no metadata stored per entry - keep it minimal, unlike a full report).
- Fingerprint: `f"{finding.rule}:{finding.path}:{hashlib.sha256(finding.message.encode()).hexdigest()[:12]}"`.
  Hashing the *message* (not storing it verbatim) means a baseline file doesn't need updating
  just because a message's wording improves in a later version - but a message hash is **not**
  stable across a genuine content edit at the flagged location, which is the deliberately
  cheap, if imperfect, tradeoff: a real baseline entry usually goes stale (and must be
  re-captured) exactly when the underlying issue was looked at anyway, which is an acceptable
  prompt.
- `Config.baseline: str | None = None` - a relative path to a baseline JSON file, resolved
  against `root` the same way `docsentinel.toml`/`doc_sentinel.toml` is. Not set by default - a
  project must opt in explicitly.
- `engine.scan()`: when `settings.baseline` is set and the file exists, load it and drop any
  `Finding` whose fingerprint is present from the returned `findings` tuple - **before** severity
  /exit-code logic runs, so a baselined `error` genuinely stops failing the build, not just stops
  being "strict."
- New CLI subcommand: `docsentinel baseline <root>` - runs a scan with **no** `select`/`ignore`
  override (always the full configured rule set) and writes every current finding's fingerprint
  to the configured (or `--output`-specified) baseline file, overwriting it. This is a snapshot
  tool, not a merge tool - re-running it always reflects exactly current reality.
- A baseline is a **ceiling, not a target**: nothing in this task enforces that the baseline only
  shrinks (that is a human/CI-review discipline question for Task 03 and beyond, same as
  `flakeforge-baseline.json`'s own stated policy) - this task only implements the suppression
  mechanism itself.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/config.py` | Modify - `Config.baseline` field + validation |
| `src/docsentinel/baseline.py` | Create - fingerprinting, load/save, filtering |
| `src/docsentinel/engine.py` | Modify - apply baseline filtering in `scan()` |
| `src/docsentinel/cli.py` | Modify - `baseline` subcommand |
| `tests/test_baseline.py` | Create |

## Symbols / fields

`src/docsentinel/baseline.py`:

| Symbol | Kind | Notes |
|--------|------|-------|
| `fingerprint(finding: Finding) -> str` | function | Per the Decision's exact format. |
| `load_baseline(path: Path) -> frozenset[str]` | function | Empty `frozenset()` if the file does not exist (a configured-but-not-yet-created baseline is not an error - `docsentinel baseline` creates it). Raises `ConfigError` (reuse the existing exception type, imported from `config.py`) on malformed JSON or a non-list/non-dict shape. |
| `save_baseline(path: Path, findings: tuple[Finding, ...]) -> None` | function | Writes `{"fingerprints": sorted(fingerprint(f) for f in findings)}`, `indent=2`, creating parent directories as needed (mirror `doc_registry.py`'s `--cursor` flag's `parent.mkdir(parents=True, exist_ok=True)` precedent from the Canonix Engine tooling this project's scaffold drew on, applied here to this project's own code for the first time). |
| `filter_baselined(findings: tuple[Finding, ...], known: frozenset[str]) -> tuple[Finding, ...]` | function | `tuple(f for f in findings if fingerprint(f) not in known)`. |

`src/docsentinel/config.py`: add `baseline: str | None = None` to `Config`; validate (if present)
that it is a nonempty string - resolution to an actual path happens in `engine.py`, not here
(`config.py` stays about *parsing*, not filesystem resolution, per its existing division of
labor with `engine.py`).

`src/docsentinel/cli.py`: `commands.add_parser("baseline", ...)` with a `root` positional
(default `.`) and `--config`/`--output` options; calls `scan()` with select/ignore left at
whatever the config specifies (do **not** force "all rules" by bypassing config - a project that
has permanently `ignore`d a rule should not have it reappear in the baseline file) - revise the
Decision's "no select/ignore override" line to mean "no *CLI flag* override," not "ignore the
config file's own select/ignore" - then calls `save_baseline`.

## Tests (`tests/test_baseline.py`)

- `test_fingerprint_is_stable_for_identical_finding` - same `Finding` twice → same fingerprint.
- `test_fingerprint_differs_by_rule_path_or_message` - changing any one of the three changes it.
- `test_load_baseline_missing_file_is_empty_set`.
- `test_load_baseline_malformed_json_raises_config_error`.
- `test_save_then_load_round_trips`.
- `test_filter_baselined_drops_known_findings_only`.
- `test_scan_with_baseline_suppresses_matching_findings` - end-to-end: plant a `DS101` finding,
  capture it via `save_baseline`, re-run `scan()` with `Config(baseline=...)` pointed at that
  file - zero findings returned.
- `test_scan_with_baseline_still_reports_new_findings` - same setup, then plant a *second*,
  different dangling link after capturing the baseline - the new one is still reported.
- `test_cli_baseline_subcommand_writes_file` - `main(["baseline", str(tmp_path)])` creates the
  file at the expected default location and it round-trips through `load_baseline`.

## Success criteria

- [ ] Baseline filtering happens before severity/exit-code logic (Story 03.0 Task 01) - a fully
      baselined tree exits `0` even under `--strict`, since baselined findings are removed from
      `result.findings` entirely, not merely down-weighted.
- [ ] `docsentinel baseline` is idempotent - running it twice in a row with no intervening doc
      changes produces byte-identical output (sorted fingerprints, stable JSON formatting).

## Constraints

- Full type annotations; `ConfigError` (imported, not redefined) is the one error type for
  baseline-loading failures, consistent with how `config.py` already centralizes its error type.
- No bare `except:`; JSON/OS errors on baseline load are handled the same way `config.py`
  handles them for the main config file (see its `except (OSError, UnicodeDecodeError,
  tomllib.TOMLDecodeError)` precedent, adapted to `json.JSONDecodeError` here).
