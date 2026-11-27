"""The DS302 API key never leaves the backend constructor (Milestone 0010 threat model M5, HIGH FC-5).

Each case runs ``docsentinel scan`` through ``cli.main`` with the sentinel key set, a per-test log
directory and a ``docsentinel`` handler capturing every record at DEBUG, then asserts that neither
the sentinel nor its first eight characters appear in stdout, stderr, the per-run log file
(tracebacks included), any ``LogRecord`` (``msg``, ``args``, ``exc_text``), the ``ScanResult``
(``pending`` and every ``Finding`` field included), every packaged template's report, the client
``repr``, or the ``doctor`` and ``rules`` output.

The first eight characters of the sentinel are ``sentinel``, which the product name
``docsentinel`` contains (logger names, the log file name, the stderr prefix). The prefix check
therefore runs on the text with every ``docsentinel`` removed (case-insensitive); the full sentinel
and its distinctive ``not-a-real-key`` fragment are checked on the raw text.

The external resources replaced: the backend (a shared fake registered under the default name
``lenz``, so the CLI's default configuration selects it), candidate selection (no spaCy model) and
the deep-readiness probe. No network is reached and DS301 is stubbed.
"""

import io
import logging
import re
import traceback
from collections.abc import Iterator
from pathlib import Path
from typing import Optional

import pytest

from docsentinel import cli
from docsentinel.detectors import fact_check
from docsentinel.fact_check.protocol import FactCheckError, FactCheckResult
from docsentinel.log import LOG_DIR_ENV
from docsentinel.models import ScanResult
from docsentinel.reporting import render
from docsentinel.rules import ANALYZERS
from docsentinel.telemetry.loader import packaged_template_names
from tests.fact_check_fakes import SENTINEL, FakeBackendBase, make_fake_backend, register_fake_backend

#: The default backend's key variable (plan contract C3).
LENZ_KEY_ENV = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"

#: Every packaged report template name (``context`` ``report``; the ``facts`` templates render
#: ``extract-facts`` output, not a scan).
PACKAGED_TEMPLATES = packaged_template_names()

#: The claims the patched candidate selection returns.
CLAIMS = ("Acme shipped 3 releases in 2024.", "Rotterdam handled 14 ships.")

#: The deep scan command line with consent.
SCAN_ARGS = ("--profile", "deep", "--format", "json")


def leaked(text: str) -> list[str]:
    """Return the sentinel fragments found in ``text``.

    :param text: Any captured text.
    :returns: The fragments present: the sentinel, its ``not-a-real-key`` middle, or its first eight
        characters outside the product name.
    """
    found = [fragment for fragment in (SENTINEL, "not-a-real-key") if fragment in text]
    if SENTINEL[:8] in re.sub("docsentinel", "", text, flags=re.IGNORECASE):
        found.append(SENTINEL[:8])
    return found


class RecordCollector(logging.Handler):
    """Keep every record and its formatted traceback text."""

    def __init__(self):
        """Start with no records."""
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []
        self.exc_texts: list[str] = []

    def emit(self, record: logging.LogRecord):
        """Store the record and render its exception, as a file handler would.

        :param record: The record.
        """
        self.records.append(record)
        if record.exc_info:
            self.exc_texts.append("".join(traceback.format_exception(*record.exc_info)))
        if record.exc_text:
            self.exc_texts.append(record.exc_text)

    def text(self) -> str:
        """Return every message, raw ``msg``, ``args`` and exception text, joined.

        :returns: The text.
        """
        parts: list[str] = []
        for record in self.records:
            parts.extend((str(record.msg), record.getMessage(), repr(record.args)))
        parts.extend(self.exc_texts)
        return "\n".join(parts)


@pytest.fixture
def collector() -> Iterator[RecordCollector]:
    """Attach a DEBUG collector to the ``docsentinel`` logger for one test.

    :returns: The collector.
    """
    handler = RecordCollector()
    package_logger = logging.getLogger("docsentinel")
    saved = package_logger.level
    package_logger.addHandler(handler)
    package_logger.setLevel(logging.DEBUG)
    try:
        yield handler
    finally:
        package_logger.removeHandler(handler)
        package_logger.setLevel(saved)


@pytest.fixture
def corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write a two-document corpus, set the sentinel key and patch the deep prerequisites.

    :param tmp_path: The test directory.
    :param monkeypatch: Pytest monkeypatch.
    :returns: The scan root.
    """
    root = tmp_path / "docs"
    root.mkdir()
    (root / "a.md").write_text(f"# A\n\n{CLAIMS[0]}\n", encoding="utf-8")
    (root / "b.md").write_text(f"# B\n\n{CLAIMS[1]}\n", encoding="utf-8")
    monkeypatch.setenv(LOG_DIR_ENV, str(tmp_path / "logs"))
    monkeypatch.setenv(LENZ_KEY_ENV, SENTINEL)
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    monkeypatch.setattr(
        fact_check,
        "collect_candidates",
        lambda root, documents, config, **_: tuple(
            fact_check.CandidateClaim(claim=_Claim(path), text=text, score=0.9)
            for path, text in (("a.md", CLAIMS[0]), ("b.md", CLAIMS[1]))
        ),
    )
    return root


class _Claim:
    """The one attribute DS302 reads from an extracted claim."""

    def __init__(self, path: str):
        """Keep the document path.

        :param path: The document path.
        """
        self.path = path


def _run_scan(
    root: Path, monkeypatch: pytest.MonkeyPatch, *, flag: bool = True
) -> tuple[Optional[int], Optional[ScanResult], Optional[BaseException]]:
    """Run ``docsentinel scan`` and capture its exit code, result or escaped exception.

    :param root: The scan root.
    :param monkeypatch: Pytest monkeypatch, used to record the ScanResult.
    :param flag: Whether to pass ``--use-external-api``.
    :returns: ``(exit code, result, exception)``; exactly one of code and exception is set.
    """
    results: list[ScanResult] = []
    real_scan = cli.scan

    def recording(*args: object, **kwargs: object) -> ScanResult:
        """Record the result of the real scan."""
        result = real_scan(*args, **kwargs)
        results.append(result)
        return result

    monkeypatch.setattr(cli, "scan", recording)
    argv = ["scan", str(root), *SCAN_ARGS, *(("--use-external-api",) if flag else ())]
    try:
        code: Optional[int] = cli.main(argv)
        escaped: Optional[BaseException] = None
    except RuntimeError as exc:
        code, escaped = None, exc
    return code, (results[0] if results else None), escaped


def _log_files_text(tmp_path: Path) -> str:
    """Return the text of every per-run log file written under ``tmp_path/logs``.

    :param tmp_path: The test directory.
    :returns: The joined file contents.
    """
    files = sorted((tmp_path / "logs").glob("docsentinel-*.log"))
    assert files, "the CLI wrote no per-run log file"
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def _result_text(result: Optional[ScanResult]) -> str:
    """Return every surface of a scan result: repr, pending, each Finding field and every packaged report.

    :param result: The scan result, or ``None`` when the scan raised.
    :returns: The joined text.
    """
    if result is None:
        return ""
    parts = [repr(result), repr(result.pending), result.notice or ""]
    for finding in result.findings:
        parts.extend(str(value) for value in vars(finding).values())
    parts.extend(render(result, name) for name in PACKAGED_TEMPLATES)
    return "\n".join(parts)


def _doctor_and_rules_text(monkeypatch: pytest.MonkeyPatch, root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    """Return the ``doctor`` and ``rules`` output with the sentinel key and env consent set.

    :param monkeypatch: Pytest monkeypatch.
    :param root: The directory doctor runs in.
    :param capsys: Pytest output capture.
    :returns: Their joined stdout and stderr.
    """
    monkeypatch.chdir(root)
    monkeypatch.setenv("DOCSENTINEL_USE_EXTERNAL_API", "1")
    cli.main(["doctor"])
    cli.main(["rules"])
    captured = capsys.readouterr()
    monkeypatch.delenv("DOCSENTINEL_USE_EXTERNAL_API")
    return captured.out + captured.err


def _assert_nothing_leaked(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    collector: RecordCollector,
    result: Optional[ScanResult],
    fake: type[FakeBackendBase],
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
):
    """Assert the sentinel is absent from every surface named by threat model M5.

    :param tmp_path: The test directory.
    :param capsys: Pytest output capture.
    :param collector: The record collector.
    :param result: The captured scan result, if any.
    :param fake: The fake backend class.
    :param monkeypatch: Pytest monkeypatch.
    :param root: The scan root.
    """
    captured = capsys.readouterr()
    surfaces = {
        "stdout": captured.out,
        "stderr": captured.err,
        "log file": _log_files_text(tmp_path),
        "log records": collector.text(),
        "scan result": _result_text(result),
        "client repr": "\n".join(repr(client) for client in fake.instances),
    }
    surfaces["doctor and rules"] = _doctor_and_rules_text(monkeypatch, root, capsys)
    assert {name: leaked(text) for name, text in surfaces.items() if leaked(text)} == {}


def test_leak_detector_detects_each_fragment():
    """
    [Unit] DS302 key containment: verifies the leak detector sees the sentinel and ignores the product name.

    Scenario:
        Given texts with the full sentinel, its middle, its first eight characters, and only "docsentinel"
        When leaked() checks each
        Then the first three are reported and the product name alone is not.

    Boundaries:
        - Focus: the assertion helper itself, so the M5 test cannot become a no-op
        - Fixtures/params: none
        - Scope: leaked only

    On failure, first check:
        - The docsentinel removal in leaked()
    """
    assert leaked(f"Bearer {SENTINEL}") == [SENTINEL, "not-a-real-key", "sentinel"]
    assert leaked("x not-a-real-key y") == ["not-a-real-key"]
    assert leaked("key=sentinel-") == ["sentinel"]
    assert leaked("docsentinel: DocSentinel docsentinel-20261123.log") == []


def test_gate_open_success_leaks_nothing(
    tmp_path: Path,
    corpus: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    collector: RecordCollector,
):
    """
    [Unit] DS302 key containment (d): verifies a successful gate-open scan never exposes the key.

    Scenario:
        Given the sentinel key, the flag and a fake rating one claim false
        When "docsentinel scan --profile deep ... --use-external-api" runs through cli.main
        Then it exits 0 with one DS302 finding, the fake got the key, and no surface carries the key.

    Boundaries:
        - Focus: threat model M5 (success path)
        - Fixtures/params: fake registered as lenz, patched candidates, per-test log directory
        - Scope: cli.main, engine.scan, detect(), reporting.render, doctor, rules

    On failure, first check:
        - The surface named in the assertion diff
    """
    fake = register_fake_backend(monkeypatch, make_fake_backend({CLAIMS[0]: ("false", 0.8)}, name="lenz"))

    code, result, escaped = _run_scan(corpus, monkeypatch)

    assert (code, escaped) == (0, None)
    assert result is not None and [f.rule for f in result.findings] == ["DS302"]
    assert fake.calls == list(CLAIMS)
    assert [client._api_key for client in fake.instances] == [SENTINEL]
    _assert_nothing_leaked(
        tmp_path=tmp_path,
        capsys=capsys,
        collector=collector,
        result=result,
        fake=fake,
        monkeypatch=monkeypatch,
        root=corpus,
    )


def test_gate_closed_leaks_nothing(
    tmp_path: Path,
    corpus: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    collector: RecordCollector,
):
    """
    [Unit] DS302 key containment: verifies a closed gate (key set, no flag) never exposes the key.

    Scenario:
        Given the sentinel key but no flag
        When the deep CLI scan runs
        Then it exits 0, pending names the missing request, the fake is never built, and no surface carries the key.

    Boundaries:
        - Focus: threat model M5 (gate-closed path)
        - Fixtures/params: fake registered as lenz
        - Scope: cli.main, engine.scan, detect()

    On failure, first check:
        - ExternalApiGate.reasons and the doctor gate line
    """
    fake = register_fake_backend(monkeypatch, make_fake_backend(name="lenz"))

    code, result, escaped = _run_scan(corpus, monkeypatch, flag=False)

    assert (code, escaped) == (0, None)
    assert result is not None
    assert result.pending == ("DS302 skipped: pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1)",)
    assert fake.constructed == 0
    _assert_nothing_leaked(
        tmp_path=tmp_path,
        capsys=capsys,
        collector=collector,
        result=result,
        fake=fake,
        monkeypatch=monkeypatch,
        root=corpus,
    )


def test_per_claim_factcheckerror_echoing_the_key_leaks_nothing(
    tmp_path: Path,
    corpus: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    collector: RecordCollector,
):
    """
    [Unit] DS302 key containment: verifies a FactCheckError whose message echoes the key is logged by type only.

    Scenario:
        Given a fake whose check_claim raises FactCheckError("... Bearer <sentinel>") for both claims
        When the deep CLI scan runs with consent
        Then it exits 0 with no finding, two type-only WARNINGs, and no surface carries the key.

    Boundaries:
        - Focus: threat model M5 (failure path, ADR 0007 amendment: type name only)
        - Fixtures/params: fake registered as lenz
        - Scope: cli.main through _check_candidates

    On failure, first check:
        - The FactCheckError branch of _check_candidates
    """
    error = FactCheckError(f"rejected header Authorization: Bearer {SENTINEL}")
    fake = register_fake_backend(monkeypatch, make_fake_backend(dict.fromkeys(CLAIMS, error), name="lenz"))

    code, result, escaped = _run_scan(corpus, monkeypatch)

    assert (code, escaped) == (0, None)
    assert result is not None and result.findings == ()
    warnings = [r.getMessage() for r in collector.records if r.levelno == logging.WARNING]
    assert warnings == [
        "DS302: fact-check failed for a claim in a.md (FactCheckError)",
        "DS302: fact-check failed for a claim in b.md (FactCheckError)",
    ]
    _assert_nothing_leaked(
        tmp_path=tmp_path,
        capsys=capsys,
        collector=collector,
        result=result,
        fake=fake,
        monkeypatch=monkeypatch,
        root=corpus,
    )


def test_constructor_factcheckerror_leaks_nothing(
    tmp_path: Path,
    corpus: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    collector: RecordCollector,
):
    """
    [Unit] DS302 key containment (a): verifies a constructor FactCheckError echoing the key is contained.

    Scenario:
        Given a fake whose constructor raises FactCheckError carrying the sentinel
        When the deep CLI scan runs with consent
        Then it exits 0 with the fixed WARNING, no claim is sent and no surface carries the key.

    Boundaries:
        - Focus: threat model M5 item 2
        - Fixtures/params: fake registered as lenz
        - Scope: cli.main through detect()

    On failure, first check:
        - The FactCheckError branch around _construct_client
    """
    fake = register_fake_backend(
        monkeypatch, make_fake_backend(init_error=FactCheckError(f"bad key {SENTINEL}"), name="lenz")
    )

    code, result, escaped = _run_scan(corpus, monkeypatch)

    assert (code, escaped) == (0, None)
    assert result is not None and result.findings == ()
    assert fake.calls == [] and fake.instances == []
    assert "DS302 skipped: backend lenz could not be initialised (FactCheckError)" in [
        r.getMessage() for r in collector.records
    ]
    _assert_nothing_leaked(
        tmp_path=tmp_path,
        capsys=capsys,
        collector=collector,
        result=result,
        fake=fake,
        monkeypatch=monkeypatch,
        root=corpus,
    )


@pytest.mark.parametrize("case", ["constructor ValueError", "check_claim Exception"])
def test_unexpected_backend_exception_is_chainless_and_leaks_nothing(
    tmp_path: Path,
    corpus: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    collector: RecordCollector,
    case: str,
):
    """
    [Unit] DS302 key containment (b, c): verifies an exception carrying the key becomes a chainless RuntimeError.

    Scenario:
        Given a fake whose constructor raises ValueError(<sentinel>), or whose check_claim raises
        Exception("Illegal header value b'Bearer <sentinel>'") (the h11 shape)
        When the deep CLI scan runs with consent
        Then RuntimeError("DS302: backend lenz raised <type>") escapes with __cause__ and __context__ None,
        and neither the log file traceback nor any other surface carries the key.

    Boundaries:
        - Focus: threat model M5 (HIGH FC-5)
        - Fixtures/params: fake registered as lenz; two failure shapes
        - Scope: cli.main through detect()

    On failure, first check:
        - Whether detect() or _check_candidates raises the RuntimeError inside an except block
    """
    if case == "constructor ValueError":
        fake = make_fake_backend(init_error=ValueError(SENTINEL), name="lenz")
        type_name = "ValueError"
    else:
        fake = make_fake_backend({CLAIMS[0]: Exception(f"Illegal header value b'Bearer {SENTINEL}'")}, name="lenz")
        type_name = "Exception"
    register_fake_backend(monkeypatch, fake)

    code, result, escaped = _run_scan(corpus, monkeypatch)

    assert code is None and result is None
    assert isinstance(escaped, RuntimeError)
    assert str(escaped) == f"DS302: backend lenz raised {type_name}"
    assert escaped.__cause__ is None
    assert escaped.__context__ is None
    rendered = io.StringIO()
    traceback.print_exception(escaped, file=rendered)
    assert leaked(rendered.getvalue()) == []
    assert "Traceback" in _log_files_text(tmp_path)
    _assert_nothing_leaked(
        tmp_path=tmp_path,
        capsys=capsys,
        collector=collector,
        result=result,
        fake=fake,
        monkeypatch=monkeypatch,
        root=corpus,
    )


def test_unavailable_backend_leaks_nothing(
    tmp_path: Path,
    corpus: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    collector: RecordCollector,
):
    """
    [Unit] DS302 key containment: verifies an unavailable backend whose ImportError echoes the key leaks nothing.

    Scenario:
        Given the key and the flag, with load_backend raising ImportError carrying the sentinel
        When the deep CLI scan runs
        Then it exits 0, pending says the backend is not available and no surface carries the key.

    Boundaries:
        - Focus: threat model M5 (unavailable path) and the ADR 0007 honesty ruling
        - Fixtures/params: load_backend patched
        - Scope: cli.main through resolve_external_api_gate

    On failure, first check:
        - _backend_loadable logs the exception type name only
    """
    fake = make_fake_backend(name="lenz")

    def unavailable(name: str) -> type:
        """Fail like a backend whose module cannot import."""
        raise ImportError(f"cannot import lenz: {SENTINEL}")

    monkeypatch.setattr(fact_check, "load_backend", unavailable)

    code, result, escaped = _run_scan(corpus, monkeypatch)

    assert (code, escaped) == (0, None)
    assert result is not None and result.pending == ("DS302 skipped: backend lenz not available",)
    _assert_nothing_leaked(
        tmp_path=tmp_path,
        capsys=capsys,
        collector=collector,
        result=result,
        fake=fake,
        monkeypatch=monkeypatch,
        root=corpus,
    )


def test_fake_result_type_is_the_protocol_result():
    """
    [Unit] DS302 key containment: verifies the shared fake returns validated FactCheckResult objects.

    Scenario:
        Given a fake made with name "lenz" and one scripted verdict
        When check_claim is called directly
        Then the result is a FactCheckResult naming lenz, and the client repr holds no key.

    Boundaries:
        - Focus: the shared fake used by the M5 cases above
        - Fixtures/params: none
        - Scope: tests/fact_check_fakes.py

    On failure, first check:
        - make_fake_backend in tests/fact_check_fakes.py
    """
    fake = make_fake_backend({"x": "false"}, name="lenz")
    client = fake(api_key=SENTINEL)

    assert client.check_claim("x") == FactCheckResult(verdict="false", confidence=0.9, backend="lenz")
    assert fake.API_KEY_ENV_VAR == LENZ_KEY_ENV
    assert leaked(repr(client)) == []
