# Task 04 — Tests for the shared collection, the facts templates and `extract-facts`

**Parent story:** [Story 05.0](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md)  
**Role:** Testing Expert  
**Depends on:** Tasks 01–03. The tests can be written first and stay red until the code lands.

## Goal

Pin the single-source rule (C11) at the unit and mock level, the offline guarantee, the template
context split and the CLI contract. The end-to-end equality against a recording fake backend is
owned by [Story 04.0 Task 02](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/02-integration-and-mock-tests.md),
because the fake backend is built in Story 04.0 Task 01.

## Inputs

- The story [acceptance criteria](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md#acceptance-criteria)
  and [test plan](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md#test-plan), and the
  acceptance criteria of Tasks 01–03.
- CLAUDE.md "Test layout": unit tests use inline strings, mock tests replace a resource,
  integration tests load `tests/assets/<rule>/<case>` through `asset_case`.
- `tests/log_helpers.problem_output`, the `tests/conftest.py` log and settings isolation.

## Steps

1. **Unit, `tests/unit/test_mining_salience.py` (extend).**
   - Every disposition is reachable.
   - `cluster_size` is correct for a three-member cluster.
   - Trace order is total and stable under shuffled input.
   - `select_salient` equals the `selected` projection for each existing case and for the
     generated corpus of at least 200 claims.
   - The signal fields equal `numeric_density`/`entity_density`/the clustering value.
2. **Unit, `tests/unit/test_fact_check_candidates.py` (extend).**
   - `DS302_POLICY` equals the `_W_*`/`_DEDUP_THRESHOLD` constants.
   - `select_candidates(..., policy=SelectionPolicy((0.2, 0.2, 0.6), 0.9))` passes those numbers to
     `trace_salience`.
   - An invalid policy raises `ValueError`.
   - `inspect.signature(collect_candidates)` has exactly `root`, `documents`, `config`.
   - `CandidateClaim` carries the signal fields.
3. **Unit, `tests/unit/test_facts_template_context.py`.** Each Task 02 loader acceptance criterion,
   with inline template mappings: the default context, `facts`, an unknown context, a cross-context
   variable, a missing sink, and `requires_extensions` on `facts`. Each existing packaged template
   reports `context == "report"`.
   **Amended 2026-11-24 (threat model, E2-E5).** Also cover:
   - E2: an open/parse spy shows that template listing (`--format` validation, `doctor`) opens no
     `report_templates_dir` file; a malformed directory file breaks only its own selection; the
     static packaged name-to-context table equals the loaded packaged templates.
   - E3: a claim `##[error]x` gives no `##[` in `facts-json` output, and `json.loads` round-trips to
     the same string.
   - E4: a cross-context variable refused at the text root, the json root and alias scope; an
     `ext.*` filter refused in `facts`; `render_template` with a mismatched model kind raises
     `TemplateError`; `FactsModel.build` with a bad disposition raises `ValueError`; a `facts` text
     template placing `text` without `neutralize` refused; a github-sink `facts` template obeys
     T2-R1.
   - E5: claims holding U+E0041 and U+2060 are flagged `hidden_characters` and marked in
     `facts-text`; a plain claim is not.
4. **Unit, `tests/unit/test_extract_facts_offline.py` (AST).**
   - The bodies of `engine.extract_facts`, `detectors.fact_check.trace_candidates`,
     `collect_candidates`, `select_candidates` and the `cli.py` `extract-facts` handler reference
     none of `external_api_requested`, `resolve_external_api_gate`, `load_backend`,
     `USE_EXTERNAL_API_ENV`, `os.environ`, `os.getenv`, `httpx` or `docsentinel.fact_check.lenz`.
   - `dataclasses.fields(Config)` has no field whose name contains `weight` or `dedup`.
   - `detectors/fact_check.py` has exactly one `extract_claims` call site.
   - **Amended 2026-11-24 (threat model, E1, E9).** The `httpx` name check above is the E1 AST
     part (no `httpx` reference in DocSentinel code on the path). `inspect.signature` of `scan`,
     `detect` and `collect_candidates` has no `policy`, `weights` or `dedup` parameter. Config
     cases for all four tiers (TOML, `[tool.doc_sentinel]`, `--config` JSON, user settings): each of
     `weights`, `dedup_threshold`, `fact_check_weights`, `fact_check_dedup_threshold`,
     `include_rejected` and `selection_policy` gives the unknown-option `ConfigError`.
5. **Mock, `tests/mock/test_fact_check_single_source.py`.**
   - Patch `trace_candidates` to return a fixed `CandidateTrace` and patch `_check_candidates` to
     record its `candidates` argument.
   - Run a gate-open `detect()` (env `1`, sentinel key, fake backend class in a copied registry)
     and assert the recorded tuple equals the trace's `selected`.
   - Call `extract_facts()` with the same patch and assert its `facts` texts equal the same
     tuple's texts.
   - This proves both consumers read the one function.
   - **Amended 2026-11-24 (threat model, E9).** After an in-process
     `extract_facts(weights=(0.2, 0.2, 0.6), dedup_threshold=0.5)`, `DS302_POLICY` and the `_W_*`
     constants are unchanged, and `collect_candidates(...)` equals its pre-call result.
6. **Mock, `tests/mock/test_extract_facts_engine.py`**, with `trace_candidates` stubbed so no spaCy
   model is needed. Cover:
   - each override and its effect on `matches_ds302` and `notice`;
   - weights and threshold;
   - `include_rejected`;
   - `include_rejected="yes"` raising `ConfigError`;
   - `deep_ready` patched false raising `RuntimeError` before the stub is called;
   - a single-file target, with selectors ignored and one WARNING;
   - a symlinked file target raising `ValueError`;
   - an empty invoker selection raising `ConfigError(EMPTY_SELECTION_MESSAGE)`;
   - a non-UTF-8 document counted in `documents_unreadable` and not passed to the stub;
   - `profile = "deep"`, `deep_confirm = false` and `select = ["DS1"]` in the config not changing
     the result.
   - **Amended 2026-11-24 (threat model, E6, E7, E8, E11, E12):**
     - E6: `weights` holding `nan` or `inf`, `dedup_threshold=nan`, and `max_total=0` each raise
       while a `load_pipeline` (and `deep_ready`) spy records no call;
     - E7: a stub raising `ValueError(<sentinel sentence>)` becomes
       `RuntimeError("extract-facts: claim extraction failed (ValueError)")` with `__cause__` and
       `__context__` both `None`, and no log record (message or `exc_info`) holds the sentinel;
       `ConfigError`, `OSError` and `UnicodeDecodeError` pass through unchanged;
     - E8: a claim with 10,000 entities (and one entity of 5,000 code points) yields at most 32
       items of at most 200 code points, while `text` is unchanged;
     - E11 (when the follow-up lands): a document swapped for a symlink after the partition step is
       not read through the link;
     - E12: the notice equals the exact engine constants for the matching and differing cases.
7. **Assets.** Reuse the Story 04.0 `tests/assets/ds302/` cases when they exist. Otherwise add
   `tests/assets/ds302/extract_facts_basic/` now. It holds two or three short, hand-written,
   clearly synthetic Markdown files with numeric and named-entity claims, one near-duplicate pair
   across files, and one trivial sentence. Story 04.0 Task 01 then adopts it. Copy no text from
   `examples/`.
8. **Integration, `tests/integration/test_extract_facts_cli_ds302.py`** (skip with a reason when
   `deep_ready()` is false). Cover:
   - every Task 03 acceptance criterion through `cli.main`;
   - `facts-json` parsed and checked for top-level keys, ASCII, `matches_ds302: true` by default,
     and the near-duplicate pair collapsed to one fact with `cluster.size == 2`;
   - `--all` listing the trivial sentence as `below_floor`;
   - a sentinel sentence absent from stderr and the log file (`problem_output`, plus reading the
     per-run log in `DOCSENTINEL_LOG_DIR`);
   - **Amended 2026-11-24 (threat model, E1; replaces the `"httpx" in sys.modules` assertion, which
     can never pass because spaCy imports `httpx`).** A fresh-interpreter subprocess (`python -I -c`
     wrapper) first patches `socket.socket.connect`, `socket.create_connection` and
     `socket.getaddrinfo` to record the call and raise, then calls `cli.main(["extract-facts",
     <asset>])`. Afterwards it prints the recorded calls and, for `docsentinel.fact_check.lenz` and
     every value of `FACT_CHECK_BACKEND_MODULES`, whether it is in `sys.modules`. The exit code must
     be `0`, the recorded list empty and every backend module absent. Do not assert on `httpx` and
     do not manipulate `sys.modules`;
   - **Amended 2026-11-24 (threat model, E7, E8, E10, E13):**
     - E13: the sentinel test also runs with `-v` (DEBUG, including the `trace_salience` stage
       counts) and checks the `config:` INFO line;
     - E7: a patched `extract_claims` raising `ValueError(<sentinel sentence>)` exits `2` with
       `Extraction failed: extract-facts: claim extraction failed (ValueError)` and no sentinel in
       stderr, the log file or any record;
     - E8: `--all` over a generated corpus succeeds; a forced render-cap overflow with `-o` exits `2`
       and leaves no file;
     - E10: a forced render failure with `-o` leaves no file; `--include ../x`, a `##[` selector
       value and `--exclude .` exit `2` exactly as for `scan`;
     - E2: the `doctor` output has the one name-only `templates (report_templates_dir):` line;
   - the environment set to `DOCSENTINEL_USE_EXTERNAL_API=1` and a sentinel
     `DOCSENTINEL_FACTCHECK_LENZ_API_KEY` giving byte-identical output and never leaking the
     sentinel.
9. **Regression.** The Story 04.0 embedded-key grep test also covers the new files. Nothing to add
   here beyond not containing the key.

## Deliverables

New: `tests/unit/test_facts_template_context.py`, `tests/unit/test_extract_facts_offline.py`,
`tests/mock/test_fact_check_single_source.py`, `tests/mock/test_extract_facts_engine.py`,
`tests/integration/test_extract_facts_cli_ds302.py`, and possibly
`tests/assets/ds302/extract_facts_basic/`. Extended: `tests/unit/test_mining_salience.py`,
`tests/unit/test_fact_check_candidates.py`.

## Acceptance criteria

- [ ] Every acceptance criterion of the story and of Tasks 01–03 is asserted.
- [ ] No test touches the network, loads the real Lenz backend or contains a real key.
- [ ] Unit and mock tests need no spaCy model. Integration tests skip cleanly without it.
- [ ] The tests are deterministic and independent of test order.

## Test expectations

- `uv run pytest tests/unit tests/mock tests/integration -q -k "extract_facts or facts_template or single_source or mining or fact_check_candidates" -p docsentinel.pytest_plugin`
  passes on Python 3.12 and 3.13. The deep integration cases skip on 3.13 when the model is absent.
- `uv run pytest -p docsentinel.pytest_plugin` (the full suite) passes.

## Out of scope

- The DS302-versus-`extract-facts` equality through a real gate-open `scan()` with the recording
  `FakeFactCheckClient` (Story 04.0 Task 02, step 10).
