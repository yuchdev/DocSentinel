# Task 01 — Salience scoring: numeric density, entity density, combined score

**Parent story:** [Story 02.0](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md)  
**Role:** Python Expert  
**Depends on:** Story 01.0 (config keys and `fact_check.py`) and the move of `_triples.py` to
`mining/claims.py` (landing in parallel, 2026-11-21). Task 02 supplies the third signal,
distinctiveness. This task fixes the formula that combines the signals.

> **Amended 2026-11-21 (mining layer).** The module is `mining/salience.py`, not
> `detectors/fact_check_salience.py`. The weights are an explicit `SalienceWeights` parameter; the
> fixed values live in `detectors/fact_check.py` (story decision T8).

## Goal

Create `src/docsentinel/mining/salience.py` and the per-claim scoring functions. Each score is a
deterministic, pure function of a `DS301` `Claim` plus the corpus distinctiveness signal and
explicit weights. No NLP is run again, and no `Config` is read.

## Inputs

- Story README [decisions T1, T3, T6 and T8](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md#decisions)
  and the [data contracts](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md#data-contracts).
- Contracts [C7](/docs/roadmap/0010-fact-check/plan.md#c7--extraction-reuse-no-second-nlp-pipeline)
  and [C9](/docs/roadmap/0010-fact-check/plan.md#c9--layering-mining-detectors-fact-check-backends),
  and design principle 3 in the [plan](/docs/roadmap/0010-fact-check/plan.md#design-principles).
- `Claim` in `/src/docsentinel/mining/claims.py`. Its fields are `raw_object`, `object_numbers`,
  `object_entities`, `raw_sentence`, `path` and `paragraph_index`.
- `tests/unit/test_mining_layering.py`, which this module must keep green.

## Steps

1. Create the new module. Imports are limited to the standard library, `docsentinel.log`,
   `docsentinel.mining.clustering` (Task 02) and `Claim` from `docsentinel.mining.claims` (under
   `TYPE_CHECKING` only, so that importing the scorer never imports spaCy). The module must not
   import `docsentinel.config` or any other module the C9 mining row forbids, must not import
   `httpx` or `docsentinel.fact_check`, and must not read `os.environ`.
2. `token_count(claim) -> int` is `len(claim.raw_object.split())` (T3).
3. `numeric_density(claim) -> float` is `min(1.0, len(claim.object_numbers) / max(1, token_count(claim)))`.
   `entity_density(claim) -> float` is the same, using `object_entities`.
4. `SalienceWeights(numeric, entity, distinctiveness)` is a frozen dataclass. `__post_init__`
   raises `ValueError` unless each weight is a finite `float`/`int` (not `bool`) in `[0, 1]` and the
   three sum to `1.0` within `math.isclose(..., abs_tol=1e-9)`, so the result stays in `[0, 1]`.
5. `combined_score(numeric, entity, distinctiveness, *, weights: SalienceWeights) -> float` is
   `weights.numeric * numeric + weights.entity * entity + weights.distinctiveness * distinctiveness`,
   rounded to `SCORE_DECIMALS` (6) places so that sorting is stable across platforms. Each signal
   must be in `[0, 1]`; anything else raises `ValueError`. The function is monotonic in each signal
   for any valid weights.
6. In `detectors/fact_check.py`, add the policy constants `_W_NUMERIC = 0.3`, `_W_ENTITY = 0.3`
   and `_W_DISTINCT = 0.4` as plain floats (Task 03's `select_candidates()` builds the
   `SalienceWeights` from them, so importing the detector never imports `mining.salience`; see the
   story data contracts), each with a comment giving its reason. The values are fixed, not
   configurable. Whatever the values, they must meet these constraints, each
   pinned by a test:
   - (a) The weights sum to `1.0` (enforced by `SalienceWeights` itself).
   - (b) `distinctiveness < 0.5`. A claim with no numbers and no entities can never reach the
     default `fact_check_min_salience = 0.5` (T6 and the story's acceptance criterion), but it can
     when a project lowers the floor.
   - (c) A short, fully distinctive claim with one number and one entity in a three-token object
     scores at least 0.5. For example, numeric 1/3, entity 1/3 and distinctiveness 1.0 give 0.6.
   - (d) The score is monotonic in each signal.
7. The docstrings describe each signal, the weights and constraints (a) to (d), and state that the
   score is a heuristic for choosing candidates, not a measure of truth.
8. Report a `Docs impact:` line (trigger A: new module in the mining layer).

## Deliverables

- `/src/docsentinel/mining/salience.py` (new). This task adds the scoring part; Task 03 completes
  the module with `select_salient`.
- `/src/docsentinel/detectors/fact_check.py` (the three weight constants only).

## Acceptance criteria

- [ ] All scoring functions are pure and fully typed. Each returns a value in `[0, 1]` and rounds
      exactly as specified. None takes a `Config`.
- [ ] `SalienceWeights` rejects a negative weight, a `bool`, a non-finite value and a sum other
      than `1.0` with `ValueError`.
- [ ] Constraints (a) to (d) each have a unit test with hand-built `Claim` literals.
- [ ] A claim with an empty `raw_object` gets density `0.0` and does not raise.
- [ ] The scoring functions never log, never read the environment, and import nothing listed as
      banned in step 1; `tests/unit/test_mining_layering.py` stays green.
- [ ] ruff is clean, and the module follows `/docs/dev/python_coding_standard.md`.

## Test expectations

Tests are written in [Task 04](./04-fixtures-and-tests.md): the scoring functions and
`SalienceWeights` in `tests/unit/test_mining_salience.py`, the weight-constant constraints
(a) to (d) in `tests/unit/test_fact_check_candidates.py`.

## Out of scope

- TF-IDF and clustering (Task 02).
- Thresholds and caps (Task 03).
- Any configurable weight.
