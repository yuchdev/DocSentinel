"""Unit tests for ``docsentinel.mining.salience`` scoring (Milestone 0010 Story 02.0 Task 01).

Covers ``token_count``, ``numeric_density``, ``entity_density``, ``SalienceWeights`` validation and
``combined_score`` with hand-built ``Claim`` literals; no spaCy model and no vectorizer is used.
The Task 03 ``select_salient`` cases (representatives, floor, order, both caps, determinism) run
through the real clustering factory with inline ``Claim`` literals. The Story 05.0 Task 04 cases pin
``trace_salience``: every disposition, the cluster size, a total and input-order independent trace
order, the signal fields, and ``select_salient`` as its ``selected`` projection.
The ``DS302`` weight constants and constraints (a) to (d) are in
``tests/unit/test_fact_check_candidates.py``.
"""

from __future__ import annotations

import ast
import itertools
import json
import logging
import math
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

from docsentinel.mining import clustering, salience
from docsentinel.mining.claims import Claim
from docsentinel.mining.clustering import TextCluster
from docsentinel.mining.salience import (
    DISPOSITIONS,
    SCORE_DECIMALS,
    SalienceWeights,
    ScoredClaim,
    combined_score,
    entity_density,
    numeric_density,
    select_salient,
    token_count,
    trace_salience,
)

_EQUAL = SalienceWeights(numeric=0.3, entity=0.3, distinctiveness=0.4)


def _claim(raw_object: str, numbers: tuple[str, ...] = (), entities: tuple[str, ...] = ()) -> Claim:
    """Return a hand-built claim with the given object text, numbers and entities.

    :param raw_object: The object text.
    :param numbers: The object numbers.
    :param entities: The object entities.
    :return: The claim literal.
    """
    return Claim(
        subject_key="api",
        predicate_key="support",
        raw_subject="The API",
        raw_object=raw_object,
        raw_sentence=f"The API supports {raw_object}.",
        object_numbers=numbers,
        object_entities=entities,
        path="docs/a.md",
        paragraph_index=0,
    )


def test_token_count_is_whitespace_split():
    """
    [Unit] mining salience: verifies token_count counts whitespace-separated object tokens.

    Scenario:
        Given claims whose objects hold three tokens with mixed whitespace, and a blank object
        When token_count is called
        Then it returns 3 and 0

    Boundaries:
        - Focus: decision T3, a cheap whitespace count with no NLP pass
        - Fixtures/params: hand-built Claim literals
        - Scope: token_count only

    On failure, first check:
        - Whether token_count started re-tokenizing with spaCy
    """
    assert token_count(_claim("  version\t3.2 \n ships ")) == 3
    assert token_count(_claim("   ")) == 0


def test_densities_normal_case():
    """
    [Unit] mining salience: verifies numeric and entity density are a share of object tokens.

    Scenario:
        Given a four-token object with one number and two entities
        When numeric_density and entity_density are called
        Then they return 0.25 and 0.5

    Boundaries:
        - Focus: the two density formulas of decision T1
        - Fixtures/params: one hand-built Claim literal
        - Scope: density functions only

    On failure, first check:
        - Whether the denominator stopped being token_count(claim)
    """
    claim = _claim("Python 3.12 on Linux", numbers=("3.12",), entities=("Python", "Linux"))
    assert numeric_density(claim) == 0.25
    assert entity_density(claim) == 0.5


def test_densities_cap_at_one():
    """
    [Unit] mining salience: verifies a density never exceeds 1.0.

    Scenario:
        Given a one-token object carrying three numbers and two entities
        When the densities are computed
        Then both are exactly 1.0

    Boundaries:
        - Focus: the min(1.0, ...) cap
        - Fixtures/params: one hand-built Claim literal
        - Scope: density functions only

    On failure, first check:
        - Whether the min(1.0, ...) cap was removed
    """
    claim = _claim("1-2-3", numbers=("1", "2", "3"), entities=("A", "B"))
    assert numeric_density(claim) == 1.0
    assert entity_density(claim) == 1.0


def test_empty_object_scores_zero_without_raising():
    """
    [Unit] mining salience: verifies an empty raw_object gives density 0.0 and does not raise.

    Scenario:
        Given a claim with an empty raw_object and no numbers or entities
        When both densities are computed
        Then each is 0.0

    Boundaries:
        - Focus: the max(1, token_count) denominator guard
        - Fixtures/params: one hand-built Claim literal
        - Scope: density functions only

    On failure, first check:
        - Whether the max(1, ...) guard was dropped (ZeroDivisionError)
    """
    claim = _claim("")
    assert numeric_density(claim) == 0.0
    assert entity_density(claim) == 0.0


def test_empty_object_with_numbers_is_capped():
    """
    [Unit] mining salience: verifies an empty object with numbers still stays in [0, 1].

    Scenario:
        Given a claim whose raw_object is blank but whose numbers and entities are non-empty
        When both densities are computed
        Then each is 1.0 (denominator 1, then capped)

    Boundaries:
        - Focus: edge case where the extracted lists disagree with the object text
        - Fixtures/params: one hand-built Claim literal
        - Scope: density functions only

    On failure, first check:
        - Whether the cap or the denominator guard changed
    """
    claim = _claim(" ", numbers=("4", "5"), entities=("X",))
    assert numeric_density(claim) == 1.0
    assert entity_density(claim) == 1.0


def test_weights_accept_valid_values():
    """
    [Unit] mining salience: verifies SalienceWeights accepts valid weights, ints and boundary values.

    Scenario:
        Given weights (0.3, 0.3, 0.4), (1, 0, 0) and (0.1, 0.2, 0.7) with float rounding error
        When SalienceWeights is built
        Then no error is raised and the fields keep their values

    Boundaries:
        - Focus: the accept side of the validation, including int and the 1e-9 sum tolerance
        - Fixtures/params: none
        - Scope: SalienceWeights only

    On failure, first check:
        - Whether the sum check became an exact == comparison
    """
    assert SalienceWeights(0.3, 0.3, 0.4).distinctiveness == 0.4
    assert SalienceWeights(1, 0, 0).numeric == 1
    SalienceWeights(0.1, 0.2, 0.7)


@pytest.mark.parametrize(
    "weights",
    [
        (-0.1, 0.6, 0.5),
        (True, 0.0, 0.0),
        (0.5, False, 0.5),
        (math.nan, 0.5, 0.5),
        (math.inf, 0.0, 0.0),
        (1.5, -0.5, 0.0),
        (0.3, 0.3, 0.3),
        (0.5, 0.5, 0.5),
        ("0.3", 0.3, 0.4),
        (None, 0.6, 0.4),
    ],
    ids=["negative", "bool-true", "bool-false", "nan", "inf", "above-one", "sum-low", "sum-high", "str", "none"],
)
def test_weights_reject_invalid_values(weights: tuple[object, object, object]):
    """
    [Unit] mining salience: verifies SalienceWeights rejects an invalid weight with ValueError.

    Scenario:
        Given a negative, bool, non-finite, out-of-range or non-number weight, or a sum other than 1.0
        When SalienceWeights is built
        Then ValueError is raised

    Boundaries:
        - Focus: the reject side of the validation
        - Fixtures/params: one invalid triple per case
        - Scope: SalienceWeights only

    On failure, first check:
        - Whether bool slipped through the isinstance(int) check
    """
    with pytest.raises(ValueError):
        SalienceWeights(*weights)  # type: ignore[arg-type]


def test_weights_are_frozen():
    """
    [Unit] mining salience: verifies SalienceWeights is immutable.

    Scenario:
        Given a valid SalienceWeights
        When a field is assigned
        Then dataclasses.FrozenInstanceError (an AttributeError) is raised

    Boundaries:
        - Focus: validated weights cannot be edited afterwards
        - Fixtures/params: none
        - Scope: SalienceWeights only

    On failure, first check:
        - Whether frozen=True was dropped from the dataclass
    """
    with pytest.raises(AttributeError):
        _EQUAL.numeric = 0.9  # type: ignore[misc]


def test_combined_score_normal_case():
    """
    [Unit] mining salience: verifies combined_score is the weighted sum of the three signals.

    Scenario:
        Given signals 1/3, 1/3 and 1.0 with weights 0.3, 0.3, 0.4
        When combined_score is called
        Then it returns 0.6

    Boundaries:
        - Focus: the weighted-sum formula
        - Fixtures/params: none
        - Scope: combined_score only

    On failure, first check:
        - Whether a weight is applied to the wrong signal
    """
    assert combined_score(1 / 3, 1 / 3, 1.0, weights=_EQUAL) == 0.6


def test_combined_score_rounds_to_score_decimals():
    """
    [Unit] mining salience: verifies the score is rounded to SCORE_DECIMALS (6) places.

    Scenario:
        Given signals whose exact weighted sum has more than six decimals
        When combined_score is called
        Then the result equals round(sum, 6)

    Boundaries:
        - Focus: platform-stable sort keys
        - Fixtures/params: none
        - Scope: combined_score only

    On failure, first check:
        - Whether SCORE_DECIMALS changed or rounding was removed
    """
    assert SCORE_DECIMALS == 6
    value = combined_score(1 / 7, 2 / 9, 0.123456789, weights=_EQUAL)
    assert value == round(0.3 / 7 + 0.3 * 2 / 9 + 0.4 * 0.123456789, 6)
    assert value == round(value, 6)


def test_combined_score_bounds():
    """
    [Unit] mining salience: verifies all-zero signals score 0.0 and all-one signals score 1.0.

    Scenario:
        Given all signals at 0 and then all at 1, with several valid weights
        When combined_score is called
        Then the result is exactly 0.0 and exactly 1.0

    Boundaries:
        - Focus: the [0, 1] range, including the 1e-9 weight-sum tolerance
        - Fixtures/params: none
        - Scope: combined_score only

    On failure, first check:
        - Whether the final clamp was removed
    """
    for weights in (_EQUAL, SalienceWeights(0.1, 0.2, 0.7), SalienceWeights(1.0, 0.0, 0.0)):
        assert combined_score(0.0, 0.0, 0.0, weights=weights) == 0.0
        assert combined_score(1.0, 1.0, 1.0, weights=weights) == 1.0


@pytest.mark.parametrize("bad", [-0.01, 1.01, math.nan, math.inf, True, "0.5", None])
@pytest.mark.parametrize("position", [0, 1, 2])
def test_combined_score_rejects_out_of_range_signal(bad: object, position: int):
    """
    [Unit] mining salience: verifies combined_score rejects a signal outside [0, 1] with ValueError.

    Scenario:
        Given one signal that is negative, above one, non-finite, a bool or not a number
        When combined_score is called
        Then ValueError is raised

    Boundaries:
        - Focus: invalid input of every signal position
        - Fixtures/params: each bad value at each position
        - Scope: combined_score only

    On failure, first check:
        - Whether the signal range check skips one of the three signals
    """
    signals: list[object] = [0.5, 0.5, 0.5]
    signals[position] = bad
    with pytest.raises(ValueError):
        combined_score(*signals, weights=_EQUAL)  # type: ignore[arg-type]


def test_combined_score_is_monotonic_in_each_signal():
    """
    [Unit] mining salience: verifies the score never decreases when one signal increases.

    Scenario:
        Given a grid of signal values and several valid weights
        When one signal is raised while the other two stay fixed
        Then the combined score does not decrease

    Boundaries:
        - Focus: constraint (d) for arbitrary valid weights
        - Fixtures/params: 6-point grid per signal, three weight sets
        - Scope: combined_score only

    On failure, first check:
        - Whether a negative weight became possible or the clamp broke ordering
    """
    grid = (0.0, 0.1, 1 / 3, 0.5, 0.9, 1.0)
    for weights in (_EQUAL, SalienceWeights(0.1, 0.2, 0.7), SalienceWeights(0.0, 0.0, 1.0)):
        for base in itertools.product(grid, repeat=3):
            for position in range(3):
                for higher in grid:
                    if higher < base[position]:
                        continue
                    raised = list(base)
                    raised[position] = higher
                    assert combined_score(*raised, weights=weights) >= combined_score(*base, weights=weights)


def test_scoring_module_imports_no_heavy_or_engine_module():
    """
    [Unit] mining salience: verifies the scorer imports only the stdlib and Claim under TYPE_CHECKING.

    Scenario:
        Given the source of mining/salience.py
        When its module-level imports are parsed
        Then every runtime import is a stdlib module (logging for the Task 03 DEBUG stage counts,
            importlib for the lazy clustering load),
            Claim comes only from a TYPE_CHECKING block, mining.clustering is not imported at module
            level, and the source never names os.environ

    Boundaries:
        - Focus: Task 01 step 1 (no spaCy or scikit-learn at import, no Config, no environment);
            Task 03 step 2.9 adds the logger, whose records are checked for claim text separately
        - Fixtures/params: none
        - Scope: AST only

    On failure, first check:
        - Whether an import of mining.claims or mining.clustering moved to module level
    """
    source = Path(salience.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    runtime: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            runtime.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            runtime.append(node.module or "")
    assert set(runtime) <= {"__future__", "importlib", "logging", "math", "dataclasses", "typing"}
    assert "os.environ" not in source
    assert "getenv" not in source


#: The fixed DS302 dedup threshold (Story 02.0 decision T2).
_THRESHOLD = 0.92

#: A long sentence; ``_NEAR`` is about 0.943 similar to it, ``_FAR`` about 0.776 (see the
#: clustering tests, same real factory).
_BASE = (
    "the service stores uploaded invoices in regional buckets encrypted with customer managed "
    "keys rotated every ninety days by the scheduler"
)
_NEAR = _BASE + " automatically"
_FAR = _BASE.replace("ninety", "thirty").replace("regional", "central")

#: Unrelated sentences, far below the threshold from each other.
_UNRELATED = (
    "the cache expires entries after ten minutes",
    "the uploader retries failed parts three times",
    "the gateway rejects requests larger than eight megabytes",
    "the scheduler runs nightly compaction jobs at midnight",
    "the exporter writes parquet files into the archive bucket",
)


def _sc(
    sentence: str,
    *,
    path: str = "docs/a.md",
    paragraph: int = 0,
    raw_object: str = "3.2 Q4",
    numbers: tuple[str, ...] = ("3.2",),
    entities: tuple[str, ...] = ("Q4",),
    subject: str = "The API",
) -> Claim:
    """Return a claim literal for the selection tests.

    :param sentence: The raw sentence.
    :param path: The document path.
    :param paragraph: The paragraph index.
    :param raw_object: The object text.
    :param numbers: The object numbers.
    :param entities: The object entities.
    :param subject: The raw subject.
    :return: The claim literal.
    """
    return Claim(
        subject_key=subject.lower(),
        predicate_key="state",
        raw_subject=subject,
        raw_object=raw_object,
        raw_sentence=sentence,
        object_numbers=numbers,
        object_entities=entities,
        path=path,
        paragraph_index=paragraph,
    )


def _select(claims: tuple[Claim, ...], **overrides: object) -> tuple[ScoredClaim, ...]:
    """Run ``select_salient`` with the DS302 weights and threshold and permissive defaults.

    :param claims: The claims.
    :param overrides: Parameter overrides.
    :return: The selection.
    """
    params: dict[str, object] = {
        "weights": _EQUAL,
        "dedup_threshold": _THRESHOLD,
        "min_salience": 0.0,
        "max_per_document": 50,
        "max_total": 500,
    }
    params.update(overrides)
    return select_salient(claims, **params)  # type: ignore[arg-type]


def _key(entry: ScoredClaim) -> tuple[float, str, int, str]:
    """Return the T5 order key of an entry.

    :param entry: A scored claim.
    :return: ``(-score, path, paragraph_index, raw_sentence)``.
    """
    return (-entry.score, entry.claim.path, entry.claim.paragraph_index, entry.claim.raw_sentence)


def _generated_corpus(size: int = 240) -> tuple[Claim, ...]:
    """Return a deterministic corpus of mostly distinct claims over twelve documents.

    :param size: The number of claims.
    :return: The claims; some sentences exceed 1,000 characters.
    """
    words = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet")
    claims: list[Claim] = []
    for index in range(size):
        a, b, c = words[index % 10], words[(index // 10) % 10], words[(index // 100) % 10]
        sentence = f"Node {a}{b}{c} token{index} holds {index} shards in zone{index % 7}."
        if index % 37 == 0:
            sentence += " " + " ".join(f"filler{index}x{k}" for k in range(150))
        claims.append(
            _sc(
                sentence,
                path=f"docs/doc{index % 12:02d}.md",
                paragraph=index % 5,
                raw_object=f"{index} shards zone{index % 7}",
                numbers=(str(index),) if index % 3 else (),
                entities=(f"zone{index % 7}",) if index % 2 else (),
            )
        )
    return tuple(claims)


def test_select_salient_empty_corpus_returns_empty():
    """
    [Unit] select_salient: verifies an empty corpus, or one of blank sentences only, selects nothing.

    Scenario:
        Given no claims, then two claims whose raw_sentence is empty or whitespace
        When select_salient runs with valid numbers
        Then it returns () both times without error

    Boundaries:
        - Focus: Task 03 acceptance (empty corpus) and step 2.2 (blank sentences dropped)
        - Fixtures/params: inline Claim literals
        - Scope: select_salient

    On failure, first check:
        - The early return before clustering in select_salient
    """
    assert _select(()) == ()
    assert _select((_sc(""), _sc("   \n\t"))) == ()


def test_select_salient_near_duplicates_keep_the_higher_scoring_member():
    """
    [Unit] select_salient: verifies two sentences above 0.92 similarity give one candidate.

    Scenario:
        Given _BASE with a number only and _NEAR (about 0.943 similar) with a number and an entity
        When select_salient runs with the 0.92 threshold
        Then only the _NEAR claim survives, although _BASE sorts first canonically

    Boundaries:
        - Focus: Story 02.0 acceptance (dedup threshold), step 2.4 (highest score wins)
        - Fixtures/params: real clustering factory
        - Scope: select_salient

    On failure, first check:
        - _representatives comparing the score before the path/sentence tie-break
    """
    low = _sc(_BASE, entities=())
    high = _sc(_NEAR)
    result = _select((low, high))
    assert [entry.claim for entry in result] == [high]
    assert result[0].cluster_id == 0


def test_select_salient_claims_below_threshold_both_survive():
    """
    [Unit] select_salient: verifies two sentences below 0.92 similarity both survive the floor.

    Scenario:
        Given _BASE and _FAR (about 0.776 similar) and a floor of 0
        When select_salient runs
        Then both claims are returned, in separate clusters

    Boundaries:
        - Focus: Story 02.0 acceptance (dedup threshold, below side)
        - Fixtures/params: real clustering factory
        - Scope: select_salient

    On failure, first check:
        - The strict > threshold comparison in mining.clustering
    """
    result = _select((_sc(_BASE), _sc(_FAR)))
    assert len(result) == 2
    assert len({entry.cluster_id for entry in result}) == 2


def test_select_salient_representative_tie_breaks_on_path():
    """
    [Unit] select_salient: verifies equal-score cluster members resolve to the smallest path.

    Scenario:
        Given the same sentence and object in docs/b.md and docs/a.md, passed b first
        When select_salient runs
        Then the single representative is the docs/a.md claim

    Boundaries:
        - Focus: step 2.4 tie-break (path, paragraph_index, raw_sentence)
        - Fixtures/params: real clustering factory
        - Scope: select_salient

    On failure, first check:
        - The representative key order
    """
    first = _sc(_BASE, path="docs/b.md")
    second = _sc(_BASE, path="docs/a.md")
    result = _select((first, second))
    assert [entry.claim.path for entry in result] == ["docs/a.md"]


def test_select_salient_drops_trivial_claim_at_default_floor():
    """
    [Unit] select_salient: verifies a claim with no number, no entity and low distinctiveness is dropped.

    Scenario:
        Given _BASE and _FAR without numbers or entities (distinctiveness about 0.22)
        When select_salient runs with the default floor 0.5
        Then nothing is selected, while a floor of 0 keeps both

    Boundaries:
        - Focus: Story 02.0 acceptance (trivial claims dropped at fact_check_min_salience = 0.5)
        - Fixtures/params: real clustering factory
        - Scope: select_salient

    On failure, first check:
        - The floor comparison and the DS302 weights
    """
    claims = (_sc(_BASE, numbers=(), entities=()), _sc(_FAR, numbers=(), entities=()))
    assert _select(claims, min_salience=0.5) == ()
    assert len(_select(claims, min_salience=0.0)) == 2


def test_select_salient_floor_is_inclusive():
    """
    [Unit] select_salient: verifies a score equal to the floor survives and one just below is dropped.

    Scenario:
        Given one claim whose score s is read from an unfloored run
        When select_salient runs with min_salience = s and with s + 1e-6
        Then the claim survives at s and is dropped at s + 1e-6

    Boundaries:
        - Focus: step 2.5 (inclusive floor)
        - Fixtures/params: real clustering factory
        - Scope: select_salient

    On failure, first check:
        - Whether the floor uses > instead of >=
    """
    claim = _sc(_UNRELATED[0], raw_object="ten minutes later", numbers=("ten",), entities=())
    (entry,) = _select((claim,))
    assert 0.0 < entry.score < 1.0
    assert _select((claim,), min_salience=entry.score) == (entry,)
    assert _select((claim,), min_salience=min(1.0, entry.score + 1e-6)) == ()


def test_select_salient_per_document_cap_then_total_cap():
    """
    [Unit] select_salient: verifies the per-document cap runs before the total cap.

    Scenario:
        Given three high-scoring claims in docs/a.md and one lower-scoring claim in docs/b.md
        When select_salient runs with max_per_document = 1 and max_total = 2
        Then the result is a.md's best claim and then b.md's claim (a total-first cap would keep
            two a.md claims and the per-document cap would then leave one)

    Boundaries:
        - Focus: Story 02.0 acceptance (both caps, in order)
        - Fixtures/params: real clustering factory
        - Scope: select_salient

    On failure, first check:
        - The order of the two cap loops
    """
    a_claims = tuple(_sc(text, path="docs/a.md", paragraph=i) for i, text in enumerate(_UNRELATED[:3]))
    b_claim = _sc(_UNRELATED[3], path="docs/b.md", raw_object="many words in this object", entities=())
    result = _select((*a_claims, b_claim), max_per_document=1, max_total=2)
    assert [entry.claim.path for entry in result] == ["docs/a.md", "docs/b.md"]
    assert result[1].claim is b_claim
    capped = _select((*a_claims, b_claim), max_per_document=2)
    assert [entry.claim.path for entry in capped].count("docs/a.md") == 2


def test_select_salient_order_is_exactly_t5_and_deterministic():
    """
    [Unit] select_salient: verifies the order is (-score, path, paragraph_index, raw_sentence), stably.

    Scenario:
        Given unrelated claims over two documents with equal and different scores
        When select_salient runs twice, on the reversed input and on a shuffled input
        Then every result is equal, and equal to itself sorted by the T5 key

    Boundaries:
        - Focus: decision T5 and the determinism acceptance criterion
        - Fixtures/params: real clustering factory, a seeded shuffle
        - Scope: select_salient

    On failure, first check:
        - The canonical sort before clustering
    """
    claims = tuple(
        _sc(text, path=f"docs/{'ab'[i % 2]}.md", paragraph=i, entities=() if i % 3 else ("Q4",))
        for i, text in enumerate(_UNRELATED)
    )
    first = _select(claims)
    shuffled = list(claims)
    random.Random(7).shuffle(shuffled)
    assert first == _select(claims)
    assert first == _select(tuple(reversed(claims)))
    assert first == _select(tuple(shuffled))
    assert list(first) == sorted(first, key=_key)
    assert len(first) == len(claims)


def test_select_salient_generated_corpus_respects_both_caps():
    """
    [Unit] select_salient: verifies the caps over a generated corpus of 240 claims.

    Scenario:
        Given 240 generated claims over twelve documents
        When select_salient runs with the default caps 3 and 25 and a floor of 0
        Then at most 25 entries are returned, at most 3 per path, in T5 order, input-order independent

    Boundaries:
        - Focus: Task 03 acceptance (caps over >= 200 claims)
        - Fixtures/params: deterministic generated corpus
        - Scope: select_salient

    On failure, first check:
        - The per-document counter and the total slice
    """
    claims = _generated_corpus()
    result = _select(claims, max_per_document=3, max_total=25)
    assert len(result) == 25
    paths = [entry.claim.path for entry in result]
    assert max(paths.count(path) for path in set(paths)) <= 3
    assert list(result) == sorted(result, key=_key)
    assert result == _select(tuple(reversed(claims)), max_per_document=3, max_total=25)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("dedup_threshold", 0),
        ("dedup_threshold", 1.5),
        ("dedup_threshold", math.nan),
        ("dedup_threshold", True),
        ("min_salience", -0.1),
        ("min_salience", 1.01),
        ("min_salience", math.inf),
        ("min_salience", "0.5"),
        ("min_salience", False),
        ("max_per_document", 0),
        ("max_per_document", 2.0),
        ("max_per_document", True),
        ("max_total", -1),
        ("max_total", "25"),
        ("weights", (0.3, 0.3, 0.4)),
    ],
)
def test_select_salient_rejects_out_of_range_numbers(name: str, value: object):
    """
    [Unit] select_salient: verifies an out-of-range or wrongly typed parameter raises ValueError.

    Scenario:
        Given an empty corpus and one invalid parameter
        When select_salient is called
        Then ValueError is raised (never ConfigError), even though there is nothing to select

    Boundaries:
        - Focus: step 2.1 validation
        - Fixtures/params: one parameter per case
        - Scope: select_salient

    On failure, first check:
        - Whether validation runs before the empty-corpus shortcut
    """
    with pytest.raises(ValueError):
        _select((), **{name: value})


def test_select_salient_debug_log_has_counts_only(caplog: pytest.LogCaptureFixture):
    """
    [Unit] select_salient: verifies the DEBUG stage line logs counts, never claim text or paths.

    Scenario:
        Given two near-duplicate claims and one unrelated claim in a distinctive path
        When select_salient runs with DEBUG capture on docsentinel
        Then one stage line names 3 claims, 2 clusters, and no record holds a sentence or the path

    Boundaries:
        - Focus: step 2.9 (counts only)
        - Fixtures/params: caplog
        - Scope: select_salient and mining.clustering logging

    On failure, first check:
        - The arguments of the salience DEBUG call
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    path = "docs/secret-roadmap.md"
    _select((_sc(_BASE, path=path), _sc(_NEAR, path=path), _sc(_UNRELATED[0], path=path)), max_total=1)
    messages = [record.getMessage() for record in caplog.records]
    assert (
        "salience: 3 claim(s) in, 2 cluster(s), 2 above the floor, 2 after the per-document cap, 1 after the total cap"
    ) in messages
    text = "\n".join(messages)
    for secret in (path, "invoices", "cache expires"):
        assert secret not in text


def test_select_salient_patched_clustering_gives_exact_scores_and_cluster_ids(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] select_salient: verifies scores and cluster ids come exactly from the densities and the clusters.

    Scenario:
        Given three claims passed in reverse canonical order and a stub cluster_near_duplicates
            that puts canonical claims 0 and 1 in cluster 0 (distinctiveness 0.5) and claim 2 in
            cluster 2 (distinctiveness 1.0)
        When select_salient runs with the DS302 weights and threshold 0.92
        Then the stub saw the canonical-order sentences and threshold 0.92, cluster 0 keeps its
            higher-scoring member, and every score equals combined_score of the claim's signals

    Boundaries:
        - Focus: step 2.3 (index-aligned scoring), step 2.4 (representative by score), T1 weights
        - Fixtures/params: monkeypatched mining.clustering.cluster_near_duplicates
        - Scope: select_salient

    On failure, first check:
        - The canonical sort before clustering and the zip of claims with clusters
    """
    low = _sc("alpha sentence", path="docs/a.md", raw_object="one two three four", numbers=("1",), entities=())
    high = _sc("bravo sentence", path="docs/a.md", paragraph=1, raw_object="v1 Q4", numbers=("1",), entities=("Q4",))
    other = _sc("charlie sentence", path="docs/b.md", raw_object="x y", numbers=(), entities=("Z",))
    seen: list[tuple[list[str], float]] = []

    def _stub(texts: list[str], *, threshold: float) -> tuple[TextCluster, ...]:
        """Record the call and return fixed clusters."""
        seen.append((list(texts), threshold))
        return (TextCluster(0, 0.5), TextCluster(0, 0.5), TextCluster(2, 1.0))

    monkeypatch.setattr(clustering, "cluster_near_duplicates", _stub)
    result = _select((other, high, low))
    assert seen == [(["alpha sentence", "bravo sentence", "charlie sentence"], 0.92)]
    expected_high = combined_score(0.5, 0.5, 0.5, weights=_EQUAL)
    expected_other = combined_score(0.0, 0.5, 1.0, weights=_EQUAL)
    assert expected_high == 0.5
    assert expected_other == 0.55
    assert result == (
        ScoredClaim(
            claim=other,
            score=expected_other,
            numeric=0.0,
            entity=0.5,
            distinctiveness=1.0,
            cluster_id=2,
            cluster_size=1,
            disposition="selected",
        ),
        ScoredClaim(
            claim=high,
            score=expected_high,
            numeric=0.5,
            entity=0.5,
            distinctiveness=0.5,
            cluster_id=0,
            cluster_size=2,
            disposition="selected",
        ),
    )


def _mining_tree(name: str) -> ast.Module:
    """Return the parsed source of one mining module.

    :param name: The module file stem, e.g. ``salience``.
    :return: The parsed module.
    """
    return ast.parse((Path(salience.__file__).parent / f"{name}.py").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["salience", "clustering"])
def test_mining_module_has_no_network_environment_or_config_surface(name: str):
    """
    [Unit] mining salience/clustering: verifies no httpx, fact_check, config, os.environ or Config parameter.

    Scenario:
        Given the source of mining/salience.py or mining/clustering.py
        When every node is walked, including function-level and TYPE_CHECKING imports
        Then no import names httpx, docsentinel.fact_check or docsentinel.config, no expression
            reads os.environ or getenv, and no parameter or return annotation names Config

    Boundaries:
        - Focus: Story 02.0 acceptance (layering and banned imports), Task 04 step 5
        - Fixtures/params: one module per case
        - Scope: AST only

    On failure, first check:
        - A new import or a Config-typed helper added to the named module
    """
    tree = _mining_tree(name)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.append(module)
            imported.extend(f"{module}.{alias.name}" for alias in node.names)
    for module in imported:
        assert module.split(".")[0] != "httpx", module
        assert not module.startswith(("docsentinel.fact_check", "docsentinel.config")), module
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"environ", "getenv", "environb"}, ast.unparse(node)
        if isinstance(node, ast.Name):
            assert node.id not in {"environ", "getenv"}, node.id
    annotations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            arguments = node.args
            for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs):
                if arg.annotation is not None:
                    annotations.append(ast.unparse(arg.annotation))
            for arg in (arguments.vararg, arguments.kwarg):
                if arg is not None and arg.annotation is not None:
                    annotations.append(ast.unparse(arg.annotation))
            if node.returns is not None:
                annotations.append(ast.unparse(node.returns))
    assert annotations
    assert not [text for text in annotations if re.search(r"\bConfig\b", text)]


_DETERMINISM_PROBE = """
import json
from docsentinel.mining.claims import Claim
from docsentinel.mining.salience import SalienceWeights, select_salient

base = ("the service stores uploaded invoices in regional buckets encrypted with customer managed "
        "keys rotated every ninety days by the scheduler")
sentences = {
    base, base + " automatically", base.replace("ninety", "thirty").replace("regional", "central"),
    "the cache expires entries after ten minutes", "the uploader retries failed parts three times",
    "the gateway rejects requests larger than eight megabytes",
    "the scheduler runs nightly compaction jobs at midnight",
}
claims = {
    Claim(subject_key="s", predicate_key="p", raw_subject="S", raw_object=f"{len(text)} Q{i % 3}",
          raw_sentence=text, object_numbers=(str(len(text)),) if i % 2 else (),
          object_entities=(f"Q{i % 3}",), path=f"docs/{'abc'[i % 3]}.md", paragraph_index=i % 2)
    for i, text in enumerate(sorted(sentences))
} | {
    Claim(subject_key="s", predicate_key="p", raw_subject="S", raw_object="7 Q1", raw_sentence=text,
          object_numbers=("7",), object_entities=("Q1",), path="docs/d.md", paragraph_index=3)
    for text in sentences
}
result = select_salient(tuple(claims), weights=SalienceWeights(0.3, 0.3, 0.4), dedup_threshold=0.92,
                        min_salience=0.0, max_per_document=2, max_total=5)
print(json.dumps([[e.score, e.cluster_id, e.claim.path, e.claim.paragraph_index, e.claim.raw_sentence]
                  for e in result]))
"""


def test_select_salient_output_is_byte_identical_across_interpreters():
    """
    [Unit] select_salient: verifies the selection is byte-for-byte identical across two fresh runs.

    Scenario:
        Given a probe that feeds select_salient a tuple built from a set of claims, so the input
            order follows the string hash seed
        When the probe runs in two fresh interpreters with PYTHONHASHSEED 0 and 4242
        Then both stdout byte strings are equal and non-trivial (five entries, near-duplicates collapsed)

    Boundaries:
        - Focus: Story 02.0 acceptance (determinism across two runs, byte-for-byte)
        - Fixtures/params: subprocess with a minimal, explicitly built environment (none inherited)
        - Scope: select_salient through the real clustering factory

    On failure, first check:
        - A set or dict iteration order leaking into the canonical sort, cluster ids or caps
    """
    outputs: list[bytes] = []
    for seed in ("0", "4242"):
        env = {"PYTHONHASHSEED": seed, "DOCSENTINEL_SETTINGS": "off"}
        completed = subprocess.run(
            [sys.executable, "-c", _DETERMINISM_PROBE], capture_output=True, env=env, check=True, timeout=120
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1]
    entries = json.loads(outputs[0])
    assert len(entries) == 5
    assert len({entry[4] for entry in entries}) == 5
    assert [entry[0] for entry in entries] == sorted((entry[0] for entry in entries), reverse=True)


def _trace(claims: tuple[Claim, ...], **overrides: object) -> tuple[ScoredClaim, ...]:
    """Run ``trace_salience`` with the same defaults as :func:`_select`.

    :param claims: The claims.
    :param overrides: Parameter overrides.
    :return: The trace.
    """
    params: dict[str, object] = {
        "weights": _EQUAL,
        "dedup_threshold": _THRESHOLD,
        "min_salience": 0.0,
        "max_per_document": 50,
        "max_total": 500,
    }
    params.update(overrides)
    return trace_salience(claims, **params)  # type: ignore[arg-type]


def _disposition_corpus() -> tuple[Claim, ...]:
    """Return a corpus in which each of the five dispositions occurs with tight caps.

    ``a.md`` holds a near-duplicate pair plus two unrelated salient claims, ``b.md`` one salient
    claim and one claim without numbers or entities, ``c.md`` one salient claim.

    :return: The claims.
    """
    return (
        _sc(_BASE, path="docs/a.md", paragraph=0, entities=()),
        _sc(_NEAR, path="docs/a.md", paragraph=1),
        _sc(_UNRELATED[0], path="docs/a.md", paragraph=2),
        _sc(_UNRELATED[1], path="docs/a.md", paragraph=3),
        _sc(_UNRELATED[2], path="docs/b.md", paragraph=0),
        _sc(_UNRELATED[3], path="docs/b.md", paragraph=1, raw_object="nightly jobs", numbers=(), entities=()),
        _sc(_UNRELATED[4], path="docs/c.md", paragraph=0),
    )


def test_trace_salience_reaches_every_disposition_for_its_reason():
    """
    [Unit] trace_salience: verifies each disposition is reachable and assigned for the documented reason.

    Scenario:
        Given a near-duplicate pair, a claim with neither number nor entity, three salient claims in one
            document and two in others
        When trace_salience runs with a floor of 0.5, max_per_document 2 and max_total 3
        Then the lower-scoring pair member is duplicate, the bare claim below_floor, the pair's
            representative (third in a.md) document_cap, the c.md claim total_cap, and three are selected

    Boundaries:
        - Focus: Story 05.0 Task 04 step 1 (every disposition reachable)
        - Fixtures/params: real clustering, inline Claim literals
        - Scope: trace_salience

    On failure, first check:
        - The order of the floor, per-document cap and total cap passes in trace_salience
    """
    claims = _disposition_corpus()
    trace = _trace(claims, min_salience=0.5, max_per_document=2, max_total=3)
    by_sentence = {entry.claim.raw_sentence: entry.disposition for entry in trace}
    assert {entry.disposition for entry in trace} == set(DISPOSITIONS)
    assert len(trace) == len(claims)
    assert by_sentence == {
        _UNRELATED[0]: "selected",
        _UNRELATED[1]: "selected",
        _UNRELATED[2]: "selected",
        _UNRELATED[4]: "total_cap",
        _NEAR: "document_cap",
        _BASE: "duplicate",
        _UNRELATED[3]: "below_floor",
    }
    assert [entry.claim.raw_sentence for entry in trace] == [
        _UNRELATED[0],
        _UNRELATED[1],
        _UNRELATED[2],
        _UNRELATED[4],
        _NEAR,
        _BASE,
        _UNRELATED[3],
    ]


def test_trace_salience_cluster_size_of_a_three_member_cluster():
    """
    [Unit] trace_salience: verifies three copies of one sentence form one cluster of size 3.

    Scenario:
        Given the same sentence in three documents and two unrelated sentences
        When trace_salience runs
        Then the three copies share one cluster_id and report cluster_size 3, exactly one is not a
            duplicate, and the unrelated claims report cluster_size 1

    Boundaries:
        - Focus: Story 05.0 Task 04 step 1 (cluster_size)
        - Fixtures/params: real clustering
        - Scope: trace_salience, clustering.cluster_sizes

    On failure, first check:
        - cluster_sizes and its index alignment with the canonical order
    """
    copies = tuple(_sc(_BASE, path=f"docs/{name}.md") for name in ("c", "a", "b"))
    others = (_sc(_UNRELATED[0], path="docs/a.md", paragraph=1), _sc(_UNRELATED[1], path="docs/b.md", paragraph=1))
    trace = _trace((*copies, *others))
    members = [entry for entry in trace if entry.claim.raw_sentence == _BASE]
    assert [entry.cluster_size for entry in members] == [3, 3, 3]
    assert len({entry.cluster_id for entry in members}) == 1
    assert sorted(entry.disposition for entry in members) == ["duplicate", "duplicate", "selected"]
    assert [e.claim.path for e in members if e.disposition == "selected"] == ["docs/a.md"]
    assert [entry.cluster_size for entry in trace if entry.claim.raw_sentence != _BASE] == [1, 1]


def test_trace_salience_order_is_total_and_input_order_independent():
    """
    [Unit] trace_salience: verifies the trace order is the total documented key, identical for shuffled input.

    Scenario:
        Given the disposition corpus plus equal-score claims differing only in subject or object
        When trace_salience runs on the input, its reverse and five seeded shuffles
        Then every run returns the same tuple, sorted by (-score, path, paragraph_index, raw_sentence,
            raw_subject, raw_object), with no two entries sharing that key

    Boundaries:
        - Focus: Story 05.0 Task 04 step 1 (trace order is total and stable)
        - Fixtures/params: seeded random shuffles
        - Scope: trace_salience

    On failure, first check:
        - _trace_key and the canonical sort in _canonical
    """
    twins = (
        _sc(_UNRELATED[2], path="docs/d.md", subject="The CLI"),
        _sc(_UNRELATED[2], path="docs/d.md", subject="The API"),
        _sc(_UNRELATED[2], path="docs/d.md", raw_object="3.2 Q5"),
    )
    claims = (*_disposition_corpus(), *twins)
    first = _trace(claims, min_salience=0.5, max_per_document=2, max_total=3)
    runs = [_trace(tuple(reversed(claims)), min_salience=0.5, max_per_document=2, max_total=3)]
    for seed in range(5):
        shuffled = list(claims)
        random.Random(seed).shuffle(shuffled)
        runs.append(_trace(tuple(shuffled), min_salience=0.5, max_per_document=2, max_total=3))
    assert all(run == first for run in runs)
    keys = [
        (-e.score, e.claim.path, e.claim.paragraph_index, e.claim.raw_sentence, e.claim.raw_subject, e.claim.raw_object)
        for e in first
    ]
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys)


def test_trace_salience_signal_fields_equal_their_sources(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] trace_salience: verifies numeric/entity equal the density functions and distinctiveness the clustering value.

    Scenario:
        Given the disposition corpus and a spy recording what cluster_near_duplicates returns
        When trace_salience runs
        Then each entry's numeric and entity equal numeric_density/entity_density of its claim, its
            distinctiveness and cluster_id equal the recorded TextCluster, and the score recombines

    Boundaries:
        - Focus: Story 05.0 Task 04 step 1 (signal fields)
        - Fixtures/params: spy around the real clustering factory
        - Scope: trace_salience, _score_canonical

    On failure, first check:
        - Whether _score_canonical stores a different value than it scores
    """
    recorded: dict[str, TextCluster] = {}
    real = clustering.cluster_near_duplicates

    def spy(texts: list[str], **kwargs: object) -> tuple[TextCluster, ...]:
        """Delegate and record each text's cluster.

        :param texts: The sentences.
        :param kwargs: The clustering keywords.
        :return: The real clusters.
        """
        clusters = tuple(real(texts, **kwargs))  # type: ignore[arg-type]
        recorded.update(zip(texts, clusters, strict=True))
        return clusters

    monkeypatch.setattr(clustering, "cluster_near_duplicates", spy)
    trace = _trace(_disposition_corpus())
    assert len(recorded) == len(trace)
    for entry in trace:
        assert entry.numeric == numeric_density(entry.claim)
        assert entry.entity == entity_density(entry.claim)
        assert entry.distinctiveness == recorded[entry.claim.raw_sentence].distinctiveness
        assert entry.cluster_id == recorded[entry.claim.raw_sentence].cluster_id
        assert entry.score == combined_score(entry.numeric, entry.entity, entry.distinctiveness, weights=_EQUAL)


#: The claim sets and parameters of every ``select_salient`` case above, for the projection test.
_PROJECTION_CASES: dict[str, tuple[tuple[Claim, ...], dict[str, object]]] = {
    "empty": ((), {}),
    "blank-only": ((_sc(""), _sc("   \n\t")), {}),
    "near-duplicates": ((_sc(_BASE, entities=()), _sc(_NEAR)), {}),
    "below-threshold": ((_sc(_BASE), _sc(_FAR)), {}),
    "tie-break-path": ((_sc(_BASE, path="docs/b.md"), _sc(_BASE, path="docs/a.md")), {}),
    "trivial-floor": (
        (_sc(_BASE, numbers=(), entities=()), _sc(_FAR, numbers=(), entities=())),
        {"min_salience": 0.5},
    ),
    "floor-inclusive": (
        (_sc(_UNRELATED[0], raw_object="ten minutes later", numbers=("ten",), entities=()),),
        {"min_salience": 1.0},
    ),
    "caps": (
        (
            *(_sc(text, path="docs/a.md", paragraph=i) for i, text in enumerate(_UNRELATED[:3])),
            _sc(_UNRELATED[3], path="docs/b.md", raw_object="many words in this object", entities=()),
        ),
        {"max_per_document": 1, "max_total": 2},
    ),
    "order": (
        tuple(
            _sc(text, path=f"docs/{'ab'[i % 2]}.md", paragraph=i, entities=() if i % 3 else ("Q4",))
            for i, text in enumerate(_UNRELATED)
        ),
        {},
    ),
    "dispositions": (_disposition_corpus(), {"min_salience": 0.5, "max_per_document": 2, "max_total": 3}),
    "generated-240": (_generated_corpus(), {"max_per_document": 3, "max_total": 25}),
    "generated-240-floor": (_generated_corpus(), {"min_salience": 0.5, "max_per_document": 2, "max_total": 40}),
}


@pytest.mark.parametrize("case", sorted(_PROJECTION_CASES))
def test_select_salient_is_the_selected_projection_of_the_trace(case: str):
    """
    [Unit] select_salient: verifies it equals the ``selected`` subsequence of trace_salience, in order.

    Scenario:
        Given the claims and parameters of every select_salient case and of the 240-claim generated corpus
        When both functions run with the same arguments
        Then select_salient equals the trace entries whose disposition is selected, in trace order, and
            every non-blank claim appears in the trace exactly once

    Boundaries:
        - Focus: Story 05.0 acceptance (select_salient == selected projection), decision X2
        - Fixtures/params: one parameter set per existing case
        - Scope: select_salient, trace_salience

    On failure, first check:
        - Whether select_salient stopped delegating to trace_salience
    """
    claims, overrides = _PROJECTION_CASES[case]
    trace = _trace(claims, **overrides)
    assert _select(claims, **overrides) == tuple(entry for entry in trace if entry.disposition == "selected")
    assert len(trace) == sum(1 for claim in claims if claim.raw_sentence.strip())
    assert len(_generated_corpus()) >= 200
