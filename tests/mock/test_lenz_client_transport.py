"""Mock-transport tests of ``LenzFactCheckClient`` (Milestone 0010 Story 03.0 Tasks 02 and 04).

Every request goes to an ``httpx.MockTransport`` whose handler records it; no test opens a socket
or contacts any host, and the session-wide network guard in ``tests/conftest.py`` fails any test
that reaches a real ``httpx`` transport. Every response body is written here as a literal built
from the five documented field names (``claims``, ``claim``, ``verdict``, ``confidence``,
``error``/``error_code``); nothing is loaded or copied from the example documentation. The only
key is the shared :data:`tests.fact_check_fakes.SENTINEL`.

The tests are named after the egress threat model's mitigation-to-test map
(``docs/security/threat-model-0010-fact-check-egress-2026-11-24.md``, E1 to E12). The client
module is imported per test by the ``lenz_module`` fixture of ``tests/conftest.py``, which also
removes it and its registry entry afterwards. The fixed messages are pinned as literals rather
than read from the module.

:data:`FAILURE_RESPONSES` is reused by ``tests/mock/test_lenz_client_no_secret_leak.py``.
"""

from __future__ import annotations

import gzip
import importlib
import json
import logging
import threading
import time
import zlib
from collections.abc import Callable, Iterator
from types import ModuleType
from typing import TYPE_CHECKING, Optional

import httpx
import pytest

from docsentinel.fact_check.protocol import FACT_CHECK_BACKENDS, FactCheckClient, FactCheckError, load_backend
from tests.conftest import NETWORK_GUARD_MESSAGE
from tests.fact_check_fakes import SENTINEL

if TYPE_CHECKING:
    from docsentinel.fact_check.lenz import LenzFactCheckClient

pytestmark = pytest.mark.usefixtures("lenz_module")

Handler = Callable[[httpx.Request], httpx.Response]

#: The client module under test.
_LENZ = "docsentinel.fact_check.lenz"

#: The one URL a request may target (E1), pinned.
ASSESS_URL = "https://lenz.io/api/v1/assess"

#: The fixed messages of threat model E12, pinned as literals.
KEY_MESSAGE = "lenz API key is missing or malformed"
CLAIM_MESSAGE = "lenz /assess claim text is empty, too long or not encodable"
ENCODING_MESSAGE = "lenz /assess response used an unsupported content encoding"
SIZE_MESSAGE = "lenz /assess response exceeded the size cap"
TIME_MESSAGE = "lenz /assess request exceeded the time limit"
SHAPE_MESSAGE = "lenz /assess returned an unexpected response shape"
ERROR_MESSAGE = "lenz /assess returned an error"
VERDICT_MESSAGE = "lenz /assess returned an unrecognised verdict"
CLOSED_MESSAGE = "lenz client is closed"

#: The cap of MAX_RESPONSE_BYTES, pinned.
MAX_RESPONSE_BYTES = 65_536

#: A marker string that must never reach a message, a result or a log record.
MARKER = "MARKER-0010-response-data"

#: A claim used where its text does not matter.
CLAIM = "Python 3.12 was released in 2023."

#: The exact request header names of threat model E8.
E8_HEADERS = {
    "host",
    "accept",
    "accept-encoding",
    "connection",
    "user-agent",
    "authorization",
    "content-type",
    "content-length",
}


def _lenz() -> ModuleType:
    """Return the client module imported by the ``lenz_module`` fixture.

    :return: The module.
    """
    return importlib.import_module(_LENZ)


def _worker_clock(now: list[float], caller_time: float) -> Callable[[], float]:
    """Return a patched ``_monotonic`` that only the request thread sees advancing.

    The calling thread always reads ``caller_time``, so ``check_claim`` computes its deadline and
    its ``join`` timeout from it and waits for the worker to finish; the worker reads ``now[0]``.
    No real time passes.

    :param now: The worker's clock, mutated by the test.
    :param caller_time: The constant time the calling thread reads.
    :return: The clock function.
    """
    caller = threading.current_thread()
    return lambda: caller_time if threading.current_thread() is caller else now[0]


class _Chunks(httpx.SyncByteStream):
    """A streamed body that counts the bytes pulled from it."""

    def __init__(self, chunks: list[bytes]):
        """Hold the chunks to yield.

        :param chunks: The body chunks, in order.
        """
        self.chunks = chunks
        self.pulled = 0

    def __iter__(self) -> Iterator[bytes]:
        """Yield each chunk, counting the bytes pulled.

        :return: An iterator over the chunks.
        """
        for chunk in self.chunks:
            self.pulled += len(chunk)
            yield chunk


def _json_response(payload: object, status: int = 200, headers: Optional[dict[str, str]] = None) -> httpx.Response:
    """Build a streamed JSON response.

    :param payload: The JSON value.
    :param status: The status code.
    :param headers: Extra headers.
    :return: The response.
    """
    return _raw_response(json.dumps(payload).encode("utf-8"), status, headers)


def _raw_response(body: bytes, status: int = 200, headers: Optional[dict[str, str]] = None) -> httpx.Response:
    """Build a streamed response with a raw body.

    :param body: The body bytes.
    :param status: The status code.
    :param headers: Extra headers.
    :return: The response.
    """
    return httpx.Response(status, headers=headers or {}, stream=httpx.ByteStream(body))


def _client(handler: Handler, requests: list[httpx.Request]) -> LenzFactCheckClient:
    """Return a client whose transport records every request and answers with ``handler``.

    :param handler: The response factory.
    :param requests: Receives every request sent.
    :return: The client.
    """

    def record(request: httpx.Request) -> httpx.Response:
        """Record the request and answer it.

        :param request: The request sent.
        :return: The handler's response.
        """
        requests.append(request)
        return handler(request)

    return _lenz().LenzFactCheckClient(SENTINEL, transport=httpx.MockTransport(record))


def _success(verdict: object = "True", confidence: object = 0.9) -> httpx.Response:
    """Return a documented one-claim success response.

    :param verdict: The raw verdict value.
    :param confidence: The raw confidence value.
    :return: The response.
    """
    return _json_response({"claims": [{"claim": "x", "verdict": verdict, "confidence": confidence}], "error": None})


def _failure(handler: Handler, requests: Optional[list[httpx.Request]] = None) -> FactCheckError:
    """Send one claim and return the ``FactCheckError`` it raised.

    :param handler: The response factory.
    :param requests: Receives every request sent, when given.
    :return: The raised error.
    """
    client = _client(handler, [] if requests is None else requests)
    with pytest.raises(FactCheckError) as info:
        client.check_claim(CLAIM)
    client.close()
    return info.value


def _assert_fixed(error: FactCheckError, message: str):
    """Assert ``error`` has exactly ``message`` and no exception chain (E7.4, E12).

    :param error: The raised error.
    :param message: The expected fixed text.
    """
    assert str(error) == message
    assert error.__cause__ is None
    assert error.__context__ is None
    assert MARKER not in str(error)
    assert SENTINEL not in str(error)


def _success_body(confidence: str) -> bytes:
    """Return a raw one-claim success body with ``confidence`` written verbatim.

    :param confidence: The JSON text of the confidence value.
    :return: The body bytes.
    """
    return b'{"claims": [{"claim": "x", "verdict": "True", "confidence": ' + confidence.encode("ascii") + b"}]}"


#: Every response-side failure shape with its fixed message; also driven by the no-secret-leak
#: module. Each entry is ``(id, handler, message)``.
FAILURE_RESPONSES: list[tuple[str, Handler, str]] = [
    (
        "redirect_302",
        lambda r: _raw_response(b"", 302, {"Location": "https://other.example/x"}),
        "lenz /assess returned HTTP 302",
    ),
    ("status_401", lambda r: _raw_response(b"denied " + MARKER.encode(), 401), "lenz /assess returned HTTP 401"),
    ("status_429", lambda r: _raw_response(b"", 429, {"Retry-After": "1"}), "lenz /assess returned HTTP 429"),
    ("status_500", lambda r: _raw_response(b"", 500), "lenz /assess returned HTTP 500"),
    ("gzip", lambda r: _raw_response(gzip.compress(b"{}"), 200, {"Content-Encoding": "gzip"}), ENCODING_MESSAGE),
    ("content_length_over_cap", lambda r: _raw_response(b"{}", 200, {"Content-Length": "65537"}), SIZE_MESSAGE),
    ("streamed_over_cap", lambda r: _raw_response(b" " * (MAX_RESPONSE_BYTES + 1)), SIZE_MESSAGE),
    ("malformed_json", lambda r: _raw_response(b"{not json " + MARKER.encode()), SHAPE_MESSAGE),
    ("deep_nesting", lambda r: _raw_response(b"[" * 10_000 + b"]" * 10_000), SHAPE_MESSAGE),
    ("nan", lambda r: _raw_response(_success_body("NaN")), SHAPE_MESSAGE),
    ("huge_integer", lambda r: _raw_response(_success_body("1" + "0" * 400)), SHAPE_MESSAGE),
    ("confidence_str", lambda r: _success(confidence="0.9"), SHAPE_MESSAGE),
    ("confidence_bool", lambda r: _success(confidence=True), SHAPE_MESSAGE),
    ("top_level_list", lambda r: _json_response([]), SHAPE_MESSAGE),
    ("claims_not_list", lambda r: _json_response({"claims": {}}), SHAPE_MESSAGE),
    ("unknown_verdict", lambda r: _success(verdict=MARKER), VERDICT_MESSAGE),
    (
        "safe_error_code",
        lambda r: _json_response({"claims": [], "error_code": "rate_limited"}),
        "lenz /assess returned error rate_limited",
    ),
    ("unsafe_error_code", lambda r: _json_response({"claims": [], "error_code": MARKER}), ERROR_MESSAGE),
    ("error_text", lambda r: _json_response({"claims": [], "error": MARKER}), ERROR_MESSAGE),
    (
        "pre_decoded_content",
        lambda r: httpx.Response(200, content=b"{}"),
        "lenz /assess request failed (StreamConsumed)",
    ),
]


# --- success shape and registry ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0.9, 0.9), (1.4, 1.0), (-0.2, 0.0), (1, 1.0), (0, 0.0), (0.0, 0.0), (1.0, 1.0)],
)
def test_success_maps_and_clamps_confidence(raw: object, expected: float):
    """
    [Unit] lenz client: verifies a documented success maps to a result with a clamped confidence.

    Scenario:
        Given a one-claim success response with a given confidence
        When check_claim runs
        Then the result is true/lenz, the confidence is a float clamped to [0.0, 1.0] and the
        client satisfies the FactCheckClient protocol.

    Boundaries:
        - Focus: Task 02 step 4.8, E6.5
        - Fixtures/params: raw, expected
        - Scope: LenzFactCheckClient with httpx.MockTransport

    On failure, first check:
        - _confidence clamping in lenz.py

    :param raw: The raw confidence value.
    :param expected: The clamped value.
    """
    client = _client(lambda request: _success(confidence=raw), [])
    result = client.check_claim(CLAIM)
    assert isinstance(client, FactCheckClient)
    assert (result.verdict, result.confidence, result.backend, result.citations) == ("true", expected, "lenz", ())
    assert type(result.confidence) is float
    client.close()


@pytest.mark.parametrize(
    "payload",
    [{"claims": [], "error": "x", "error_code": "no_claim"}, {"claims": [], "error": None, "error_code": None}],
    ids=["no_claim", "empty_claims"],
)
def test_no_claim_and_empty_claims_are_unverifiable(payload: dict[str, object]):
    """
    [Unit] lenz client: verifies no_claim and an empty claims list give unverifiable at 0.0.

    Scenario:
        Given a no_claim response and an empty claims response
        When check_claim runs
        Then each returns unverifiable with confidence 0.0, never an error.

    Boundaries:
        - Focus: decision U6, Task 02 steps 4.3 and 4.5
        - Fixtures/params: payload
        - Scope: LenzFactCheckClient with httpx.MockTransport

    On failure, first check:
        - The order of the no_claim and error checks in _parse_assess

    :param payload: The response body.
    """
    client = _client(lambda request: _json_response(payload), [])
    result = client.check_claim("A claim.")
    assert (result.verdict, result.confidence, result.backend, result.citations) == ("unverifiable", 0.0, "lenz", ())
    client.close()


def test_load_backend_returns_lenz_class(lenz_module: ModuleType):
    """
    [Unit] lenz client: verifies load_backend("lenz") returns the class the module registered.

    Scenario:
        Given the client module imported (it registers itself)
        When load_backend("lenz") is called
        Then it returns LenzFactCheckClient, whose name and key variable are fixed.

    Boundaries:
        - Focus: Task 03 step 1, Task 04 step 6
        - Fixtures/params: lenz_module (removes the registry entry afterwards)
        - Scope: protocol.load_backend

    On failure, first check:
        - The FACT_CHECK_BACKENDS assignment at the end of lenz.py

    :param lenz_module: The imported client module.
    """
    cls = load_backend("lenz")
    assert cls is lenz_module.LenzFactCheckClient
    assert FACT_CHECK_BACKENDS["lenz"] is cls
    assert (cls.name, cls.API_KEY_ENV_VAR) == ("lenz", "DOCSENTINEL_FACTCHECK_LENZ_API_KEY")


def test_network_guard_trips():
    """
    [Unit] test session: verifies the session-wide network guard refuses a real httpx transport.

    Scenario:
        Given a default httpx.Client (real HTTPTransport)
        When it sends a request to a non-routable TEST-NET-1 address
        Then the guard raises AssertionError("real network transport reached") before any socket.

    Boundaries:
        - Focus: Task 04 step 1 self-test
        - Fixtures/params: the session-scoped _no_real_network_transport fixture
        - Scope: httpx.HTTPTransport.handle_request

    On failure, first check:
        - _no_real_network_transport in tests/conftest.py
    """
    with httpx.Client(trust_env=False) as client:
        with pytest.raises(AssertionError, match=f"^{NETWORK_GUARD_MESSAGE}$"):
            client.get("http://192.0.2.1:9/")


# --- E1: one fixed URL ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "claim",
    [
        "Is it true? Yes.",
        "See section #anchor for details.",
        "The path ../../etc/passwd is relative.",
        "Mail admin@evil.example for access.",
        "See https://evil.example/../x?y=1#z @host for details.",
        "//evil.example/assess",
    ],
)
def test_request_targets_exact_assess_url(claim: str):
    """
    [Unit] lenz client: verifies claim text never changes the request URL.

    Scenario:
        Given a claim holding ?, #, a dot-dot segment, @ or a full URL
        When check_claim sends it
        Then exactly one POST went to https://lenz.io/api/v1/assess with no query or fragment, and
        the claim travelled only in the JSON body.

    Boundaries:
        - Focus: E1
        - Fixtures/params: claim
        - Scope: LenzFactCheckClient._fetch

    On failure, first check:
        - The stream() call in _fetch (it must pass ASSESS_URL unchanged)

    :param claim: The URL-shaped claim text.
    """
    requests: list[httpx.Request] = []
    client = _client(lambda request: _success(), requests)
    client.check_claim(claim)
    client.close()
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == ASSESS_URL
    assert (request.url.host, request.url.path, request.url.query, request.url.fragment) == (
        "lenz.io",
        "/api/v1/assess",
        b"",
        "",
    )
    assert json.loads(request.content) == {"claim": claim}


# --- E2: redirects and status ------------------------------------------------------------------


def test_redirect_302_not_followed():
    """
    [Unit] lenz client: verifies a 302 is an error, is not followed and its Location is not echoed.

    Scenario:
        Given a 302 response whose Location names another host
        When check_claim runs
        Then FactCheckError says HTTP 302, exactly one request was recorded and the Location value
        is absent from the message.

    Boundaries:
        - Focus: E2
        - Fixtures/params: none
        - Scope: LenzFactCheckClient._check_head

    On failure, first check:
        - follow_redirects=False and the status check in _check_head
    """
    location = "https://other.example/steal?k=1"
    requests: list[httpx.Request] = []
    error = _failure(lambda request: _raw_response(b"", 302, {"Location": location}), requests)
    _assert_fixed(error, "lenz /assess returned HTTP 302")
    assert "302" in str(error)
    assert location not in str(error) and "other.example" not in str(error)
    assert len(requests) == 1
    assert str(requests[0].url) == ASSESS_URL


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503, 201, 204, 301, 307, 308])
def test_status_401_429_500_raise(status: int):
    """
    [Unit] lenz client: verifies every status other than 200 raises a fixed FactCheckError.

    Scenario:
        Given a response with a non-200 status and a body holding a marker
        When check_claim runs
        Then FactCheckError says "returned HTTP <status>", the body is not echoed and no retry is made.

    Boundaries:
        - Focus: E2 (any non-200 including 2xx and 3xx), no retries
        - Fixtures/params: status
        - Scope: LenzFactCheckClient._check_head

    On failure, first check:
        - status != 200 in _check_head

    :param status: The HTTP status.
    """
    requests: list[httpx.Request] = []
    error = _failure(lambda request: _raw_response(MARKER.encode(), status), requests)
    _assert_fixed(error, f"lenz /assess returned HTTP {status}")
    assert len(requests) == 1


# --- E3: no ambient proxy or CA ---------------------------------------------------------------


def test_env_proxy_and_ca_vars_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory):
    """
    [Unit] lenz client: verifies proxy and CA environment variables never reach the real client.

    Scenario:
        Given HTTPS_PROXY, ALL_PROXY, SSL_CERT_FILE (a missing file) and SSL_CERT_DIR set
        When the client is built with no transport injected
        Then the httpx.Client has trust_env False and no proxy mounts, construction did not try to
        load the missing CA file, and no request was sent.

    Boundaries:
        - Focus: E3 (trust_env=False)
        - Fixtures/params: monkeypatch sets the variables; the session network guard is active
        - Scope: LenzFactCheckClient.__init__ with the real HTTPTransport, never used

    On failure, first check:
        - trust_env=False in the httpx.Client call (a trusted SSL_CERT_FILE that is missing raises)
    """
    missing = tmp_path_factory.mktemp("ca") / "missing-ca.pem"
    monkeypatch.setenv("HTTPS_PROXY", "http://192.0.2.1:9")
    monkeypatch.setenv("ALL_PROXY", "socks5://192.0.2.1:9")
    monkeypatch.setenv("SSL_CERT_FILE", str(missing))
    monkeypatch.setenv("SSL_CERT_DIR", str(missing.parent))
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _forbidden_send)

    client = _lenz().LenzFactCheckClient(SENTINEL)

    inner = vars(client)["_client"]
    assert inner.trust_env is False
    assert inner._mounts == {}
    assert type(inner._transport) is httpx.HTTPTransport
    assert not missing.exists()
    client.close()


def _forbidden_send(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
    """Fail the test if the real transport is asked to send anything.

    :param self: The transport.
    :param request: The request.
    :raises AssertionError: Always.
    """
    raise AssertionError("a request was sent")


# --- E4: hard deadline ------------------------------------------------------------------------


def test_slow_drip_body_exceeds_deadline(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] lenz client: verifies the deadline is checked between raw body chunks.

    Scenario:
        Given a patched monotonic clock that jumps past the deadline once the body starts
        When check_claim reads a chunked body
        Then the time-limit FactCheckError is raised, with no real sleep, and the rest of the
        stream is never pulled.

    Boundaries:
        - Focus: E4.3
        - Fixtures/params: monkeypatch replaces lenz._monotonic only
        - Scope: LenzFactCheckClient._read_capped

    On failure, first check:
        - The deadline check in the _read_capped loop
    """
    now = [1000.0]
    pulled: list[bytes] = []
    monkeypatch.setattr(_lenz(), "_monotonic", _worker_clock(now, 1000.0))

    class Drip(httpx.SyncByteStream):
        """A body whose second chunk arrives after the deadline."""

        def __iter__(self) -> Iterator[bytes]:
            """Yield chunks, advancing the patched clock past the deadline after the first.

            :return: An iterator over the chunks.
            """
            for chunk in (b'{"claims": ', b"[]", b"}"):
                pulled.append(chunk)
                yield chunk
                now[0] += 31.0

    error = _failure(lambda request: httpx.Response(200, stream=Drip()))
    _assert_fixed(error, TIME_MESSAGE)
    assert pulled == [b'{"claims": ', b"[]"]


def test_slow_drip_within_deadline_succeeds(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] lenz client: verifies a body that finishes just before the deadline is accepted.

    Scenario:
        Given a patched clock advancing 29 s across a chunked success body
        When check_claim reads it
        Then the result is returned (the deadline boundary is not off by one chunk).

    Boundaries:
        - Focus: E4.3 boundary
        - Fixtures/params: monkeypatch replaces lenz._monotonic only
        - Scope: LenzFactCheckClient._read_capped

    On failure, first check:
        - The >= deadline comparisons in _read_capped
    """
    now = [1000.0]
    monkeypatch.setattr(_lenz(), "_monotonic", _worker_clock(now, 1000.0))
    body = json.dumps({"claims": [{"claim": "x", "verdict": "False", "confidence": 0.5}]}).encode()

    class Drip(httpx.SyncByteStream):
        """A body that arrives slowly but within the deadline."""

        def __iter__(self) -> Iterator[bytes]:
            """Yield the body in halves, advancing the clock 14.5 s per chunk.

            :return: An iterator over the chunks.
            """
            for chunk in (body[:10], body[10:]):
                now[0] += 14.5
                yield chunk

    client = _client(lambda request: httpx.Response(200, stream=Drip()), [])
    result = client.check_claim(CLAIM)
    client.close()
    assert (result.verdict, result.confidence) == ("false", 0.5)


def test_hung_header_phase_bounded():
    """
    [Unit] lenz client: verifies a transport that never answers is cut off at the hard deadline.

    Scenario:
        Given a handler blocking on an event and a subclass with a 0.05 s deadline
        When check_claim runs
        Then the time-limit FactCheckError is raised within 1 s; the event is set in teardown and
        the abandoned worker is joined once for at most 1 s.

    Boundaries:
        - Focus: E4 (hard wall-clock deadline outside the blocking call); the one allowed real wait
        - Fixtures/params: none
        - Scope: LenzFactCheckClient.check_claim worker thread

    On failure, first check:
        - The daemon thread and join(timeout=...) in check_claim
    """
    release = threading.Event()
    workers: list[threading.Thread] = []

    class FastDeadline(_lenz().LenzFactCheckClient):
        """The client with a 0.05 s deadline."""

        REQUEST_TIMEOUT_SECONDS = 0.05

    def hang(request: httpx.Request) -> httpx.Response:
        """Block until teardown releases the event.

        :param request: The request sent.
        :return: A success response, too late to be read.
        """
        workers.append(threading.current_thread())
        release.wait(5)
        return _success()

    client = FastDeadline(SENTINEL, transport=httpx.MockTransport(hang))
    try:
        started = time.monotonic()
        with pytest.raises(FactCheckError) as info:
            client.check_claim("A claim.")
        assert time.monotonic() - started < 1.0
        _assert_fixed(info.value, TIME_MESSAGE)
        assert [worker.daemon for worker in workers] == [True]
        assert workers[0] is not threading.current_thread()
    finally:
        release.set()
        if workers:
            workers[0].join(1.0)
        client.close()


# --- E5: encoding and size cap ------------------------------------------------------------------


def test_oversized_streamed_body_stops_early():
    """
    [Unit] lenz client: verifies a streamed body over the cap stops after at most one extra chunk.

    Scenario:
        Given a 200 response streaming MAX_RESPONSE_BYTES + 1 bytes in 4 KiB chunks from a
        generator, followed by more, and no Content-Length
        When check_claim reads it
        Then it raises the size-cap error and pulled at most the cap plus one chunk.

    Boundaries:
        - Focus: E5 (raw-byte cap)
        - Fixtures/params: none
        - Scope: LenzFactCheckClient._read_capped

    On failure, first check:
        - The running total in _read_capped
    """
    size = MAX_RESPONSE_BYTES + 1
    chunks = [b"x" * 4096] * (size // 4096) + [b"x" * (size % 4096)] + [b"x" * 4096] * 64
    stream = _Chunks(chunks)
    error = _failure(lambda request: httpx.Response(200, stream=stream))
    _assert_fixed(error, SIZE_MESSAGE)
    assert MAX_RESPONSE_BYTES < stream.pulled <= MAX_RESPONSE_BYTES + 4096


def test_body_exactly_at_cap_is_read():
    """
    [Unit] lenz client: verifies a body of exactly MAX_RESPONSE_BYTES is not refused by the cap.

    Scenario:
        Given a valid success body padded with JSON whitespace to exactly the cap
        When check_claim reads it
        Then the result is returned.

    Boundaries:
        - Focus: E5 boundary (> cap, not >= cap)
        - Fixtures/params: none
        - Scope: LenzFactCheckClient._read_capped

    On failure, first check:
        - The total > MAX_RESPONSE_BYTES comparison
    """
    body = json.dumps({"claims": [{"claim": "x", "verdict": "True", "confidence": 0.7}]}).encode()
    body += b" " * (MAX_RESPONSE_BYTES - len(body))
    assert len(body) == MAX_RESPONSE_BYTES
    client = _client(lambda request: _raw_response(body, 200, {"Content-Length": str(len(body))}), [])
    assert client.check_claim(CLAIM).confidence == 0.7
    client.close()


def _double_gzip_bomb() -> bytes:
    """Build a small double-gzip body that would inflate to a megabyte of zeros.

    :return: The compressed bytes (a few hundred bytes).
    """
    return gzip.compress(gzip.compress(b"0" * 1_000_000))


@pytest.mark.parametrize(
    ("encoding", "body"),
    [
        ("gzip", gzip.compress(b'{"claims": []}')),
        ("gzip, gzip", _double_gzip_bomb()),
        ("deflate", zlib.compress(b'{"claims": []}')),
        ("identity, deflate", zlib.compress(b'{"claims": []}')),
        ("GZIP", gzip.compress(b'{"claims": []}')),
        ("br", b"\x00"),
        ("zstd", b"\x00"),
        ("x-unknown", b'{"claims": []}'),
    ],
)
def test_gzip_encoded_body_refused(monkeypatch: pytest.MonkeyPatch, encoding: str, body: bytes):
    """
    [Unit] lenz client: verifies any non-identity Content-Encoding is refused before decoding.

    Scenario:
        Given a 200 response with a compressed or unknown Content-Encoding (including a double-gzip bomb)
        When check_claim runs
        Then the encoding error is raised, no body byte was pulled and no httpx decoder ran.

    Boundaries:
        - Focus: E5 (no decompressor ever runs)
        - Fixtures/params: encoding, body; monkeypatch makes every httpx content decoder fail the test
        - Scope: LenzFactCheckClient._check_head

    On failure, first check:
        - The Content-Encoding token check in _check_head and the iter_raw() read

    :param encoding: The Content-Encoding header value.
    :param body: The body bytes.
    """
    assert len(_double_gzip_bomb()) < 4096
    decoders: list[str] = []
    for name in ("GZipDecoder", "DeflateDecoder", "BrotliDecoder", "ZStandardDecoder", "MultiDecoder"):
        decoder = getattr(httpx._decoders, name)
        monkeypatch.setattr(decoder, "decode", _recording_decode(decoders, name))
    stream = _Chunks([body])
    error = _failure(lambda request: httpx.Response(200, headers={"Content-Encoding": encoding}, stream=stream))
    _assert_fixed(error, ENCODING_MESSAGE)
    assert stream.pulled == 0
    assert decoders == []


def _recording_decode(calls: list[str], name: str) -> Callable[[object, bytes], bytes]:
    """Return a ``decode`` replacement that records its use.

    :param calls: Receives the decoder name on every call.
    :param name: The decoder class name.
    :return: The replacement method.
    """

    def decode(self: object, data: bytes) -> bytes:
        """Record the call and return the data unchanged.

        :param self: The decoder.
        :param data: The encoded data.
        :return: ``data``.
        """
        calls.append(name)
        return data

    return decode


def test_identity_encoding_is_accepted():
    """
    [Unit] lenz client: verifies an explicit identity Content-Encoding is read normally.

    Scenario:
        Given a success response with Content-Encoding "Identity"
        When check_claim runs
        Then the result is returned.

    Boundaries:
        - Focus: E5 (identity is the one accepted token, case-insensitive)
        - Fixtures/params: none
        - Scope: LenzFactCheckClient._check_head

    On failure, first check:
        - The casefold in the token check
    """
    body = json.dumps({"claims": [{"claim": "x", "verdict": "True", "confidence": 0.9}]}).encode()
    client = _client(lambda request: _raw_response(body, 200, {"Content-Encoding": " Identity "}), [])
    assert client.check_claim(CLAIM).verdict == "true"
    client.close()


@pytest.mark.parametrize("length", ["65537", "99999999999999999999", "9" * 40])
def test_content_length_over_cap_refused(length: str):
    """
    [Unit] lenz client: verifies a Content-Length above the cap is refused before the body is read.

    Scenario:
        Given a 200 response declaring a Content-Length above MAX_RESPONSE_BYTES (also beyond 20 digits)
        When check_claim runs
        Then the size-cap error is raised and no body byte was pulled.

    Boundaries:
        - Focus: E5 (early refusal; never an allocation hint)
        - Fixtures/params: length
        - Scope: LenzFactCheckClient._check_head

    On failure, first check:
        - The Content-Length loop in _check_head

    :param length: The declared Content-Length.
    """
    stream = _Chunks([b"{}"])
    error = _failure(lambda request: httpx.Response(200, headers={"Content-Length": length}, stream=stream))
    _assert_fixed(error, SIZE_MESSAGE)
    assert stream.pulled == 0


@pytest.mark.parametrize("length", ["10", "0", "not-a-number"])
def test_misleading_content_length_ignored_for_cap(length: str):
    """
    [Unit] lenz client: verifies the cap counts the bytes actually received, not Content-Length.

    Scenario:
        Given a response declaring a small or bogus Content-Length but streaming cap + 1 bytes
        When check_claim reads it
        Then the size-cap error is raised.

    Boundaries:
        - Focus: E5 (running total of actual raw bytes)
        - Fixtures/params: length
        - Scope: LenzFactCheckClient._read_capped

    On failure, first check:
        - Whether _read_capped trusts Content-Length

    :param length: The misleading Content-Length.
    """
    stream = _Chunks([b" " * 4096] * 17)
    error = _failure(lambda request: httpx.Response(200, headers={"Content-Length": length}, stream=stream))
    _assert_fixed(error, SIZE_MESSAGE)
    assert stream.pulled <= MAX_RESPONSE_BYTES + 4096


# --- E6: parser abuse --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        b"[" * 10_000 + b"]" * 10_000,
        b'{"a":' * 10_000 + b"1" + b"}" * 10_000,
        b'{"claims": ' + b"[" * 10_000 + b"]" * 10_000 + b"}",
    ],
    ids=["lists", "objects", "inside_claims"],
)
def test_deep_nesting_raises_fact_check_error(body: bytes):
    """
    [Unit] lenz client: verifies 10,000 levels of nesting within the cap is a shape error, not RecursionError.

    Scenario:
        Given a body nested 10,000 levels deep that fits within MAX_RESPONSE_BYTES
        When check_claim parses it
        Then FactCheckError has the fixed shape message.

    Boundaries:
        - Focus: E6.2 (RecursionError mapped)
        - Fixtures/params: body
        - Scope: _decode_json

    On failure, first check:
        - The RecursionError in _decode_json's except clause

    :param body: The deeply nested body.
    """
    assert len(body) <= MAX_RESPONSE_BYTES
    _assert_fixed(_failure(lambda request: _raw_response(body)), SHAPE_MESSAGE)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_nan_infinity_refused(constant: str):
    """
    [Unit] lenz client: verifies non-finite confidence values are refused.

    Scenario:
        Given a success body whose confidence is NaN, +/-Infinity or overflows to infinity
        When check_claim parses it
        Then FactCheckError has the fixed shape message.

    Boundaries:
        - Focus: E6.2 and E6.5
        - Fixtures/params: constant
        - Scope: _decode_json, _confidence

    On failure, first check:
        - parse_constant and math.isfinite in lenz.py

    :param constant: The JSON text of the confidence.
    """
    _assert_fixed(_failure(lambda request: _raw_response(_success_body(constant))), SHAPE_MESSAGE)


@pytest.mark.parametrize("digits", [400, 5000])
def test_huge_integer_confidence_refused(digits: int):
    """
    [Unit] lenz client: verifies a huge integer confidence is a FactCheckError, never OverflowError.

    Scenario:
        Given a confidence that is a 400-digit integer, or 5000 digits (above the int parse limit)
        When check_claim parses it
        Then FactCheckError has the fixed shape message.

    Boundaries:
        - Focus: E6.2 (digit limit) and E6.5 (OverflowError mapped)
        - Fixtures/params: digits
        - Scope: _decode_json, _confidence

    On failure, first check:
        - The OverflowError handling in _confidence

    :param digits: The number of digits.
    """
    _assert_fixed(_failure(lambda request: _raw_response(_success_body("1" + "0" * (digits - 1)))), SHAPE_MESSAGE)


@pytest.mark.parametrize("confidence", [True, False, "0.9", None, [0.9], {"v": 0.9}])
def test_confidence_bool_str_refused(confidence: object):
    """
    [Unit] lenz client: verifies a confidence that is not an int or float is refused.

    Scenario:
        Given a confidence given as a bool, a numeric string, null, a list or an object
        When check_claim parses it
        Then FactCheckError has the fixed shape message.

    Boundaries:
        - Focus: E6.5 (type(v) in (int, float), so bool is refused)
        - Fixtures/params: confidence
        - Scope: _confidence

    On failure, first check:
        - The exact type check in _confidence

    :param confidence: The raw confidence value.
    """
    _assert_fixed(_failure(lambda request: _success(confidence=confidence)), SHAPE_MESSAGE)


def test_missing_confidence_refused():
    """
    [Unit] lenz client: verifies a claim row without a confidence is refused.

    Scenario:
        Given a claim row with a verdict and no confidence
        When check_claim parses it
        Then FactCheckError has the fixed shape message.

    Boundaries:
        - Focus: E6.5
        - Fixtures/params: none
        - Scope: _parse_assess

    On failure, first check:
        - first.get("confidence") handling
    """
    _assert_fixed(_failure(lambda request: _json_response({"claims": [{"verdict": "True"}]})), SHAPE_MESSAGE)


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (
            b'{"claims": [{"claim": "caf\xe9", "verdict": "True", "confidence": 0.9}]}',
            "application/json; charset=latin-1",
        ),
        (b'{"claims": [{"claim": "caf\xe9", "verdict": "True", "confidence": 0.9}]}', "application/json"),
        ('{"claims": []}'.encode("utf-16"), "application/json; charset=utf-16"),
        (b"\xef\xbb\xbf" + b'{"claims": []}', "application/json"),
        (b'{"claims": [{"claim": "\xed\xa0\x80", "verdict": "True", "confidence": 0.9}]}', "application/json"),
    ],
    ids=["latin1_declared", "latin1_undeclared", "utf16", "utf8_bom", "encoded_surrogate"],
)
def test_non_utf8_body_refused(body: bytes, content_type: str):
    """
    [Unit] lenz client: verifies the body is decoded as strict UTF-8 whatever charset is declared.

    Scenario:
        Given a body that is not strict UTF-8 JSON (latin-1 with or without a declared charset,
        UTF-16, a UTF-8 BOM, an encoded surrogate)
        When check_claim parses it
        Then FactCheckError has the fixed shape message.

    Boundaries:
        - Focus: E6.1
        - Fixtures/params: body, content_type
        - Scope: _decode_json

    On failure, first check:
        - body.decode("utf-8", "strict") in _decode_json

    :param body: The raw body.
    :param content_type: The declared Content-Type.
    """
    _assert_fixed(_failure(lambda request: _raw_response(body, 200, {"Content-Type": content_type})), SHAPE_MESSAGE)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        "claims",
        42,
        None,
        {"claims": {}},
        {"claims": "x"},
        {"claims": None},
        {},
        {"claims": ["x"]},
        {"claims": [None]},
        {"claims": [{"verdict": 1, "confidence": 0.9}]},
        {"claims": [{"verdict": None, "confidence": 0.9}]},
        {"claims": [{"confidence": 0.9}]},
    ],
    ids=[
        "list",
        "string",
        "number",
        "null",
        "claims_dict",
        "claims_str",
        "claims_null",
        "claims_missing",
        "row_str",
        "row_null",
        "verdict_int",
        "verdict_null",
        "verdict_missing",
    ],
)
def test_top_level_and_claims_types(payload: object):
    """
    [Unit] lenz client: verifies every wrong top-level, claims or row type is a shape error.

    Scenario:
        Given a body whose top level is not an object, whose claims is not a list, or whose first
        row or verdict has the wrong type
        When check_claim parses it
        Then FactCheckError has the fixed shape message.

    Boundaries:
        - Focus: E6.3 (Task 02 steps 4.3 to 4.9)
        - Fixtures/params: payload
        - Scope: _parse_assess

    On failure, first check:
        - The isinstance checks in _parse_assess

    :param payload: The JSON value.
    """
    _assert_fixed(_failure(lambda request: _json_response(payload)), SHAPE_MESSAGE)


@pytest.mark.parametrize(
    "body",
    [
        b'{"claims": [], "claims": [{"claim": "x", "verdict": "True", "confidence": 0.9}]}',
        b'{"claims": [{"claim": "x", "verdict": "False", "verdict": "True", "confidence": 0.9}]}',
        b'{"claims": [{"claim": "x", "verdict": "True", "confidence": 0.1, "confidence": 0.9}]}',
        b'{"error_code": "no_claim", "error_code": null, "claims": []}',
    ],
    ids=["claims", "verdict", "confidence", "error_code"],
)
def test_duplicate_json_keys_refused(body: bytes):
    """
    [Unit] lenz client: verifies a duplicate key anywhere in the body is refused, never last-wins.

    Scenario:
        Given a body repeating claims, verdict, confidence or error_code
        When check_claim parses it
        Then FactCheckError has the fixed shape message (no silent choice of either value).

    Boundaries:
        - Focus: E6 (strict JSON; _unique_object)
        - Fixtures/params: body
        - Scope: _decode_json

    On failure, first check:
        - object_pairs_hook=_unique_object in _decode_json

    :param body: The raw body with a duplicate key.
    """
    _assert_fixed(_failure(lambda request: _raw_response(body)), SHAPE_MESSAGE)


@pytest.mark.parametrize(
    "error_code",
    [
        "bad\r\ncode",
        "##[error]x",
        "a" * 65,
        "\x1b[31mred",
        "Rate_Limited",
        "rate-limited",
        "",
        "code‮",
        7,
        ["rate_limited"],
    ],
    ids=["crlf", "workflow_command", "len65", "ansi", "upper", "dash", "empty", "bidi", "int", "list"],
)
def test_error_code_not_echoed_unless_safe(error_code: object):
    """
    [Unit] lenz client: verifies an unsafe error_code and the error text never reach the message.

    Scenario:
        Given an error response whose error_code has CR/LF, ##[, 65 characters, an ANSI escape,
        another unsafe shape or a non-string type, and whose error text holds a marker
        When check_claim parses it
        Then the message is exactly "lenz /assess returned an error".

    Boundaries:
        - Focus: E6.4
        - Fixtures/params: error_code
        - Scope: _parse_assess

    On failure, first check:
        - _ERROR_CODE_RE and its fullmatch

    :param error_code: The unsafe error_code value.
    """
    payload = {"claims": [], "error": MARKER, "error_code": error_code}
    _assert_fixed(_failure(lambda request: _json_response(payload)), ERROR_MESSAGE)


@pytest.mark.parametrize("error_code", ["rate_limited", "a" * 64, "x"])
def test_safe_error_code_is_named(error_code: str):
    """
    [Unit] lenz client: verifies a safe error_code is named while the error text is still dropped.

    Scenario:
        Given an error response with an error_code matching [a-z_]{1,64} and a marker error text
        When check_claim parses it
        Then the message is "lenz /assess returned error <code>" without the marker.

    Boundaries:
        - Focus: E6.4 positive side and the 64-character bound
        - Fixtures/params: error_code
        - Scope: _parse_assess

    On failure, first check:
        - _ERROR_CODE_RE bounds

    :param error_code: The safe error code.
    """
    payload = {"claims": [], "error": MARKER, "error_code": error_code}
    _assert_fixed(_failure(lambda request: _json_response(payload)), f"lenz /assess returned error {error_code}")


# --- E7: key handling ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [
        "",
        " " + SENTINEL,
        SENTINEL + "\r\n",
        SENTINEL + "\n",
        SENTINEL + " ",
        "tab\t" + SENTINEL,
        SENTINEL + "\x7f",
        SENTINEL + "\x00",
        SENTINEL + "é",
        "k" * 15,
        "k" * 257,
        "Bearer " + SENTINEL,
        None,
        SENTINEL.encode("ascii"),
    ],
    ids=[
        "empty",
        "leading_space",
        "crlf",
        "lf",
        "trailing_space",
        "tab",
        "del",
        "nul",
        "non_ascii",
        "len15",
        "len257",
        "bearer_prefix",
        "none",
        "bytes",
    ],
)
def test_malformed_key_refused_without_echo(monkeypatch: pytest.MonkeyPatch, key: object):
    """
    [Unit] lenz client: verifies a malformed key is refused with fixed text before any httpx object exists.

    Scenario:
        Given a key that breaks the E7 grammar
        When the client is constructed
        Then FactCheckError carries the fixed message, no key substring and no chain, and
        httpx.Client was never instantiated.

    Boundaries:
        - Focus: E7.1
        - Fixtures/params: key; monkeypatch makes httpx.Client construction fail the test
        - Scope: LenzFactCheckClient.__init__

    On failure, first check:
        - _API_KEY_RE and the isinstance check in __init__

    :param key: The malformed key.
    """
    monkeypatch.setattr(httpx.Client, "__init__", _forbidden_client_init)
    with pytest.raises(FactCheckError) as info:
        _lenz().LenzFactCheckClient(key)  # type: ignore[arg-type]
    _assert_fixed(info.value, KEY_MESSAGE)
    if isinstance(key, str) and key.strip():
        assert key.strip() not in str(info.value)


def _forbidden_client_init(self: httpx.Client, *args: object, **kwargs: object):
    """Fail the test if an ``httpx.Client`` is constructed.

    :param self: The client.
    :param args: Ignored.
    :param kwargs: Ignored.
    :raises AssertionError: Always.
    """
    raise AssertionError("httpx.Client constructed for a malformed key")


@pytest.mark.parametrize("key", ["k" * 16, "~" * 256, "!" * 16, SENTINEL])
def test_key_bounds_accepted(key: str):
    """
    [Unit] lenz client: verifies keys at both length bounds and every printable edge are accepted.

    Scenario:
        Given a key of exactly 16 or 256 printable characters, or the sentinel
        When the client is constructed with a mock transport and a claim is sent
        Then the Authorization header is exactly "Bearer <key>".

    Boundaries:
        - Focus: E7.1 edge
        - Fixtures/params: key
        - Scope: LenzFactCheckClient.__init__

    On failure, first check:
        - The {16,256} bounds of _API_KEY_RE

    :param key: The accepted key.
    """
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        """Record the request and answer success.

        :param request: The request.
        :return: A success response.
        """
        requests.append(request)
        return _success()

    client = _lenz().LenzFactCheckClient(key, transport=httpx.MockTransport(record))
    client.check_claim(CLAIM)
    client.close()
    assert requests[0].headers["authorization"] == f"Bearer {key}"


# --- E8: request content -----------------------------------------------------------------------


def test_request_body_and_headers_exact():
    """
    [Unit] lenz client: verifies the request is exactly POST /assess with the E8 header set.

    Scenario:
        Given a mock transport recording the request
        When check_claim sends one claim
        Then the method is POST, the header names equal the E8 list, the fixed header values hold,
        the body is a JSON object with exactly one key and no Cookie header is sent.

    Boundaries:
        - Focus: E8
        - Fixtures/params: none
        - Scope: LenzFactCheckClient.__init__ headers and _fetch

    On failure, first check:
        - The header dictionary in __init__ and the json= argument in _fetch
    """
    requests: list[httpx.Request] = []
    client = _client(lambda request: _success(), requests)
    client.check_claim('Ünïcode claim with a "quote".')
    client.close()
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == ASSESS_URL
    assert set(request.headers.keys()) == E8_HEADERS
    assert request.headers["accept"] == "application/json"
    assert request.headers["accept-encoding"] == "identity"
    assert request.headers["user-agent"] == "docsentinel"
    assert request.headers["authorization"] == f"Bearer {SENTINEL}"
    assert request.headers["content-type"] == "application/json"
    assert request.headers["host"] == "lenz.io"
    assert int(request.headers["content-length"]) == len(request.content)
    body = json.loads(request.content)
    assert body == {"claim": 'Ünïcode claim with a "quote".'}
    assert list(body) == ["claim"]


@pytest.mark.parametrize(
    "claim",
    ["", "   ", "\n\t", "x" * 1001, "é" * 1001, "\ud800", "ok \udfff", None, b"bytes claim", 42],
    ids=[
        "empty",
        "blank",
        "whitespace",
        "len1001",
        "len1001_nonascii",
        "lone_high",
        "lone_low",
        "none",
        "bytes",
        "int",
    ],
)
def test_claim_bounds_refused_before_send(claim: object):
    """
    [Unit] lenz client: verifies an unsendable claim is refused before any request.

    Scenario:
        Given an empty, blank, over-long (1,001 code points), unencodable or non-string claim
        When check_claim runs
        Then FactCheckError has the fixed claim message and no request was recorded, while a claim
        of exactly 1,000 code points is still sent.

    Boundaries:
        - Focus: E8
        - Fixtures/params: claim
        - Scope: LenzFactCheckClient._claim_is_sendable

    On failure, first check:
        - _claim_is_sendable

    :param claim: The unsendable claim.
    """
    requests: list[httpx.Request] = []
    client = _client(lambda request: _success(), requests)
    with pytest.raises(FactCheckError) as info:
        client.check_claim(claim)  # type: ignore[arg-type]
    _assert_fixed(info.value, CLAIM_MESSAGE)
    assert requests == []
    assert client.check_claim("é" * 1000).verdict == "true"
    assert len(requests) == 1
    client.close()


def test_set_cookie_not_replayed():
    """
    [Unit] lenz client: verifies a Set-Cookie from the backend is never sent back.

    Scenario:
        Given a backend that sets a cookie on its first response
        When two claims are sent
        Then neither request carries a Cookie header and the jar is empty afterwards.

    Boundaries:
        - Focus: E8 (cookie jar cleared per request)
        - Fixtures/params: none
        - Scope: LenzFactCheckClient._fetch

    On failure, first check:
        - The cookies.clear() calls in _fetch
    """
    requests: list[httpx.Request] = []
    client = _client(lambda request: _success() if requests[1:] else _with_cookie(), requests)
    client.check_claim("One.")
    client.check_claim("Two.")
    assert len(requests) == 2
    assert ["cookie" in request.headers for request in requests] == [False, False]
    assert len(vars(client)["_client"].cookies) == 0
    client.close()


def _with_cookie() -> httpx.Response:
    """Return a success response that sets a cookie.

    :return: The response.
    """
    response = _success()
    response.headers["Set-Cookie"] = "track=1; Path=/; Domain=lenz.io"
    return response


# --- E9: trust in response values --------------------------------------------------------------


@pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
def test_unrecognised_verdict_message_does_not_echo(caplog: pytest.LogCaptureFixture, confidence: float):
    """
    [Unit] lenz client: verifies an unrecognised verdict raises fixed text at every confidence.

    Scenario:
        Given a success body whose verdict is a marker string, at confidence 0.0, 0.5 or 1.0
        When check_claim parses it with DEBUG capture
        Then FactCheckError says "returned an unrecognised verdict" and the marker is in no
        message or log record (no confidence band guesses a verdict).

    Boundaries:
        - Focus: E9, owner ruling Q4
        - Fixtures/params: confidence; caplog at DEBUG
        - Scope: _parse_assess

    On failure, first check:
        - _normalize_verdict and VERDICT_MESSAGE

    :param caplog: The log capture.
    :param confidence: The confidence sent with the marker verdict.
    """
    caplog.set_level(logging.DEBUG)
    error = _failure(lambda request: _success(verdict=MARKER, confidence=confidence))
    _assert_fixed(error, VERDICT_MESSAGE)
    assert not [record for record in caplog.records if MARKER in record.getMessage()]


def test_response_claim_and_extra_fields_never_used(caplog: pytest.LogCaptureFixture):
    """
    [Unit] lenz client: verifies the claim echo, extra fields and later rows never reach the result.

    Scenario:
        Given a success body whose claim echo, an extra citations field, a top-level error text
        that is null-equivalent, and a second claim row all hold markers
        When check_claim parses it with DEBUG capture
        Then the result is built from claims[0].verdict and confidence only, citations is (), and
        the markers are in no result field or log record.

    Boundaries:
        - Focus: E9
        - Fixtures/params: caplog at DEBUG
        - Scope: _parse_assess

    On failure, first check:
        - Which keys _parse_assess reads
    """
    caplog.set_level(logging.DEBUG)
    payload = {
        "claims": [
            {
                "claim": MARKER,
                "verdict": "False",
                "confidence": 0.25,
                "citations": [MARKER, {"url": f"https://{MARKER}.example"}],
                "explanation": MARKER,
            },
            {"claim": MARKER, "verdict": "True", "confidence": 1.0},
        ],
        "citations": [MARKER],
        MARKER: MARKER,
    }
    client = _client(lambda request: _json_response(payload), [])
    result = client.check_claim(CLAIM)
    client.close()
    assert (result.verdict, result.confidence, result.backend, result.citations) == ("false", 0.25, "lenz", ())
    assert MARKER not in repr(result)
    assert not [record for record in caplog.records if MARKER in record.getMessage()]


# --- E12: exception boundary --------------------------------------------------------------------


def _scenario_key(monkeypatch: pytest.MonkeyPatch) -> FactCheckError:
    """Construct a client with a malformed key.

    :param monkeypatch: Unused.
    :return: The raised error.
    """
    with pytest.raises(FactCheckError) as info:
        _lenz().LenzFactCheckClient("short")
    return info.value


def _scenario_claim(monkeypatch: pytest.MonkeyPatch) -> FactCheckError:
    """Send an empty claim.

    :param monkeypatch: Unused.
    :return: The raised error.
    """
    client = _client(lambda request: _success(), [])
    with pytest.raises(FactCheckError) as info:
        client.check_claim("")
    return info.value


def _scenario_response(handler: Handler) -> Callable[[pytest.MonkeyPatch], FactCheckError]:
    """Return a scenario that sends one claim answered by ``handler``.

    :param handler: The response factory.
    :return: The scenario.
    """
    return lambda monkeypatch: _failure(handler)


def _scenario_time(monkeypatch: pytest.MonkeyPatch) -> FactCheckError:
    """Send a claim whose body arrives after the patched deadline.

    :param monkeypatch: Patches lenz._monotonic.
    :return: The raised error.
    """
    now = [0.0]
    monkeypatch.setattr(_lenz(), "_monotonic", _worker_clock(now, 0.0))

    def late(request: httpx.Request) -> httpx.Response:
        """Advance the clock past the deadline, then answer.

        :param request: The request.
        :return: A success response.
        """
        now[0] += 60.0
        return _success()

    return _failure(late)


def _scenario_transport(monkeypatch: pytest.MonkeyPatch) -> FactCheckError:
    """Send a claim through a transport that raises ConnectError carrying the sentinel.

    :param monkeypatch: Unused.
    :return: The raised error.
    """

    def broken(request: httpx.Request) -> httpx.Response:
        """Raise a connect error whose text carries the sentinel.

        :param request: The request sent.
        :raises httpx.ConnectError: Always.
        """
        raise httpx.ConnectError(f"Bearer {SENTINEL} {MARKER}", request=request)

    return _failure(broken)


def _scenario_closed(monkeypatch: pytest.MonkeyPatch) -> FactCheckError:
    """Send a claim on a closed client.

    :param monkeypatch: Unused.
    :return: The raised error.
    """
    client = _client(lambda request: _success(), [])
    client.close()
    with pytest.raises(FactCheckError) as info:
        client.check_claim(CLAIM)
    return info.value


@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        (_scenario_key, KEY_MESSAGE),
        (_scenario_claim, CLAIM_MESSAGE),
        (_scenario_response(lambda r: _raw_response(b"", 503)), "lenz /assess returned HTTP 503"),
        (_scenario_response(lambda r: _raw_response(b"{}", 200, {"Content-Encoding": "gzip"})), ENCODING_MESSAGE),
        (_scenario_response(lambda r: _raw_response(b" " * (MAX_RESPONSE_BYTES + 1))), SIZE_MESSAGE),
        (_scenario_time, TIME_MESSAGE),
        (_scenario_transport, "lenz /assess request failed (ConnectError)"),
        (
            _scenario_response(lambda r: httpx.Response(200, content=b"{}")),
            "lenz /assess request failed (StreamConsumed)",
        ),
        (_scenario_response(lambda r: _raw_response(b"{not json")), SHAPE_MESSAGE),
        (
            _scenario_response(lambda r: _json_response({"claims": [], "error_code": "quota_exceeded"})),
            "lenz /assess returned error quota_exceeded",
        ),
        (_scenario_response(lambda r: _json_response({"claims": [], "error": MARKER})), ERROR_MESSAGE),
        (_scenario_response(lambda r: _success(verdict="Mixed")), VERDICT_MESSAGE),
        (_scenario_closed, CLOSED_MESSAGE),
    ],
    ids=[
        "key",
        "claim",
        "http_status",
        "encoding",
        "size",
        "time",
        "request_failed",
        "request_failed_stream",
        "shape",
        "error_code",
        "error",
        "verdict",
        "closed",
    ],
)
def test_every_failure_is_fact_check_error(
    monkeypatch: pytest.MonkeyPatch, scenario: Callable[[pytest.MonkeyPatch], FactCheckError], message: str
):
    """
    [Unit] lenz client: verifies each fixed message of E12 is produced exactly, without a chain.

    Scenario:
        Given one failure scenario per fixed message
        When it runs
        Then FactCheckError carries exactly that text (at most 200 characters, no request or
        response data) and __cause__ and __context__ are None.

    Boundaries:
        - Focus: E12, E7.4
        - Fixtures/params: scenario, message; monkeypatch for the patched-clock case
        - Scope: LenzFactCheckClient

    On failure, first check:
        - The raise sites in lenz.py (each outside every except block)

    :param monkeypatch: Pytest monkeypatch.
    :param scenario: Produces the error.
    :param message: The expected fixed text.
    """
    error = scenario(monkeypatch)
    _assert_fixed(error, message)
    assert type(error) is FactCheckError
    assert len(str(error)) <= 200


@pytest.mark.parametrize(
    ("case_id", "handler", "message"), FAILURE_RESPONSES, ids=[case[0] for case in FAILURE_RESPONSES]
)
def test_failure_responses_raise_fixed_messages(case_id: str, handler: Handler, message: str):
    """
    [Unit] lenz client: verifies the shared failure table (also used by the no-secret-leak module).

    Scenario:
        Given each response-side failure shape of FAILURE_RESPONSES
        When check_claim runs
        Then FactCheckError carries the listed fixed message and no chain.

    Boundaries:
        - Focus: E2, E5, E6, E9, E12 (table consistency)
        - Fixtures/params: case_id, handler, message
        - Scope: LenzFactCheckClient with httpx.MockTransport

    On failure, first check:
        - The FAILURE_RESPONSES entry named by case_id

    :param case_id: The case name.
    :param handler: The response factory.
    :param message: The expected message.
    """
    _assert_fixed(_failure(handler), message)


def test_close_idempotent_and_never_raises(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    """
    [Unit] lenz client: verifies close() is idempotent and swallows an httpx close error.

    Scenario:
        Given a client whose httpx.Client.close raises OSError carrying the sentinel
        When close() is called twice
        Then neither call raises, the inner close ran once, and the DEBUG record names only the type.

    Boundaries:
        - Focus: E12 (close never raises)
        - Fixtures/params: monkeypatch patches httpx.Client.close; caplog at DEBUG
        - Scope: LenzFactCheckClient.close

    On failure, first check:
        - The closed flag and the except in close()
    """
    caplog.set_level(logging.DEBUG)
    calls: list[int] = []
    client = _client(lambda request: _success(), [])

    def explode(self: httpx.Client):
        """Raise from httpx.Client.close.

        :param self: The httpx client.
        :raises OSError: Always.
        """
        calls.append(1)
        raise OSError(SENTINEL)

    monkeypatch.setattr(httpx.Client, "close", explode)
    client.close()
    client.close()
    assert calls == [1]
    messages = [record.getMessage() for record in caplog.records if record.name == _LENZ]
    assert "lenz client close failed (OSError)" in messages
    assert not [message for message in messages if SENTINEL in message]


def test_close_on_healthy_client_twice():
    """
    [Unit] lenz client: verifies closing a working client twice closes the httpx client once.

    Scenario:
        Given a client that answered one claim
        When close() is called twice
        Then the inner httpx.Client is closed and no error is raised.

    Boundaries:
        - Focus: E12 (idempotent close)
        - Fixtures/params: none
        - Scope: LenzFactCheckClient.close

    On failure, first check:
        - The _closed flag
    """
    client = _client(lambda request: _success(), [])
    client.check_claim(CLAIM)
    client.close()
    client.close()
    assert vars(client)["_client"].is_closed is True


def test_check_claim_after_close():
    """
    [Unit] lenz client: verifies check_claim on a closed client raises without touching httpx.

    Scenario:
        Given a closed client
        When check_claim runs, also with a claim that would otherwise be refused
        Then FactCheckError says "lenz client is closed" and no request was recorded.

    Boundaries:
        - Focus: E12 (closed flag checked first)
        - Fixtures/params: none
        - Scope: LenzFactCheckClient.check_claim

    On failure, first check:
        - The _closed check at the top of check_claim
    """
    requests: list[httpx.Request] = []
    client = _client(lambda request: _success(), requests)
    client.close()
    for claim in (CLAIM, ""):
        with pytest.raises(FactCheckError) as info:
            client.check_claim(claim)
        _assert_fixed(info.value, CLOSED_MESSAGE)
    assert requests == []
