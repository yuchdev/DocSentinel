"""Unit tests for the ``DS302`` salience weight constants (Milestone 0010 Story 02.0 Task 01).

Pins constraints (a) to (d) of ``docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/
01-salience-scoring.md`` on ``_W_NUMERIC``, ``_W_ENTITY`` and ``_W_DISTINCT`` in
``detectors/fact_check.py``, with hand-built ``Claim`` literals, and the Task 03
``select_candidates`` wrapper: ``ConfigError`` re-validation, the policy constants, the 1,000-code-point
text bound and order preservation. Story 05.0 Task 04 adds ``SelectionPolicy``/``DS302_POLICY``,
``select_candidates(policy=)``, the ``CandidateClaim`` signal fields and the exact
``collect_candidates`` signature.
"""

from __future__ import annotations

import dataclasses
import inspect
import itertools
import math
import subprocess
import sys

import pytest

from docsentinel.config import Config, ConfigError
from docsentinel.detectors import fact_check
from docsentinel.mining import salience
from docsentinel.mining.claims import Claim
from docsentinel.mining.salience import (
    SalienceWeights,
    ScoredClaim,
    combined_score,
    entity_density,
    numeric_density,
    select_salient,
)

#: The default ``fact_check_min_salience`` floor the constraints are stated against.
_DEFAULT_FLOOR = 0.5


def _weights() -> SalienceWeights:
    """Return the DS302 weights built from the detector's constants."""
    return SalienceWeights(fact_check._W_NUMERIC, fact_check._W_ENTITY, fact_check._W_DISTINCT)


def _claim(raw_object: str, numbers: tuple[str, ...] = (), entities: tuple[str, ...] = ()) -> Claim:
    """Return a hand-built claim with the given object text, numbers and entities.

    :param raw_object: The object text.
    :param numbers: The object numbers.
    :param entities: The object entities.
    :return: The claim literal.
    """
    return Claim(
        subject_key="release",
        predicate_key="ship",
        raw_subject="The release",
        raw_object=raw_object,
        raw_sentence=f"The release ships {raw_object}.",
        object_numbers=numbers,
        object_entities=entities,
        path="docs/release.md",
        paragraph_index=2,
    )


def test_default_floor_matches_config():
    """
    [Unit] DS302 weights: verifies the constraints are stated against the real default floor.

    Scenario:
        Given a default Config
        When fact_check_min_salience is read
        Then it equals 0.5

    Boundaries:
        - Focus: constraints (b) and (c) refer to the shipped default
        - Fixtures/params: none
        - Scope: Config default only

    On failure, first check:
        - Whether the default floor changed without re-checking the weights
    """
    assert Config().fact_check_min_salience == _DEFAULT_FLOOR


def test_weights_are_plain_floats_with_fixed_values():
    """
    [Unit] DS302 weights: verifies the constants are plain floats 0.3, 0.3 and 0.4.

    Scenario:
        Given detectors/fact_check.py
        When the three weight constants are read
        Then they are floats with the specified values

    Boundaries:
        - Focus: Task 01 step 6 (plain floats, not a SalienceWeights at import time)
        - Fixtures/params: none
        - Scope: module constants only

    On failure, first check:
        - Whether a constant was turned into a SalienceWeights or made configurable
    """
    values = (fact_check._W_NUMERIC, fact_check._W_ENTITY, fact_check._W_DISTINCT)
    assert all(type(value) is float for value in values)
    assert values == (0.3, 0.3, 0.4)


def test_constraint_a_weights_sum_to_one():
    """
    [Unit] DS302 weights: verifies constraint (a), the weights build a valid SalienceWeights.

    Scenario:
        Given the three DS302 weight constants
        When SalienceWeights is built from them
        Then no ValueError is raised and the sum is 1.0 within 1e-9

    Boundaries:
        - Focus: constraint (a)
        - Fixtures/params: none
        - Scope: constants and SalienceWeights validation

    On failure, first check:
        - Whether one constant was changed without rebalancing the others
    """
    weights = _weights()
    assert abs(weights.numeric + weights.entity + weights.distinctiveness - 1.0) <= 1e-9


def test_constraint_b_distinctiveness_alone_cannot_reach_default_floor():
    """
    [Unit] DS302 weights: verifies constraint (b), distinctiveness alone stays below 0.5.

    Scenario:
        Given a claim with no numbers and no entities and full distinctiveness 1.0
        When it is scored with the DS302 weights
        Then the score is below the default floor 0.5, but reaches a lowered floor of 0.4

    Boundaries:
        - Focus: constraint (b) and decision T6
        - Fixtures/params: one hand-built Claim literal
        - Scope: scoring functions with the DS302 weights

    On failure, first check:
        - Whether _W_DISTINCT was raised to 0.5 or more
    """
    assert fact_check._W_DISTINCT < _DEFAULT_FLOOR
    claim = _claim("the stable channel")
    score = combined_score(numeric_density(claim), entity_density(claim), 1.0, weights=_weights())
    assert score < _DEFAULT_FLOOR
    assert score >= 0.4


def test_constraint_c_short_distinctive_claim_reaches_floor():
    """
    [Unit] DS302 weights: verifies constraint (c), a short distinctive numeric/entity claim scores >= 0.5.

    Scenario:
        Given a three-token object with one number and one entity and distinctiveness 1.0
        When it is scored with the DS302 weights
        Then the score is 0.6, at least the default floor

    Boundaries:
        - Focus: constraint (c)
        - Fixtures/params: one hand-built Claim literal
        - Scope: scoring functions with the DS302 weights

    On failure, first check:
        - Whether the numeric or entity weight was lowered too far
    """
    claim = _claim("version 3.2 Q4", numbers=("3.2",), entities=("Q4",))
    score = combined_score(numeric_density(claim), entity_density(claim), 1.0, weights=_weights())
    assert score >= _DEFAULT_FLOOR
    assert score == 0.6


def test_constraint_d_score_is_monotonic_in_each_signal():
    """
    [Unit] DS302 weights: verifies constraint (d), the score is monotonic in each signal.

    Scenario:
        Given a grid of signal values and the DS302 weights
        When one signal is raised while the other two stay fixed
        Then the combined score does not decrease

    Boundaries:
        - Focus: constraint (d) for the shipped weights
        - Fixtures/params: 5-point grid per signal
        - Scope: combined_score with the DS302 weights

    On failure, first check:
        - Whether a constant became negative
    """
    weights = _weights()
    grid = (0.0, 0.25, 1 / 3, 0.75, 1.0)
    for base in itertools.product(grid, repeat=3):
        for position in range(3):
            for higher in grid:
                if higher < base[position]:
                    continue
                raised = list(base)
                raised[position] = higher
                assert combined_score(*raised, weights=weights) >= combined_score(*base, weights=weights)


def _numbered(index: int, *, path: str = "docs/release.md", sentence: str = "") -> Claim:
    """Return a distinct, salient claim literal.

    :param index: Makes the sentence and object unique.
    :param path: The document path.
    :param sentence: The raw sentence; a generated unique one when empty.
    :return: The claim literal.
    """
    return Claim(
        subject_key="release",
        predicate_key="ship",
        raw_subject="The release",
        raw_object=f"{index} Q{index}",
        raw_sentence=sentence or f"Release train{index} ships build{index} in quarter{index}.",
        object_numbers=(str(index),),
        object_entities=(f"Q{index}",),
        path=path,
        paragraph_index=index,
    )


def _ds302_selection(claims: tuple[Claim, ...], config: Config) -> tuple[ScoredClaim, ...]:
    """Return select_salient with the DS302 constants and the config's selection values.

    :param claims: The claims.
    :param config: The configuration.
    :return: The mining-layer selection.
    """
    return select_salient(
        claims,
        weights=_weights(),
        dedup_threshold=fact_check._DEDUP_THRESHOLD,
        min_salience=config.fact_check_min_salience,
        max_per_document=config.fact_check_max_claims_per_document,
        max_total=config.fact_check_max_claims_total,
    )


def test_dedup_threshold_is_fixed_policy_constant():
    """
    [Unit] select_candidates: verifies the dedup threshold is the plain float 0.92 and not a Config field.

    Scenario:
        Given detectors/fact_check.py and Config
        When _DEDUP_THRESHOLD and the Config fields are read
        Then the constant is 0.92 and no Config field names a dedup threshold or a weight

    Boundaries:
        - Focus: decision T2 and the Security notes (not configurable)
        - Fixtures/params: none
        - Scope: module constant and Config fields

    On failure, first check:
        - Whether a dedup or weight option was added to Config
    """
    assert type(fact_check._DEDUP_THRESHOLD) is float
    assert fact_check._DEDUP_THRESHOLD == 0.92
    names = {field.name for field in dataclasses.fields(Config)}
    assert not {name for name in names if "dedup" in name or "weight" in name}


def test_select_candidates_empty_corpus_returns_empty():
    """
    [Unit] select_candidates: verifies no claims and a default Config select nothing.

    Scenario:
        Given no claims and Config()
        When select_candidates runs
        Then it returns ()

    Boundaries:
        - Focus: Task 03 acceptance (empty corpus)
        - Fixtures/params: none
        - Scope: select_candidates

    On failure, first check:
        - The re-validation of the default values
    """
    assert fact_check.select_candidates((), Config()) == ()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("fact_check_max_claims_per_document", 0),
        ("fact_check_max_claims_per_document", 10_000),
        ("fact_check_max_claims_total", 0),
        ("fact_check_max_claims_total", 10_000),
        ("fact_check_max_claims_total", True),
        ("fact_check_min_salience", 1.5),
        ("fact_check_min_salience", float("nan")),
        ("fact_check_min_salience", "0.5"),
    ],
)
def test_select_candidates_rejects_invalid_injected_config_before_mining(
    name: str, value: object, monkeypatch: pytest.MonkeyPatch
):
    """
    [Unit] select_candidates: verifies an injected out-of-range selection value is a ConfigError.

    Scenario:
        Given an injected Config with one invalid selection value and a spy on select_salient
        When select_candidates runs on one claim
        Then ConfigError is raised and select_salient is never called

    Boundaries:
        - Focus: Task 03 step 4.1 (fail closed, before mining)
        - Fixtures/params: one value per case, monkeypatched select_salient
        - Scope: select_candidates

    On failure, first check:
        - Whether validation still runs before the lazy import
    """
    calls: list[object] = []
    monkeypatch.setattr(salience, "trace_salience", lambda *a, **k: calls.append(k) or ())
    config = dataclasses.replace(Config(), **{name: value})
    with pytest.raises(ConfigError):
        fact_check.select_candidates((_numbered(1),), config)
    assert calls == []


def test_select_candidates_passes_policy_constants_and_ignores_time_budget(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] select_candidates: verifies the DS302 constants and the three config values reach select_salient.

    Scenario:
        Given a Config with floor 0.25, caps 2 and 7 and an invalid time budget of 0
        When select_candidates runs with a spy on select_salient
        Then the spy sees the DS302 weights, 0.92 and those three values, and no error is raised

    Boundaries:
        - Focus: Task 03 steps 4.3 and 4.5 (owner ruling Q3: time budget not read here)
        - Fixtures/params: monkeypatched select_salient
        - Scope: select_candidates

    On failure, first check:
        - Whether select_candidates started validating fact_check_time_budget_seconds
    """
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(salience, "trace_salience", lambda claims, **kw: seen.append(kw) or ())
    config = dataclasses.replace(
        Config(),
        fact_check_min_salience=0.25,
        fact_check_max_claims_per_document=2,
        fact_check_max_claims_total=7,
        fact_check_time_budget_seconds=0,
    )
    assert fact_check.select_candidates((_numbered(1),), config) == ()
    assert seen == [
        {
            "weights": SalienceWeights(numeric=0.3, entity=0.3, distinctiveness=0.4),
            "dedup_threshold": 0.92,
            "min_salience": 0.25,
            "max_per_document": 2,
            "max_total": 7,
        }
    ]


def test_select_candidates_preserves_select_salient_order_exactly(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] select_candidates: verifies the wrapper never re-sorts, filters or truncates the mining output.

    Scenario:
        Given a stub select_salient returning three entries in a deliberately non-T5 order, one
            with a score below the configured floor
        When select_candidates runs
        Then the candidates carry the same claims and scores in exactly that order

    Boundaries:
        - Focus: Task 03 step 4.4
        - Fixtures/params: monkeypatched select_salient
        - Scope: select_candidates mapping

    On failure, first check:
        - Any sort or filter added to the mapping
    """
    signals = {"numeric": 0.0, "entity": 0.0, "distinctiveness": 0.0, "cluster_size": 1, "disposition": "selected"}
    entries = (
        ScoredClaim(claim=_numbered(3, path="docs/z.md"), score=0.1, cluster_id=2, **signals),
        ScoredClaim(claim=_numbered(1), score=0.9, cluster_id=0, **signals),
        ScoredClaim(claim=_numbered(2, path="docs/a.md"), score=0.5, cluster_id=1, **signals),
    )
    # Story 05.0: select_candidates projects the trace_salience trace (decision X2).
    monkeypatch.setattr(salience, "trace_salience", lambda claims, **kw: entries)
    result = fact_check.select_candidates((), Config())
    assert [(c.claim, c.score) for c in result] == [(e.claim, e.score) for e in entries]


def test_select_candidates_matches_real_select_salient_order():
    """
    [Unit] select_candidates: verifies the real wrapper returns the select_salient order and is deterministic.

    Scenario:
        Given ten distinct salient claims over two documents and a permissive injected Config
        When select_candidates runs twice and on the reversed input
        Then all three results are equal and map one-to-one, in order, onto select_salient's output

    Boundaries:
        - Focus: Task 03 acceptance (determinism, order preserved)
        - Fixtures/params: real clustering factory
        - Scope: select_candidates and select_salient

    On failure, first check:
        - Whether the wrapper passes the config values unchanged
    """
    claims = tuple(_numbered(i, path=f"docs/{'ab'[i % 2]}.md") for i in range(10))
    config = dataclasses.replace(Config(), fact_check_min_salience=0.0, fact_check_max_claims_per_document=50)
    result = fact_check.select_candidates(claims, config)
    assert result == fact_check.select_candidates(claims, config)
    assert result == fact_check.select_candidates(tuple(reversed(claims)), config)
    expected = _ds302_selection(claims, config)
    assert [(c.claim, c.score) for c in result] == [(e.claim, e.score) for e in expected]
    assert len(result) == 10


def test_select_candidates_text_is_stripped_and_bounded():
    """
    [Unit] select_candidates: verifies text is the stripped sentence cut to 1,000 code points.

    Scenario:
        Given a padded short sentence and a sentence of 1,500 non-ASCII code points
        When select_candidates runs with a floor of 0
        Then the short text is stripped and the long one is exactly its first 1,000 code points

    Boundaries:
        - Focus: Task 03 step 3 (MAX_CANDIDATE_CHARS)
        - Fixtures/params: real clustering factory
        - Scope: select_candidates mapping

    On failure, first check:
        - The strip/cut order in _candidate_text
    """
    long_sentence = "  " + " ".join(f"\u00e9tape{k}" for k in range(150)) + "  "
    assert len(long_sentence.strip()) > 1000
    claims = (
        _numbered(1, sentence="   Release 3.2 ships in Q4.  \n"),
        _numbered(2, path="docs/other.md", sentence=long_sentence),
    )
    config = dataclasses.replace(Config(), fact_check_min_salience=0.0)
    by_path = {c.claim.path: c.text for c in fact_check.select_candidates(claims, config)}
    assert by_path["docs/release.md"] == "Release 3.2 ships in Q4."
    assert by_path["docs/other.md"] == long_sentence.strip()[: fact_check.MAX_CANDIDATE_CHARS]
    assert len(by_path["docs/other.md"]) == 1000


def test_select_candidates_generated_corpus_bounds_count_and_text():
    """
    [Unit] select_candidates: verifies the caps and the text bound over 240 generated claims.

    Scenario:
        Given 240 distinct claims over twelve documents, some sentences over 1,000 characters
        When select_candidates runs with the default caps and a floor of 0
        Then exactly 25 candidates, at most 3 per path, and each text at most 1,000 code points

    Boundaries:
        - Focus: Task 03 acceptance (generated corpus of at least 200 claims)
        - Fixtures/params: deterministic generated corpus
        - Scope: select_candidates

    On failure, first check:
        - The per-document cap in select_salient or MAX_CANDIDATE_CHARS
    """
    claims = []
    for index in range(240):
        sentence = f"Node n{index} holds {index} shards in zone{index % 7}."
        if index % 10 == 0:
            sentence += " " + " ".join(f"word{index}x{k}" for k in range(200))
        claims.append(_numbered(index, path=f"docs/doc{index % 12:02d}.md", sentence=sentence))
    config = dataclasses.replace(Config(), fact_check_min_salience=0.0)
    result = fact_check.select_candidates(tuple(claims), config)
    assert len(result) == config.fact_check_max_claims_total == 25
    paths = [c.claim.path for c in result]
    assert max(paths.count(p) for p in set(paths)) <= config.fact_check_max_claims_per_document
    assert all(len(c.text) <= fact_check.MAX_CANDIDATE_CHARS for c in result)


def test_importing_fact_check_does_not_import_salience_or_sklearn():
    """
    [Unit] select_candidates: verifies importing the detector imports neither mining.salience nor scikit-learn.

    Scenario:
        Given a fresh interpreter
        When docsentinel and docsentinel.detectors.fact_check are imported
        Then mining.salience, mining.clustering and sklearn are absent from sys.modules

    Boundaries:
        - Focus: Task 03 step 4.2 (lazy import)
        - Fixtures/params: subprocess
        - Scope: import side effects only

    On failure, first check:
        - A module-level import of mining.salience in detectors/fact_check.py
    """
    probe = (
        "import sys, docsentinel, docsentinel.detectors.fact_check\n"
        "mods = ('docsentinel.mining.salience', 'docsentinel.mining.clustering', 'sklearn')\n"
        "print(','.join(m for m in mods if m in sys.modules))\n"
    )
    completed = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert completed.stdout.strip() == ""


#: A long sentence; ``_NEAR`` is about 0.943 similar to it through the real factory, ``_FAR`` about
#: 0.776 (the same pair the clustering tests measure).
_BASE = (
    "the service stores uploaded invoices in regional buckets encrypted with customer managed "
    "keys rotated every ninety days by the scheduler"
)
_NEAR = _BASE + " automatically"
_FAR = _BASE.replace("ninety", "thirty").replace("regional", "central")


def _sentence_claim(
    sentence: str, *, path: str, numbers: tuple[str, ...], entities: tuple[str, ...], raw_object: str = "3.2 Q4"
) -> Claim:
    """Return a claim literal with a chosen sentence and signals.

    :param sentence: The raw sentence.
    :param path: The document path.
    :param numbers: The object numbers.
    :param entities: The object entities.
    :param raw_object: The object text.
    :return: The claim literal.
    """
    return Claim(
        subject_key="service",
        predicate_key="store",
        raw_subject="The service",
        raw_object=raw_object,
        raw_sentence=sentence,
        object_numbers=numbers,
        object_entities=entities,
        path=path,
        paragraph_index=0,
    )


def test_select_candidates_dedup_at_092_through_real_factory_with_default_config():
    """
    [Unit] select_candidates: verifies the fixed 0.92 threshold collapses a near pair and keeps a far pair.

    Scenario:
        Given _BASE in docs/a.md (number only) and _NEAR in docs/b.md (number and entity), then
            _BASE and _FAR in two documents, all with a short salient object
        When select_candidates runs with Config() (default floor 0.5, default caps)
        Then the near pair gives exactly one candidate, the higher-scoring _NEAR claim, and the far
            pair (one-token object, so both densities saturate) gives two candidates

    Boundaries:
        - Focus: Story 02.0 acceptance (0.92 through the real factory and the DS302 constant)
        - Fixtures/params: real create_vectorizer(), default Config
        - Scope: select_candidates and select_salient

    On failure, first check:
        - _DEDUP_THRESHOLD wiring in select_candidates, or a create_vectorizer() parameter change
    """
    low = _sentence_claim(_BASE, path="docs/a.md", numbers=("3.2",), entities=())
    high = _sentence_claim(_NEAR, path="docs/b.md", numbers=("3.2",), entities=("Q4",))
    near = fact_check.select_candidates((low, high), Config())
    assert [candidate.claim for candidate in near] == [high]
    assert near[0].text == _NEAR
    assert near[0].score >= _DEFAULT_FLOOR

    left = _sentence_claim(_BASE, path="docs/a.md", numbers=("3.2",), entities=("Q4",), raw_object="3.2-Q4")
    right = _sentence_claim(_FAR, path="docs/b.md", numbers=("3.2",), entities=("Q4",), raw_object="3.2-Q4")
    far = fact_check.select_candidates((right, left), Config())
    assert [candidate.claim for candidate in far] == [left, right]


def test_select_candidates_drops_trivial_claim_at_default_floor():
    """
    [Unit] select_candidates: verifies a claim with no number, no entity and low distinctiveness is dropped.

    Scenario:
        Given _BASE and _FAR without numbers or entities (distinctiveness about 0.22 each)
        When select_candidates runs with Config() and with the floor lowered to 0
        Then the default floor 0.5 selects nothing and the lowered floor keeps both

    Boundaries:
        - Focus: Story 02.0 acceptance (trivial claims dropped at fact_check_min_salience = 0.5)
        - Fixtures/params: real clustering factory
        - Scope: select_candidates

    On failure, first check:
        - _W_DISTINCT (constraint b) or the default fact_check_min_salience
    """
    claims = (
        _sentence_claim(_BASE, path="docs/a.md", numbers=(), entities=(), raw_object="plain words here"),
        _sentence_claim(_FAR, path="docs/b.md", numbers=(), entities=(), raw_object="plain words here"),
    )
    assert Config().fact_check_min_salience == _DEFAULT_FLOOR
    assert fact_check.select_candidates(claims, Config()) == ()
    lowered = dataclasses.replace(Config(), fact_check_min_salience=0.0)
    assert len(fact_check.select_candidates(claims, lowered)) == 2


def test_select_candidates_per_document_cap_then_total_cap_through_config():
    """
    [Unit] select_candidates: verifies the Config caps apply per document first, then corpus-wide.

    Scenario:
        Given four salient distinct claims in docs/a.md and one in each of docs/b.md and docs/c.md
        When select_candidates runs with per-document cap 2 and total cap 3
        Then a.md contributes at most 2, the total is exactly 3, and the result equals the
            select_salient order for the same numbers

    Boundaries:
        - Focus: Story 02.0 acceptance (both caps, in order) through the wrapper
        - Fixtures/params: real clustering factory
        - Scope: select_candidates

    On failure, first check:
        - Whether the wrapper swaps the two cap values
    """
    claims = (
        *(_numbered(i, path="docs/a.md") for i in range(4)),
        _numbered(10, path="docs/b.md"),
        _numbered(11, path="docs/c.md"),
    )
    config = dataclasses.replace(
        Config(), fact_check_max_claims_per_document=2, fact_check_max_claims_total=3, fact_check_min_salience=0.0
    )
    result = fact_check.select_candidates(claims, config)
    paths = [candidate.claim.path for candidate in result]
    assert len(result) == 3
    assert paths.count("docs/a.md") <= 2
    expected = _ds302_selection(claims, config)
    assert [(c.claim, c.score) for c in result] == [(e.claim, e.score) for e in expected]


def test_ds302_policy_equals_the_weight_and_threshold_constants():
    """
    [Unit] DS302_POLICY: verifies the policy is exactly the _W_* weights and _DEDUP_THRESHOLD, as floats.

    Scenario:
        Given the detector module constants
        When DS302_POLICY is compared field by field
        Then weights == (_W_NUMERIC, _W_ENTITY, _W_DISTINCT), dedup_threshold == _DEDUP_THRESHOLD, and
            every value is a plain float

    Boundaries:
        - Focus: Story 05.0 Task 04 step 2 (one source of the DS302 policy)
        - Fixtures/params: none
        - Scope: SelectionPolicy, DS302_POLICY

    On failure, first check:
        - Whether DS302_POLICY was rebuilt from literals instead of the constants
    """
    policy = fact_check.DS302_POLICY
    assert policy.weights == (fact_check._W_NUMERIC, fact_check._W_ENTITY, fact_check._W_DISTINCT)
    assert policy.dedup_threshold == fact_check._DEDUP_THRESHOLD
    assert all(type(value) is float for value in (*policy.weights, policy.dedup_threshold))
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.dedup_threshold = 0.5  # type: ignore[misc]


def test_select_candidates_passes_an_exploration_policy_to_trace_salience(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] select_candidates: verifies policy=SelectionPolicy((0.2, 0.2, 0.6), 0.9) reaches trace_salience unchanged.

    Scenario:
        Given a spy on trace_salience and the default Config
        When select_candidates runs with the exploration policy, then with the default policy
        Then the spy sees weights (0.2, 0.2, 0.6) and threshold 0.9 first, the DS302 values second

    Boundaries:
        - Focus: Story 05.0 Task 04 step 2 (policy keyword)
        - Fixtures/params: monkeypatched trace_salience
        - Scope: select_candidates, _trace_selection

    On failure, first check:
        - Whether _trace_selection reads the module constants instead of policy
    """
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(salience, "trace_salience", lambda claims, **kw: seen.append(kw) or ())
    policy = fact_check.SelectionPolicy((0.2, 0.2, 0.6), 0.9)
    assert fact_check.select_candidates((_numbered(1),), Config(), policy=policy) == ()
    assert fact_check.select_candidates((_numbered(1),), Config()) == ()
    assert [(kw["weights"], kw["dedup_threshold"]) for kw in seen] == [
        (SalienceWeights(numeric=0.2, entity=0.2, distinctiveness=0.6), 0.9),
        (SalienceWeights(numeric=0.3, entity=0.3, distinctiveness=0.4), 0.92),
    ]


@pytest.mark.parametrize(
    "policy",
    [
        fact_check.SelectionPolicy((0.5, 0.5, 0.5), 0.92),
        fact_check.SelectionPolicy((math.nan, 0.5, 0.5), 0.92),
        fact_check.SelectionPolicy((1.5, -0.25, -0.25), 0.92),
        fact_check.SelectionPolicy((0.3, 0.3, 0.4), 0.0),
        fact_check.SelectionPolicy((0.3, 0.3, 0.4), 1.5),
        fact_check.SelectionPolicy((0.3, 0.3, 0.4), math.inf),
        fact_check.SelectionPolicy((0.3, 0.3, 0.4), True),  # type: ignore[arg-type]
    ],
    ids=["sum", "nan-weight", "negative-weight", "zero-threshold", "high-threshold", "inf-threshold", "bool"],
)
def test_select_candidates_and_validator_refuse_an_invalid_policy(policy: fact_check.SelectionPolicy):
    """
    [Unit] select_candidates: verifies an invalid policy raises ValueError from both the selection and the validator.

    Scenario:
        Given a policy whose weights or threshold is out of range, non-finite or a bool
        When select_candidates runs on one claim and validate_selection_policy checks it
        Then both raise ValueError

    Boundaries:
        - Focus: Story 05.0 Task 04 step 2, threat model E6
        - Fixtures/params: one invalid policy per case
        - Scope: select_candidates, validate_selection_policy

    On failure, first check:
        - SalienceWeights and require_dedup_threshold
    """
    with pytest.raises(ValueError):
        fact_check.select_candidates((_numbered(1),), Config(), policy=policy)
    with pytest.raises(ValueError):
        fact_check.validate_selection_policy(policy)


def test_validator_refuses_weights_of_the_wrong_shape():
    """
    [Unit] validate_selection_policy: verifies weights that are not a 3-tuple raise the documented ValueError.

    Scenario:
        Given weights of length 2 and a list of three numbers
        When validate_selection_policy runs
        Then each raises ValueError naming the three-number shape

    Boundaries:
        - Focus: Story 05.0 Task 01 step 4.3 (shape check)
        - Fixtures/params: two malformed shapes
        - Scope: validate_selection_policy

    On failure, first check:
        - The tuple/length check at the top of validate_selection_policy
    """
    for weights in ((0.5, 0.5), [0.3, 0.3, 0.4]):
        with pytest.raises(ValueError, match="weights must be a tuple of three numbers"):
            fact_check.validate_selection_policy(fact_check.SelectionPolicy(weights, 0.92))  # type: ignore[arg-type]


def test_collect_candidates_signature_is_exactly_root_documents_config():
    """
    [Unit] collect_candidates: verifies its parameters are exactly root, documents, config (no policy).

    Scenario:
        Given collect_candidates and trace_candidates
        When their signatures are inspected
        Then collect_candidates has exactly (root, documents, config) and trace_candidates adds only a
            keyword-only policy defaulting to DS302_POLICY

    Boundaries:
        - Focus: plan contract C11, decision X5
        - Fixtures/params: none
        - Scope: signatures

    On failure, first check:
        - A keyword added to collect_candidates
    """
    collect = inspect.signature(fact_check.collect_candidates).parameters
    assert list(collect) == ["root", "documents", "config"]
    trace = inspect.signature(fact_check.trace_candidates).parameters
    assert list(trace) == ["root", "documents", "config", "policy"]
    assert trace["policy"].kind is inspect.Parameter.KEYWORD_ONLY
    assert trace["policy"].default is fact_check.DS302_POLICY


def test_candidate_claims_carry_the_trace_signal_fields():
    """
    [Unit] select_candidates: verifies each CandidateClaim carries the signal and cluster fields of its trace entry.

    Scenario:
        Given three distinct claims and two copies of one sentence in another document
        When select_candidates runs with a floor of 0 and the same claims are traced by trace_salience
        Then each candidate's score, numeric, entity, distinctiveness, cluster_id and cluster_size equal
            the selected trace entry's, and the duplicated sentence reports cluster_size 2

    Boundaries:
        - Focus: Story 05.0 Task 01 step 2 (extended CandidateClaim)
        - Fixtures/params: real clustering
        - Scope: select_candidates, _trace_selection

    On failure, first check:
        - The CandidateClaim construction in _trace_selection
    """
    shared = "Release train9 ships build9 in quarter9."
    claims = (
        *(_numbered(k) for k in range(3)),
        _numbered(9, path="docs/a.md", sentence=shared),
        _numbered(9, path="docs/b.md", sentence=shared),
    )
    config = dataclasses.replace(Config(), fact_check_min_salience=0.0)
    candidates = fact_check.select_candidates(claims, config)
    traced = [
        entry
        for entry in salience.trace_salience(
            claims, weights=_weights(), dedup_threshold=0.92, min_salience=0.0, max_per_document=3, max_total=25
        )
        if entry.disposition == "selected"
    ]
    assert len(candidates) == len(traced) == 4
    for candidate, entry in zip(candidates, traced, strict=True):
        assert candidate.claim is entry.claim
        assert (
            candidate.score,
            candidate.numeric,
            candidate.entity,
            candidate.distinctiveness,
            candidate.cluster_id,
            candidate.cluster_size,
        ) == (entry.score, entry.numeric, entry.entity, entry.distinctiveness, entry.cluster_id, entry.cluster_size)
    assert [c.cluster_size for c in candidates if c.text == shared] == [2]
