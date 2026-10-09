# Task 02 - Deep Reporting Wording & Architecture Refresh

**Story:** [04.0 - Deep-Profile Reporting & Exit-Code Semantics](README.md)
**Depends on:** [01 - Advisory-only exit codes for deep](01-advisory-only-exit-codes-for-deep.md),
Milestone 0003 Story 01.0 (the `pending`/`notice` branches), Story 02.0 (`DS301` findings)

## Purpose

An exit code of `0` on a `deep` run with findings present is correct (Task 01) but surprising unless
the report *says why*. This task makes the report honest and self-explaining for every `deep`
outcome - rules evaluated, opt-in missing, deps missing, nothing registered - and adds a short
advisory banner so a reader never mistakes a candidate for a verdict or a `0` exit for "validated."
It also lands the narrow `docs/architecture/README.md` update giving `deep` its first defined content
without overclaiming reliability.

## Decision this task implements

1. **Advisory banner on deep runs with findings.** When `result.profile == "deep"` and
   `result.findings` is non-empty, `reporting.render` prepends (text) / includes (JSON) a one-line
   advisory: `"Deep findings are heuristic candidates for review - they do not fail the build."`
   This is informational, derived from `profile` + presence of findings; it does not alter the
   `ScanResult` contract's fields.
2. **`notice` wording for a confirmed, ready, evaluated deep run** reads as advisory, e.g.
   `f"{len(active_codes)} deep rule(s) evaluated (heuristic, advisory-only)."` - reusing the
   "N rule(s) evaluated" shape from Milestone 0001 Story 01.0 Task 03 but marked advisory. An empty
   findings list under this notice means "ran and found no candidates," never "validated."
3. **The `pending` messages from Story 01.0/02.0 are the single source of the not-ran explanations** -
   this task does not add new ones; it ensures `reporting.render` surfaces them clearly (opt-in
   missing, deps missing, nothing registered, all-filtered-out). No message duplication across
   modules.
4. **JSON report carries the same information, structurally** - the advisory banner is a field/line
   the JSON consumer can read, not only a text-mode nicety, so a CI job parsing JSON can tell a `deep`
   run's findings are advisory. Keep it within the existing `dataclasses.asdict(result)` serialization
   approach; if a new surfaced string is needed, derive it in `render` rather than widening the frozen
   `ScanResult` contract (a contract change would need its own cross-component migration note).
5. **Architecture doc: narrow and honest.** Replace the current "explicitly enabled semantic
   integrations to `deep`. These profiles do not perform those checks today" sentence with a short
   paragraph stating: `deep` now registers one detector, `DS301` (fact-contradiction *candidates*);
   it is opt-in (Story 01.0's confirmation gate), heuristic (expected false positives), advisory-only
   (never fails a build, Task 01), and backed by the periodic `docs-reviewer` agent (Story 03.0) for
   triage and doc-vs-code behavioral-drift review. Do **not** imply `deep` is comprehensive or
   reliable - name exactly what ships.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/reporting.py` | Modify - advisory banner for deep runs, in text and JSON |
| `src/docsentinel/engine.py` | Modify (if needed) - deep `notice` advisory wording (coordinate with Story 01.0 Task 01's `notice` branching; this may already be in place - extend, don't duplicate) |
| `docs/architecture/README.md` | Modify - narrow `deep` paragraph (coordinate with Story 02.0 Task 03's edit to the same paragraph - integrate, do not overwrite) |
| `tests/test_reporting.py` | Create or modify - banner/notice rendering tests |
| `tests/test_scan.py` | Modify - deep `notice` wording test |

## Symbols / fields

| Symbol | Change |
|--------|--------|
| `render(result, format)` | When `result.profile == "deep"` and `result.findings`, include the advisory banner line (text: prepended after the header lines; JSON: a derived field such as `"advisory"` added to the serialized object, derived in `render`, not stored on `ScanResult`). `fast`/`standard` rendering is unchanged. |
| deep `notice` (in `engine.scan`) | For a confirmed, ready, evaluated deep run, the advisory "N deep rule(s) evaluated (heuristic, advisory-only)" wording per Decision §2 - extending the Story 01.0 Task 01 branching, not adding a parallel one. |

## Tests

`tests/test_reporting.py`:
- `test_deep_run_with_findings_shows_advisory_banner_text` - a `ScanResult(profile="deep",
  findings=(<DS301>,))` rendered as text contains the advisory banner line.
- `test_deep_run_with_findings_advisory_in_json` - same result as JSON contains the advisory
  field/flag, parseable by `json.loads`.
- `test_fast_run_has_no_advisory_banner` - `profile="fast"` with findings → no advisory banner
  (regression: the banner is deep-only).
- `test_deep_run_without_findings_no_banner` - `profile="deep"`, empty findings → no banner (the
  banner is for present-but-advisory findings; a clean run relies on `notice`).

`tests/test_scan.py`:
- `test_deep_evaluated_notice_is_advisory` - confirmed, ready deep run → `notice` contains both
  "evaluated" and an advisory marker, and never "not implemented."

## Success criteria

- [ ] A `deep` run with findings renders an advisory banner in **both** text and JSON, so no consumer
      mistakes a candidate for a verdict or the `0` exit for a validated audit.
- [ ] The banner and advisory notice are **deep-only** - `fast`/`standard` rendering and notices are
      byte-identical to before (regression-tested).
- [ ] No new `pending` message is introduced here - the not-ran explanations remain Story 01.0/02.0's
      single source; this task only surfaces them.
- [ ] `ScanResult`'s frozen contract is **not** widened - the advisory string is derived in `render`.
      If a contributor finds a contract change genuinely necessary, this task's scope requires a
      cross-component migration note naming every `ScanResult` consumer (CLI, library `__init__`,
      pytest plugin, `reporting`) before proceeding - prefer the derive-in-`render` path.
- [ ] `docs/architecture/README.md`'s `deep` paragraph names exactly what ships (DS301, opt-in,
      heuristic, advisory, docs-reviewer-backed) without overclaiming, and integrates cleanly with
      Story 02.0 Task 03's edit to the same paragraph.

## Constraints

- Full type annotations; no bare `except:`.
- Prefer deriving the advisory string in `reporting.render` over any change to the frozen
  `ScanResult` dataclass - a contract change ripples to every consumer and must not be done casually.
- Keep the architecture paragraph short and factual - this is the "defined but narrow content"
  update, not a feature advertisement. Reliability claims about a heuristic detector are forbidden.
