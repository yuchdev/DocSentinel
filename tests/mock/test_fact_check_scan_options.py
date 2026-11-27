"""``scan()`` fact checks and invoker selection policy for DS302 (owner rulings of 2026-11-27).

A fake backend is registered under ``fake`` and DS301 and the deep readiness check are replaced, so
no spaCy model loads and no network is reached. The only key value set is the sentinel of threat
model 0010 M12.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from docsentinel import FactCheck, FactCheckClaim, scan
from docsentinel.config import Config, ConfigError
from docsentinel.detectors import fact_check
from docsentinel.fact_check.protocol import ClaimVerdict, FactCheckResult
from docsentinel.models import Document
from docsentinel.rules import ANALYZERS
from tests.fact_check_fakes import FAKE_KEY_ENV, SENTINEL, FakeBackendBase, make_fake_backend, register_fake_backend


@pytest.fixture
def fake_backend(monkeypatch: pytest.MonkeyPatch) -> type[FakeBackendBase]:
    """Register a fresh fake backend.

    :param monkeypatch: Pytest monkeypatch.
    :returns: The fake class.
    """
    return register_fake_backend(monkeypatch, make_fake_backend())


@pytest.fixture
def deep_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a one-document scan root with an open DS302 gate and DS301 stubbed.

    :param tmp_path: Pytest temporary directory.
    :param monkeypatch: Pytest monkeypatch.
    :returns: The scan root.
    """
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)
    return tmp_path


def _candidate(path: str, text: str) -> fact_check.CandidateClaim:
    """Build a candidate without running claim extraction.

    :param path: The document path.
    :param text: The text to send.
    :returns: The candidate.
    """
    return fact_check.CandidateClaim(claim=SimpleNamespace(path=path), text=text, score=0.9)


def _spy_collect(monkeypatch: pytest.MonkeyPatch, candidates: tuple[fact_check.CandidateClaim, ...]) -> list:
    """Replace collect_candidates with a spy recording the policy it receives.

    :param monkeypatch: Pytest monkeypatch.
    :param candidates: What the spy returns.
    :returns: The list the received policies are appended to.
    """
    seen: list[fact_check.SelectionPolicy] = []

    def collect(
        root: Path, documents: tuple, config: Config, *, policy: fact_check.SelectionPolicy = fact_check.DS302_POLICY
    ) -> tuple[fact_check.CandidateClaim, ...]:
        """Record the policy and return the fixed candidates."""
        seen.append(policy)
        return candidates

    monkeypatch.setattr(fact_check, "collect_candidates", collect)
    return seen


def _deep_config() -> Config:
    """Return a deep configuration on the fake backend.

    :returns: The configuration.
    """
    return Config(profile="deep", fact_check_backend="fake")


def test_scan_result_lists_every_fact_check(
    deep_root: Path, monkeypatch: pytest.MonkeyPatch, fake_backend: type[FakeBackendBase]
):
    """
    [Unit] scan fact checks: verifies ScanResult.fact_checks lists true and false facts in send order.

    Scenario:
        Given an open gate and two candidates rated Mostly True (with one rated claim) and false
        When scan runs
        Then result.fact_checks holds two FactCheck records with the explicit labels, only the
        false one reported, and exactly one DS302 finding.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (fact checks in the result), engine forwarding
        - Fixtures/params: fake backend, collect_candidates replaced
        - Scope: engine.scan -> _run_analyzer -> detect -> _check_candidates

    On failure, first check:
        - _analyzer_accepts_fact_checks and the fact_checks list in engine.scan
    """
    _spy_collect(monkeypatch, (_candidate("a.md", "One."), _candidate("a.md", "Two.")))
    fake_backend.verdicts["One."] = FactCheckResult(
        "true", 0.7, "fake", label="Mostly True", claims=(ClaimVerdict("One.", "Mostly True", 0.7),)
    )
    fake_backend.verdicts["Two."] = ("false", 0.9)

    result = scan(deep_root, config=_deep_config(), use_external_api=True)

    assert result.fact_checks == (
        FactCheck("a.md", "One.", "Mostly True", 0.7, "fake", False, (FactCheckClaim("One.", "Mostly True", 0.7),)),
        FactCheck("a.md", "Two.", "False", 0.9, "fake", True),
    )
    assert [finding.rule for finding in result.findings] == ["DS302"]


def test_scan_without_ds302_has_no_fact_checks(deep_root: Path, fake_backend: type[FakeBackendBase]):
    """
    [Unit] scan fact checks: verifies a closed gate or a fast scan leaves fact_checks empty.

    Scenario:
        Given the same root
        When a fast scan and a deep scan without consent run
        Then both results have fact_checks == () and the backend is never called.

    Boundaries:
        - Focus: the default of ScanResult.fact_checks
        - Fixtures/params: fake backend
        - Scope: engine.scan

    On failure, first check:
        - The tuple(fact_checks) of engine.scan
    """
    assert scan(deep_root).fact_checks == ()
    assert scan(deep_root, config=_deep_config(), use_external_api=False).fact_checks == ()
    assert fake_backend.calls == []


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, fact_check.DS302_POLICY),
        ({"fact_weights": (0.5, 0.5, 0.0)}, fact_check.SelectionPolicy((0.5, 0.5, 0.0), 0.92)),
        ({"fact_dedup_threshold": 0.8}, fact_check.SelectionPolicy((0.3, 0.3, 0.4), 0.8)),
        (
            {"fact_weights": (0.2, 0.2, 0.6), "fact_dedup_threshold": 1.0},
            fact_check.SelectionPolicy((0.2, 0.2, 0.6), 1.0),
        ),
    ],
    ids=["default", "weights", "threshold", "both"],
)
def test_invoker_policy_reaches_the_selection(
    deep_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_backend: type[FakeBackendBase],
    kwargs: dict[str, object],
    expected: fact_check.SelectionPolicy,
):
    """
    [Unit] scan selection policy: verifies fact_weights and fact_dedup_threshold reach collect_candidates.

    Scenario:
        Given an open gate and collect_candidates replaced by a spy
        When scan runs with no override, weights only, threshold only, and both
        Then the spy receives DS302_POLICY, or that policy with the given field(s) replaced.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (scan --weights/--dedup-threshold reach DS302)
        - Fixtures/params: kwargs, expected
        - Scope: engine.scan -> detect(policy=) -> collect_candidates(policy=)

    On failure, first check:
        - _exploration_policy in engine.py and the policy forwarding in _run_analyzer
    """
    seen = _spy_collect(monkeypatch, ())

    scan(deep_root, config=_deep_config(), use_external_api=True, **kwargs)

    assert seen == [expected]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fact_weights": (0.5, 0.5, 0.5)},
        {"fact_weights": (0.5, 0.5)},
        {"fact_weights": (True, 0.0, 0.0)},
        {"fact_weights": (float("nan"), 0.5, 0.5)},
        {"fact_dedup_threshold": 0.0},
        {"fact_dedup_threshold": 1.5},
        {"fact_dedup_threshold": True},
    ],
    ids=["sum", "length", "bool", "nan", "zero", "above-one", "bool-threshold"],
)
def test_invalid_invoker_policy_raises_before_any_send(
    deep_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_backend: type[FakeBackendBase],
    kwargs: dict[str, object],
):
    """
    [Unit] scan selection policy: verifies an invalid weight or threshold raises ValueError, nothing sent.

    Scenario:
        Given an open gate
        When scan runs with weights not summing to 1, of the wrong length, a bool or NaN weight,
        or a threshold of 0, above 1 or a bool
        Then ValueError is raised and the backend is never called.

    Boundaries:
        - Focus: the documented ValueError of scan(fact_weights=, fact_dedup_threshold=)
        - Fixtures/params: kwargs
        - Scope: engine.scan

    On failure, first check:
        - _exploration_policy / validate_selection_policy
    """
    seen = _spy_collect(monkeypatch, (_candidate("a.md", "One."),))

    with pytest.raises(ValueError):
        scan(deep_root, config=_deep_config(), use_external_api=True, **kwargs)

    assert seen == []
    assert fake_backend.calls == []


def _facts_file(tmp_path: Path, *texts: str) -> Path:
    """Write a facts-json file listing ``texts`` for ``a.md``, all rejected by the selection.

    :param tmp_path: Pytest temporary directory.
    :param texts: The fact texts, in file order.
    :returns: The file path, outside the scan root.
    """
    path = tmp_path.parent / f"{tmp_path.name}-facts.json"
    facts = [{"path": "a.md", "text": text, "disposition": "below_floor"} for text in texts]
    path.write_text(
        json.dumps({"schema": "docsentinel-facts", "schema_version": 1, "facts": facts}), encoding="utf-8"
    )
    return path


def test_detect_with_facts_sends_them_without_reading_documents(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, fake_backend: type[FakeBackendBase]
):
    """
    [Unit] DS302 facts file: verifies detect(facts=) sends exactly those facts, one request each.

    Scenario:
        Given an open gate, fact_check_combination 'all', two facts and a document that does not
        exist on disk, with trace_candidates and collect_candidates replaced by tripwires
        When detect runs with facts=
        Then both facts are sent alone in order (the combination is ignored), no document is read,
        no extraction or selection runs, the false one is a finding with the explicit label and
        the INFO line names the fact count.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (--include-facts replaces extraction and selection)
        - Fixtures/params: fake backend, tripwires, caplog
        - Scope: fact_check.detect

    On failure, first check:
        - The facts branch of detect
    """
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)

    def tripwire(*args: object, **kwargs: object):
        """Fail the test: extraction or selection must not run."""
        raise AssertionError("extraction or selection ran")

    monkeypatch.setattr(fact_check, "trace_candidates", tripwire)
    monkeypatch.setattr(fact_check, "collect_candidates", tripwire)
    fake_backend.verdicts["Two."] = ("false", 0.9)
    facts = (_candidate("a.md", "One."), _candidate("b.md", "Two."))
    caplog.set_level(logging.INFO, logger="docsentinel")

    findings = fact_check.detect(
        Path("/nonexistent-root"),
        (Document("missing.md", 1),),
        Config(profile="deep", fact_check_backend="fake", fact_check_combination="all"),
        use_external_api=True,
        facts=facts,
    )

    assert fake_backend.calls == ["One.", "Two."]
    assert [(f.path, f.value) for f in findings] == [("b.md", "False (confidence 0.90): Two.")]
    assert "DS302: 2 fact(s) taken from the facts file; no extraction or selection" in caplog.messages


def test_detect_with_facts_keeps_the_consent_gate(
    monkeypatch: pytest.MonkeyPatch, fake_backend: type[FakeBackendBase]
):
    """
    [Unit] DS302 facts file: verifies facts= does not bypass the dual consent gate.

    Scenario:
        Given the key set but no consent, and then consent but no key
        When detect runs with facts=
        Then nothing is sent and no finding is produced.

    Boundaries:
        - Focus: the gate is unchanged by --include-facts
        - Fixtures/params: fake backend
        - Scope: fact_check.detect

    On failure, first check:
        - The gate check at the top of detect
    """
    facts = (_candidate("a.md", "One."),)
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)
    assert fact_check.detect(Path("."), (), _deep_config(), use_external_api=False, facts=facts) == ()
    monkeypatch.delenv(FAKE_KEY_ENV)
    assert fact_check.detect(Path("."), (), _deep_config(), use_external_api=True, facts=facts) == ()
    assert fake_backend.calls == []


def test_scan_facts_file_is_sent_and_selection_options_are_ignored(
    deep_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_backend: type[FakeBackendBase]
):
    """
    [Unit] scan facts_file: verifies the file's facts are sent and the invoker policy is not built.

    Scenario:
        Given an open gate, a facts file of two below-floor facts and invalid fact_weights
        When scan runs with facts_file= and those weights
        Then no ValueError is raised (the policy is ignored), extraction never runs, both facts
        are sent and recorded in fact_checks.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (facts_file wins over fact_weights/fact_dedup_threshold)
        - Fixtures/params: fake backend, collect_candidates tripwire
        - Scope: engine.scan -> _run_analyzer(facts=) -> detect

    On failure, first check:
        - The file_facts handling in engine.scan and the facts forwarding in _run_analyzer
    """
    seen = _spy_collect(monkeypatch, ())
    path = _facts_file(tmp_path, "First fact.", "Second fact.")

    result = scan(
        deep_root,
        config=_deep_config(),
        use_external_api=True,
        facts_file=path,
        fact_weights=(0.9, 0.9, 0.9),
        fact_dedup_threshold=7.0,
    )

    assert seen == []
    assert fake_backend.calls == ["First fact.", "Second fact."]
    assert [check.fact for check in result.fact_checks] == ["First fact.", "Second fact."]


def test_scan_bad_facts_file_fails_before_any_analyzer(
    deep_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_backend: type[FakeBackendBase]
):
    """
    [Unit] scan facts_file: verifies an invalid facts file is a ConfigError before any analyzer runs.

    Scenario:
        Given a facts file that is not facts-json and a DS301 spy
        When scan runs with facts_file=
        Then ConfigError names the file and the DS301 spy and the backend are never called.

    Boundaries:
        - Focus: fail closed before analyzers
        - Fixtures/params: fake backend, DS301 spy
        - Scope: engine.scan

    On failure, first check:
        - Where engine.scan calls load_facts_file
    """
    ran: list[str] = []
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ran.append("DS301") or ())
    bad = tmp_path.parent / f"{tmp_path.name}-bad.json"
    bad.write_text("[]", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"^facts file .*: not a facts-json file"):
        scan(deep_root, config=_deep_config(), use_external_api=True, facts_file=bad)

    assert ran == []
    assert fake_backend.calls == []
