# Story 02.0 — Claim salience and data-mining filter

**Profile:** `deep` · **New modules (mining layer, contract C9):**
`src/docsentinel/mining/salience.py` (claim scoring, representative choice, floor, ordering, caps)
and `src/docsentinel/mining/clustering.py` (corpus-wide TF-IDF near-duplicate clustering and
distinctiveness) · **Detector-side wrapper:** `select_candidates(claims, config)` and
`CandidateClaim` in `src/docsentinel/detectors/fact_check.py` (created by Story 01.0 Task 05) ·
**Consumes:** `DS301`'s `Claim` tuples (`mining/claims.py`), the vectorizer factory in
`mining/corpus.py`, the `fact_check_min_salience`/`fact_check_max_claims_per_document`/
`fact_check_max_claims_total` config keys (Story 01.0) ·
**Produces:** `CandidateClaim` tuples for `fact_check.py` to send through Story 03.0's client.
**Parent:** [Milestone 0010 plan](/docs/roadmap/0010-fact-check/plan.md) (design principle 3,
contracts C7 and C9).
**Security-sensitive:** no new attack surface (no filesystem path, no network, no secret) — this
story reads only already-extracted claim text that `DS301` already reads from discovered
documents. No dedicated Security Auditor task; its output is still named in Story 01.0's Security
notes as a load-bearing exposure bound.

> **Amended 2026-11-21 (owner decision: mining layer).** The scoring and clustering moved from the
> planned `detectors/fact_check_salience.py` into `mining/salience.py` and `mining/clustering.py`,
> as pure functions with explicit numeric parameters and no `Config`. `select_candidates()` became
> a thin wrapper in `detectors/fact_check.py`. The ordering and tie-break contract is unchanged.
> See decisions T4, T7 and T8.

> **Amended 2026-11-23 (Story 05.0, plan contract C11).**
> [Story 05.0 Task 01](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/01-shared-candidate-collection-and-public-api.md)
> changes three things here:
>
> - `ScoredClaim` gains `numeric`, `entity`, `distinctiveness`, `cluster_size` and `disposition`.
> - A pure `trace_salience(...)` keeps every canonical claim with its disposition, and
>   `select_salient(...)` becomes its `selected` subsequence.
> - `select_candidates` gains a keyword-only `policy: SelectionPolicy = DS302_POLICY`, and
>   `CandidateClaim` gains the signal and cluster fields.
>
> The T5 order, the tie-breaks, the floor, the caps and the fixed DS302 constants are unchanged. The
> weights and the threshold stay non-configurable for DS302. Only the offline `extract-facts`
> command can pass another policy (Story 05.0 decision X5). If this story is implemented before
> Story 05.0, it may implement the data contracts below as written, and Story 05.0 Task 01 extends
> them.

## Goal

Turn "every extracted claim" into "a small, deterministic, non-trivial subset" before any of it
ever reaches an external backend. This is explicitly **data mining**, not a sentence sweep: a
statistical scoring and clustering pass over the whole scan's claim pool, reusing `scikit-learn`
(already a core dependency since Milestone 0002's `DS202`) rather than adding a new one.

## Tasks

| Task | Deliverable | Role | Status |
|---|---|---|---|
| `01-salience-scoring.md` | `mining/salience.py`: numeric-density and entity-density scoring over a `Claim`, `SalienceWeights`, the combined score function | Python Expert | ✅ Complete |
| `02-corpus-dedup-clustering.md` | `mining/clustering.py`: corpus-wide TF-IDF vectorization (the `mining/corpus.py` factory) and chunked cosine-similarity clustering of claim sentences, with a distinctiveness signal per sentence | Python Expert | ✅ Complete |
| `03-candidate-selection-and-caps.md` | `mining/salience.py` `select_salient(...)` (representatives, floor, deterministic order, caps; explicit numbers only) and the detector-side `select_candidates(claims, config) -> tuple[CandidateClaim, ...]` wrapper in `detectors/fact_check.py` | Python Expert | ✅ Complete |
| `04-fixtures-and-tests.md` | Unit tests for scoring, clustering, ranking and the wrapper with tiny inline claim sets (no spaCy model needed — `Claim` is a plain dataclass); the mining layering tripwire stays green | Testing Expert | ✅ Complete |

## Scope

- Pure, deterministic, synchronous mining functions in `mining/salience.py` and
  `mining/clustering.py`, taking the whole scan's `tuple[Claim, ...]` (or their sentences) and
  explicit numeric parameters, never a `Config`.
- The combined salience score (numeric density + entity density + TF-IDF distinctiveness) and the
  near-duplicate clustering/dedup pass.
- The two hard caps (`fact_check_max_claims_per_document`, `fact_check_max_claims_total`) and the
  single quality floor (`fact_check_min_salience`), applied by the mining function from numbers
  the detector wrapper reads off the `Config`.
- The thin `select_candidates(claims, config)` wrapper and the `CandidateClaim` data contract in
  `detectors/fact_check.py`.

## Non-goals

- Any network call, any backend-specific logic, any API key (Story 03.0).
- Changing `DS301`'s own contradiction-candidate logic, `_disagree()`, or its finding generation.
- Moving `detectors/standard/corpus.py`, `detectors/_triples.py` or `deep_support.py` into
  `mining/`; that move is a separate change landing in parallel. This story consumes the new paths.
- A new `scikit-learn` dependency version bump or a new third-party library — `TfidfVectorizer`
  and the sparse dot product from the already-pinned `scikit-learn>=1.4`/`scipy` are sufficient.
- Persisting or caching salience scores across scans.

## Design

### Decisions

| # | Decision | Rationale |
|---|---|---|
| T1 | The score is a weighted sum of three signals, each normalized to `[0, 1]`: numeric density (`len(claim.object_numbers) / max(1, token_count)`), entity density (`len(claim.object_entities) / max(1, token_count)`), and a corpus TF-IDF "distinctiveness" score (`1 - max cosine similarity to any other claim's sentence outside its own cluster`) | Numeric and named-entity claims ("version 3.2 ships in Q4", "the API key is required") are exactly the shape of claim a fact-checking API can usefully score; the TF-IDF term penalizes boilerplate sentences that repeat near-verbatim across many files (the opposite of "non-trivial") |
| T2 | Near-identical claim sentences across the corpus (cosine similarity above a fixed threshold, `0.92`, not configurable) are clustered; only the highest-scoring member of each cluster becomes a candidate. The mining function takes the threshold as an explicit `dedup_threshold` parameter; the fixed value `0.92` is a `DS302` policy constant in `detectors/fact_check.py` | This is the dedup half of "data mining": a claim restated in five files costs one external call, not five, and is also the main exposure-reduction lever alongside the hard caps |
| T3 | `token_count` uses `len(claim.raw_object.split())`, a cheap whitespace count, not a second spaCy pass | `Claim` objects already carry everything needed; re-tokenizing with spaCy here would be a second NLP pipeline invocation contract C7 rules out |
| T4 | **Amended 2026-11-21.** Clustering **reuses the `mining/corpus.py` vectorizer factory** (promoted to a public `create_vectorizer()`; today `_create_vectorizer()`), but **not** the cached `build_corpus_model()`. The vectorizer and clustering run once per scan over every claim's `raw_sentence`, in a model local to the call | The earlier objection ("a deep scan must not depend on standard-profile internals") no longer applies: the factory now lives in the shared mining layer, not in a standard-profile detector, so the deep profile depends on `mining/`, not on `standard`. One TF-IDF configuration (English stop words from scikit-learn's built-in list, so no download; word token pattern; sublinear TF) keeps calibration in one place. `build_corpus_model()` stays unshared: it chunks whole documents into paragraphs, reads files, and is `lru_cache`d on paragraph floors, none of which fits a claim pool. What gets harder: a change to the factory now recalibrates `DS202`, `DS203` and `DS302` together, so Task 04 pins the factory's parameters with a test and the `0.92` threshold's acceptance cases run through the real factory |
| T5 | Selection order is deterministic: candidates are sorted by `(-score, path, paragraph_index, raw_sentence)` before either cap is applied, so `fact_check_max_claims_total` always keeps the same claims for the same input, and a test can assert exact output. The order is owned by `mining/salience.py`; the detector wrapper never reorders | Matches the project-wide rule that every detector output is stable/sorted (`DS202`, `DS301` both sort their findings) |
| T6 | A claim with no numeric content and no named entity (score contribution `0` on both of those terms) can still become a candidate if its TF-IDF distinctiveness term alone clears `fact_check_min_salience`, but this is expected to be rare given the weighting | Keeps the filter a single combined score rather than an all-or-nothing numeric/entity gate, which the milestone brief's "numeric-claim density, named-entity count, **or** a statistical salience score" framing (data mining, not a rigid rule) calls for |
| T7 | **New 2026-11-21.** Two mining modules, not one: `mining/clustering.py` is text-generic (it takes `Sequence[str]` and knows nothing about `Claim`), `mining/salience.py` is claim-specific and composes it | Clustering is the scikit-learn-heavy, reusable half (a later `DS202` near-duplicate pass could call it); scoring and ranking are small, `Claim`-aware and testable with no vectorizer at all. Splitting keeps each module's test file focused and lets `salience.py`'s scoring tests patch clustering out. Cost: one more module and one intra-mining import (`salience` -> `clustering` -> `corpus`), which the layering rule allows (C9) |
| T8 | **New 2026-11-21.** `select_candidates(claims, config)` is a **thin detector-side wrapper** in `detectors/fact_check.py`, not a function that moves into the detector wholesale. The wrapper re-validates the four numeric `fact_check_*` values (raising `ConfigError`), reads the policy constants (`_W_NUMERIC`/`_W_ENTITY`/`_W_DISTINCT`, `_DEDUP_THRESHOLD`), calls `mining.salience.select_salient(...)` with explicit numbers, and maps each result to a `CandidateClaim` with its bounded `text` | Keeps every ordering, tie-break and cap rule in the pure, `Config`-free mining function, where it is unit-tested with plain numbers; the detector holds only what is `DS302` policy (the fixed weights and threshold, the 1,000-character send bound, `ConfigError` re-validation, which the mining layer cannot raise because it may not import `config`). Rejected: putting the whole selection in the detector, which would move the determinism contract out of the layer the owner created for it and make it testable only through a `Config` |

### Data contracts

```python
# src/docsentinel/mining/clustering.py (new; stdlib, numpy/scipy, scikit-learn,
# docsentinel.mining.corpus, docsentinel.log only)

SIMILARITY_CHUNK_ROWS: Final[int] = 512
ROUND_DECIMALS: Final[int] = 6


@dataclass(frozen=True)
class TextCluster:
    """Cluster membership and distinctiveness of one input text."""

    cluster_id: int         # smallest input index in the text's connected component
    distinctiveness: float  # 1 - max similarity to a text outside the cluster, in [0, 1]


def cluster_near_duplicates(
    texts: Sequence[str],
    *,
    threshold: float,
    chunk_rows: int = SIMILARITY_CHUNK_ROWS,
) -> tuple[TextCluster, ...]:
    """Cluster near-identical texts with TF-IDF cosine similarity.

    :param texts: Texts in the caller's canonical order; the output is index-aligned.
    :param threshold: Link two texts when similarity is strictly greater than this,
        in (0, 1].
    :param chunk_rows: Row-chunk size of the similarity computation, >= 1.
    :raises ValueError: For a threshold or chunk size out of range.
    """
```

```python
# src/docsentinel/mining/salience.py (new; stdlib, docsentinel.mining.claims (Claim),
# docsentinel.mining.clustering, docsentinel.log only)

SCORE_DECIMALS: Final[int] = 6


@dataclass(frozen=True)
class SalienceWeights:
    """Weights of the three signals; each in [0, 1], summing to 1.0 (else ValueError)."""

    numeric: float
    entity: float
    distinctiveness: float


@dataclass(frozen=True)
class ScoredClaim:
    """One claim with its combined score and cluster id."""

    claim: Claim
    score: float     # combined [0, 1] salience score, rounded to SCORE_DECIMALS
    cluster_id: int


def select_salient(
    claims: tuple[Claim, ...],
    *,
    weights: SalienceWeights,
    dedup_threshold: float,
    min_salience: float,
    max_per_document: int,
    max_total: int,
) -> tuple[ScoredClaim, ...]:
    """Score, dedup-cluster, floor, order and cap claims (pure, no Config).

    :returns: One representative per cluster with score >= min_salience, sorted by
        (-score, path, paragraph_index, raw_sentence), at most max_per_document per
        path, then at most max_total overall.
    :raises ValueError: For any numeric parameter out of range.
    """
```

```python
# src/docsentinel/detectors/fact_check.py (Story 01.0 Task 05 module; this story adds)

MAX_CANDIDATE_CHARS: Final[int] = 1000
_W_NUMERIC: Final[float] = 0.3       # plain floats: building SalienceWeights here would import
_W_ENTITY: Final[float] = 0.3        # mining.salience (and scikit-learn) at module import time;
_W_DISTINCT: Final[float] = 0.4      # select_candidates() builds SalienceWeights from them
_DEDUP_THRESHOLD: Final[float] = 0.92


@dataclass(frozen=True)
class CandidateClaim:
    """One claim that survived the salience/dedup filter, ready for an external check."""

    claim: Claim   # the underlying DS301 Claim this candidate was derived from
    text: str      # claim.raw_sentence stripped, cut to MAX_CANDIDATE_CHARS code points
    score: float   # the combined [0, 1] salience score, for ordering/debugging only


def select_candidates(
    claims: tuple[Claim, ...],
    config: Config,
) -> tuple[CandidateClaim, ...]:
    """Adapt the effective Config to mining.salience.select_salient and bound the text.

    Re-validates the four numeric fact_check_* values (ConfigError), never reads
    use_external_api, the environment or any secret, and never reorders the result.
    """
```

`SalienceWeights` and `Claim` are imported by `fact_check.py` only under `TYPE_CHECKING` or inside
`select_candidates()` (which builds `SalienceWeights` from the three float constants), so that importing
`docsentinel` and every fast/standard scan still never imports scikit-learn through `mining`.
The mining functions are pure and synchronous: no I/O, no environment, no network, and no logging
of claim text (stage counts only, at DEBUG, through `docsentinel.log`). They are safe to unit-test
with a handful of inline `Claim(...)` literals — no document assets and no spaCy model.

### Interaction with Story 01.0's caps

```text
all extracted claims (mining.claims.extract_claims(), pooled across every document)
        │
        ▼   detectors/fact_check.py select_candidates(): re-validate Config, read policy constants
        ▼   mining/salience.py select_salient():
canonical order; score each claim (T1: numeric density + entity density + distinctiveness)
        │          └─ distinctiveness and cluster ids from mining/clustering.py (T2, T4)
        ▼
keep the top-scoring member per cluster
        │
        ▼
drop any claim below min_salience (inclusive floor)
        │
        ▼
sort by (-score, path, paragraph_index, raw_sentence)   (T5, determinism)
        │
        ▼
keep at most max_per_document per path, then at most max_total overall
        │
        ▼   back in select_candidates(): map to CandidateClaim, bound text to 1,000 code points
tuple[CandidateClaim, ...] -> Story 03.0's backend client, one check_claim() call each
```

## Security notes

- The mining modules never touch the filesystem beyond the already-read document text they are
  handed, never import `httpx` or `docsentinel.fact_check`, never read an environment variable, and
  never import `config` (C9; enforced by `tests/unit/test_mining_layering.py`). Their only
  load-bearing security property is the one Story 01.0's Security notes already name: they keep
  "only a small, chosen subset of claims" true, bounding what Story 03.0 can ever send.
- The `0.92` clustering threshold, the weights and the token-count heuristic (T3) are **not**
  configurable, on purpose: a project config lowering the clustering threshold could inflate the
  candidate count past what the two hard caps expect, and a project loosening either hard cap
  already covers the legitimate "I want more/less sent" case without touching the clustering
  internals. Making them explicit mining parameters does not make them configurable: only
  `detectors/fact_check.py` passes them, from module constants.

## Acceptance criteria

- [ ] `select_salient((), ...)` and `select_candidates((), Config())` return `()` with no error
      (empty corpus).
- [ ] Two claims with cosine similarity above `0.92` produce exactly one candidate (the
      higher-scoring one); two claims below that threshold both survive (if both clear
      `fact_check_min_salience`).
- [ ] A claim with zero numeric tokens and zero entities and low TF-IDF distinctiveness is
      dropped at the default `fact_check_min_salience = 0.5`.
- [ ] `fact_check_max_claims_per_document` caps the per-document count even when more candidates
      would otherwise qualify; `fact_check_max_claims_total` caps the corpus-wide count after the
      per-document cap.
- [ ] Output order is exactly `(-score, path, paragraph_index, raw_sentence)` for a fixed input,
      asserted byte-for-byte across two runs (determinism), and `select_candidates` preserves the
      order `select_salient` returns.
- [ ] `mining/salience.py` and `mining/clustering.py` take no `Config` and import no
      `docsentinel.config`; `tests/unit/test_mining_layering.py` stays green with both modules
      present.
- [ ] Neither mining module imports `httpx` or `docsentinel.fact_check`, nor references
      `os.environ`.
- [ ] Clustering builds its vectorizer only through `mining.corpus.create_vectorizer()`.

## Test plan

| Layer | File (new) | Covers |
|---|---|---|
| Unit | `tests/unit/test_mining_salience.py` | The three score terms in isolation and combined, `SalienceWeights` validation, representative choice, floor, order, both caps, an empty corpus, with hand-built `Claim` literals |
| Unit | `tests/unit/test_mining_clustering.py` | The `0.92` threshold through the real factory, transitive linking, representative-free index alignment, corpus-wide scope, chunking, the factory-parameter pin |
| Unit | `tests/unit/test_fact_check_candidates.py` | The `select_candidates` wrapper: `ConfigError` re-validation, the policy constants and weight constraints, the 1,000-code-point text bound, order preservation |
| Unit | `tests/unit/test_mining_layering.py` (existing, from the move) | Stays green; no change needed beyond what Task 04 notes |

## Docs to update

Deferred to Story 04.0: `/docs/user/reference/configuration.md` (the six `fact_check_*` keys, if
not already covered by Story 01.0's docs task) and `/docs/dev/markdown_scanner.md`'s "deep
profile" note, if one exists by then, naming `mining/salience.py` and `mining/clustering.py`
alongside `mining/claims.py`.
