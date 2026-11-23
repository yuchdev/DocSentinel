# Task 02 — End-to-end DS302 tests, the per-claim failure path, and the embedded-key regression check

**Parent story:** [Story 04.0](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/README.md)  
**Role:** Testing Expert  
**Depends on:** [Task 01](./01-fixtures-and-fake-backend.md) and, for step 10,
[Story 05.0](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md).

## Goal

Run `DS302` end to end through `scan()` and the CLI against the fake backend. Cover every gate
combination, both reportable verdicts, the clean verdict, the per-claim failure path, and the
salience behaviour at corpus level. Add the regression check that runs across the whole milestone:
the embedded example key never appears outside its own file, and no test reaches the real endpoint.

## Inputs

- Story README [acceptance criteria](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/README.md#acceptance-criteria)
  and [test plan](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/README.md#test-plan).
- The finding contract in [Story 01.0 Task 05](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/05-ds302-registration-and-engine-dispatch.md).
- Plan [exit gates](/docs/roadmap/0010-fact-check/plan.md#exit-gates) 1, 2, 6 and 8.
- The session network guard in `/tests/conftest.py` (Story 03.0 Task 04).

## Steps

1. **File names.** Integration files that load assets carry the rule IDs as a suffix (CLAUDE.md
   test layout). The README names are corrected to that convention:

   | README name | File to create |
   |---|---|
   | `test_ds302_full_scan_clean_verdict_ds301.py` | `tests/integration/test_fact_check_clean_verdict_ds301_ds302.py` |
   | `test_ds302_full_scan_false_verdict_reports.py` | `tests/integration/test_fact_check_reportable_verdict_ds302.py` |
   | `test_ds302_gate_variations_ds301.py` | `tests/integration/test_fact_check_gate_variations_ds301_ds302.py` |
   | `test_ds302_per_claim_network_error_skipped.py` | `tests/mock/test_fact_check_per_claim_error_skipped.py` |
   | `test_no_lenz_example_key_leaked.py` | `tests/integration/test_no_lenz_example_key_leaked.py` (repository check, loads no assets) |
   | `test_fact_check_extract_facts_equivalence_ds302.py` | `tests/integration/test_fact_check_extract_facts_equivalence_ds302.py` (step 10, Story 05.0) |

2. **Clean verdict.** With both gates on and the fake returning `true`, `DS302` reports zero findings.
   `DS301` findings match a scan with `select = ["DS301"]` exactly. `pending` is empty.
3. **Reportable verdicts.** With `false` or `mixed` and confidence at or above
   `fact_check_min_confidence`, there is one finding per candidate. Check each field: `rule`, `path`,
   `severity="warning"`, `type="unverified claim"`, `value` equal to
   `<verdict> (confidence <0.00>): <exact text sent>` (compare the suffix with the fake's `calls`),
   the message format with a 200-code-point snippet and **no** confidence (owner ruling Q2), and the
   order `(path, message)`. A second scan whose fake returns the same verdict with a different
   confidence gives the same baseline fingerprints. Two more cases: confidence just below the floor gives no finding, and a
   `false` verdict at confidence exactly equal to the floor gives one finding. The CLI exits `0`
   (advisory). `--format json` and `--format text` both render the finding.
4. **Gate variations.** Test each of the following:
   - `deep_confirm` off: `DS301` and `DS302` are both skipped, and the existing deep-wide `pending`
     is byte-identical to master.
   - Confirmed, no flag: `DS302` skips with one WARNING and one `pending` entry, `DS301` runs, and
     `notice` counts only `DS301` (owner ruling Q1).
   - Confirmed, flag set, no key: the same skip, and the reason lists only the key.
   - Confirmed, env `1`, key set: `DS302` runs.
   - Each of the above through `scan()` and through the CLI (`--use-external-api`), where it applies.
   - `DS302` removed with `ignore = ["DS302"]`: no WARNING and no `pending` entry.
5. **Per-claim failure (mock).** One candidate in `fail_on` makes the scan complete. Every other
   candidate is still sent, as recorded in `calls`. One WARNING names the document path, and no log
   record contains the claim text. Exit code is `0`. Add two cases in the same file:
   - Unrecognised verdict (owner ruling Q4): the fake raises `FactCheckError` for one claim as a
     backend does for an unknown verdict; that claim gives one WARNING and no finding, never a
     `mixed` finding.
   - Time budget (owner ruling Q3): with `fact_check_time_budget_seconds = 1` and a patched clock
     that passes the deadline after the first call, exactly one claim is in `calls`, one budget
     WARNING with counts only is logged, and exit code is `0`. No real sleep.
6. **Salience end to end.** The `salience_filter_drops_trivial_claim` case: the trivial claim never
   appears in `calls`. The `corpus_dedup_collapses_repeated_claim` case: a sentence repeated in three
   documents is sent once. The cap cases: `fact_check_max_claims_total = 1` sends exactly one claim.
7. **Embedded-key regression test.** The test must not itself contain the key or any prefix of it.
   - Find the needle at runtime: open `examples/docs/lenz_fact-checking.md`, locate the key-shaped
     token by its documented context (for example, the value after `Bearer` or after the key's
     variable assignment), and keep it only in memory.
   - If the example file is missing, skip with a reason. If the file exists but no key-shaped token
     is found, fail. A missing needle must not make the test pass vacuously.
   - Walk every repository file except `.git`, `.venv`, `dist`, `build`, `reports`, `.idea` and that
     example file itself, and fail on any match.
   - The failure message names only the path and line number, never the token.
   - In the same file, assert that no file under `tests/` or `src/` contains the host string `lenz.io`
     outside `src/docsentinel/fact_check/lenz.py` and the Story 03.0 transport tests, which
     check the URL.
8. **No real network, session-wide.** Run the full suite with the Story 03.0 guard active. Add one
   assertion here that the guard fixture is active, so that removing it fails a test.
9. **Self-scan checks**, run locally and recorded in the PR description:
   - `uv run docsentinel scan . --format json` exits `0` with zero `DS302` findings.
   - `uv run docsentinel scan . --profile deep --i-understand-deep-is-heuristic --format json` exits
     `0`, has zero `DS302` findings, and its `pending` holds the `DS302 skipped:` entry.

10. **`extract-facts` equals the DS302 send set (plan contract C11, Story 05.0).** For each asset
    case where `DS302` sends at least one claim, and for `extract_facts_basic`:
    - Run a gate-open `scan()` with the recording `FakeFactCheckClient` and collect `calls`.
    - Run `extract_facts(root)` with the same root, config and include/exclude, and assert
      `[f.text for f in result.facts] == calls` (order included) and `result.matches_ds302`.
    - Repeat through the CLI with `extract-facts <root> --format facts-json` and compare
      `facts[].text`.
    - Lower `fact_check_max_claims_total` in the project config and assert that both sides shrink
      together and stay equal.
    - Pass `--max-total 1` only to `extract-facts`, and assert that its output is a prefix of
      `calls` and `matches_ds302` is `false`.
    - Pass `--weights 0.2,0.2,0.6` only to `extract-facts`, and assert that `matches_ds302` is
      `false` while the DS302 `calls` are unchanged.
    - Run `extract-facts` with `DOCSENTINEL_USE_EXTERNAL_API=1` and the fake key set, and assert
      that the fake records **no** call and the output is identical.

Skip the deep cases with a reason when `deep_ready()` is false (Python 3.13), as the `DS301` tests do.

## Deliverables

The six test files from step 1.

## Acceptance criteria

- [ ] Every case in the story test plan and every asset case from Task 01 is asserted.
- [ ] The full suite runs green with zero real network requests. The guard is proven active.
- [ ] The regression test finds its needle at runtime, fails if no needle is found, and passes on the
      current tree.
- [ ] No new test file contains the example key, a prefix of it, or text copied from `examples/`.
- [ ] Both self-scans meet the step 9 expectations.

## Test expectations

- `uv run pytest tests/integration tests/mock -q -k "fact_check or lenz_example" -p docsentinel.pytest_plugin`
  passes.
- `uv run --locked pytest -p docsentinel.pytest_plugin` (the full suite) passes on Python 3.12 and
  3.13 (plan exit gate 1).

## Out of scope

- Unit-level salience and transport cases, which Stories 02.0 and 03.0 already cover.
- Any run against the real `lenz.io` endpoint.
