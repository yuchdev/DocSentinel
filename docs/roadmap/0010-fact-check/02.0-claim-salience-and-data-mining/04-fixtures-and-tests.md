# Task 04: Unit tests for salience scoring, clustering, selection and the candidate wrapper

**Parent story:** [Story 02.0](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md)  
**Role:** Testing Expert  
**Depends on:** Tasks 01 to 03. The tests can be written first and stay red until the code lands.

> **Amended 2026-11-21 (mining layer).** Test files follow the new modules:
> `test_mining_salience.py`, `test_mining_clustering.py` and `test_fact_check_candidates.py`
> replace the planned `test_fact_check_salience_*.py` files.

## Goal

Pin the filter's behaviour with unit tests that use small inline `Claim` literals. The tests need no
spaCy model, no document assets and no network. `Claim` lives in `mining/claims.py`, which imports
`spacy` as a library (always installed), but these tests never load a model.

## Inputs

- The story's [acceptance criteria](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md#acceptance-criteria)
  and [test plan](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md#test-plan).
- The acceptance criteria of Tasks 01, 02 and 03.
- Contract [C9](/docs/roadmap/0010-fact-check/plan.md#c9--layering-mining-detectors-fact-check-backends)
  and `tests/unit/test_mining_layering.py`.

## Steps

1. Add one small helper in each test module, or a shared private helper next to the tests, that
   builds a `Claim` with defaults. Write every sentence by hand for this milestone. Keep them short
   and obviously synthetic. Do not copy any text from `examples/`.
2. In `tests/unit/test_mining_salience.py`, test:
   - the token count;
   - each density, including the `min(1.0, ...)` saturation;
   - `SalienceWeights` validation (negative, `bool`, non-finite, sum other than `1.0`);
   - `combined_score` monotonicity, rounding, and that a signal outside `[0, 1]` raises
     `ValueError`;
   - `select_salient`: the empty corpus, the inclusive floor, the representative tie-break, the
     per-document cap applied before the total cap, the exact output order for a fixed input,
     shuffled and reversed input giving identical output, out-of-range numbers raising
     `ValueError`, and a generated corpus of at least 200 claims that never exceeds either cap.
     Patch `clustering.cluster_near_duplicates` where a test needs exact cluster ids or
     distinctiveness values.
3. In `tests/unit/test_mining_clustering.py`, test:
   - linking above the threshold and no link at exactly 0.92. Patch the similarity computation
     where literal sentences cannot reach an exact value;
   - transitive linking;
   - corpus-wide scope (identical sentences link regardless of where they came from);
   - index alignment with the input;
   - the empty input, the single-text case and the empty-vocabulary case;
   - out-of-range `threshold` and `chunk_rows` raising `ValueError`;
   - chunked computation, with `chunk_rows=2`;
   - the vectorizer pin: `mining.corpus.create_vectorizer()` keeps the parameters `DS202`/`DS203`
     were calibrated with (`stop_words="english"`, the word token pattern, `sublinear_tf=True`),
     so a factory change that would also move `DS302`'s `0.92` cut-off fails loudly.
4. In `tests/unit/test_fact_check_candidates.py` (the detector-side wrapper), test:
   - `select_candidates((), Config())` returns `()`;
   - an injected `Config` with an out-of-range cap or floor raises `ConfigError` and `select_salient`
     is not called;
   - the weight-constant (`_W_NUMERIC`/`_W_ENTITY`/`_W_DISTINCT`) constraints (a) to (d) from
     Task 01, and `_DEDUP_THRESHOLD == 0.92`;
   - importing `docsentinel.detectors.fact_check` does not import `docsentinel.mining.salience`,
     `docsentinel.mining.clustering` or `sklearn` (fresh interpreter);
   - the 1,000-code-point text bound and whitespace stripping;
   - order preservation: with `select_salient` patched to return a fixed sequence, the wrapper
     returns the same claims in the same order;
   - the numbers passed to `select_salient` are exactly the `Config` values and the constants.
5. **Layering and banned imports.**
   - `tests/unit/test_mining_layering.py` must stay green with `mining/salience.py` and
     `mining/clustering.py` present. Do not weaken it. If it does not already allow
     `docsentinel.mining.*` imports between mining modules (`salience` -> `clustering` -> `corpus`,
     `salience` -> `claims` under `TYPE_CHECKING`), report that to the owner rather than editing
     the allow-list silently.
   - In `test_mining_salience.py`, add one `ast`-based check over both new mining modules: no
     `httpx` import, no `docsentinel.fact_check` import, no reference to `os.environ`, and no
     parameter annotated `Config`.

## Deliverables

New: `tests/unit/test_mining_salience.py`, `tests/unit/test_mining_clustering.py`,
`tests/unit/test_fact_check_candidates.py`.

## Acceptance criteria

- [ ] Every acceptance criterion in the story and in Tasks 01 to 03 is covered by an assertion.
- [ ] `tests/unit/test_mining_layering.py` is green with the new modules in place.
- [ ] No test loads assets, loads a spaCy model, reads the environment or touches the network.
- [ ] The tests are deterministic: they pass in every run and do not depend on test order or on
      shared state between tests.

## Test expectations

- `uv run pytest tests/unit -q -k "mining or fact_check_candidates" -p docsentinel.pytest_plugin`
  passes on Python 3.12 and 3.13. The filter needs only scikit-learn, so these tests do not depend
  on `mining.nlp.deep_ready()`.
- `uv run pytest -p docsentinel.pytest_plugin` (the full suite) passes.

## Out of scope

- End-to-end salience through `scan()`. Story 04.0 covers it in the assets
  `salience_filter_drops_trivial_claim` and `corpus_dedup_collapses_repeated_claim`.
