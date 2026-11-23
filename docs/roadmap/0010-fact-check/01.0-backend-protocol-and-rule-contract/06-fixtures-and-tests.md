# Task 06 — Tests for gate resolution, config validation, the Protocol and engine dispatch

**Parent story:** [Story 01.0](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md)  
**Role:** Testing Expert  
**Depends on:** Tasks 03 to 05 for the tests to pass. Unit tests can be written first and stay red
until the code lands. The Task 02 threat model is a standing input.

> **Amended 2026-11-23 (threat model).** Applies
> [threat model 0010 fact-check gating](/docs/security/threat-model-0010-fact-check-gating-2026-11-23.md)
> amendment A1 and the test side of mitigations M1 to M12 (its mitigation-to-test map is
> normative). Changed: step 1 (the fixture also clears `LENZ_API_KEY`, M12), steps 4 and 5 (extra
> cases), three new unit files (`test_fact_check_repo_hygiene.py`, `test_fact_check_env_reads.py`,
> `test_fact_check_env_isolation.py`), the deliverables and the acceptance criteria.

## Goal

Pin the story's contract with tests: the gate, the config surface, the Protocol and registry, the
engine forwarding and the D5 surfacing. No test reaches a network, a real API key or the real Lenz
backend.

## Inputs

- The story's [test plan](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#test-plan)
  and [acceptance criteria](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#acceptance-criteria),
  plus the acceptance criteria of Tasks 03, 04 and 05.
- The Task 02 threat model. Each mitigation needs exactly one named test.
- `/tests/conftest.py` (environment isolation, the `asset_case` fixture), `/tests/assets/README.md`,
  `/tests/log_helpers.py`, and the existing spaCy lazy-import tests (reuse their fresh-interpreter
  pattern).

## Steps

1. **Environment isolation.** In `/tests/conftest.py`, add an autouse fixture that removes
   `DOCSENTINEL_USE_EXTERNAL_API` and every environment variable whose name starts with
   `DOCSENTINEL_FACTCHECK_` for every test, the same way `DOCSENTINEL_SETTINGS` is handled. This
   stops a developer's real key from reaching any test. *Amended 2026-11-23 (threat model, M12):*
   the fixture also removes `LENZ_API_KEY` (defence in depth against accidental example-code
   imports). Tests only ever set the sentinel `sentinel-not-a-real-key-0010`, and only through
   `monkeypatch`.
2. **Shared fake.** Create `/tests/fact_check_fakes.py`. It sits at the tests root so that both the
   mock and the integration suites can import it, and `src/` must never import it. It provides
   `make_fake_backend(verdicts, *, fail_on=frozenset()) -> type`:
   - It returns a class with `name = "fake"`,
     `API_KEY_ENV_VAR = "DOCSENTINEL_FACTCHECK_FAKE_API_KEY"`, and a constructor that accepts
     `api_key`.
   - `check_claim` records each claim in a class-level `calls` list. It raises `FactCheckError` for
     any claim in `fail_on`, returns `verdicts[claim]` when present, and otherwise returns
     `unverifiable`.
   - It provides a fixture, `register_fake_backend(monkeypatch, cls)`, that patches
     `FACT_CHECK_BACKENDS` for one test only.

   Story 04.0 Task 01 extends this module and must not fork it. The sentinel key is
   `"sentinel-not-a-real-key-0010"`. It must not resemble any real provider key.
3. **Asset case.** Create `/tests/assets/ds302/gate_off_no_flag/`: two short, hand-written Markdown
   documents, each with one sentence that contains a number and a named entity. Write the text
   yourself. Do not copy it from `examples/`.
4. **Unit tests** (inline strings only, no assets):
   - `test_fact_check_gate_resolution.py`:
     - `external_api_requested` accepts exactly `"1"`. It rejects `"true"`, `"yes"`, `" 1"`, `"1\n"`,
       `"01"` and an empty value.
     - *Amended 2026-11-23 (threat model, M2):* the parametrised rejected list also holds
       `"TRUE"`, `"1 "`, `"1\r"`, `"0"` and a full-width digit one; an AST assertion shows the
       helper does not reference `_env_confirms`.
     - The flag/keyword OR env truth table.
     - The order and text of `reasons()`.
     - `skip_message()`.
     - `key_present` for an unset, empty and non-empty variable.
     - An injected `Config` with an unknown backend raises `ConfigError`.
     - *Amended 2026-11-23 (threat model, M1):* an injected `Config` carrying
       `use_external_api=True` through `object.__setattr__`, and a `Config` subclass with a
       `use_external_api` property, both give `requested is False`.
     - *Amended 2026-11-23 (threat model, M3):* `external_api_requested("false")` (and `1`, `0`,
       `None`) raises `ConfigError`, and `resolve_external_api_gate` returns a `requested` that is
       a real `bool`; a direct `detect(..., use_external_api="false")` with the fake key set raises
       and the fake backend records no call.
     - *Amended 2026-11-23 (threat model, M7):* an injected `Config(fact_check_backend="lenz\n")`
       raises `ConfigError`, not `ValueError`.
   - `test_fact_check_config.py`:
     - The defaults.
     - Each key from standalone TOML, `[tool.doc_sentinel]`, JSON and user settings.
     - Every invalid case from the Task 03 acceptance criteria, with its exact message, including
       the `fact_check_time_budget_seconds` cases (`0`, `3601`, `True`, `300.0`).
     - `use_external_api` in each file kind raises the unknown-option error.
     - *Amended 2026-11-23 (threat model, M1):* the same for the FC-1 near-miss spellings
       (`use-external-api`, `useExternalApi`, `use_external_apis`, `external_api`,
       `fact_check_enabled`, a nested `[tool.doc_sentinel.fact_check]` table, a key with a
       trailing space), and `fact_check_lenz_api_key` set to the sentinel gives an unknown-option
       `ConfigError` whose message does not contain the sentinel.
     - `Config` has no `use_external_api` attribute.
     - The refused-key set is unchanged.
     - `config.FACT_CHECK_BACKEND_NAMES == set(FACT_CHECK_BACKEND_MODULES)`.
   - `test_fact_check_protocol.py`:
     - The structural `isinstance` cases.
     - The `FactCheckResult` validation cases.
     - `expected_api_key_env_var`.
     - The `load_backend` cases from Task 04: pre-registered, unknown, a C3 mismatch, and that only
       mapped modules are imported (with `importlib.import_module` patched).
     - *Amended 2026-11-23 (threat model, M7):* `"lenz\n"`, `"Lenz"`, `"lenz "`, a full-width
       letter, 33 characters, `"../x"` and `"docsentinel.fact_check.lenz"` are refused;
       `importlib.import_module` is never called with an unmapped name;
       `FactCheckResult(backend="lenz\n", ...)` raises `FactCheckError`.
   - `test_fact_check_layering.py` (plan contract C9, modelled on
     `tests/unit/test_mining_layering.py`): parse every module under `src/docsentinel/fact_check/`
     with `ast` and assert that it imports only the standard library, `docsentinel.log`, other
     `docsentinel.fact_check.*` modules and, in `lenz.py` only, `httpx`; that none imports `docsentinel.config`, `rules`, `detectors`,
     `engine`, `cli`, `reporting`, `telemetry`, `baseline`, `discovery` or `mining`; and that
     `fact_check/__init__.py` has no import statement. Until Story 03.0 lands, the test covers
     `__init__.py` and `protocol.py` only, and it picks up `lenz.py` automatically when it appears.
   - *Amended 2026-11-23 (threat model, A1).* Three new unit files:
     - `test_fact_check_env_reads.py` (M8; replaces the step 5 "AST or grep test"): parse every
       module under `src/docsentinel/` and assert that (a) only `detectors/fact_check.py` reads
       `DOCSENTINEL_USE_EXTERNAL_API` or a `DOCSENTINEL_FACTCHECK_*` variable (so `cli.py`,
       `config.py` and `engine.py` read neither), (b) no module contains a standalone
       `LENZ_API_KEY`, matched as `(?<![A-Za-z0-9_])LENZ_API_KEY` (the C3 name
       `DOCSENTINEL_FACTCHECK_LENZ_API_KEY` contains it as a substring and is allowed; amended
       2026-11-23 at Task 04), and (c) no module under `src/docsentinel/fact_check/` reads `os.environ` or
       calls `os.getenv`.
     - `test_fact_check_repo_hygiene.py` (M4, M12): `/.pre-commit-hooks.yaml` contains no
       `--use-external-api`, and no file under `/.github/workflows/` contains
       `--use-external-api`, `DOCSENTINEL_USE_EXTERNAL_API` or `DOCSENTINEL_FACTCHECK_`.
     - `test_fact_check_env_isolation.py` (M12): run a child
       `pytest -p docsentinel.pytest_plugin` on one inline test with `DOCSENTINEL_USE_EXTERNAL_API`,
       `DOCSENTINEL_FACTCHECK_FAKE_API_KEY` (sentinel value) and `LENZ_API_KEY` (sentinel value)
       set in the parent environment, and assert the child test sees none of them. This proves
       the autouse fixture runs.
5. **Mock tests:**
   - `test_fact_check_engine_dispatch.py`:
     - A spy analyzer that declares `use_external_api` receives it. One that does not declare it is
       called exactly as before.
     - No gate resolution happens when `DS302` is not selected.
     - With the gate closed, `pending` holds exactly one entry and exactly one WARNING is logged.
     - Q1: with `DS301` and `DS302` active and the gate closed, `rules_evaluated == 1`, `opt_in_off`
       is empty and `notice` is `1 deep rule(s) evaluated (heuristic, advisory-only).`; with the gate
       open, `rules_evaluated == 2`. With `DS302` dropped by `ignore`, `notice`, `pending` and
       `rules_evaluated` equal the master values.
     - Q2: the finding `message` contains no confidence; `value` is
       `<verdict> (confidence <0.00>): <exact text sent>`; two runs whose fake returns the same
       verdict with different confidence give equal `baseline` fingerprints.
     - Q3: with an injected `clock` that passes the deadline after N calls, exactly N claims are
       sent, exactly one budget WARNING with counts only is logged, and the findings of the sent
       claims are kept. No real sleep.
     - Q4: a fake whose `check_claim` raises `FactCheckError` for an unrecognised verdict (and a fake
       that tries to build `FactCheckResult` with an out-of-vocabulary verdict) gives one WARNING
       and no finding for that claim; no finding ever has verdict `mixed` from such a claim.
     - With the gate open, the fake backend and an injected `select_candidates` are used, findings
       follow the Task 05 contract, and `close()` is called.
     - A `FactCheckError` from one candidate is skipped.
     - `scan(use_external_api="1")` raises `ConfigError`.
     - An unavailable backend (an `ImportError` raised from a patched `load_backend`) gives one
       WARNING and zero findings.
     - The spaCy pipeline (`mining.nlp.load_pipeline`) and `mining.claims.extract_claims` are
       patched, so no model is needed.
     - *Amended 2026-11-23 (threat model):*
       - M3: `scan(use_external_api=...)` with `"false"`, `"1"`, `1`, `0` and `None` raises
         `ConfigError` before discovery (a discovery spy is not called).
       - M8: with only `LENZ_API_KEY` set to the sentinel and the flag given, the gate is closed,
         the reason is `set DOCSENTINEL_FACTCHECK_FAKE_API_KEY`, and the fake records no call.
       - M9: with the gate closed, spies on `mining.nlp.load_pipeline`,
         `collect_candidates`/`select_candidates`, `load_backend` and the fake constructor are
         not called.
       - M10: gate open gives exactly one INFO record in the Task 05 step 5 format, with integer
         args plus the backend name; it is also emitted, with the counts so far, when the M5
         `RuntimeError` propagates mid-loop; a closed gate gives none; the record text contains no
         path and no claim text.
       - M11: a fake result whose `citations` hold a marker string; the marker is absent from
         findings, log records and every packaged template's output.
   - `test_fact_check_no_key_logged.py`:
     - Set the sentinel key and capture every log record at DEBUG through a `docsentinel` root
       handler, across the gate-open, gate-closed, failure and unavailable paths.
     - Assert that the sentinel never appears in any record message, its args, `exc_text`, any
       `Finding` field, `ScanResult`, `pending`, the `repr` of the fake client, or the
       `doctor`/`rules` output.
     - *Amended 2026-11-23 (threat model, A1/M5, HIGH FC-5):* add fakes that (a) raise
       `FactCheckError` from `__init__`, (b) raise `ValueError` whose message contains the
       sentinel from `__init__`, (c) raise a plain `Exception` whose message contains
       `Bearer <sentinel>` from `check_claim` (the `h11` shape), and (d) succeed. Run each case
       through `cli.main` with `DOCSENTINEL_LOG_DIR` set to a temporary directory, and assert that
       neither the sentinel nor its first eight characters appear in stdout, stderr, the per-run
       log file (including tracebacks), any `LogRecord` (`msg`, `args`, `exc_text`),
       `ScanResult`, `pending`, any `Finding` field, every packaged template's rendered report,
       the client `repr`, or the `doctor` and `rules` output. For (b) and (c), the re-raised
       `RuntimeError` has `__cause__ is None` and `__context__ is None`.
   - A fresh-interpreter check (subprocess, `python -I`): after `import docsentinel`, after a fast
     scan and a standard scan, and after `docsentinel doctor` and `docsentinel rules`, `"httpx"` is
     not in `sys.modules`. *Amended 2026-11-23 (threat model, M9):* also a confirmed deep scan with
     `select = ["DS302"]` and the gate closed leaves `httpx`, `docsentinel.fact_check.lenz`,
     `docsentinel.mining.claims`, `docsentinel.mining.salience` and `docsentinel.mining.clustering`
     out of `sys.modules` (`select` excludes `DS301`, which loads `mining.claims` itself).
   - The env-read AST test is `tests/unit/test_fact_check_env_reads.py` (step 4, amended
     2026-11-23, threat model M8).
6. **Integration test.** `tests/integration/test_fact_check_gate_off_ds302.py` loads `gate_off_no_flag`
   through `asset_case`.

   This file name replaces the README's `test_ds302_gate_off_ds101.py`. The rule-ID suffix must name
   the asset rule, which is `ds302`.

   It checks the following:
   - A confirmed deep `scan()` with no flag and no key reports zero `DS302` findings, logs one
     WARNING and adds one `pending` entry.
   - The same result holds with the key set but no flag, and with the flag set but no key. In those
     cases the reason lists only the missing item.
   - `docsentinel scan --profile deep --i-understand-deep-is-heuristic` exits `0`.
   - The `rules` line and the `doctor` line match the Task 03 text exactly.
   - *Amended 2026-11-23 (threat model, M6):* exact-string equality of the WARNING, the `pending`
     entry and the `doctor` line for: neither, key only, flag only; and in the config-error state
     the `doctor` line is exactly `fact-check gate: unknown (configuration error)`, with the
     repository's offending key name in no `fact-check gate:` line.

   Skip the deep cases with a clear reason when `mining.nlp.deep_ready()` is false, as the
   existing `DS301` tests do. This applies on Python 3.13, where textacy is not installed.

## Deliverables

New files:
- `tests/unit/test_fact_check_gate_resolution.py`
- `tests/unit/test_fact_check_config.py`
- `tests/unit/test_fact_check_protocol.py`
- `tests/unit/test_fact_check_layering.py`
- `tests/unit/test_fact_check_env_reads.py` (amended 2026-11-23, threat model M8)
- `tests/unit/test_fact_check_repo_hygiene.py` (amended 2026-11-23, threat model M4)
- `tests/unit/test_fact_check_env_isolation.py` (amended 2026-11-23, threat model M12)
- `tests/mock/test_fact_check_engine_dispatch.py`
- `tests/mock/test_fact_check_no_key_logged.py`
- `tests/integration/test_fact_check_gate_off_ds302.py`
- `tests/fact_check_fakes.py`
- `tests/assets/ds302/gate_off_no_flag/`

Updated: `tests/conftest.py`.

## Acceptance criteria

- [ ] Every item in the story's test plan and every Task 02 mitigation has a named test.
      *Amended 2026-11-23 (threat model):* each of M1 to M12 is covered in the file the threat
      model's mitigation-to-test map names, and the M5 sentinel test is neither missing nor
      skipped (a merge-gate condition).
- [ ] *Amended 2026-11-23 (threat model, M12):* the autouse fixture clears
      `DOCSENTINEL_USE_EXTERNAL_API`, every `DOCSENTINEL_FACTCHECK_*` variable and `LENZ_API_KEY`,
      and `test_fact_check_env_isolation.py` proves it.
- [ ] No unit test loads assets. The integration file that loads assets carries the `_ds302` suffix.
- [ ] No test creates a real `httpx` transport, sends a request, reads a real key, or imports or runs
      anything from `examples/`.
- [ ] No test file contains the API key from `examples/docs/lenz_fact-checking.md` or any prefix of
      it.

## Test expectations

- `uv run pytest tests/unit tests/mock tests/integration -q -k fact_check -p docsentinel.pytest_plugin`
  is green.
- `uv run pytest -p docsentinel.pytest_plugin` (the full suite) is green on Python 3.12 and 3.13,
  with the deep cases skipped on 3.13.
- `uv run docsentinel scan . --format json` exits `0` with zero `DS302` findings.

## Out of scope

- Salience tests (Story 02.0 Task 04).
- Lenz transport tests (Story 03.0 Task 04).
- The full end-to-end verdict matrix (Story 04.0 Task 02).
