"""DS302 send loop with ``fact_check_combination`` and a fake backend (no network)."""

import logging
from types import SimpleNamespace

import pytest

from docsentinel import cli
from docsentinel.config import Config
from docsentinel.detectors import fact_check
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
        ("a.md", "false (confidence 0.90): Three. Four."),
        ("b.md", "false (confidence 0.90): Three. Four."),
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
    [Unit] DS302 combination: verifies a combined fact over the send limit is skipped with a WARNING.

    Scenario:
        Given two 600-character candidates combined with 'all' (1,201 characters)
        When _check_candidates runs
        Then nothing is sent and one WARNING names the group and its length.

    Boundaries:
        - Focus: the MAX_CANDIDATE_CHARS bound holds for combined text (no truncation)
        - Fixtures/params: fake backend, caplog
        - Scope: _check_candidates called directly

    On failure, first check:
        - The length check before check_claim in _check_candidates
    """
    candidates = (_candidate("a.md", "x" * 600), _candidate("a.md", "y" * 600))

    assert fact_check._check_candidates(fake_backend(api_key=SENTINEL), candidates, _config("all")) == ()

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
