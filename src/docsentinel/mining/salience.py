"""Claim salience scoring for the ``DS302`` fact-check candidate filter (Milestone 0010 Story 02.0).

A claim's salience is a weighted sum of three signals, each normalized to ``[0, 1]`` (decision
T1):

- **numeric density**: the share of the claim's object tokens that are numbers,
  ``min(1, len(object_numbers) / max(1, token_count))``;
- **entity density**: the same share for named entities, using ``object_entities``;
- **distinctiveness**: a corpus TF-IDF signal computed by ``mining/clustering.py`` (Task 02),
  ``1 - max similarity`` to a claim sentence outside the claim's own near-duplicate cluster.

``token_count`` is a whitespace count of ``raw_object`` (decision T3), so scoring never runs a
second NLP pipeline (contract C7). Every signal is computed separately, so a caller can keep the
per-signal breakdown next to the combined score (Story 05.0's ``trace_salience``).

The weights are an explicit :class:`SalienceWeights` argument: this module reads no ``Config``
and no environment, and the fixed ``DS302`` values live in ``detectors/fact_check.py``
(decision T8). Whatever their values, the ``DS302`` weights meet four constraints, each pinned
by a unit test:

- (a) the weights sum to ``1.0`` (enforced here by :class:`SalienceWeights`), so the combined
  score stays in ``[0, 1]``;
- (b) the distinctiveness weight is below ``0.5``, so a claim with no number and no entity never
  reaches the default ``fact_check_min_salience = 0.5`` (decision T6), but can when a project
  lowers the floor;
- (c) a short, fully distinctive claim with one number and one entity in a three-token object
  scores at least ``0.5``;
- (d) the combined score is monotonic (non-decreasing) in each signal, which holds for any
  valid, non-negative weights.

The score is a heuristic for choosing which claims are worth an external check. It is not a
measure of truth, accuracy or importance.

:func:`trace_salience` (Story 05.0, decision X2) composes the scoring with ``mining/clustering.py``:
it keeps one representative per near-duplicate cluster, applies the inclusive ``min_salience``
floor, sorts by ``(-score, path, paragraph_index, raw_sentence)`` (decision T5) and applies the
per-document cap, then the total cap, recording for every canonical claim why it was kept or
dropped (:data:`DISPOSITIONS`). :func:`select_salient` (Story 02.0 Task 03) is its ``selected``
subsequence, so ordering, tie-breaks and caps live once. Every number is an explicit argument;
this module never raises ``ConfigError``.

The functions here are pure and synchronous: no I/O, no environment, and no logging except the
DEBUG stage counts of :func:`trace_salience` (counts only, never claim text or paths). Importing
this module imports neither spaCy nor scikit-learn: ``Claim`` is imported for type checking only,
and ``mining.clustering`` (scikit-learn) is imported lazily when claims are scored.
"""

from __future__ import annotations

import importlib
import logging
import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from docsentinel.mining.claims import Claim

#: Decimal places the combined score is rounded to, so sorting is stable across platforms.
SCORE_DECIMALS: Final[int] = 6

#: Absolute tolerance of the "weights sum to 1.0" check.
_WEIGHT_SUM_TOLERANCE: Final[float] = 1e-9

logger = logging.getLogger(__name__)


def _in_unit_interval(value: object) -> bool:
    """Return whether ``value`` is a finite ``int`` or ``float`` (not a ``bool``) in ``[0, 1]``.

    :param value: The value to test.
    :return: ``True`` when the value is a valid signal or weight.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and 0.0 <= value <= 1.0


def token_count(claim: Claim) -> int:
    """Return the whitespace token count of the claim's object text (decision T3).

    :param claim: The extracted claim.
    :return: ``len(claim.raw_object.split())``; ``0`` for an empty or blank object.
    """
    return len(claim.raw_object.split())


def _density(count: int, claim: Claim) -> float:
    """Return ``count`` per object token, capped at ``1.0``.

    :param count: The number of matching items (numbers or entities) in the object.
    :param claim: The claim whose object tokens are the denominator.
    :return: ``min(1.0, count / max(1, token_count(claim)))``.
    """
    return min(1.0, count / max(1, token_count(claim)))


def numeric_density(claim: Claim) -> float:
    """Return the share of the claim's object tokens that are numbers.

    A claim with an empty ``raw_object`` divides by one, so it scores ``0.0`` when it has no
    numbers and never raises.

    :param claim: The extracted claim.
    :return: ``min(1.0, len(object_numbers) / max(1, token_count))``, in ``[0, 1]``.
    """
    return _density(len(claim.object_numbers), claim)


def entity_density(claim: Claim) -> float:
    """Return the share of the claim's object tokens that are named entities.

    :param claim: The extracted claim.
    :return: ``min(1.0, len(object_entities) / max(1, token_count))``, in ``[0, 1]``.
    """
    return _density(len(claim.object_entities), claim)


@dataclass(frozen=True)
class SalienceWeights:
    """Weights of the three salience signals.

    Each weight is a finite ``int`` or ``float`` (never a ``bool``) in ``[0, 1]``, and the three
    sum to ``1.0`` within an absolute tolerance of ``1e-9``, so the combined score stays in
    ``[0, 1]`` (constraint (a)).

    :ivar numeric: Weight of the numeric density.
    :ivar entity: Weight of the entity density.
    :ivar distinctiveness: Weight of the corpus distinctiveness.
    """

    numeric: float
    entity: float
    distinctiveness: float

    def __post_init__(self):
        """Validate the weights.

        :raises ValueError: When a weight is not a finite non-``bool`` number in ``[0, 1]``, or
            the three do not sum to ``1.0``.
        """
        for name in ("numeric", "entity", "distinctiveness"):
            if not _in_unit_interval(getattr(self, name)):
                raise ValueError(f"salience weight {name} must be a finite number in [0, 1]")
        total = self.numeric + self.entity + self.distinctiveness
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=_WEIGHT_SUM_TOLERANCE):
            raise ValueError("salience weights must sum to 1.0")


def combined_score(
    numeric: float,
    entity: float,
    distinctiveness: float,
    *,
    weights: SalienceWeights,
) -> float:
    """Combine the three signals into one salience score.

    The score is ``weights.numeric * numeric + weights.entity * entity +
    weights.distinctiveness * distinctiveness``, rounded to :data:`SCORE_DECIMALS` places. With
    non-negative weights it is monotonic in each signal (constraint (d)). It is a heuristic for
    choosing candidates, not a measure of truth.

    :param numeric: The numeric density, in ``[0, 1]``.
    :param entity: The entity density, in ``[0, 1]``.
    :param distinctiveness: The corpus distinctiveness, in ``[0, 1]``.
    :param weights: The signal weights.
    :return: The combined score in ``[0, 1]``.
    :raises ValueError: When a signal is not a finite non-``bool`` number in ``[0, 1]``.
    """
    for name, value in (("numeric", numeric), ("entity", entity), ("distinctiveness", distinctiveness)):
        if not _in_unit_interval(value):
            raise ValueError(f"salience signal {name} must be a finite number in [0, 1]")
    raw = weights.numeric * numeric + weights.entity * entity + weights.distinctiveness * distinctiveness
    # The weight sum may exceed 1.0 by the 1e-9 tolerance; clamping keeps [0, 1] and monotonicity.
    return min(1.0, max(0.0, round(raw, SCORE_DECIMALS)))


#: Every disposition :func:`trace_salience` can give a canonical claim (Story 05.0, decision X2).
DISPOSITIONS: Final[tuple[str, ...]] = ("selected", "duplicate", "below_floor", "document_cap", "total_cap")


@dataclass(frozen=True)
class ScoredClaim:
    """One claim with its salience signals, near-duplicate cluster and selection disposition.

    :ivar claim: The extracted claim.
    :ivar score: The combined ``[0, 1]`` salience score, rounded to :data:`SCORE_DECIMALS` places.
    :ivar numeric: The numeric density, in ``[0, 1]``.
    :ivar entity: The entity density, in ``[0, 1]``.
    :ivar distinctiveness: The corpus distinctiveness from clustering, in ``[0, 1]``.
    :ivar cluster_id: The canonical index of the smallest member of the claim's cluster.
    :ivar cluster_size: The number of canonical claims sharing ``cluster_id``, ``>= 1``.
    :ivar disposition: One of :data:`DISPOSITIONS`: why the claim was kept or dropped.
    """

    claim: Claim
    score: float
    numeric: float
    entity: float
    distinctiveness: float
    cluster_id: int
    cluster_size: int
    disposition: str


def _require_unit_number(name: str, value: object, *, open_low: bool = False) -> float:
    """Return ``value`` as a float when it is a finite non-``bool`` number in range.

    :param name: The parameter name used in the message.
    :param value: The candidate value.
    :param open_low: Whether ``0`` is excluded, giving ``(0, 1]`` instead of ``[0, 1]``.
    :return: The value as a ``float``.
    :raises ValueError: When the value is not a finite number in the range.
    """
    interval = "(0, 1]" if open_low else "[0, 1]"
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not _in_unit_interval(value):
        raise ValueError(f"{name} must be a finite number in {interval}")
    if open_low and value == 0:
        raise ValueError(f"{name} must be a finite number in {interval}")
    return float(value)


def require_dedup_threshold(value: object) -> float:
    """Return a valid clustering threshold as a ``float`` (the check :func:`trace_salience` runs).

    :param value: The candidate threshold.
    :return: The threshold, a finite number in ``(0, 1]``.
    :raises ValueError: When the value is a ``bool``, not a finite number, or out of range.
    """
    return _require_unit_number("dedup_threshold", value, open_low=True)


def _require_positive_int(name: str, value: object) -> int:
    """Return ``value`` when it is an ``int >= 1`` and not a ``bool``.

    :param name: The parameter name used in the message.
    :param value: The candidate value.
    :return: The value.
    :raises ValueError: When the value is not an ``int >= 1``.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an int >= 1")
    return value


def _canonical(claims: tuple[Claim, ...]) -> list[Claim]:
    """Drop claims with a blank sentence and sort the rest into the canonical order.

    :param claims: The claims in the caller's order.
    :return: The claims sorted by ``(path, paragraph_index, raw_sentence, raw_subject, raw_object)``.
    """
    kept = [claim for claim in claims if claim.raw_sentence.strip()]
    kept.sort(key=lambda c: (c.path, c.paragraph_index, c.raw_sentence, c.raw_subject, c.raw_object))
    return kept


def _score_canonical(
    canonical: list[Claim],
    *,
    weights: SalienceWeights,
    dedup_threshold: float,
) -> list[ScoredClaim]:
    """Cluster the canonical claims and score each one, index-aligned (step 2.3).

    Every entry carries the provisional disposition ``selected``; :func:`trace_salience` replaces
    it once the representatives, the floor and the caps are known.

    :param canonical: The claims in canonical order.
    :param weights: The signal weights.
    :param dedup_threshold: The clustering link threshold in ``(0, 1]``.
    :return: One :class:`ScoredClaim` per canonical claim, in canonical order.
    """
    # scikit-learn: imported only when claims exist (fixed literal, importlib tripwire allowlist).
    clustering = importlib.import_module("docsentinel.mining.clustering")

    clusters = clustering.cluster_near_duplicates([c.raw_sentence for c in canonical], threshold=dedup_threshold)
    sizes = clustering.cluster_sizes(clusters)
    scored: list[ScoredClaim] = []
    for claim, cluster, size in zip(canonical, clusters, sizes, strict=True):
        numeric = numeric_density(claim)
        entity = entity_density(claim)
        scored.append(
            ScoredClaim(
                claim=claim,
                score=combined_score(numeric, entity, cluster.distinctiveness, weights=weights),
                numeric=numeric,
                entity=entity,
                distinctiveness=cluster.distinctiveness,
                cluster_id=cluster.cluster_id,
                cluster_size=size,
                disposition="selected",
            )
        )
    return scored


def _representatives(scored: list[ScoredClaim]) -> list[int]:
    """Return the canonical position of the highest-scoring member of each cluster (step 2.4).

    Ties are broken by the smallest ``(path, paragraph_index, raw_sentence)``, then by the
    canonical position, so the choice is total.

    :param scored: The scored claims in canonical order.
    :return: One position per cluster, in ascending canonical order.
    """
    best: dict[int, int] = {}
    for index, entry in enumerate(scored):
        current = best.get(entry.cluster_id)
        if current is None or _representative_key(entry, index) < _representative_key(scored[current], current):
            best[entry.cluster_id] = index
    return sorted(best.values())


def _representative_key(entry: ScoredClaim, index: int) -> tuple[float, str, int, str, int]:
    """Return the sort key choosing a cluster's representative (smallest wins).

    :param entry: A scored claim.
    :param index: Its canonical position, the final tie-break.
    :return: ``(-score, path, paragraph_index, raw_sentence, index)``.
    """
    claim = entry.claim
    return (-entry.score, claim.path, claim.paragraph_index, claim.raw_sentence, index)


def _selection_key(entry: ScoredClaim) -> tuple[float, str, int, str]:
    """Return the T5 selection order key of a scored claim.

    :param entry: A scored claim.
    :return: ``(-score, path, paragraph_index, raw_sentence)``.
    """
    claim = entry.claim
    return (-entry.score, claim.path, claim.paragraph_index, claim.raw_sentence)


def _trace_key(entry: ScoredClaim) -> tuple[float, str, int, str, str, str]:
    """Return the trace order key; the T5 key of :func:`_selection_key` is its prefix.

    :param entry: A scored claim.
    :return: ``(-score, path, paragraph_index, raw_sentence, raw_subject, raw_object)``.
    """
    claim = entry.claim
    return (-entry.score, claim.path, claim.paragraph_index, claim.raw_sentence, claim.raw_subject, claim.raw_object)


def trace_salience(
    claims: tuple[Claim, ...],
    *,
    weights: SalienceWeights,
    dedup_threshold: float,
    min_salience: float,
    max_per_document: int,
    max_total: int,
) -> tuple[ScoredClaim, ...]:
    """Score, cluster and disposition every canonical claim (pure, no ``Config``).

    The steps are those of :func:`select_salient`: validate the numbers; drop claims with a blank
    sentence and sort the rest canonically, so the input order never matters; cluster
    near-duplicate sentences corpus-wide and score each claim; keep the highest-scoring member of
    each cluster; drop representatives below ``min_salience`` (a score equal to the floor
    survives); sort by ``(-score, path, paragraph_index, raw_sentence)``; keep at most
    ``max_per_document`` per path; keep the first ``max_total``. Nothing is discarded: each
    canonical claim is returned once, with the disposition ``duplicate`` (a cluster member that is
    not its representative), ``below_floor``, ``document_cap``, ``total_cap`` or ``selected``. The
    stage counts are logged at DEBUG, never claim text or paths.

    :param claims: Every extracted claim of the scan, in any order.
    :param weights: The signal weights.
    :param dedup_threshold: Link two sentences when their similarity is strictly greater, in
        ``(0, 1]``.
    :param min_salience: The inclusive score floor, in ``[0, 1]``.
    :param max_per_document: The most claims selected per ``path``, an ``int >= 1``.
    :param max_total: The most claims selected overall, an ``int >= 1``.
    :returns: Every canonical claim, sorted by (-score, path, paragraph_index, raw_sentence,
        raw_subject, raw_object); ties keep the canonical order. The ``selected`` subsequence
        equals :func:`select_salient` with the same arguments.
    :raises ValueError: For any numeric parameter out of range, or ``weights`` that is not a
        :class:`SalienceWeights`.
    """
    if not isinstance(weights, SalienceWeights):
        raise ValueError("weights must be a SalienceWeights")
    threshold = require_dedup_threshold(dedup_threshold)
    floor = _require_unit_number("min_salience", min_salience)
    per_document = _require_positive_int("max_per_document", max_per_document)
    total = _require_positive_int("max_total", max_total)

    canonical = _canonical(claims)
    scored = _score_canonical(canonical, weights=weights, dedup_threshold=threshold) if canonical else []
    dispositions = ["duplicate"] * len(scored)
    representatives = _representatives(scored)
    above_floor: list[int] = []
    for index in representatives:
        if scored[index].score >= floor:
            above_floor.append(index)
        else:
            dispositions[index] = "below_floor"
    # Stable sort over ascending canonical positions: T5 ties keep the canonical order.
    above_floor.sort(key=lambda index: _selection_key(scored[index]))

    per_path: dict[str, int] = {}
    capped: list[int] = []
    for index in above_floor:
        path = scored[index].claim.path
        if per_path.get(path, 0) < per_document:
            per_path[path] = per_path.get(path, 0) + 1
            capped.append(index)
        else:
            dispositions[index] = "document_cap"
    for rank, index in enumerate(capped):
        dispositions[index] = "selected" if rank < total else "total_cap"

    logger.debug(
        "salience: %d claim(s) in, %d cluster(s), %d above the floor, %d after the per-document cap, "
        "%d after the total cap",
        len(claims),
        len(representatives),
        len(above_floor),
        len(capped),
        min(len(capped), total),
    )
    traced = [replace(entry, disposition=disposition) for entry, disposition in zip(scored, dispositions, strict=True)]
    # Stable sort of the canonical order, so equal keys keep their canonical positions.
    traced.sort(key=_trace_key)
    return tuple(traced)


def select_salient(
    claims: tuple[Claim, ...],
    *,
    weights: SalienceWeights,
    dedup_threshold: float,
    min_salience: float,
    max_per_document: int,
    max_total: int,
) -> tuple[ScoredClaim, ...]:
    """Return the ``selected`` subsequence of :func:`trace_salience` (pure, no ``Config``).

    The order is the T5 order ``(-score, path, paragraph_index, raw_sentence)``: it is a prefix of
    the trace key, and two representatives never tie on it because identical sentences share a
    cluster.

    :param claims: Every extracted claim of the scan, in any order.
    :param weights: The signal weights.
    :param dedup_threshold: Link two sentences when their similarity is strictly greater, in
        ``(0, 1]``.
    :param min_salience: The inclusive score floor, in ``[0, 1]``.
    :param max_per_document: The most claims kept per ``path``, an ``int >= 1``.
    :param max_total: The most claims kept overall, an ``int >= 1``.
    :returns: One representative per cluster with score >= min_salience, sorted by
        (-score, path, paragraph_index, raw_sentence), at most max_per_document per
        path, then at most max_total overall.
    :raises ValueError: For any numeric parameter out of range, or ``weights`` that is not a
        :class:`SalienceWeights`.
    """
    traced = trace_salience(
        claims,
        weights=weights,
        dedup_threshold=dedup_threshold,
        min_salience=min_salience,
        max_per_document=max_per_document,
        max_total=max_total,
    )
    return tuple(entry for entry in traced if entry.disposition == "selected")
