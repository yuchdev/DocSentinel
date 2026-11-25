"""DS302 gate, engine dispatch and send loop with a fake backend (Milestone 0010 Story 01.0 Task 05).

No test here makes a network call or uses a real backend: a fake client is registered in
``FACT_CHECK_BACKENDS`` under the name ``fake`` and candidate collection is replaced, so spaCy is
never loaded. The key value is the sentinel of threat model 0010 M12.
"""

import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest

from docsentinel import cli, engine, scan
from docsentinel.baseline import fingerprint
from docsentinel.config import Config, ConfigError
from docsentinel.detectors import fact_check
from docsentinel.fact_check.protocol import FACT_CHECK_BACKENDS, FactCheckError, FactCheckResult
from docsentinel.models import Finding
from docsentinel.reporting import render
from docsentinel.rules import ANALYZERS
from docsentinel.telemetry.loader import packaged_template_names
from tests.fact_check_fakes import (
    FAKE_KEY_ENV,
    SENTINEL,
    FakeBackendBase,
    make_fake_backend,
    register_fake_backend,
)

#: A marker returned as a citation; it must never reach a finding or a log record (M11).
CITATION_MARKER = "citation-marker-0010"

#: The gate WARNING and ``pending`` text with neither prerequisite present.
NEITHER_MESSAGE = f"DS302 skipped: pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1); set {FAKE_KEY_ENV}"


def _candidate(path: str, text: str) -> fact_check.CandidateClaim:
    """Build a candidate without running claim extraction.

    :param path: The document path.
    :param text: The text to send.
    :returns: The candidate.
    """
    return fact_check.CandidateClaim(claim=SimpleNamespace(path=path), text=text, score=0.9)


@pytest.fixture
def fake_backend(monkeypatch: pytest.MonkeyPatch) -> type[FakeBackendBase]:
    """Register a fresh shared fake backend whose results carry the citation marker.

    :param monkeypatch: Pytest monkeypatch.
    :returns: The fake class.
    """
    return register_fake_backend(monkeypatch, make_fake_backend(citations=(CITATION_MARKER,)))


def _deep_config(**overrides: object) -> Config:
    """Return a confirmed deep configuration using the fake backend.

    :param overrides: Extra ``Config`` fields.
    :returns: The configuration.
    """
    return Config(profile="deep", fact_check_backend="fake", **overrides)


def _records(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    """Return DocSentinel records at exactly ``level``.

    :param caplog: Pytest log capture.
    :param level: The level.
    :returns: The records.
    """
    return [r for r in caplog.records if r.name.startswith("docsentinel") and r.levelno == level]


def _all_log_text(caplog: pytest.LogCaptureFixture) -> str:
    """Return every captured message, formatted, joined.

    :param caplog: Pytest log capture.
    :returns: The text.
    """
    return "\n".join(r.getMessage() for r in caplog.records)


def test_closed_gate_scan_skips_ds302_and_reports_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fake_backend: type[FakeBackendBase],
):
    """
    [Unit] DS302 dispatch: verifies a closed gate gives one WARNING, one pending entry and no count.

    Scenario:
        Given a confirmed deep scan with DS301 stubbed, DS302 active and neither the flag nor the key
        When the scan runs
        Then pending holds the skip message, DS302 is not counted and nothing heavy is touched.

    Boundaries:
        - Focus: ADR 0007 Contract 6 and threat model M9
        - Fixtures/params: fake backend, spies on the extraction and backend loading
        - Scope: engine.scan with an injected Config

    On failure, first check:
        - The external_off computation in engine.scan and detect()'s early return
    """
    (tmp_path / "a.md").write_text("# A\n\nThe tool supports 3 profiles.\n", encoding="utf-8")
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    touched: list[str] = []
    monkeypatch.setattr(fact_check, "collect_candidates", lambda *a: touched.append("collect") or ())
    monkeypatch.setattr(fact_check, "load_backend", lambda name: touched.append("load") or fake_backend)
    monkeypatch.setattr(fact_check.nlp, "load_pipeline", lambda: touched.append("pipeline"))
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = scan(tmp_path, config=_deep_config())

    assert result.enabled_rules == ("DS301", "DS302")
    assert result.pending == (NEITHER_MESSAGE,)
    assert result.rules_evaluated == 1
    assert result.notice == "1 deep rule(s) evaluated (heuristic, advisory-only)."
    assert result.findings == ()
    assert [r.getMessage() for r in _records(caplog, logging.WARNING)] == [NEITHER_MESSAGE]
    assert touched == []
    assert fake_backend.constructed == 0
    assert not [r for r in caplog.records if r.getMessage().startswith("DS302: sent")]


def test_ds302_ignored_resolves_no_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] DS302 dispatch: verifies an ignored DS302 adds no pending entry and logs no WARNING.

    Scenario:
        Given a confirmed deep scan that ignores DS302 and an injected invalid backend name
        When the scan runs
        Then the gate is never resolved, so the invalid name raises nothing and pending is empty.

    Boundaries:
        - Focus: byte-identity of a deep scan without DS302 (ADR 0007 Contract 6)
        - Fixtures/params: DS301 stubbed
        - Scope: engine.scan

    On failure, first check:
        - Whether the gate is resolved only when EXTERNAL_API_RULES intersects the active codes
    """
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    caplog.set_level(logging.WARNING, logger="docsentinel")

    result = scan(
        tmp_path, config=Config(profile="deep", ignore=("DS302",), fact_check_backend="x\n")
    )

    assert result.enabled_rules == ("DS301",)
    assert result.pending == ()
    assert result.rules_evaluated == 1
    assert _records(caplog, logging.WARNING) == []


@pytest.mark.parametrize("value", ["false", "1", 1, 0, None])
def test_scan_refuses_non_bool_consent_before_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: object):
    """
    [Unit] DS302 dispatch: verifies scan() refuses a non-bool use_external_api before discovery.

    Scenario:
        Given a use_external_api value that is not a bool
        When scan() is called
        Then ConfigError is raised and discovery never runs.

    Boundaries:
        - Focus: threat model M3 (type confusion)
        - Fixtures/params: the five values of the acceptance criterion
        - Scope: engine.scan

    On failure, first check:
        - The first statement of engine.scan
    """
    discovered: list[Path] = []
    monkeypatch.setattr(engine, "discover_with_stats", lambda *a: discovered.append(a[0]))

    with pytest.raises(ConfigError, match="^use_external_api must be True or False$"):
        scan(tmp_path, use_external_api=value)

    assert discovered == []


def test_open_gate_checks_every_candidate_and_builds_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fake_backend: type[FakeBackendBase],
):
    """
    [Unit] DS302 dispatch: verifies the send loop, the finding format and the INFO counts line.

    Scenario:
        Given an open gate, three candidates of which one fails with FactCheckError
        When a confirmed deep scan runs
        Then the other two are still checked, only the reportable one is a finding, the confidence is
        only in value, citations reach nothing, and one INFO counts line is logged.

    Boundaries:
        - Focus: S10, Q2, Q4, M10 and M11
        - Fixtures/params: fake backend, the sentinel key, candidate collection replaced
        - Scope: engine.scan through detect() and _check_candidates

    On failure, first check:
        - _check_candidates and _finding in detectors/fact_check.py
    """
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)
    candidates = (
        _candidate("a.md", "Claim one."),
        _candidate("a.md", "Claim two."),
        _candidate("b.md", "Claim three."),
    )
    monkeypatch.setattr(fact_check, "collect_candidates", lambda *a: candidates)
    fake_backend.verdicts.update(
        {
            "Claim one.": FactCheckError("fake backend: unrecognised verdict"),
            "Claim two.": ("false", 0.8123),
            "Claim three.": ("mixed", 0.1),
        }
    )
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = scan(tmp_path, config=_deep_config(), use_external_api=True)

    assert fake_backend.calls == ["Claim one.", "Claim two.", "Claim three."]
    assert fake_backend.closed == 1
    assert result.pending == ()
    assert result.rules_evaluated == 2
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding == Finding(
        rule="DS302",
        path="a.md",
        message="external fact-check: 'Claim two.' rated false by fake - review to confirm",
        severity="warning",
    )
    assert finding.value == "false (confidence 0.81): Claim two."
    assert finding.type == "unverified claim"
    infos = [r for r in _records(caplog, logging.INFO) if r.getMessage().startswith("DS302: sent")]
    assert [r.getMessage() for r in infos] == [
        "DS302: sent 3 claim(s) from 2 document(s) to backend fake; 1 failed, 1 reported, 0 not sent (time budget)"
    ]
    text = _all_log_text(caplog)
    assert "Claim one." not in text
    assert CITATION_MARKER not in text and CITATION_MARKER not in repr(result)
    assert SENTINEL not in text and SENTINEL not in repr(result)


def test_factcheckerror_message_never_reaches_the_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fake_backend: type[FakeBackendBase],
):
    """
    [Unit] DS302 containment: verifies a FactCheckError message from check_claim is never logged.

    Scenario:
        Given an open gate and a backend whose check_claim raises FactCheckError echoing the key
        When a confirmed deep scan runs
        Then the WARNING names only the exception type and the key appears in no log record.

    Boundaries:
        - Focus: M5 (FC-5) on the per-claim FactCheckError path
        - Fixtures/params: fake backend, the sentinel key, candidate collection replaced
        - Scope: engine.scan through detect() and _check_candidates

    On failure, first check:
        - the FactCheckError branch of _check_candidates in detectors/fact_check.py
    """
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)
    monkeypatch.setattr(fact_check, "collect_candidates", lambda *a: (_candidate("a.md", "Claim one."),))
    fake_backend.verdicts.update({"Claim one.": FactCheckError(f"header rejected: Bearer {SENTINEL}")})
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = scan(tmp_path, config=_deep_config(), use_external_api=True)

    assert result.findings == ()
    warnings = [r.getMessage() for r in _records(caplog, logging.WARNING)]
    assert "DS302: fact-check failed for a claim in a.md (FactCheckError)" in warnings
    assert SENTINEL not in _all_log_text(caplog)


def test_backend_exception_is_contained_without_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fake_backend: type[FakeBackendBase],
):
    """
    [Unit] DS302 containment: verifies a non-FactCheckError from check_claim becomes a chainless RuntimeError.

    Scenario:
        Given a check_claim that raises an exception whose message carries the sentinel key
        When detect() runs with an open gate
        Then RuntimeError names only the type, has no cause or context, and the INFO line still logs.

    Boundaries:
        - Focus: threat model M5 (HIGH FC-5) and M10
        - Fixtures/params: fake backend, sentinel key
        - Scope: detect() called directly

    On failure, first check:
        - Whether the RuntimeError is raised inside an except block
    """
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)
    monkeypatch.setattr(fact_check, "collect_candidates", lambda *a: (_candidate("a.md", "Claim."),))
    fake_backend.verdicts["Claim."] = Exception(f"Illegal header value b'Bearer {SENTINEL}'")
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    with pytest.raises(RuntimeError) as raised:
        fact_check.detect(tmp_path, (), _deep_config(), use_external_api=True)

    assert str(raised.value) == "DS302: backend fake raised Exception"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert fake_backend.closed == 1
    assert SENTINEL[:8] not in _all_log_text(caplog)
    assert len([r for r in caplog.records if r.getMessage().startswith("DS302: sent 1 claim(s)")]) == 1


def test_constructor_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fake_backend: type[FakeBackendBase],
):
    """
    [Unit] DS302 containment: verifies constructor FactCheckError is a WARNING and any other error is contained.

    Scenario:
        Given a backend constructor raising FactCheckError, then ValueError carrying the sentinel
        When detect() runs with an open gate
        Then the first gives the fixed WARNING and (), the second a chainless RuntimeError.

    Boundaries:
        - Focus: threat model M5 items 2 and 3
        - Fixtures/params: fake backend
        - Scope: detect() called directly

    On failure, first check:
        - The construction try block in detect()
    """
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)
    caplog.set_level(logging.WARNING, logger="docsentinel")
    fake_backend.init_error = FactCheckError("fake: invalid key shape")

    assert fact_check.detect(tmp_path, (), _deep_config(), use_external_api=True) == ()
    assert [r.getMessage() for r in _records(caplog, logging.WARNING)] == [
        "DS302 skipped: backend fake could not be initialised (FactCheckError)"
    ]

    fake_backend.init_error = ValueError(SENTINEL)
    with pytest.raises(RuntimeError) as raised:
        fact_check.detect(tmp_path, (), _deep_config(), use_external_api=True)
    assert str(raised.value) == "DS302: backend fake raised ValueError"
    assert raised.value.__cause__ is None and raised.value.__context__ is None
    assert fake_backend.calls == []


def test_key_vanishing_after_gate_gives_gate_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fake_backend: type[FakeBackendBase],
):
    """
    [Unit] DS302 gate: verifies a key removed between the gate and construction skips with the gate WARNING.

    Scenario:
        Given an open gate whose key variable is removed while the backend loads
        When detect() runs
        Then it returns () with the gate WARNING and never constructs the client.

    Boundaries:
        - Focus: threat model M5 item 1
        - Fixtures/params: load_backend replaced by one that removes the key
        - Scope: detect() called directly

    On failure, first check:
        - _construct_client in detectors/fact_check.py
    """
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)

    def _load(name: str) -> type[FakeBackendBase]:
        """Remove the key, as if the environment changed, and return the fake.

        :param name: The backend name.
        :returns: The fake class.
        """
        monkeypatch.delenv(FAKE_KEY_ENV, raising=False)
        return fake_backend

    monkeypatch.setattr(fact_check, "load_backend", _load)
    caplog.set_level(logging.WARNING, logger="docsentinel")

    assert fact_check.detect(tmp_path, (), _deep_config(), use_external_api=True) == ()
    assert [r.getMessage() for r in _records(caplog, logging.WARNING)] == [f"DS302 skipped: set {FAKE_KEY_ENV}"]
    assert fake_backend.constructed == 0


def test_unavailable_backend_is_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] DS302 backend loading: verifies a backend whose module is missing gives one fixed WARNING.

    Scenario:
        Given the lenz backend whose module cannot be imported, with the flag and its key set
        When detect() runs
        Then it returns () and the WARNING is the fixed gate text naming the backend only.

    Boundaries:
        - Focus: ADR 0007 Contract 2 (backend unavailable)
        - Fixtures/params: the lenz key variable set to the sentinel
        - Scope: detect() called directly

    On failure, first check:
        - Whether the sys.modules None entry still makes load_backend raise ImportError
    """
    monkeypatch.setenv("DOCSENTINEL_FACTCHECK_LENZ_API_KEY", SENTINEL)
    monkeypatch.delitem(FACT_CHECK_BACKENDS, "lenz", raising=False)
    # A None entry makes the import fail, standing for a missing module or a missing httpx.
    monkeypatch.setitem(sys.modules, "docsentinel.fact_check.lenz", None)
    caplog.set_level(logging.WARNING, logger="docsentinel")

    assert fact_check.detect(tmp_path, (), Config(), use_external_api=True) == ()
    assert [r.getMessage() for r in _records(caplog, logging.WARNING)] == ["DS302 skipped: backend lenz not available"]


def test_other_tool_key_does_not_open_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fake_backend: type[FakeBackendBase],
):
    """
    [Unit] DS302 gate: verifies LENZ_API_KEY alone never opens the gate.

    Scenario:
        Given only LENZ_API_KEY set and the flag given
        When detect() runs
        Then the gate is closed with the per-backend reason and the fake records no call.

    Boundaries:
        - Focus: threat model M8
        - Fixtures/params: fake backend
        - Scope: detect() called directly

    On failure, first check:
        - Which variable resolve_external_api_gate reads
    """
    monkeypatch.setenv("LENZ_API_KEY", SENTINEL)
    caplog.set_level(logging.WARNING, logger="docsentinel")

    assert fact_check.detect(tmp_path, (), _deep_config(), use_external_api=True) == ()
    assert [r.getMessage() for r in _records(caplog, logging.WARNING)] == [f"DS302 skipped: set {FAKE_KEY_ENV}"]
    assert fake_backend.constructed == 0


def test_time_budget_stops_sending(caplog: pytest.LogCaptureFixture, fake_backend: type[FakeBackendBase]):
    """
    [Unit] DS302 budget: verifies an exhausted budget stops before the next call and keeps earlier findings.

    Scenario:
        Given a clock that passes the deadline after the first call and three candidates
        When _check_candidates runs
        Then one claim is sent, one budget WARNING is logged and the first finding is kept.

    Boundaries:
        - Focus: owner ruling Q3 (ADR 0007 Contract 7)
        - Fixtures/params: injected clock seam
        - Scope: _check_candidates called directly

    On failure, first check:
        - Where the deadline is taken and checked in _check_candidates
    """
    fake_backend.verdicts["One."] = ("false", 0.9)
    ticks = iter([0.0, 0.0, 10_000.0, 10_000.0])
    candidates = (_candidate("a.md", "One."), _candidate("a.md", "Two."), _candidate("b.md", "Three."))
    caplog.set_level(logging.INFO, logger="docsentinel")

    findings = fact_check._check_candidates(
        fake_backend(api_key=SENTINEL),
        candidates,
        _deep_config(fact_check_time_budget_seconds=5),
        clock=lambda: next(ticks),
    )

    assert fake_backend.calls == ["One."]
    assert [f.value for f in findings] == ["false (confidence 0.90): One."]
    assert [r.getMessage() for r in _records(caplog, logging.WARNING)] == [
        "DS302: time budget of 5 s exhausted; 2 of 3 claim(s) not checked"
    ]
    assert [r.getMessage() for r in _records(caplog, logging.INFO)] == [
        "DS302: sent 1 claim(s) from 1 document(s) to backend fake; 0 failed, 1 reported, 2 not sent (time budget)"
    ]


def test_confidence_does_not_change_the_fingerprint(fake_backend: type[FakeBackendBase]):
    """
    [Unit] DS302 finding: verifies two confidences with one verdict give the same fingerprint.

    Scenario:
        Given the same claim rated false at 0.7 and at 0.95
        When the findings are fingerprinted
        Then the fingerprints are equal and neither message contains a confidence.

    Boundaries:
        - Focus: owner ruling Q2
        - Fixtures/params: fake backend
        - Scope: _check_candidates and baseline.fingerprint

    On failure, first check:
        - Whether the message carries the confidence
    """
    candidates = (_candidate("a.md", "Same."),)
    prints = []
    for confidence in (0.7, 0.95):
        fake_backend.verdicts["Same."] = ("false", confidence)
        (finding,) = fact_check._check_candidates(fake_backend(api_key=SENTINEL), candidates, _deep_config())
        assert "confidence" not in finding.message
        prints.append(fingerprint(finding))

    assert prints[0] == prints[1]


def test_check_candidates_refuses_an_invalid_injected_budget(fake_backend: type[FakeBackendBase]):
    """
    [Unit] DS302 budget: verifies an injected out-of-range budget fails closed before any call.

    Scenario:
        Given an injected Config with fact_check_time_budget_seconds = 0
        When _check_candidates runs
        Then ConfigError is raised and nothing is sent.

    Boundaries:
        - Focus: re-validation of an injected Config (ADR 0007 Contract 7)
        - Fixtures/params: fake backend
        - Scope: _check_candidates called directly

    On failure, first check:
        - config.validate_fact_check_option
    """
    with pytest.raises(ConfigError, match="^fact_check_time_budget_seconds must be an integer from 1 to 3600$"):
        fact_check._check_candidates(
            fake_backend(api_key=SENTINEL), (_candidate("a.md", "X."),), _deep_config(fact_check_time_budget_seconds=0)
        )

    assert fake_backend.calls == []


class NotABackend:
    """A registered class that fails the protocol check (wrong key variable)."""

    name = "fake"
    API_KEY_ENV_VAR: ClassVar[str] = "SOMETHING_ELSE"

    def check_claim(self, claim: str) -> FactCheckResult:
        """Never called.

        :param claim: The text.
        :returns: Nothing; it raises.
        :raises AssertionError: Always.
        """
        raise AssertionError(claim)


def test_unavailable_backend_closes_the_gate_in_scan_and_doctor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
):
    """
    [Unit] DS302 gate: verifies a backend that cannot be loaded counts as a closed gate everywhere.

    Scenario:
        Given the flag and the key, but a lenz module that cannot be imported, then a fake failing the protocol check
        When a confirmed deep scan runs and doctor prints its gate line
        Then DS302 is not counted, pending and the single WARNING say the backend is not available,
        no INFO counts line is logged and doctor prints the gate as off.

    Boundaries:
        - Focus: owner ruling 2026-11-23 (unavailable backend is a closed gate)
        - Fixtures/params: DS301 stubbed, sentinel key
        - Scope: engine.scan, detect() and cli doctor

    On failure, first check:
        - ExternalApiGate.backend_available and _backend_loadable
    """
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    monkeypatch.delitem(FACT_CHECK_BACKENDS, "lenz", raising=False)
    # A None entry makes the import fail, standing for a missing module or a missing httpx.
    monkeypatch.setitem(sys.modules, "docsentinel.fact_check.lenz", None)
    monkeypatch.setenv("DOCSENTINEL_FACTCHECK_LENZ_API_KEY", SENTINEL)
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = scan(tmp_path, config=Config(profile="deep"), use_external_api=True)

    assert result.pending == ("DS302 skipped: backend lenz not available",)
    assert result.rules_evaluated == 1
    assert result.notice == "1 deep rule(s) evaluated (heuristic, advisory-only)."
    assert [r.getMessage() for r in _records(caplog, logging.WARNING)] == ["DS302 skipped: backend lenz not available"]
    assert not [r for r in caplog.records if r.getMessage().startswith("DS302: sent")]
    assert SENTINEL not in _all_log_text(caplog)

    monkeypatch.setenv("DOCSENTINEL_USE_EXTERNAL_API", "1")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["doctor"]) == 0
    gate_lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("fact-check gate:")]
    assert gate_lines == ["fact-check gate: off (backend lenz not available)"]

    monkeypatch.setitem(FACT_CHECK_BACKENDS, "fake", NotABackend)
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)
    gate = fact_check.resolve_external_api_gate(_deep_config(), use_external_api=True)
    assert gate.open is False
    assert gate.skip_message() == "DS302 skipped: backend fake not available"


#: Every packaged report template name (``context`` ``report``; the ``facts`` templates render
#: ``extract-facts`` output, not a scan).
PACKAGED_TEMPLATES = packaged_template_names()


def _open_gate_scan_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Prepare a confirmed deep scan with DS301 stubbed and the fake key set.

    :param tmp_path: The scan root.
    :param monkeypatch: Pytest monkeypatch.
    """
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)


@pytest.mark.parametrize(("flag", "expected"), [(False, False), (True, True)])
def test_engine_forwards_consent_only_to_analyzers_that_declare_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: bool, expected: bool
):
    """
    [Unit] DS302 dispatch: verifies use_external_api reaches a declaring analyzer and no other.

    Scenario:
        Given DS302 replaced by a spy declaring use_external_api and DS301 by a two-argument spy
        When a confirmed deep scan runs with and without the flag
        Then the DS302 spy receives the bool and the DS301 spy is called with (root, documents) only.

    Boundaries:
        - Focus: _analyzer_accepts_use_external_api and _run_analyzer
        - Fixtures/params: flag False/True; the fake key is not set, so the gate stays closed
        - Scope: engine.scan with both analyzers replaced

    On failure, first check:
        - Whether _run_analyzer forwards use_external_api unconditionally
    """
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    plain_calls: list[tuple[object, ...]] = []
    declaring_calls: list[object] = []

    def plain(*args: object, **kwargs: object) -> tuple[Finding, ...]:
        """Record the call shape of an analyzer that declares no consent keyword."""
        plain_calls.append((len(args), tuple(sorted(kwargs))))
        return ()

    def declaring(
        root: Path, documents: tuple, config: Config, *, use_external_api: bool = False
    ) -> tuple[Finding, ...]:
        """Record the forwarded consent."""
        declaring_calls.append(use_external_api)
        return ()

    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: plain(root, docs))
    monkeypatch.setitem(ANALYZERS, "DS302", declaring)

    scan(tmp_path, config=Config(profile="deep"), use_external_api=flag)

    assert plain_calls == [(2, ())]
    assert declaring_calls == [expected]
    assert type(declaring_calls[0]) is bool


def test_run_analyzer_calls_a_non_declaring_analyzer_as_before(tmp_path: Path):
    """
    [Unit] DS302 dispatch: verifies _run_analyzer adds no keyword to an analyzer without use_external_api.

    Scenario:
        Given a config-accepting analyzer that declares no use_external_api
        When _run_analyzer is called with use_external_api=True
        Then the analyzer receives exactly (root, documents, config).

    Boundaries:
        - Focus: byte-identical dispatch for every existing analyzer
        - Fixtures/params: none
        - Scope: engine._run_analyzer

    On failure, first check:
        - _analyzer_accepts_use_external_api
    """
    seen: list[tuple[object, ...]] = []

    def analyzer(root: Path, documents: tuple, config: Config) -> tuple[Finding, ...]:
        """Record the positional arguments."""
        seen.append((root, documents, config))
        return ()

    settings = Config()
    assert engine._run_analyzer(analyzer, tmp_path, (), settings, None, True) == ()
    assert seen == [(tmp_path, (), settings)]


def test_ds302_ignored_matches_a_scan_without_ds302(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] DS302 dispatch: verifies ignoring DS302 restores the pre-DS302 notice, pending and count.

    Scenario:
        Given the same confirmed deep scan once with ignore = ["DS302"] and once with select = ["DS301"]
        When both run with neither the flag nor the key
        Then notice, pending and rules_evaluated are equal and are the pre-Milestone-0010 values.

    Boundaries:
        - Focus: owner ruling Q1 (master byte-identity)
        - Fixtures/params: DS301 stubbed
        - Scope: engine.scan

    On failure, first check:
        - The external_off arithmetic in engine.scan
    """
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())

    ignored = scan(tmp_path, config=Config(profile="deep", ignore=("DS302",)))
    reference = scan(tmp_path, config=Config(profile="deep", select=("DS301",)))

    for result in (ignored, reference):
        assert result.notice == "1 deep rule(s) evaluated (heuristic, advisory-only)."
        assert result.pending == ()
        assert result.rules_evaluated == 1
    assert (ignored.notice, ignored.pending, ignored.rules_evaluated) == (
        reference.notice,
        reference.pending,
        reference.rules_evaluated,
    )


@pytest.mark.parametrize("bad_verdict", ["maybe", "MIXED", "mixed ", "False"])
def test_out_of_vocabulary_verdict_is_skipped_not_mapped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fake_backend: type[FakeBackendBase],
    bad_verdict: str,
):
    """
    [Unit] DS302 verdicts: verifies a fake building a result with an unknown verdict yields no finding.

    Scenario:
        Given an open gate and a fake whose check_claim builds FactCheckResult with an out-of-vocabulary verdict
        When the scan runs
        Then one WARNING names the document and FactCheckError, and no finding (never "mixed") is produced.

    Boundaries:
        - Focus: owner ruling Q4
        - Fixtures/params: four near-miss verdict spellings
        - Scope: engine.scan through _check_candidates

    On failure, first check:
        - FactCheckResult.__post_init__ verdict check
    """
    _open_gate_scan_setup(tmp_path, monkeypatch)
    monkeypatch.setattr(fact_check, "collect_candidates", lambda *a: (_candidate("a.md", "Claim."),))
    fake_backend.verdicts["Claim."] = (bad_verdict, 0.99)
    caplog.set_level(logging.WARNING, logger="docsentinel")

    result = scan(tmp_path, config=_deep_config(), use_external_api=True)

    assert fake_backend.calls == ["Claim."]
    assert result.findings == ()
    assert [r.getMessage() for r in _records(caplog, logging.WARNING)] == [
        "DS302: fact-check failed for a claim in a.md (FactCheckError)"
    ]


def test_closed_gate_touches_no_extraction_selection_or_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_backend: type[FakeBackendBase]
):
    """
    [Unit] DS302 gate: verifies a closed gate never loads spaCy, selects candidates or builds a client.

    Scenario:
        Given the flag but no key, with spies on load_pipeline, select_candidates, load_backend and the constructor
        When a confirmed deep scan runs with the real collect_candidates in place
        Then no spy is called and the fake records no call.

    Boundaries:
        - Focus: threat model M9
        - Fixtures/params: fake backend, DS301 stubbed
        - Scope: engine.scan through detect()

    On failure, first check:
        - The early return in detect() and _backend_loadable's guard
    """
    (tmp_path / "a.md").write_text("# A\n\nAcme ships 3 releases.\n", encoding="utf-8")
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    touched: list[str] = []
    monkeypatch.setattr(fact_check.nlp, "load_pipeline", lambda: touched.append("pipeline"))
    monkeypatch.setattr(fact_check, "select_candidates", lambda *a: touched.append("select") or ())
    monkeypatch.setattr(fact_check, "load_backend", lambda name: touched.append("load") or fake_backend)

    result = scan(tmp_path, config=_deep_config(), use_external_api=True)

    assert result.pending == (f"DS302 skipped: set {FAKE_KEY_ENV}",)
    assert touched == []
    assert fake_backend.constructed == 0
    assert fake_backend.calls == []


def test_open_gate_runs_extraction_through_patched_pipeline_and_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_backend: type[FakeBackendBase]
):
    """
    [Unit] DS302 dispatch: verifies the open path reads each Markdown document and sends the selected text.

    Scenario:
        Given an open gate, a patched spaCy pipeline, a patched extract_statements and an injected select_candidates
        When a confirmed deep scan runs
        Then extract_statements sees every .md document's text, the fake receives the selected text,
        its "false" verdict becomes a finding and close() is called once.

    Boundaries:
        - Focus: collect_candidates wiring with no spaCy model (Task 06 step 5)
        - Fixtures/params: fake backend, sentinel key
        - Scope: engine.scan through detect(), collect_candidates and _check_candidates

    On failure, first check:
        - collect_candidates in detectors/fact_check.py
    """
    _open_gate_scan_setup(tmp_path, monkeypatch)
    (tmp_path / "b.md").write_text("Acme was founded in 1999.\n", encoding="utf-8")
    monkeypatch.setattr(fact_check.nlp, "load_pipeline", lambda: "pipeline")
    seen: list[tuple[object, str, str]] = []

    def extract(pipeline: object, text: str, path: str) -> tuple[SimpleNamespace, ...]:
        """Record the call and return one claim per document."""
        seen.append((pipeline, text, path))
        return (SimpleNamespace(path=path, raw_sentence=text.strip()),)

    monkeypatch.setattr("docsentinel.mining.claims.extract_statements", extract)
    # Story 05.0: trace_candidates pools the claims into the private trace helper (plan contract C11).
    monkeypatch.setattr(
        fact_check,
        "_trace_selection",
        lambda claims, config, policy: tuple(
            (fact_check.CandidateClaim(claim=c, text=c.raw_sentence, score=0.9), "selected")
            for c in claims
            if c.path == "b.md"
        ),
    )
    fake_backend.verdicts["Acme was founded in 1999."] = ("false", 0.75)

    result = scan(tmp_path, config=_deep_config(), use_external_api=True)

    assert seen == [("pipeline", "# A\n", "a.md"), ("pipeline", "Acme was founded in 1999.\n", "b.md")]
    assert fake_backend.calls == ["Acme was founded in 1999."]
    assert [(f.rule, f.path, f.value) for f in result.findings] == [
        ("DS302", "b.md", "false (confidence 0.75): Acme was founded in 1999.")
    ]
    assert fake_backend.closed == 1
    assert result.rules_evaluated == 2
    assert result.pending == ()


def test_info_counts_line_has_integer_args_and_no_path_or_claim(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, fake_backend: type[FakeBackendBase]
):
    """
    [Unit] DS302 audit line: verifies the INFO counts record is counts plus the backend name only.

    Scenario:
        Given an open gate, two candidates under a distinctive path, the first rated false
        and the second raising a plain Exception
        When detect() runs
        Then the RuntimeError propagates and exactly one INFO counts record is logged with the counts so far,
        integer args plus the backend name, and no path or claim text.

    Boundaries:
        - Focus: threat model M10 (also on the M5 RuntimeError path)
        - Fixtures/params: fake backend, sentinel key
        - Scope: detect() called directly

    On failure, first check:
        - The finally block of _check_candidates
    """
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)
    path = "docs/private-roadmap.md"
    monkeypatch.setattr(
        fact_check,
        "collect_candidates",
        lambda *a: (_candidate(path, "First claim text."), _candidate(path, "Second claim text.")),
    )
    fake_backend.verdicts.update({"First claim text.": "false", "Second claim text.": Exception("boom")})
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    with pytest.raises(RuntimeError, match="^DS302: backend fake raised Exception$"):
        fact_check.detect(Path("."), (), _deep_config(), use_external_api=True)

    infos = [r for r in _records(caplog, logging.INFO) if r.getMessage().startswith("DS302: sent")]
    assert len(infos) == 1
    record = infos[0]
    assert record.getMessage() == (
        "DS302: sent 2 claim(s) from 1 document(s) to backend fake; 0 failed, 1 reported, 0 not sent (time budget)"
    )
    assert record.args == (2, 1, "fake", 0, 1, 0)
    assert [type(arg) for arg in record.args] == [int, int, str, int, int, int]
    assert path not in record.getMessage() and "private-roadmap" not in record.getMessage()
    assert "claim text" not in record.getMessage()


@pytest.mark.parametrize("template", PACKAGED_TEMPLATES)
def test_citations_reach_no_finding_log_or_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fake_backend: type[FakeBackendBase],
    template: str,
):
    """
    [Unit] DS302 findings: verifies backend citations never reach a finding, a log record or a report.

    Scenario:
        Given an open gate and a fake whose "false" result carries a marker citation
        When the scan runs and the result is rendered through a packaged template
        Then the marker is in no Finding field, no log record and no rendered report.

    Boundaries:
        - Focus: threat model M11
        - Fixtures/params: fake backend with a marker citation, every packaged template
        - Scope: engine.scan and reporting.render

    On failure, first check:
        - _finding in detectors/fact_check.py and the template contexts
    """
    _open_gate_scan_setup(tmp_path, monkeypatch)
    monkeypatch.setattr(fact_check, "collect_candidates", lambda *a: (_candidate("a.md", "Claim."),))
    fake_backend.verdicts["Claim."] = "false"
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = scan(tmp_path, config=_deep_config(), use_external_api=True)
    report = render(result, template, config=_deep_config(), root=tmp_path)

    assert len(result.findings) == 1
    assert "DS302" in report
    assert CITATION_MARKER not in report
    assert CITATION_MARKER not in repr(result.findings[0].__dict__)
    assert CITATION_MARKER not in _all_log_text(caplog)
    assert all(CITATION_MARKER not in str(arg) for r in caplog.records for arg in (r.args or ()))


def test_patched_load_backend_import_error_is_one_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fake_backend: type[FakeBackendBase],
):
    """
    [Unit] DS302 backend loading: verifies an ImportError from load_backend closes the gate with one WARNING.

    Scenario:
        Given the flag, the fake key and load_backend patched to raise ImportError
        When a confirmed deep scan runs
        Then there are zero findings, one WARNING and one pending entry naming the backend, and no call.

    Boundaries:
        - Focus: ADR 0007 honesty ruling (backend not available)
        - Fixtures/params: fake backend, sentinel key
        - Scope: engine.scan through resolve_external_api_gate and detect()

    On failure, first check:
        - _backend_loadable
    """
    _open_gate_scan_setup(tmp_path, monkeypatch)

    def unavailable(name: str) -> type:
        """Fail like a missing backend module."""
        raise ImportError(f"No module named 'httpx' {SENTINEL}")

    monkeypatch.setattr(fact_check, "load_backend", unavailable)
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = scan(tmp_path, config=_deep_config(), use_external_api=True)

    assert result.findings == ()
    assert result.pending == ("DS302 skipped: backend fake not available",)
    assert [r.getMessage() for r in _records(caplog, logging.WARNING)] == ["DS302 skipped: backend fake not available"]
    assert fake_backend.constructed == 0 and fake_backend.calls == []
    assert SENTINEL not in _all_log_text(caplog)
