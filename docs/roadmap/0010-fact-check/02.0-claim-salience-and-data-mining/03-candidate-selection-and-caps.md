# Task 03 — `select_salient()` and the `select_candidates()` wrapper: floor, representatives, ordering and caps

**Parent story:** [Story 02.0](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md)  
**Role:** Python Expert  
**Depends on:** [Task 01](./01-salience-scoring.md) and [Task 02](./02-corpus-dedup-clustering.md).

> **Amended 2026-11-21 (mining layer).** Selection is split (story decision T8): the pure
> `select_salient(...)` in `mining/salience.py` owns representatives, floor, order and caps, with
> explicit numbers; the thin `select_candidates(claims, config)` wrapper and `CandidateClaim` live
> in `detectors/fact_check.py`. The ordering and tie-break contract is unchanged.

> **Amended 2026-11-23 (Story 05.0, plan contract C11).** Steps 2.2–2.8 are later re-expressed as
> `trace_salience(...)`, which records a disposition for every claim instead of dropping it, and
> `select_salient` becomes its `selected` projection, with the same output. See
> [Story 05.0 Task 01](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/01-shared-candidate-collection-and-public-api.md)
> step 1. "Configurable dedup or weight parameters" stays out of scope **for DS302**. The
> CLI-only exploration policy of Story 05.0 never reaches `select_candidates` from a `Config`.

## Goal

Implement the entry point `DS302` calls. It returns a bounded, deterministically ordered
`tuple[CandidateClaim, ...]`. Together, these two functions are the only control on how much
document text Story 03.0 can send.

## Inputs

- The story's [data contracts](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md#data-contracts),
  [pipeline](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md#interaction-with-story-010s-caps)
  and decisions T5 and T8.
- Contracts [C4](/docs/roadmap/0010-fact-check/plan.md#c4--fixed-transport-bounded-content) (which keys
  bound content) and [C9](/docs/roadmap/0010-fact-check/plan.md#c9--layering-mining-detectors-fact-check-backends),
  and the Story 01.0 [config reference](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#config-reference).
- [Story 01.0 Task 05](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/05-ds302-registration-and-engine-dispatch.md),
  which calls `select_candidates` and uses `candidate.text` as both the text sent and the finding
  `value`.

## Steps

1. **`ScoredClaim`** in `mining/salience.py` is a frozen dataclass with `claim`, `score` and
   `cluster_id`.
2. **`select_salient(claims, *, weights, dedup_threshold, min_salience, max_per_document, max_total)`**
   in `mining/salience.py`, in this order:
   1. Validate the numbers: `min_salience` a finite number in `[0, 1]`, `dedup_threshold` in
      `(0, 1]`, `max_per_document` and `max_total` an `int >= 1` (a `bool` is refused). Any
      violation raises `ValueError`. The mining layer may not import `config`, so it never raises
      `ConfigError`.
   2. Canonicalize: drop claims whose `raw_sentence` is empty or only whitespace, and sort the rest
      by `(path, paragraph_index, raw_sentence, raw_subject, raw_object)`. Every later step uses
      this order, so the output does not depend on the order the claims were passed in.
   3. Call `clustering.cluster_near_duplicates([c.raw_sentence for c in canonical],
      threshold=dedup_threshold)` (Task 02), then compute `combined_score(..., weights=weights)` for
      each claim (Task 01).
   4. Keep one representative per cluster: the member with the highest score. Break ties by the
      smallest `(path, paragraph_index, raw_sentence)`.
   5. Drop representatives whose `score < min_salience`. The floor is inclusive: a score equal to
      the floor survives.
   6. Sort by `(-score, path, paragraph_index, raw_sentence)`. The last key is a final tie-break
      that T5 needs to be total.
   7. Keep at most `max_per_document` per `path`, in sorted order.
   8. Keep the first `max_total` overall.
   9. Log the counts at DEBUG through `docsentinel.log`: claims in, clusters, above the floor,
      after the per-document cap and after the total cap. Never log claim text or paths.
   10. Return a tuple of `ScoredClaim`.
3. **`CandidateClaim`** in `detectors/fact_check.py` is a frozen dataclass with `claim`, `text` and
   `score`, as in the story data contracts.
   - `text` is `claim.raw_sentence` with surrounding whitespace stripped, then cut to
     `MAX_CANDIDATE_CHARS = 1000` code points.
   - `score` is in `[0, 1]`. It is used for ordering and DEBUG counts only.
4. **`select_candidates(claims, config) -> tuple[CandidateClaim, ...]`** in
   `detectors/fact_check.py`:
   1. Re-validate the four numeric `fact_check_*` values of the `config` passed in, using the same
      bounds as `config.py`. An injected `Config` bypasses load-time validation, so this check fails
      closed with `ConfigError`. Reuse the `config.py` validators rather than copying them.
   2. Import `docsentinel.mining.salience` lazily (`importlib.import_module`, inside the function),
      so that importing `docsentinel` never imports scikit-learn.
   3. Build `SalienceWeights(numeric=_W_NUMERIC, entity=_W_ENTITY, distinctiveness=_W_DISTINCT)`
      and call `select_salient(claims, weights=<those weights>, dedup_threshold=_DEDUP_THRESHOLD,
      min_salience=config.fact_check_min_salience,
      max_per_document=config.fact_check_max_claims_per_document,
      max_total=config.fact_check_max_claims_total)`. `_DEDUP_THRESHOLD = 0.92` is a module
      constant with a comment pointing at the story's Security notes.
   4. Map each `ScoredClaim` to a `CandidateClaim` in the order returned. Never re-sort, filter or
      truncate the sequence here.
   5. Read only the `fact_check_*` keys named above. Never read `use_external_api`, the
      environment or any secret. Do not read `fact_check_time_budget_seconds` (owner ruling Q3,
      2026-11-21): the time budget bounds the send loop in `_check_candidates` (Story 01.0 Task 05),
      not the selection, and the claim caps here stay the only bound on how much text can be sent.
5. Report a `Docs impact:` line (trigger A).

## Deliverables

- `/src/docsentinel/mining/salience.py` (complete).
- `/src/docsentinel/detectors/fact_check.py` (`CandidateClaim`, `select_candidates`,
  `MAX_CANDIDATE_CHARS`, `_DEDUP_THRESHOLD`).

## Acceptance criteria

- [ ] `select_salient((), ...)` and `select_candidates((), Config())` return `()`.
- [ ] Each acceptance criterion in the story README holds and has a test: the dedup threshold,
      trivial claims dropped at the default floor, both caps in the right order, determinism and the
      layering/banned imports.
- [ ] The output never has more than `max_total` (`fact_check_max_claims_total`) entries, never more
      than `max_per_document` entries for any one path, and every `CandidateClaim.text` is at most
      1,000 code points. This is checked over a generated corpus of at least 200 claims.
- [ ] `select_salient` with an out-of-range number raises `ValueError`; `select_candidates` with an
      injected `Config` holding an out-of-range cap, for example `0` or `10_000`, raises
      `ConfigError` before calling into `mining`.
- [ ] Two calls on the same input return equal tuples. The input in reverse order gives the same
      output. `select_candidates` returns its candidates in exactly the `select_salient` order.
- [ ] `mining/salience.py` takes no `Config`, imports no `docsentinel.config`, and keeps
      `tests/unit/test_mining_layering.py` green.

## Test expectations

Tests are written in [Task 04](./04-fixtures-and-tests.md): `select_salient` in
`tests/unit/test_mining_salience.py`, the wrapper in `tests/unit/test_fact_check_candidates.py`.

## Out of scope

- Sending (Story 03.0).
- The finding format (Story 01.0 Task 05).
- Configurable dedup or weight parameters.
