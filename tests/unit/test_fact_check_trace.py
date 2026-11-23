"""Unit tests for the shared DS302 / extract-facts candidate source (Milestone 0010 Story 05.0 Task 01).

Pins plan contract C11 (one extraction loop, ``collect_candidates`` without a policy), the
``SelectionPolicy`` constants, ``trace_salience`` dispositions with ``select_salient`` as its
``selected`` projection, and threat model 0010 extract-facts E9 (no exploration key in any config
tier or on a DS302 surface).
"""

import ast
import inspect
import json
from pathlib import Path

import pytest

from docsentinel import engine
from docsentinel.config import Config, ConfigError, load_config
from docsentinel.detectors import fact_check
from docsentinel.mining import salience
from docsentinel.mining.claims import Claim

#: The exploration names that must never be configuration keys (threat model E9).
_EXPLORATION_KEYS = (
    "weights",
    "dedup_threshold",
    "fact_check_weights",
    "fact_check_dedup_threshold",
    "include_rejected",
    "selection_policy",
)

_WEIGHTS = salience.SalienceWeights(0.3, 0.3, 0.4)


def _claim(index: int, *, path: str = "docs/a.md", sentence: str = "") -> Claim:
    """Return a claim literal.

    :param index: Makes the claim unique.
    :param path: The document path.
    :param sentence: The sentence; a generated unique one when empty.
    :return: The claim.
    """
    return Claim(
        subject_key="node",
        predicate_key="hold",
        raw_subject="Node",
        raw_object=f"{index} shards Q{index}" if index % 3 else "many shards here",
        raw_sentence=sentence or f"Node alpha{index} holds {index} shards in region{index} today.",
        object_numbers=(str(index),) if index % 3 else (),
        object_entities=(f"DATE:Q{index}",) if index % 3 else (),
        path=path,
        paragraph_index=index,
    )


def _corpus() -> tuple[Claim, ...]:
    """Return 40 claims over four documents with exact duplicates and low-salience claims.

    :return: The claims.
    """
    claims = [_claim(k, path=f"docs/d{k % 4}.md") for k in range(36)]
    claims += [_claim(k, path="docs/dup.md", sentence=claims[k].raw_sentence) for k in range(4)]
    return tuple(claims)


def _params(**overrides: object) -> dict[str, object]:
    """Return selection parameters with overrides.

    :param overrides: Parameter overrides.
    :return: The keyword arguments.
    """
    params: dict[str, object] = {
        "weights": _WEIGHTS,
        "dedup_threshold": 0.92,
        "min_salience": 0.5,
        "max_per_document": 3,
        "max_total": 8,
    }
    params.update(overrides)
    return params


def test_trace_has_every_disposition_once_and_projects_to_select_salient():
    """
    [Unit] trace_salience: verifies each canonical claim appears once with a valid disposition.

    Scenario:
        Given 40 claims with duplicates, low-salience claims and tight caps
        When trace_salience and select_salient run on the same arguments
        Then the trace holds every claim once, all five dispositions occur, cluster sizes are >= 1,
        and the selected subsequence equals select_salient

    Boundaries:
        - Focus: Task 01 step 1, decision X2
        - Fixtures/params: real clustering
        - Scope: trace_salience, select_salient

    On failure, first check:
        - The disposition assignment order in trace_salience
    """
    claims = _corpus()
    trace = salience.trace_salience(claims, **_params())  # type: ignore[arg-type]
    assert len(trace) == len(claims)
    assert {id(entry.claim) for entry in trace} == {id(claim) for claim in claims}
    assert {entry.disposition for entry in trace} == set(salience.DISPOSITIONS)
    assert all(entry.cluster_size >= 1 for entry in trace)
    assert all(entry.cluster_size >= 2 for entry in trace if entry.disposition == "duplicate")
    selected = tuple(entry for entry in trace if entry.disposition == "selected")
    assert selected == salience.select_salient(claims, **_params())  # type: ignore[arg-type]
    keys = [
        (-e.score, e.claim.path, e.claim.paragraph_index, e.claim.raw_sentence, e.claim.raw_subject, e.claim.raw_object)
        for e in trace
    ]
    assert keys == sorted(keys)


def test_trace_signals_recombine_to_score():
    """
    [Unit] trace_salience: verifies the signal fields recombine to the combined score.

    Scenario:
        Given the 40-claim corpus
        When trace_salience runs
        Then combined_score(numeric, entity, distinctiveness) equals each entry's score

    Boundaries:
        - Focus: ScoredClaim signal fields
        - Fixtures/params: real clustering
        - Scope: trace_salience

    On failure, first check:
        - Whether _score_canonical stores the same signals it scores
    """
    for entry in salience.trace_salience(_corpus(), **_params()):  # type: ignore[arg-type]
        assert entry.score == salience.combined_score(
            entry.numeric, entry.entity, entry.distinctiveness, weights=_WEIGHTS
        )


def test_trace_empty_and_invalid():
    """
    [Unit] trace_salience: verifies an empty corpus traces nothing and a bad threshold raises.

    Scenario:
        Given no claims, then a threshold of 0
        When trace_salience runs
        Then the first returns () and the second raises ValueError

    Boundaries:
        - Focus: edge and invalid input
        - Fixtures/params: none
        - Scope: trace_salience

    On failure, first check:
        - The validation at the top of trace_salience
    """
    assert salience.trace_salience((), **_params()) == ()  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="dedup_threshold"):
        salience.trace_salience((), **_params(dedup_threshold=0))  # type: ignore[arg-type]


def test_ds302_policy_is_built_from_the_constants():
    """
    [Unit] DS302_POLICY: verifies the policy equals the fixed weight and threshold constants.

    Scenario:
        Given detectors/fact_check.py
        When DS302_POLICY is read and validated
        Then it equals ((0.3, 0.3, 0.4), 0.92) and validation returns an equal policy

    Boundaries:
        - Focus: Task 01 step 2
        - Fixtures/params: none
        - Scope: SelectionPolicy, validate_selection_policy

    On failure, first check:
        - The _W_* and _DEDUP_THRESHOLD constants
    """
    assert fact_check.DS302_POLICY == fact_check.SelectionPolicy((0.3, 0.3, 0.4), 0.92)
    assert fact_check.validate_selection_policy(fact_check.DS302_POLICY) == fact_check.DS302_POLICY


def test_trace_candidates_is_the_only_extraction_loop():
    """
    [Unit] fact_check: verifies exactly one extract_claims call, inside trace_candidates, and detect uses collect_candidates.

    Scenario:
        Given the parsed source of detectors/fact_check.py
        When every call is inspected
        Then one call names extract_claims, in trace_candidates, and detect calls collect_candidates

    Boundaries:
        - Focus: plan contract C11, Task 01 acceptance
        - Fixtures/params: AST only
        - Scope: detectors/fact_check.py

    On failure, first check:
        - A second extraction loop added to the module
    """
    tree = ast.parse(Path(fact_check.__file__).read_text(encoding="utf-8"))
    owners: list[str] = []
    detect_calls: set[str] = set()
    for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)):
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            name = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")
            if name == "extract_claims":
                owners.append(function.name)
            if function.name == "detect":
                detect_calls.add(name)
    assert owners == ["trace_candidates"]
    assert "collect_candidates" in detect_calls


@pytest.mark.parametrize(
    "function", [fact_check.collect_candidates, fact_check.detect, engine.scan], ids=lambda f: f.__name__
)
def test_ds302_surfaces_take_no_policy(function: object):
    """
    [Unit] DS302 surfaces: verifies collect_candidates, detect and scan take no policy, weights or dedup parameter.

    Scenario:
        Given the three DS302-reachable callables
        When their signatures are inspected
        Then no parameter name contains policy, weight or dedup

    Boundaries:
        - Focus: decision X5, threat model E9
        - Fixtures/params: one callable per case
        - Scope: signatures only

    On failure, first check:
        - A policy keyword added to a DS302 path
    """
    names = inspect.signature(function).parameters  # type: ignore[arg-type]
    assert not [n for n in names if "policy" in n or "weight" in n or "dedup" in n]


@pytest.mark.parametrize("key", _EXPLORATION_KEYS)
def test_exploration_keys_are_refused_in_every_config_tier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str):
    """
    [Unit] config: verifies an exploration name is an unknown option in TOML, pyproject, JSON and user settings.

    Scenario:
        Given one exploration key in each configuration tier
        When the configuration loads
        Then each tier raises the unknown-option ConfigError and Config has no such field

    Boundaries:
        - Focus: threat model E9
        - Fixtures/params: one key per case, four tiers
        - Scope: load_config

    On failure, first check:
        - Whether a weight or threshold became a Config field
    """
    assert key not in set(Config.__dataclass_fields__)
    toml_root = tmp_path / "toml"
    toml_root.mkdir()
    (toml_root / "docsentinel.toml").write_text(f"{key} = 1\n", encoding="utf-8")
    pyproject_root = tmp_path / "pyproject"
    pyproject_root.mkdir()
    (pyproject_root / "pyproject.toml").write_text(f"[tool.doc_sentinel]\n{key} = 1\n", encoding="utf-8")
    json_file = tmp_path / "c.json"
    json_file.write_text(json.dumps({key: 1}), encoding="utf-8")
    for root, path in ((toml_root, None), (pyproject_root, None), (tmp_path, json_file)):
        with pytest.raises(ConfigError, match="Unknown config options"):
            load_config(root, path, user_settings=False)
    settings_dir = tmp_path / "user"
    settings_dir.mkdir(mode=0o700)
    settings_file = settings_dir / "settings.json"
    settings_file.write_text(json.dumps({key: 1}), encoding="utf-8")
    settings_file.chmod(0o600)
    monkeypatch.setenv("DOCSENTINEL_SETTINGS", str(settings_file))
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ConfigError, match="Unknown config options"):
        load_config(empty)
