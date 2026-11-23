"""DS302 and ``extract_facts`` read one candidate function (Milestone 0010 Story 05.0 Task 04, step 5).

``trace_candidates`` is replaced by one stub returning a fixed ``CandidateTrace`` and
``_check_candidates`` by a recorder, so no spaCy model and no backend is needed. A gate-open
``detect()`` (environment ``DOCSENTINEL_USE_EXTERNAL_API=1``, the M12 sentinel key and a fake backend
registered for this test only) must hand the backend exactly the trace's ``selected`` tuple, and
``extract_facts()`` must list exactly the same texts: both consumers read the one function (plan
contract C11). The last case is the in-process leak check of threat model 0010-extract-facts E9: an
exploration run leaves ``DS302_POLICY``, the ``_W_*`` constants and ``collect_candidates`` unchanged.
"""

import dataclasses
from pathlib import Path
from types import SimpleNamespace

import pytest

from docsentinel import engine, extract_facts
from docsentinel.config import Config
from docsentinel.detectors import fact_check
from docsentinel.mining.claims import Claim
from docsentinel.models import Document
from tests.fact_check_fakes import FAKE_KEY_ENV, FAKE_NAME, SENTINEL, make_fake_backend, register_fake_backend


def _claim(index: int, path: str) -> Claim:
    """Return a salient claim literal.

    :param index: Makes the claim unique.
    :param path: The document path.
    :returns: The claim.
    """
    return Claim(
        subject_key="node",
        predicate_key="hold",
        raw_subject="Node",
        raw_object=f"{index} shards Q{index}",
        raw_sentence=f"Node alpha{index} holds {index} shards in Q{index} region{index}.",
        object_numbers=(str(index),),
        object_entities=(f"DATE:Q{index}",),
        path=path,
        paragraph_index=index,
    )


def _fixed_trace() -> fact_check.CandidateTrace:
    """Return a trace with three selected and two rejected candidates, in a non-sorted order.

    :returns: The trace.
    """
    entries = []
    for index, (path, disposition) in enumerate(
        [
            ("b.md", "selected"),
            ("a.md", "below_floor"),
            ("a.md", "selected"),
            ("b.md", "duplicate"),
            ("a.md", "selected"),
        ]
    ):
        claim = _claim(index, path)
        entries.append(
            (fact_check.CandidateClaim(claim=claim, text=claim.raw_sentence, score=0.9 - index / 10), disposition)
        )
    return fact_check.CandidateTrace(entries=tuple(entries), documents_read=2, claims_extracted=5)


@pytest.fixture
def stubbed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Replace the one candidate function and the send loop, open both gates for a fake backend.

    :param tmp_path: Pytest temporary directory (the scan root, holding a.md and b.md).
    :param monkeypatch: Pytest monkeypatch.
    :returns: ``trace``, ``policies`` (each stub call's policy), ``sent`` (each recorded candidates
        tuple), ``backend`` and ``root``.
    """
    assert engine.trace_candidates is fact_check.trace_candidates
    (tmp_path / "a.md").write_text("# A\n\nAlpha.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\n\nBravo.\n", encoding="utf-8")
    state = SimpleNamespace(trace=_fixed_trace(), policies=[], sent=[], root=tmp_path)

    def _trace_stub(
        root: Path,
        documents: tuple[Document, ...],
        config: Config,
        *,
        policy: fact_check.SelectionPolicy = fact_check.DS302_POLICY,
    ) -> fact_check.CandidateTrace:
        """Record the policy and return the fixed trace.

        :param root: The scan root.
        :param documents: The readable documents.
        :param config: The effective configuration.
        :param policy: The selection policy.
        :returns: The fixed trace.
        """
        state.policies.append(policy)
        return state.trace

    def _record(client: object, candidates: tuple[fact_check.CandidateClaim, ...], config: Config) -> tuple[()]:
        """Record the candidates DS302 would send.

        :param client: The backend client.
        :param candidates: The candidates.
        :param config: The effective configuration.
        :returns: No findings.
        """
        state.sent.append(candidates)
        return ()

    monkeypatch.setattr(fact_check, "trace_candidates", _trace_stub)
    monkeypatch.setattr(engine, "trace_candidates", _trace_stub)
    monkeypatch.setattr(fact_check, "_check_candidates", _record)
    monkeypatch.setattr(engine, "deep_ready", lambda: True)
    monkeypatch.setenv("DOCSENTINEL_USE_EXTERNAL_API", "1")
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)
    state.backend = register_fake_backend(monkeypatch, make_fake_backend())
    return state


def test_detect_and_extract_facts_read_the_one_candidate_function(stubbed: SimpleNamespace):
    """
    [Unit] C11 single source: verifies gate-open detect() sends, and extract_facts lists, exactly the trace's selected.

    Scenario:
        Given trace_candidates stubbed with a fixed trace (3 selected of 5) and _check_candidates recording
        When detect() runs with both gates open for a fake backend, then extract_facts() runs on the same root
        Then the recorded candidates are the trace's selected tuple, the facts' texts are its texts in the
            same order, and both calls passed DS302_POLICY

    Boundaries:
        - Focus: plan contract C11, Task 04 step 5
        - Fixtures/params: stubbed trace_candidates and _check_candidates, env gate 1, sentinel key
        - Scope: fact_check.detect, engine.extract_facts

    On failure, first check:
        - Whether detect() or extract_facts() stopped calling trace_candidates
    """
    documents = (Document("a.md", 1), Document("b.md", 1))
    config = Config(fact_check_backend=FAKE_NAME)

    assert fact_check.detect(stubbed.root, documents, config) == ()
    result = extract_facts(stubbed.root, config=config)

    assert stubbed.sent == [stubbed.trace.selected]
    assert len(stubbed.trace.selected) == 3
    assert [fact.text for fact in result.facts] == [candidate.text for candidate in stubbed.trace.selected]
    assert [fact.path for fact in result.facts] == ["b.md", "a.md", "a.md"]
    assert result.matches_ds302 is True
    assert stubbed.policies == [fact_check.DS302_POLICY, fact_check.DS302_POLICY]
    assert stubbed.backend.constructed == 1
    assert stubbed.backend.closed == 1


def test_include_rejected_lists_the_whole_trace_in_trace_order(stubbed: SimpleNamespace):
    """
    [Unit] C11 single source: verifies --all lists every trace entry, in order, with its disposition.

    Scenario:
        Given the stubbed fixed trace
        When extract_facts runs with include_rejected=True
        Then the facts are the five trace entries in trace order with their dispositions, ranked 1 to 5,
            and the selected subset equals what detect() would send

    Boundaries:
        - Focus: decision X7 over the shared trace
        - Fixtures/params: stubbed trace_candidates
        - Scope: engine.extract_facts

    On failure, first check:
        - The listed filter in extract_facts
    """
    result = extract_facts(stubbed.root, config=Config(), include_rejected=True)

    assert [(f.text, f.disposition) for f in result.facts] == [
        (candidate.text, disposition) for candidate, disposition in stubbed.trace.entries
    ]
    assert [f.rank for f in result.facts] == [1, 2, 3, 4, 5]
    assert [f.text for f in result.selected] == [c.text for c in stubbed.trace.selected]


def test_exploration_run_leaves_the_ds302_policy_and_candidates_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    [Unit] C11 single source: verifies an in-process exploration run changes no DS302 state (E9).

    Scenario:
        Given patched deep readiness, pipeline and claim extraction (real salience and clustering)
        When collect_candidates runs, then extract_facts(weights=(0.2, 0.2, 0.6), dedup_threshold=0.5),
            then collect_candidates again
        Then DS302_POLICY and the _W_*/_DEDUP_THRESHOLD constants are unchanged, both collect_candidates
            results are equal, and the exploration run reports matches_ds302 false

    Boundaries:
        - Focus: threat model 0010-extract-facts E9 (no module-global mutation, no policy-blind cache)
        - Fixtures/params: patched extraction only
        - Scope: fact_check.collect_candidates, engine.extract_facts

    On failure, first check:
        - A module global or cache written by the exploration path
    """
    monkeypatch.setattr(engine, "deep_ready", lambda: True)
    monkeypatch.setattr(fact_check.nlp, "load_pipeline", lambda: "pipeline")

    def _extract(pipeline: object, text: str, path: str) -> tuple[Claim, ...]:
        """Return claim literals for one document.

        :param pipeline: Ignored.
        :param text: Ignored.
        :param path: The document path.
        :returns: Four claims.
        """
        offset = 0 if path == "a.md" else 10
        return tuple(_claim(offset + k, path) for k in range(4))

    monkeypatch.setattr("docsentinel.mining.claims.extract_claims", _extract)
    (tmp_path / "a.md").write_text("# A\n\nAlpha.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\n\nBravo.\n", encoding="utf-8")
    documents = (Document("a.md", 1), Document("b.md", 1))
    config = dataclasses.replace(Config(), fact_check_min_salience=0.0)
    policy_before = fact_check.DS302_POLICY
    constants_before = (
        fact_check._W_NUMERIC,
        fact_check._W_ENTITY,
        fact_check._W_DISTINCT,
        fact_check._DEDUP_THRESHOLD,
    )
    before = fact_check.collect_candidates(tmp_path, documents, config)

    explored = extract_facts(tmp_path, config=config, weights=(0.2, 0.2, 0.6), dedup_threshold=0.5)

    after = fact_check.collect_candidates(tmp_path, documents, config)
    assert explored.matches_ds302 is False
    assert explored.settings.weights == (0.2, 0.2, 0.6)
    assert explored.settings.dedup_threshold == 0.5
    assert fact_check.DS302_POLICY is policy_before
    assert fact_check.DS302_POLICY == fact_check.SelectionPolicy((0.3, 0.3, 0.4), 0.92)
    assert (
        fact_check._W_NUMERIC,
        fact_check._W_ENTITY,
        fact_check._W_DISTINCT,
        fact_check._DEDUP_THRESHOLD,
    ) == constants_before
    assert before
    assert after == before
