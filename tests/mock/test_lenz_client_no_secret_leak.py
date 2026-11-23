"""The sentinel API key never leaves the ``httpx`` header store (Story 03.0 Task 04 step 5, egress E7).

Every case drives ``LenzFactCheckClient`` through an ``httpx.MockTransport`` with DEBUG capture on
the root, ``httpx`` and ``httpcore`` loggers, then searches every sink a key could leak into: log
records (message, arguments and exception text), every ``FactCheckError`` message, its
``__cause__`` and ``__context__`` and its formatted traceback, every ``FactCheckResult`` field,
``repr``/``str`` of the client and ``vars(client)`` (the ``httpx`` client object itself, whose
header store masks ``Authorization``, is checked through its own masked ``repr``). No network is
reached; the only key is :data:`tests.fact_check_fakes.SENTINEL`.
"""

from __future__ import annotations

import importlib
import logging
import traceback
from types import ModuleType
from typing import Optional

import httpx
import pytest

from docsentinel.fact_check.protocol import FactCheckError, FactCheckResult
from tests.fact_check_fakes import SENTINEL
from tests.mock.test_lenz_client_transport import FAILURE_RESPONSES, Handler

pytestmark = pytest.mark.usefixtures("lenz_module")

#: The client module under test.
_LENZ = "docsentinel.fact_check.lenz"

#: A success response body built from the documented field names.
_SUCCESS = b'{"claims": [{"claim": "x", "verdict": "True", "confidence": 0.9}], "error": null}'


def _lenz() -> ModuleType:
    """Return the client module imported by the ``lenz_module`` fixture.

    :return: The module.
    """
    return importlib.import_module(_LENZ)


def _stream(body: bytes, status: int = 200) -> httpx.Response:
    """Build a streamed response.

    :param body: The body bytes.
    :param status: The status code.
    :return: The response.
    """
    return httpx.Response(status, stream=httpx.ByteStream(body))


def _raise_with_key(request: httpx.Request) -> httpx.Response:
    """Raise a transport error whose text carries the key and the request headers.

    :param request: The request sent.
    :raises httpx.ConnectError: Always.
    """
    raise httpx.ConnectError(f"{SENTINEL} {dict(request.headers)!r}", request=request)


def _raise_foreign(request: httpx.Request) -> httpx.Response:
    """Raise a ``ValueError`` (mapped to a request failure) whose text carries the key.

    :param request: The request sent.
    :raises ValueError: Always.
    """
    raise ValueError(f"Bearer {SENTINEL}")


#: Every transport case: the shared failure table plus success, no-claim and transport errors.
_CASES: list[tuple[str, Handler]] = [(case_id, handler) for case_id, handler, _ in FAILURE_RESPONSES] + [
    ("success", lambda request: _stream(_SUCCESS)),
    ("no_claim", lambda request: _stream(b'{"claims": [], "error_code": "no_claim"}')),
    ("connect_error", _raise_with_key),
    ("value_error", _raise_foreign),
]


class _Sinks:
    """Every text a key could leak into, collected across cases."""

    def __init__(self):
        """Start with no collected text or errors."""
        self.texts: list[str] = []
        self.errors: list[FactCheckError] = []

    def add_error(self, error: FactCheckError):
        """Collect an error's message, chain and formatted traceback.

        :param error: The raised error.
        """
        self.errors.append(error)
        self.texts += [str(error), repr(error), repr(error.args), str(error.__cause__), str(error.__context__)]
        self.texts += traceback.format_exception(error)

    def add_result(self, result: FactCheckResult):
        """Collect every field of a result.

        :param result: The returned result.
        """
        self.texts += [repr(result), result.verdict, str(result.confidence), result.backend, repr(result.citations)]

    def add_client(self, client: object):
        """Collect ``repr``/``str`` and every instance attribute of a client.

        :param client: The client.
        """
        self.texts += [repr(client), str(client)]
        for name, value in vars(client).items():
            self.texts.append(name)
            if isinstance(value, httpx.Client):
                self.texts += [repr(value), repr(value.headers), repr(value.cookies)]
            else:
                self.texts.append(repr(value))

    def add_records(self, records: list[logging.LogRecord]):
        """Collect every captured log record.

        :param records: The records.
        """
        for record in records:
            self.texts += [record.getMessage(), repr(record.args), record.exc_text or "", repr(record.exc_info)]


def _capture_debug(caplog: pytest.LogCaptureFixture):
    """Capture DEBUG records on the root, ``httpx`` and ``httpcore`` loggers.

    :param caplog: The log capture.
    """
    for name in (None, "httpx", "httpcore", _LENZ):
        caplog.set_level(logging.DEBUG, logger=name)


def _run_case(handler: Handler, sinks: _Sinks):
    """Drive one claim through ``handler`` and collect the outcome into ``sinks``.

    :param handler: The response factory.
    :param sinks: The collector.
    """
    client = _lenz().LenzFactCheckClient(SENTINEL, transport=httpx.MockTransport(handler))
    sinks.add_client(client)
    outcome: Optional[FactCheckResult] = None
    try:
        outcome = client.check_claim("Python 3.12 was released in 2023.")
    except FactCheckError as error:
        sinks.add_error(error)
    if outcome is not None:
        sinks.add_result(outcome)
    sinks.add_client(client)
    client.close()
    sinks.add_client(client)


def _run_constructor_and_claim_refusals(sinks: _Sinks):
    """Drive the key, claim-bound and closed-client refusals into ``sinks``.

    :param sinks: The collector.
    """
    for key in ("", SENTINEL + "\r\n", SENTINEL + " ", "Bearer " + SENTINEL, SENTINEL[:15], SENTINEL * 10):
        with pytest.raises(FactCheckError) as info:
            _lenz().LenzFactCheckClient(key)
        sinks.add_error(info.value)
    client = _lenz().LenzFactCheckClient(SENTINEL, transport=httpx.MockTransport(lambda request: _stream(_SUCCESS)))
    for claim in ("", "x" * 1001, "\ud800"):
        with pytest.raises(FactCheckError) as info:
            client.check_claim(claim)
        sinks.add_error(info.value)
    client.close()
    with pytest.raises(FactCheckError) as info:
        client.check_claim("A claim.")
    sinks.add_error(info.value)
    sinks.add_client(client)


def _run_close_failure(monkeypatch: pytest.MonkeyPatch, sinks: _Sinks):
    """Close a client whose ``httpx.Client.close`` raises an error carrying the key.

    :param monkeypatch: Patches ``httpx.Client.close`` for this step only.
    :param sinks: The collector.
    """
    client = _lenz().LenzFactCheckClient(SENTINEL, transport=httpx.MockTransport(lambda request: _stream(_SUCCESS)))

    def explode(self: httpx.Client):
        """Raise an error carrying the key.

        :param self: The httpx client.
        :raises OSError: Always.
        """
        raise OSError(SENTINEL)

    with monkeypatch.context() as patch:
        patch.setattr(httpx.Client, "close", explode)
        client.close()
    sinks.add_client(client)


def _collect_everything(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> _Sinks:
    """Run every case with DEBUG capture and return the collected sinks.

    :param monkeypatch: Pytest monkeypatch.
    :param caplog: The log capture.
    :return: The collected sinks.
    """
    _capture_debug(caplog)
    sinks = _Sinks()
    for _, handler in _CASES:
        _run_case(handler, sinks)
    _run_constructor_and_claim_refusals(sinks)
    _run_close_failure(monkeypatch, sinks)
    sinks.add_records(caplog.records)
    return sinks


def test_sentinel_absent_from_all_sinks(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    """
    [Unit] lenz no-secret-leak: verifies the sentinel key reaches no log record, message, chain, result or attribute.

    Scenario:
        Given DEBUG capture on root, httpx and httpcore, and every transport case (success,
        no_claim, each failure shape, transport errors whose text carries the key, key and claim
        refusals, a closed client, a failing close)
        When each case runs
        Then the sentinel appears in no record, FactCheckError message, __cause__, __context__,
        traceback, FactCheckResult field, repr/str of the client or vars(client) entry; the only
        place it lives is the masked httpx header store.

    Boundaries:
        - Focus: E7 (threat model EG-7), story README test plan
        - Fixtures/params: caplog at DEBUG; monkeypatch for the failing close only
        - Scope: LenzFactCheckClient with httpx.MockTransport

    On failure, first check:
        - The leaking text below; then __init__ (key kept only in headers=) and every log call
    """
    sinks = _collect_everything(monkeypatch, caplog)

    leaks = [text for text in sinks.texts if SENTINEL in text or SENTINEL[:16] in text]
    assert leaks == []
    assert len(sinks.errors) >= len(FAILURE_RESPONSES) + 10
    assert caplog.records, "DEBUG capture recorded nothing; the leak check would be vacuous"
    probe = _lenz().LenzFactCheckClient(SENTINEL, transport=httpx.MockTransport(lambda request: _stream(_SUCCESS)))
    inner = vars(probe)["_client"]
    assert inner.headers["authorization"] == f"Bearer {SENTINEL}"
    assert SENTINEL not in repr(inner.headers)
    assert sorted(vars(probe)) == ["_client", "_closed"]
    probe.close()


def test_exceptions_have_no_chain(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    """
    [Unit] lenz no-secret-leak: verifies every FactCheckError the client raises has no exception chain.

    Scenario:
        Given every transport, key, claim and closed-client case
        When each FactCheckError is inspected
        Then __cause__ and __context__ are None, so no foreign exception text (which may hold the
        key) is ever attached.

    Boundaries:
        - Focus: E7.4, E12
        - Fixtures/params: caplog, monkeypatch
        - Scope: every raise site of LenzFactCheckClient

    On failure, first check:
        - A raise placed inside an except block in lenz.py
    """
    sinks = _collect_everything(monkeypatch, caplog)

    chained = [(str(error), error.__cause__, error.__context__) for error in sinks.errors]
    assert [entry for entry in chained if entry[1] is not None or entry[2] is not None] == []
    assert {type(error) for error in sinks.errors} == {FactCheckError}
