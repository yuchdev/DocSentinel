# Task 01: DS302 asset cases and the fake backend

**Parent story:** [Story 04.0](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/README.md)  
**Role:** Testing Expert  
**Depends on:** the code from Stories 01.0, 02.0 and 03.0 is merged. This task extends
`/tests/fact_check_fakes.py` and `/tests/assets/ds302/` from Story 01.0 Task 06.

## Goal

Build the test data that Task 02's end-to-end tests run `DS302` against through `scan()`. The data
consists of one asset folder per case and a deterministic fake backend registered only inside the
test suite. Every test uses the fake. No test uses the real `lenz` entry.

## Inputs

- Story README [fixture and fake-backend shape](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/README.md#fixture-and-fake-backend-shape)
  and its list of asset cases.
- `/tests/fact_check_fakes.py`: `make_fake_backend` and `register_fake_backend` from Story 01.0
  Task 06. Extend this module; do not fork it.
- `/tests/assets/README.md` and the `asset_case` fixture in `/tests/conftest.py`.
- Plan [exit gate 8](/docs/roadmap/0010-fact-check/plan.md#exit-gates).

## Steps

1. Extend the fake module:
   - Add `fake_deep_config(**overrides) -> Config`, built as `dataclasses.replace(Config(), profile="deep", deep_confirm=True, fact_check_backend="fake", ...)`.
   - Add a `fact_check_env(monkeypatch, *, flag: bool, key: bool)` helper that sets
     `DOCSENTINEL_USE_EXTERNAL_API=1` and the sentinel `DOCSENTINEL_FACTCHECK_FAKE_API_KEY`.
   - Expose the class-level `calls` record so a test can assert exactly which texts were "sent" and
     how many.

   The fake is registered through `monkeypatch` on `FACT_CHECK_BACKENDS` for one test only. It is
   never registered at import time, and `src/` never imports this module.
2. Create one asset folder per case under `/tests/assets/ds302/`:
   - `gate_off_no_flag` (already exists)
   - `gate_off_no_key`
   - `both_gates_on_clean_verdict`
   - `both_gates_on_false_verdict_reports`
   - `both_gates_on_mixed_verdict_reports`
   - `per_claim_network_error_skipped`
   - `salience_filter_drops_trivial_claim`
   - `corpus_dedup_collapses_repeated_claim`
   - `deep_confirm_off_skips_everything_including_ds302`

   Each folder is a small tree of real Markdown. Keep paragraphs to one sentence so the fake's
   verdict keys can match the extracted `raw_sentence` reliably. Write every sentence by hand for
   this milestone: short, clearly synthetic, with a number or a named entity where the case needs
   one. Copy nothing from `examples/check_fact.py` `CLAIMS_DB` or from
   `examples/docs/lenz_fact-checking.md`.
3. If a case needs specific verdicts, put a `verdicts.json` file next to its documents. It maps the
   exact candidate text to `{verdict, confidence}`, and `fail_on` lists the texts for which the fake
   raises `FactCheckError`. These files are named so discovery ignores them, because they are not
   `.md`.
4. The repository's `docsentinel.toml` already excludes `tests/assets/*` from the self-scan, so do
   not add a new exclude pattern. Run the self-scan to confirm.
5. Document the cases in `/tests/assets/README.md` if that file lists cases per rule.

## Deliverables

- `/tests/fact_check_fakes.py` (extended)
- `/tests/assets/ds302/<case>/` for each of the nine cases
- `/tests/assets/README.md`, if it lists cases per rule

## Acceptance criteria

- [ ] All nine case folders exist, and each one is used by at least one Task 02 test.
- [ ] `FACT_CHECK_BACKENDS` has no `"fake"` entry outside a test's `monkeypatch` scope. A guard test
      asserts that a fresh `import docsentinel` yields only `{}`, or only `{"lenz"}` once
      `load_backend` has run.
- [ ] No asset or helper contains the example key or any prefix of it. No asset contains claim text
      copied from `examples/`.
- [ ] The self-scan `uv run docsentinel scan . --format json` still exits `0`.

## Test expectations

The tests that use this data are written in [Task 02](./02-integration-and-mock-tests.md).

## Out of scope

- Fixtures for a second backend.
- Changes to the fixtures of `DS301`.
