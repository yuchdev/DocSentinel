"""DS302 send loop with ``fact_check_combination`` and a fake backend (no network)."""

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from docsentinel import cli, models
from docsentinel.config import Config
from docsentinel.detectors import fact_check
from docsentinel.fact_check.protocol import ClaimVerdict, FactCheckResult
from tests.fact_check_fakes import SENTINEL, FakeBackendBase, make_fake_backend, register_fake_backend


def _candidate(path: str, text: str) -> fact_check.CandidateClaim:
    """Build a candidate without running claim extraction.

    :param path: The document path.
    :param text: The text to send.
    :returns: The candidate.
    """
    return fact_check.CandidateClaim(claim=SimpleNamespace(path=path), text=text, score=0.9)


@pytest.fixture
def fake_backend(monkeypatch: pytest.MonkeyPatch) -> type[FakeBackendBase]:
    """Register a fresh fake backend.

    :param monkeypatch: Pytest monkeypatch.
    :returns: The fake class.
    """
    return register_fake_backend(monkeypatch, make_fake_backend())


def _config(combination: str) -> Config:
    """Return a deep configuration on the fake backend with ``combination``.

    :param combination: The ``fact_check_combination`` value.
    :returns: The configuration.
    """
    return Config(profile="deep", fact_check_backend="fake", fact_check_combination=combination)


def test_ranges_send_one_request_per_group(fake_backend: type[FakeBackendBase]):
    """
    [Unit] DS302 combination: verifies '1-2,3-4' sends two combined requests and reports on each document.

    Scenario:
        Given five candidates over two documents and the combination '1-2,3-4'
        When _check_candidates runs and the second group is rated false
        Then three requests are sent ('One. Two.', 'Three. Four.', 'Five.') and the false fact gives one
        finding per document it drew claims from.

    Boundaries:
        - Focus: request count and per-document attribution of a combined fact
        - Fixtures/params: fake backend
        - Scope: _check_candidates called directly

    On failure, first check:
        - combine_candidates and _group_findings in detectors/fact_check.py
    """
    fake_backend.verdicts["Three. Four."] = ("false", 0.9)
    candidates = (
        _candidate("a.md", "One."),
        _candidate("a.md", "Two."),
        _candidate("a.md", "Three."),
        _candidate("b.md", "Four."),
        _candidate("b.md", "Five."),
    )

    findings = fact_check._check_candidates(fake_backend(api_key=SENTINEL), candidates, _config("1-2,3-4"))

    assert fake_backend.calls == ["One. Two.", "Three. Four.", "Five."]
    assert [(f.path, f.value) for f in findings] == [
        ("a.md", "False (confidence 0.90): Three. Four."),
        ("b.md", "False (confidence 0.90): Three. Four."),
    ]


def test_all_sends_a_single_request(caplog: pytest.LogCaptureFixture, fake_backend: type[FakeBackendBase]):
    """
    [Unit] DS302 combination: verifies 'all' sends one request and logs the grouping counts.

    Scenario:
        Given three candidates and the combination 'all'
        When _check_candidates runs
        Then one request carries all three texts and an INFO line names 3 claims in 1 fact.

    Boundaries:
        - Focus: the 'all' keyword
        - Fixtures/params: fake backend, caplog
        - Scope: _check_candidates called directly

    On failure, first check:
        - The FACT_COMBINATION_ALL branch of combine_candidates
    """
    caplog.set_level(logging.INFO, logger="docsentinel")
    candidates = tuple(_candidate("a.md", text) for text in ("A.", "B.", "C."))

    fact_check._check_candidates(fake_backend(api_key=SENTINEL), candidates, _config("all"))

    assert fake_backend.calls == ["A. B. C."]
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert "DS302: fact combination all: 3 claim(s) grouped into 1 fact(s)" in messages
    assert (
        "DS302: sent 1 claim(s) from 1 document(s) to backend fake; 0 failed, 0 reported, 0 not sent (time budget)"
        in messages
    )


def test_an_over_long_combined_fact_is_not_sent(caplog: pytest.LogCaptureFixture, fake_backend: type[FakeBackendBase]):
    """
    [Unit] DS302 combination: verifies a combined range over the send limit is skipped with a WARNING.

    Scenario:
        Given two 600-character candidates combined with the range '1-2' (1,201 characters)
        When _check_candidates runs
        Then nothing is sent and one WARNING names the group and its length ('all' would split
        them instead, see test_all_splits_an_over_long_join_into_whole_claim_facts).

    Boundaries:
        - Focus: the MAX_CANDIDATE_CHARS bound holds for combined text (no truncation)
        - Fixtures/params: fake backend, caplog
        - Scope: _check_candidates called directly

    On failure, first check:
        - The length check before check_claim in _check_candidates
    """
    candidates = (_candidate("a.md", "x" * 600), _candidate("a.md", "y" * 600))

    assert fact_check._check_candidates(fake_backend(api_key=SENTINEL), candidates, _config("1-2")) == ()

    assert fake_backend.calls == []
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["DS302: combined fact 1-2 is 1201 characters, over the 1000-character limit; not sent"]


def test_each_keeps_one_request_per_claim(fake_backend: type[FakeBackendBase]):
    """
    [Unit] DS302 combination: verifies the default sends every claim alone.

    Scenario:
        Given two candidates and the default combination
        When _check_candidates runs
        Then two requests are sent, one per claim.

    Boundaries:
        - Focus: default behaviour unchanged
        - Fixtures/params: fake backend
        - Scope: _check_candidates called directly

    On failure, first check:
        - The FACT_COMBINATION_EACH branch of combine_candidates
    """
    candidates = (_candidate("a.md", "One."), _candidate("a.md", "Two."))

    fact_check._check_candidates(fake_backend(api_key=SENTINEL), candidates, _config("each"))

    assert fake_backend.calls == ["One.", "Two."]


def test_all_splits_an_over_long_join_into_whole_claim_facts(
    caplog: pytest.LogCaptureFixture, fake_backend: type[FakeBackendBase]
):
    """
    [Unit] DS302 combination: verifies 'all' splits a join over the limit into facts of whole claims.

    Scenario:
        Given three candidates of 600, 399 and 2 characters and the combination 'all'
        When _check_candidates runs
        Then two requests are sent: the first two claims joined (1,000 characters, at the bound)
        and the third alone; no WARNING is logged and no fact is skipped.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (all is packed, never refused for its length)
        - Fixtures/params: fake backend, caplog
        - Scope: _check_candidates called directly

    On failure, first check:
        - _pack_all in detectors/fact_check.py
    """
    caplog.set_level(logging.INFO, logger="docsentinel")
    candidates = (_candidate("a.md", "x" * 600), _candidate("a.md", "y" * 399), _candidate("b.md", "z."))

    fact_check._check_candidates(fake_backend(api_key=SENTINEL), candidates, _config("all"))

    assert fake_backend.calls == ["x" * 600 + " " + "y" * 399, "z."]
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert "DS302: fact combination all: 3 claim(s) grouped into 2 fact(s)" in messages


def test_fact_checks_sink_records_every_checked_fact(
    caplog: pytest.LogCaptureFixture, fake_backend: type[FakeBackendBase]
):
    """
    [Unit] DS302 fact checks: verifies one FactCheck per checked fact, true and false alike.

    Scenario:
        Given three candidates rated Mostly True, false at 0.9 and false at 0.3 (below the 0.6
        confidence floor), the first result carrying two rated claims
        When _check_candidates runs with a fact_checks list
        Then three FactCheck records are appended in send order with the explicit verdict label,
        confidence, backend and claims; only the confident false one is reported and is the only
        finding; the per-fact INFO line names the explicit label.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (fact checks in the report, explicit labels)
        - Fixtures/params: fake backend, caplog
        - Scope: _check_candidates called directly

    On failure, first check:
        - The fact_checks.append and the fact INFO line in _check_candidates
    """
    caplog.set_level(logging.INFO, logger="docsentinel")
    parts = (ClaimVerdict("One a.", "True", 0.9), ClaimVerdict("One b.", "Mostly True", 0.6))
    fake_backend.verdicts["One."] = FactCheckResult("true", 0.6, "fake", label="Mostly True", claims=parts)
    fake_backend.verdicts["Two."] = ("false", 0.9)
    fake_backend.verdicts["Three."] = ("false", 0.3)
    candidates = (_candidate("a.md", "One."), _candidate("a.md", "Two."), _candidate("b.md", "Three."))
    sink: list[models.FactCheck] = []

    findings = fact_check._check_candidates(
        fake_backend(api_key=SENTINEL), candidates, _config("each"), fact_checks=sink
    )

    assert sink == [
        models.FactCheck(
            path="a.md",
            fact="One.",
            verdict="Mostly True",
            confidence=0.6,
            backend="fake",
            reported=False,
            claims=(models.FactCheckClaim("One a.", "True", 0.9), models.FactCheckClaim("One b.", "Mostly True", 0.6)),
        ),
        models.FactCheck(path="a.md", fact="Two.", verdict="False", confidence=0.9, backend="fake", reported=True),
        models.FactCheck(path="b.md", fact="Three.", verdict="False", confidence=0.3, backend="fake", reported=False),
    ]
    assert [(f.path, f.value) for f in findings] == [("a.md", "False (confidence 0.90): Two.")]
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert 'DS302: fact 1/3 (1) "One." in a.md: verdict Mostly True, confidence 0.60, not reported' in messages
    assert 'DS302: fact 2/3 (2) "Two." in a.md: verdict False, confidence 0.90, reported' in messages


def test_without_a_sink_nothing_is_recorded(fake_backend: type[FakeBackendBase]):
    """
    [Unit] DS302 fact checks: verifies fact_checks=None (the default) still checks and reports.

    Scenario:
        Given one candidate rated false and no fact_checks list
        When _check_candidates runs
        Then the finding is produced and no error is raised.

    Boundaries:
        - Focus: the optional sink
        - Fixtures/params: fake backend
        - Scope: _check_candidates called directly

    On failure, first check:
        - The fact_checks is not None guard in _check_candidates
    """
    fake_backend.verdicts["One."] = ("false", 0.9)

    findings = fact_check._check_candidates(fake_backend(api_key=SENTINEL), (_candidate("a.md", "One."),), _config("each"))

    assert len(findings) == 1


@pytest.mark.parametrize("command", ["scan", "baseline"])
def test_cli_flag_parses_and_refuses_bad_values(command: str, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] CLI --fact-combination: verifies scan and baseline accept a valid value and exit 2 on a bad one.

    Scenario:
        Given the scan or baseline parser
        When --fact-combination is '1-6,7-8' and then '1-3,2-4'
        Then the first parses unchanged and the second is an argparse error (exit 2).

    Boundaries:
        - Focus: flag validation shared with the config loader
        - Fixtures/params: command
        - Scope: cli._build_parser only

    On failure, first check:
        - _fact_combination_argument in cli.py
    """
    parser = cli._build_parser()

    assert parser.parse_args([command, "--fact-combination", "1-6,7-8"]).fact_combination == "1-6,7-8"
    with pytest.raises(SystemExit) as raised:
        parser.parse_args([command, "--fact-combination", "1-3,2-4"])
    assert raised.value.code == 2
    assert "fact_check_combination must be" in capsys.readouterr().err


#: Every disposition a trace can give, with the candidate text used for it below.
_TRACE = (
    ("Selected one.", "selected"),
    ("Over the per-document cap.", "document_cap"),
    ("Below the floor.", "below_floor"),
    ("Over the total cap.", "total_cap"),
    ("A near duplicate.", "duplicate"),
    ("Selected two.", "selected"),
)


@pytest.mark.parametrize(
    ("combination", "expected"),
    [
        ("all", ["Selected one.", "Over the per-document cap.", "Over the total cap.", "Selected two."]),
        ("each", ["Selected one.", "Selected two."]),
        ("1-2", ["Selected one.", "Selected two."]),
    ],
)
def test_collect_candidates_all_ignores_the_caps(
    monkeypatch: pytest.MonkeyPatch, combination: str, expected: list[str]
):
    """
    [Unit] DS302 combination 'all': verifies every claim above the floor is collected, caps ignored.

    Scenario:
        Given a trace with selected, document_cap, total_cap, below-floor and duplicate entries
        When collect_candidates runs with fact_check_combination 'all', 'each' and a range
        Then 'all' gives the selected and both cap-rejected claims in trace order (never the
        below-floor or duplicate one), and the other values give the selected claims only.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (ALL_DISPOSITIONS)
        - Fixtures/params: trace_candidates replaced, combination
        - Scope: fact_check.collect_candidates

    On failure, first check:
        - ALL_DISPOSITIONS and the FACT_COMBINATION_ALL branch of collect_candidates
    """
    trace = fact_check.CandidateTrace(
        entries=tuple((_candidate("a.md", text), disposition) for text, disposition in _TRACE),
        documents_read=1,
        claims_extracted=len(_TRACE),
    )
    seen: list[fact_check.SelectionPolicy] = []

    def fake_trace(
        root: Path, documents: tuple, config: Config, *, policy: fact_check.SelectionPolicy
    ) -> fact_check.CandidateTrace:
        """Record the policy and return the fixed trace."""
        seen.append(policy)
        return trace

    monkeypatch.setattr(fact_check, "trace_candidates", fake_trace)

    collected = fact_check.collect_candidates(Path("."), (), _config(combination))

    assert [candidate.text for candidate in collected] == expected
    assert seen == [fact_check.DS302_POLICY]


def test_collect_candidates_forwards_an_invoker_policy(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] DS302 selection policy: verifies collect_candidates passes the invoker's policy to the trace.

    Scenario:
        Given an invoker policy with weights (0.5, 0.5, 0.0) and threshold 0.8
        When collect_candidates runs with it
        Then trace_candidates receives exactly that policy.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (scan --weights/--dedup-threshold reach DS302)
        - Fixtures/params: trace_candidates replaced
        - Scope: fact_check.collect_candidates

    On failure, first check:
        - The policy= keyword of collect_candidates
    """
    policy = fact_check.SelectionPolicy((0.5, 0.5, 0.0), 0.8)
    seen: list[fact_check.SelectionPolicy] = []

    def fake_trace(
        root: Path, documents: tuple, config: Config, *, policy: fact_check.SelectionPolicy
    ) -> fact_check.CandidateTrace:
        """Record the policy and return an empty trace."""
        seen.append(policy)
        return fact_check.CandidateTrace(entries=(), documents_read=0, claims_extracted=0)

    monkeypatch.setattr(fact_check, "trace_candidates", fake_trace)

    assert fact_check.collect_candidates(Path("."), (), _config("each"), policy=policy) == ()
    assert seen == [policy]
