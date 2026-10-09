# Task 01 - Advisory-Only Exit-Code Semantics for Deep

**Story:** [04.0 - Deep-Profile Reporting & Exit-Code Semantics](README.md)
**Depends on:** Milestone 0001 Story 03.0 Task 01 (the `_exit_code(result, *, strict)` helper this
task extends), Milestone 0003 Story 02.0 (`DS301`, the `deep` findings in question)

## Purpose

`DS301` is a candidate generator with expected false positives. If a candidate could fail a build -
even under `--strict` - users would quickly `ignore = ["DS3"]` the whole range or stop trusting the
tool, defeating the point. This task makes the policy explicit and enforced: **`deep` findings are
advisory-only** - they print, they can be baselined, they feed the `docs-reviewer` agent, but they
never change the exit code. This is a deliberate asymmetry versus `fast`/`standard`, and it is the
exit-code half of the plan's "candidate, never verdict" guideline.

## Decision this task implements (record precisely - do not improvise at implementation time)

1. **Default behavior is unchanged for `fast`/`standard`** (Milestone 0001 Story 03.0 Task 01):
   exit `1` iff some finding has `severity == "error"`; `--strict` makes any finding exit `1`.
2. **`deep` is exempt from both.** A `deep` run exits `0` on findings regardless of severity **and**
   regardless of `--strict`. Since profile scoping is exact (a `deep` run contains only `deep`
   findings) and `DS301` is `warning`-only anyway, the simplest correct rule is: **when
   `result.profile == "deep"`, findings never contribute to the exit code.** Exit `2` (config/scan
   failure) is untouched - a genuine `ConfigError`/`ValueError`/`OSError` still exits `2`.
3. **Why profile, not per-finding severity:** keying off `result.profile == "deep"` (rather than
   joining each finding's rule back to its `Rule.profile`) is both correct here and robust to a future
   `deep` rule that someone mis-registers at a higher severity - the advisory guarantee holds for the
   whole profile, not one rule's declared severity. Document this reasoning inline so it is not
   "simplified" into a severity check later.
4. **`--strict` on a `deep` run is accepted but inert**, exactly like the deep-confirm flag is inert
   on `fast`: passing `--strict --profile deep` is not an error; it simply has no effect on the exit
   code. (It may still matter to a future `--fail-on-deep`; see §5.)
5. **Future `--fail-on-deep` is documented as deferred, not built.** A separate, explicit opt-in
   (`--fail-on-deep` flag or `deep_fail = true` config) could let a project that has tuned `DS301`
   promote its candidates to build-failing. This task does **not** implement it - it records it in the
   `_exit_code` docstring and in `docs/architecture/README.md` (Task 02) as the single, deliberate
   escape hatch, so the advisory-only default is clearly a choice with a known future override, not an
   oversight.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/cli.py` | Modify - `_exit_code` gains the `deep`-profile exemption |
| `tests/test_scan.py` | Modify/add exit-code tests for `deep` |

## Symbols / fields

| Symbol | Change |
|--------|--------|
| `_exit_code(result: ScanResult, *, strict: bool) -> int` | Add a leading guard: `if result.profile == "deep": return 0`. Then the existing Milestone 0001 Story 03.0 Task 01 logic (`if strict: return 1 if result.findings else 0; return 1 if any error else 0`) applies to `fast`/`standard` unchanged. Docstring states the advisory-only rule, the profile-not-severity rationale (§3), and the deferred `--fail-on-deep` escape hatch (§5). |

No new CLI flag is added by this task (`--fail-on-deep` is explicitly deferred). `--strict` stays
the single existing flag; the `deep` guard sits in front of its effect.

## Tests

- `test_deep_findings_never_fail_exit_code` - a `ScanResult(profile="deep", findings=(<one DS301
  warning>,))` → `_exit_code(result, strict=False) == 0`.
- `test_deep_findings_exempt_even_under_strict` - same result, `strict=True` → `0` (the asymmetry:
  a `warning` finding on `fast` under `--strict` would be `1`).
- `test_deep_exemption_holds_even_for_error_severity` - a `ScanResult(profile="deep", ...)` carrying
  a hypothetical `error`-severity finding still exits `0` (proves the guard is profile-keyed, not
  severity-keyed, per Decision §3).
- `test_fast_and_standard_exit_codes_unchanged` - regression: `profile="fast"` with an `error`
  finding → `1`; `profile="standard"` warnings-only under `--strict` → `1`; both unaffected by this
  task.
- `test_cli_deep_scan_exit_code_zero_end_to_end` - `main(["scan", str(tmp_path), "--profile",
  "deep", "--i-understand-deep-is-heuristic"])` against a confirmed, ready corpus that produces a
  `DS301` candidate returns `0` (findings printed, build not failed). `deep`-marked (needs the model);
  pair it with a model-free variant that constructs the `ScanResult` directly and calls `_exit_code`.

## Success criteria

- [ ] A `deep` run with any number of `DS301` findings exits `0`, with and without `--strict` -
      proven by tests covering both flag states.
- [ ] The `deep` exemption is keyed on `result.profile == "deep"`, not on per-finding severity -
      proven by `test_deep_exemption_holds_even_for_error_severity`.
- [ ] `fast`/`standard` exit-code behavior from Milestone 0001 Story 03.0 Task 01 is unchanged -
      guarded by a regression test.
- [ ] Exit code `2` (config/scan failure) is untouched; only the `0`/`1` boundary is affected, and
      only to add the `deep` exemption.
- [ ] `_exit_code`'s docstring records the advisory-only decision, the profile-not-severity
      rationale, and the deferred `--fail-on-deep` escape hatch.

## Constraints

- Full type annotations; `_exit_code` stays a pure function over `(ScanResult, bool)` with no
  argparse/`sys` dependency (Milestone 0001 Story 03.0 Task 01's invariant).
- Do not implement `--fail-on-deep` or any deep-failing mode in this task - documenting the deferral
  is the whole deliverable on that front. Keep the escape hatch a note, not code.
