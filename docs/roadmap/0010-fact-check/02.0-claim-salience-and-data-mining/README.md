# Story 02.0 — Claim salience and data-mining filter

**Profile:** `deep` · **New module:** `src/docsentinel/detectors/fact_check_salience.py` ·
**Consumes:** `DS301`'s `Claim` tuples (`_triples.py`), the `fact_check_min_salience`/
`fact_check_max_claims_per_document`/`fact_check_max_claims_total` config keys (Story 01.0) ·
**Produces:** `CandidateClaim` tuples for Story 03.0/`fact_check.py` to send externally.
**Parent:** [Milestone 0010 plan](/docs/roadmap/0010-fact-check/plan.md) (design principle 3,
contract C7).
**Security-sensitive:** no new attack surface (no filesystem path, no network, no secret) — this
story reads only already-extracted claim text that `DS301` already reads from discovered
documents. No dedicated Security Auditor task; its output is still named in Story 01.0's Security
notes as a load-bearing exposure bound.

## Goal

Turn "every extracted claim" into "a small, deterministic, non-trivial subset" before any of it
ever reaches an external backend. This is explicitly **data mining**, not a sentence sweep: a
statistical scoring and clustering pass over the whole scan's claim pool, reusing `scikit-learn`
(already a core dependency since Milestone 0002's `DS202`) rather than adding a new one.

## Tasks

| Task | Deliverable | Role | Status |
|---|---|---|---|
| `01-salience-scoring.md` | Numeric-claim-density and named-entity-count scoring over a `Claim`; the combined score function | Python Expert | ⬜ Not written |
| `02-corpus-dedup-clustering.md` | Corpus-wide TF-IDF vectorization and cosine-similarity clustering of claim sentences (scikit-learn), one representative candidate per cluster | Python Expert | ⬜ Not written |
| `03-candidate-selection-and-caps.md` | `select_candidates(claims, config) -> tuple[CandidateClaim, ...]`: threshold by `fact_check_min_salience`, cap by the two `fact_check_max_claims_*` keys, deterministic ordering/tie-breaking | Python Expert | ⬜ Not written |
| `04-fixtures-and-tests.md` | Unit tests for scoring, clustering and capping with tiny inline claim sets (no spaCy model needed — `Claim` is a plain dataclass) | Testing Expert | ⬜ Not written |

## Scope

- A pure, deterministic, synchronous function `select_candidates()` taking the whole scan's
  `tuple[Claim, ...]` (already computed by `DS302`'s `detect()`, reusing `DS301`'s extraction) and
  the effective `Config`, returning a bounded, ordered `tuple[CandidateClaim, ...]`.
- The combined salience score (numeric density + entity count + TF-IDF uniqueness) and the
  near-duplicate clustering/dedup pass.
- The two hard caps (`fact_check_max_claims_per_document`, `fact_check_max_claims_total`) and the
  single quality floor (`fact_check_min_salience`).

## Non-goals

- Any network call, any backend-specific logic, any API key (Story 03.0).
- Changing `DS301`'s own contradiction-candidate logic, `_disagree()`, or its finding generation.
- A new `scikit-learn` dependency version bump or a new third-party library — `TfidfVectorizer`
  and `cosine_similarity` from the already-pinned `scikit-learn>=1.4` are sufficient.
- Persisting or caching salience scores across scans.

## Design

### Decisions

| # | Decision | Rationale |
|---|---|---|
| T1 | The score is a weighted sum of three signals, each normalized to `[0, 1]`: numeric density (`len(claim.object_numbers) / max(1, token_count)`), entity density (`len(claim.object_entities) / max(1, token_count)`), and a corpus TF-IDF "distinctiveness" score (`1 - max cosine similarity to any other claim's sentence outside its own cluster`) | Numeric and named-entity claims ("version 3.2 ships in Q4", "the API key is required") are exactly the shape of claim a fact-checking API can usefully score; the TF-IDF term penalizes boilerplate sentences that repeat near-verbatim across many files (the opposite of "non-trivial") |
| T2 | Near-identical claim sentences across the corpus (cosine similarity above a fixed internal threshold, `0.92`, not configurable) are clustered; only the highest-scoring member of each cluster becomes a candidate | This is the dedup half of "data mining": a claim restated in five files costs one external call, not five, and is also the main exposure-reduction lever alongside the hard caps |
| T3 | `token_count` uses `len(claim.raw_object.split())`, a cheap whitespace count, not a second spaCy pass | `Claim` objects already carry everything needed; re-tokenizing with spaCy here would be a second NLP pipeline invocation Story 01.0's design principle 2 explicitly rules out |
| T4 | The TF-IDF vectorizer and the clustering run once per scan over every claim's `raw_sentence`, mirroring `DS202`'s existing corpus-model pattern (`build_corpus_model`) in spirit but as an independent, deep-profile-local model — it is **not** the same cached object `DS202` builds, because profiles are exact, not cumulative (Milestone 0005/CLAUDE.md convention), and a deep scan must not depend on standard-profile internals | Keeps the profile boundary intact while reusing the proven technique (`TfidfVectorizer` + `cosine_similarity`) |
| T5 | Selection order is deterministic: candidates are sorted by `(-score, path, paragraph_index)` before either cap is applied, so `fact_check_max_claims_total` always keeps the same claims for the same input, and a test can assert exact output | Matches the project-wide rule that every detector output is stable/sorted (`DS202`, `DS301` both sort their findings) |
| T6 | A claim with no numeric content and no named entity (score contribution `0` on both of those terms) can still become a candidate if its TF-IDF distinctiveness term alone clears `fact_check_min_salience`, but this is expected to be rare given the weighting | Keeps the filter a single combined score rather than an all-or-nothing numeric/entity gate, which the milestone brief's "numeric-claim density, named-entity count, **or** a statistical salience score" framing (data mining, not a rigid rule) calls for |

### Data contract

```python
# src/docsentinel/detectors/fact_check_salience.py (new; stdlib + scikit-learn only)

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from docsentinel.config import Config

if TYPE_CHECKING:
    from docsentinel.detectors._triples import Claim


@dataclass(frozen=True)
class CandidateClaim:
    """One claim that survived the salience/dedup filter, ready for an external check."""

    claim: Claim      # the underlying DS301 Claim this candidate was derived from
    text: str          # claim.raw_sentence, bounded to 1000 characters (never the whole paragraph)
    score: float       # the combined [0, 1] salience score, for logging/debugging only


def select_candidates(
    claims: tuple[Claim, ...],
    config: Config,
) -> tuple[CandidateClaim, ...]:
    """Score, dedup-cluster and cap claims into a bounded, deterministic candidate list.

    :param claims: Every claim DS301's extractor produced for this scan's documents.
    :param config: The effective Config (reads the five fact_check_* keys from
        Story 01.0; never reads use_external_api or any secret -- it has none to read).
    :returns: Candidates sorted by (-score, path, paragraph_index), filtered by
        fact_check_min_salience, deduplicated by near-identical sentence, and
        capped by fact_check_max_claims_per_document then fact_check_max_claims_total.
    """
```

`select_candidates` is pure and synchronous: no I/O, no logging of claim text beyond what `DS301`
already logs at `DEBUG` (claim/candidate counts only, through `safe()`), no network. It is safe to
unit-test with a handful of inline `Claim(...)` literals — no document assets, no spaCy model, and
no live `scikit-learn` fixture beyond what the function constructs internally.

### Interaction with Story 01.0's caps

```text
all extracted claims (DS301's extract_claims(), pooled across every document)
        │
        ▼
score each claim (T1: numeric density + entity density + TF-IDF distinctiveness)
        │
        ▼
cluster near-identical sentences corpus-wide (T2), keep the top-scoring member per cluster
        │
        ▼
drop any claim below fact_check_min_salience
        │
        ▼
sort by (-score, path, paragraph_index)              (T5, determinism)
        │
        ▼
keep at most fact_check_max_claims_per_document per path
        │
        ▼
keep at most fact_check_max_claims_total overall
        │
        ▼
tuple[CandidateClaim, ...] -> Story 03.0's backend client, one check_claim() call each
```

## Security notes

- This module never touches the filesystem beyond the already-read document text it is handed,
  never imports `httpx`, and never reads an environment variable. Its only load-bearing security
  property is the one Story 01.0's Security notes already name: it is the mechanism that keeps
  "only a small, chosen subset of claims" true, bounding what Story 03.0 can ever send.
- The `0.92` clustering threshold and the token-count heuristic (T3) are **not** configurable, on
  purpose: a project config lowering the clustering threshold could inflate the candidate count
  past what the two hard caps expect, and a project loosening either hard cap already covers the
  legitimate "I want more/less sent" case without touching the clustering internals.

## Acceptance criteria

- [ ] `select_candidates(())` returns `()` with no error (empty corpus).
- [ ] Two claims with cosine similarity above `0.92` produce exactly one candidate (the
      higher-scoring one); two claims below that threshold both survive (if both clear
      `fact_check_min_salience`).
- [ ] A claim with zero numeric tokens and zero entities and low TF-IDF distinctiveness is
      dropped at the default `fact_check_min_salience = 0.5`.
- [ ] `fact_check_max_claims_per_document` caps the per-document count even when more candidates
      would otherwise qualify; `fact_check_max_claims_total` caps the corpus-wide count after the
      per-document cap.
- [ ] Output order is exactly `(-score, path, paragraph_index)` for a fixed input, asserted
      byte-for-byte across two runs (determinism).
- [ ] No call in this module imports `httpx`, `os.environ`, or any name from
      `docsentinel.detectors.fact_check_protocol`.

## Test plan

| Layer | File (new) | Covers |
|---|---|---|
| Unit | `test_fact_check_salience_scoring.py` | The three score terms in isolation and combined, with hand-built `Claim` literals |
| Unit | `test_fact_check_salience_clustering.py` | The `0.92` dedup threshold, representative selection, corpus-wide (not per-document) scope |
| Unit | `test_fact_check_salience_caps.py` | Both hard caps, the sort order/determinism, an empty-corpus input |

## Docs to update

Deferred to Story 04.0: `/docs/user/reference/configuration.md` (the five `fact_check_*` keys, if
not already covered by Story 01.0's docs task) and `/docs/dev/markdown_scanner.md`'s "deep
profile" note, if one exists by then, naming this module alongside `_triples.py`.
