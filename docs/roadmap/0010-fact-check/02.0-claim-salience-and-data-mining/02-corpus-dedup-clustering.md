# Task 02 — Corpus-wide TF-IDF distinctiveness and near-duplicate clustering

**Parent story:** [Story 02.0](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md)  
**Role:** Python Expert  
**Depends on:** [Task 01](./01-salience-scoring.md) and the move of
`detectors/standard/corpus.py` to `mining/corpus.py` (landing in parallel, 2026-11-21).

> **Amended 2026-11-21 (mining layer).** The clustering is `mining/clustering.py`, text-generic,
> with the threshold as an explicit parameter, and it reuses the `mining/corpus.py` vectorizer
> factory (story decisions T4 and T7). It was part of the planned `detectors/fact_check_salience.py`.

## Goal

Make one deterministic pass over every claim sentence in the scan's corpus. The pass vectorizes the
sentences with TF-IDF, groups near-identical sentences across the whole corpus (owner ruling D7),
and gives each sentence a distinctiveness signal in `[0, 1]`. When the same claim appears in N
files, the selection step can then send it once, not N times.

## Inputs

- Story README [decisions T1, T2, T4 and T7](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md#decisions),
  the [data contracts](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md#data-contracts)
  and the [pipeline diagram](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/README.md#interaction-with-story-010s-caps).
- Owner ruling D7 (corpus-wide scope), recorded in [status.md](/docs/roadmap/0010-fact-check/status.md#notes--decisions).
- Contract [C9](/docs/roadmap/0010-fact-check/plan.md#c9--layering-mining-detectors-fact-check-backends).
- `/src/docsentinel/mining/corpus.py`: the vectorizer factory to reuse. Do not use its cached
  `build_corpus_model()` (T4).

## Steps

1. **Vectorizer factory.** If the move has not already done so, promote `_create_vectorizer()` in
   `mining/corpus.py` to a public `create_vectorizer() -> TfidfVectorizer` with the same
   parameters, and update `build_corpus_model()` to call it. Do not change its parameters: that
   would recalibrate `DS202`/`DS203`. A private alias is not kept.
2. **Module.** Create `src/docsentinel/mining/clustering.py`. Imports are limited to the standard
   library, `numpy`, `scipy.sparse`, `docsentinel.mining.corpus` and `docsentinel.log`. It knows
   nothing about `Claim`: the input is `Sequence[str]` in the caller's canonical order, and the
   output is index-aligned with it.
3. **Validation.** `cluster_near_duplicates(texts, *, threshold, chunk_rows=SIMILARITY_CHUNK_ROWS)`
   raises `ValueError` when `threshold` is not a finite number in `(0, 1]` or `chunk_rows` is not
   an `int >= 1` (a `bool` is refused for both). An empty input returns `()`.
4. **Vectorize** the texts with `create_vectorizer().fit_transform(...)`. The model is local to one
   call. It is not cached across scans and not shared with `DS202`'s corpus model. The factory's
   stop-word list is scikit-learn's built-in English list, so nothing is downloaded.
5. If vectorizing raises `ValueError` because the vocabulary is empty, put every text in its own
   cluster with distinctiveness `0.0`. This is the conservative choice: less text is sent. Log one
   DEBUG line with counts only.
6. **Cosine similarity**: compute it on the L2-normalized TF-IDF rows in row chunks of `chunk_rows`
   rows (default `SIMILARITY_CHUNK_ROWS = 512`). Never build a dense `n x n` matrix in one step.
   Peak memory must be `O(chunk x n)`. Document the complexity in the docstring.
7. **Clustering**: two texts are linked when their similarity is strictly greater than
   `threshold`. Clusters are the connected components of that graph. Build them with union-find
   over the input order, and use the smallest input index as the cluster id. Clustering does not
   look at document boundaries. The caller (`mining/salience.py`, Task 03) passes `0.92`, which it
   receives from `detectors/fact_check.py`; the value is fixed and not configurable (see the
   story's Security notes).
8. **Distinctiveness**: for each text, compute `1 - max(similarity to any text outside its own
   cluster)`, clamped to `[0, 1]`, and give `1.0` when no other cluster exists. Round it to
   `ROUND_DECIMALS` (6) places, the same rounding as `combined_score`.
9. Return `tuple[TextCluster, ...]` (`cluster_id`, `distinctiveness`), one per input text.
10. Report a `Docs impact:` line (trigger A: new mining module; public factory in
    `mining/corpus.py`).

## Deliverables

- `/src/docsentinel/mining/clustering.py` (new).
- `/src/docsentinel/mining/corpus.py` (`create_vectorizer()` public, if not already).

## Acceptance criteria

- [ ] Two sentences with similarity above 0.92 share a cluster, and two below it do not. Exactly
      0.92 is not linked.
- [ ] Linking is transitive: if A is linked to B and B to C, then A, B and C form one cluster even
      when A and C are not linked to each other.
- [ ] Identical sentences from different documents share a cluster. This is corpus-wide, not
      per-document.
- [ ] The output is index-aligned with the input and depends only on the input order the caller
      chooses (Task 03 canonicalizes it).
- [ ] An empty input returns `()`. A single text gets distinctiveness `1.0`. A vocabulary that is
      empty after tokenizing gives `0.0` for every text and no exception.
- [ ] An out-of-range `threshold` or `chunk_rows` raises `ValueError`.
- [ ] No dense `n x n` allocation. The implementation computes in chunks, and a unit test checks
      this with `chunk_rows=2`.
- [ ] The vectorizer comes only from `mining.corpus.create_vectorizer()`; `DS202`/`DS203` results
      are unchanged (the existing standard-profile tests stay green).
- [ ] No text is logged at any level. The module takes no `Config` and keeps
      `tests/unit/test_mining_layering.py` green.

## Test expectations

Tests are written in [Task 04](./04-fixtures-and-tests.md), in `tests/unit/test_mining_clustering.py`.

## Out of scope

- Thresholding and caps (Task 03).
- Caching across scans (plan, out of scope).
- Changes to `DS202`/`DS203` behaviour or to the factory's parameters.
