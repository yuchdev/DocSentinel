"""The Lenz ``/assess`` fact-check backend (Milestone 0010 Story 03.0 Task 02, ADR 0007).

:class:`LenzFactCheckClient` implements the :class:`~docsentinel.fact_check.protocol.FactCheckClient`
protocol against the documented ``POST /assess`` endpoint, and is the only DocSentinel code that
sends document-derived text off the machine. Every transport property follows the egress threat
model ``docs/security/threat-model-0010-fact-check-egress-2026-11-24.md`` (E1 to E13):

* One fixed URL, :attr:`LenzFactCheckClient.ASSESS_URL`; nothing in it comes from claim text,
  configuration, the environment or a response (E1). Redirects are never followed and any status
  other than 200 is an error (E2).
* ``trust_env=False``: no proxy or CA variable picks the route or the trust anchors, and TLS
  verification against the ``certifi`` bundle cannot be turned off (E3).
* A hard wall-clock deadline of :attr:`LenzFactCheckClient.REQUEST_TIMEOUT_SECONDS` per call, from
  outside every blocking socket call: the request runs in a daemon thread the caller joins with a
  timeout (E4).
* Only an identity-encoded body is accepted, read with ``iter_raw()`` and capped at
  :attr:`LenzFactCheckClient.MAX_RESPONSE_BYTES` raw bytes, so no decompressor ever runs (E5).
* Strict UTF-8, no ``NaN``/``Infinity``, and only the ``verdict``, ``confidence`` and ``claim``
  of each row in ``claims`` are read. Lenz may split a combined fact into several rows; every row
  is read, the result's verdict is the most severe one and its ``label`` the most severe explicit
  label (:data:`DISPLAY_LABELS`), and the first
  :data:`~docsentinel.fact_check.protocol.MAX_RESULT_CLAIMS` rows are kept in ``claims`` (owner
  rulings of 2026-11-27). The ``claim`` echo (untrusted third-party text, cut to
  :data:`~docsentinel.fact_check.protocol.MAX_RESULT_CLAIM_CHARS`) is used for the per-row INFO
  trace line (its first words, through ``quote_start``) and the report's fact-check rows; every
  other field, citations included, is ignored (E6, E9).
* The API key is validated before any ``httpx`` object exists, lives only in the ``httpx`` header
  store, and never appears in a message, an exception chain or a log record. Every
  :class:`~docsentinel.fact_check.protocol.FactCheckError` carries fixed text and is raised outside
  any ``except`` block, so ``__cause__`` and ``__context__`` are ``None`` (E7, E12).
* No retries. The module logs one INFO line per claim row (the row's first words, its explicit
  verdict label and the confidence), otherwise at most DEBUG status codes, counts and fixed
  messages, and never touches the ``httpx`` or ``httpcore`` loggers.

Layering (plan contract C9): the standard library, ``httpx`` and
``docsentinel.fact_check.protocol`` only. The module does no I/O and reads no environment at import
(E13); ``import docsentinel`` never imports it, only ``load_backend`` does.

Known limitations
-----------------

* The verdict is a third party's heuristic output, not ground truth. ``DS302`` reports it as an
  advisory prompt to review the claim, never as a verified fact.
* The raw verdict vocabulary is not documented as closed and may change on the provider's side.
  :data:`VERDICT_LABELS` maps the known labels (case-insensitive); any other label is rated
  ``unverifiable``, which ``DS302`` prints but never reports (owner ruling of 2026-11-27, which
  replaces ruling Q4).
* Only ``/assess`` is used; ``/extract``, ``/verify`` and ``/ask`` are not.
* An abandoned request thread keeps its socket until the peer closes it, its read times out or the
  process exits (threat model residual risk RE3).
"""

import json
import logging
import math
import re
import threading
import time
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import ClassVar, Final, NoReturn, Optional

import httpx

from docsentinel.fact_check.protocol import (
    FACT_CHECK_BACKENDS,
    MAX_RESULT_CLAIM_CHARS,
    MAX_RESULT_CLAIMS,
    ClaimVerdict,
    FactCheckError,
    FactCheckResult,
    Verdict,
)
from docsentinel.fact_check.protocol import VERDICT_LABELS as LABEL_ORDER
from docsentinel.log import quote_start

logger = logging.getLogger(__name__)

#: Monotonic clock of the per-request deadline (E4); a test seam that never touches ``time``.
_monotonic: Callable[[], float] = time.monotonic

#: Grammar of an accepted API key (E7): 16 to 256 printable ASCII characters, no whitespace.
_API_KEY_RE: Final[re.Pattern[str]] = re.compile(r"[\x21-\x7e]{16,256}")

#: An ``error_code`` value safe to name in a message (E6); applied with ``re.fullmatch``.
_ERROR_CODE_RE: Final[re.Pattern[str]] = re.compile(r"[a-z_]{1,64}")

#: A ``Content-Length`` value; longer digit strings are over the cap without conversion.
_CONTENT_LENGTH_RE: Final[re.Pattern[str]] = re.compile(r"[0-9]{1,20}")

#: The fixed ``FactCheckError`` messages (E12). None contains request or response data.
KEY_MESSAGE: Final = "lenz API key is missing or malformed"
CLAIM_MESSAGE: Final = "lenz /assess claim text is empty, too long or not encodable"
ENCODING_MESSAGE: Final = "lenz /assess response used an unsupported content encoding"
SIZE_MESSAGE: Final = "lenz /assess response exceeded the size cap"
TIME_MESSAGE: Final = "lenz /assess request exceeded the time limit"
SHAPE_MESSAGE: Final = "lenz /assess returned an unexpected response shape"
ERROR_MESSAGE: Final = "lenz /assess returned an error"
VERDICT_MESSAGE: Final = "lenz /assess returned an unrecognised verdict"
CLOSED_MESSAGE: Final = "lenz client is closed"


#: Lenz's confidence words as numbers, comparable with ``fact_check_min_confidence``.
CONFIDENCE_WORDS: Final[Mapping[str, float]] = MappingProxyType({"high": 0.9, "medium": 0.6, "low": 0.3})


def _status_message(status: int) -> str:
    """Return the fixed message for a non-200 status (E2).

    :param status: The integer HTTP status.
    :return: ``lenz /assess returned HTTP <status>``.
    """
    return f"lenz /assess returned HTTP {int(status)}"


def _request_failed_message(exc: BaseException) -> str:
    """Return the fixed message for a transport failure, naming the exception type only (E12).

    :param exc: The caught exception; its text is never used.
    :return: ``lenz /assess request failed (<type name>)``.
    """
    return f"lenz /assess request failed ({type(exc).__name__})"


#: Lenz's raw verdict labels (stripped, case-folded) as :data:`Verdict` values. A label that is
#: not listed is rated ``unverifiable``: it is printed, never reported as a finding.
VERDICT_LABELS: Final[Mapping[str, Verdict]] = MappingProxyType(
    {
        "true": "true",
        "mostly true": "true",
        "false": "false",
        "mostly false": "false",
        "mixed": "mixed",
        "half true": "mixed",
        "unverifiable": "unverifiable",
    }
)

#: Lenz's raw verdict labels (stripped, case-folded) as the explicit labels shown to the user.
#: A label that is not listed is shown as ``Unverifiable``.
DISPLAY_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "true": "True",
        "mostly true": "Mostly True",
        "false": "False",
        "mostly false": "Mostly False",
        "mixed": "Mixed",
        "half true": "Mixed",
        "unverifiable": "Unverifiable",
    }
)

#: Verdicts from most to least severe: a combined fact takes the most severe one of its claims.
_SEVERITY: Final[tuple[Verdict, ...]] = ("false", "mixed", "unverifiable", "true")


def _normalize_verdict(raw: str) -> Verdict:
    """Map a raw Lenz verdict string to a :data:`Verdict` (owner ruling of 2026-11-27).

    The value is stripped and case-folded and looked up in :data:`VERDICT_LABELS`. Every verdict
    is kept and printed; a label that is not listed maps to ``unverifiable``.

    :param raw: The raw ``verdict`` string from the response.
    :return: The mapped verdict.
    """
    return VERDICT_LABELS.get(raw.strip().casefold(), "unverifiable")


def _refuse_constant(name: str) -> NoReturn:
    """Refuse the non-standard JSON constants ``NaN``, ``Infinity`` and ``-Infinity`` (E6).

    :param name: The constant name ``json`` found.
    :raises ValueError: Always.
    """
    raise ValueError("non-finite JSON constant")


#: Marks a body that did not decode to JSON.
_NOT_JSON: Final = object()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object, refusing a duplicate key instead of keeping the last value (E6).

    :param pairs: The decoded key/value pairs of one JSON object, in document order.
    :return: The object as a ``dict``.
    :raises ValueError: When a key occurs twice.
    """
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _decode_json(body: bytes) -> object:
    """Decode a body as strict UTF-8 JSON, ignoring any server-declared charset (E6).

    :param body: The collected raw response bytes.
    :return: The parsed value, or :data:`_NOT_JSON` when decoding or parsing failed.
    """
    payload: object = _NOT_JSON
    try:
        payload = json.loads(
            body.decode("utf-8", "strict"), parse_constant=_refuse_constant, object_pairs_hook=_unique_object
        )
    except (ValueError, RecursionError):
        payload = _NOT_JSON  # bad UTF-8, bad JSON, NaN/Infinity, duplicate keys, the digit limit or deep nesting
    return payload


def _confidence(value: object) -> Optional[float]:
    """Return a finite confidence clamped to ``[0.0, 1.0]``, or ``None`` for a bad value (E6).

    Lenz rates confidence with a word; :data:`CONFIDENCE_WORDS` maps it to a number (stripped and
    case-folded). Any other string is refused.

    :param value: The raw ``confidence`` value; ``bool`` and other types are refused.
    :return: The clamped ``float``, or ``None``.
    """
    if isinstance(value, str):
        return CONFIDENCE_WORDS.get(value.strip().casefold())
    if not isinstance(value, (int, float)) or type(value) not in (int, float):
        return None
    try:
        number = float(value)
    except OverflowError:
        number = math.inf  # a huge int: refused below like inf (E6)
    if not math.isfinite(number):
        return None
    return max(0.0, min(1.0, number))


def _parse_assess(body: bytes, backend: str) -> FactCheckResult:
    """Turn an ``/assess`` response body into a validated result (Task 02 step 4, E6, E9).

    :param body: The raw, identity-encoded, size-capped response bytes.
    :param backend: The backend name for the result.
    :return: The result; ``unverifiable`` at confidence ``0.0`` for ``no_claim`` or no claims.
    :raises FactCheckError: With a fixed message for every other shape.
    """
    payload = _decode_json(body)
    if not isinstance(payload, dict):
        raise FactCheckError(SHAPE_MESSAGE)
    error_code = payload.get("error_code")
    if error_code == "no_claim":
        return FactCheckResult("unverifiable", 0.0, backend)
    if error_code is not None or payload.get("error") is not None:
        if isinstance(error_code, str) and _ERROR_CODE_RE.fullmatch(error_code):
            raise FactCheckError(f"lenz /assess returned error {error_code}")
        raise FactCheckError(ERROR_MESSAGE)
    claims = payload.get("claims")
    if not isinstance(claims, list):
        raise FactCheckError(SHAPE_MESSAGE)
    if not claims:
        return FactCheckResult("unverifiable", 0.0, backend)
    # Lenz splits a combined fact into several claims, each with its own verdict. Every claim is
    # read; the result is the most severe verdict (false, mixed, unverifiable, true).
    rated: list[tuple[Verdict, float]] = []
    labels: list[str] = []
    parts: list[ClaimVerdict] = []
    for position, item in enumerate(claims, start=1):
        if not isinstance(item, dict):
            raise FactCheckError(SHAPE_MESSAGE)
        raw_verdict = item.get("verdict")
        if not isinstance(raw_verdict, str):
            raise FactCheckError(SHAPE_MESSAGE)
        confidence = _confidence(item.get("confidence"))
        if confidence is None:
            raise FactCheckError(SHAPE_MESSAGE)
        verdict = _normalize_verdict(raw_verdict)
        label = DISPLAY_LABELS.get(raw_verdict.strip().casefold(), "Unverifiable")
        claim_text = item.get("claim")
        claim_text = claim_text if isinstance(claim_text, str) else ""
        # Every verdict is printed with its explicit label: True, Mostly True, False, Mostly False, ...
        logger.info(
            "lenz /assess: claim %d/%d %s: verdict %s, confidence %.2f",
            position,
            len(claims),
            quote_start(claim_text),
            label,
            confidence,
        )
        rated.append((verdict, confidence))
        labels.append(label)
        if len(parts) < MAX_RESULT_CLAIMS:
            parts.append(ClaimVerdict(claim_text[:MAX_RESULT_CLAIM_CHARS], label, confidence))
    worst = next(verdict for verdict in _SEVERITY if any(rated_verdict == verdict for rated_verdict, _ in rated))
    confidences = [confidence for verdict, confidence in rated if verdict == worst]
    # A true answer is only as sure as its weakest claim; any other verdict keeps its strongest rating.
    chosen = min(confidences) if worst == "true" else max(confidences)
    # The fact's label is the most severe label among all its claims, kept or not.
    worst_label = min(labels, key=LABEL_ORDER.index)
    result: Optional[FactCheckResult] = None
    try:
        result = FactCheckResult(worst, chosen, backend, label=worst_label, claims=tuple(parts))
    except FactCheckError:
        result = None
    if result is None:
        raise FactCheckError(SHAPE_MESSAGE)
    return result


class _Attempt:
    """The shared state of one request thread and its waiting caller (E4).

    The worker writes ``body``, ``failure`` or ``error`` before it ends; the caller reads them
    only after ``join`` saw the thread finish. When the caller gives up it sets ``abandoned`` and
    never reads them.

    :ivar abandoned: Set by the caller on deadline expiry; the worker stops reading and closes.
    :ivar body: The capped raw body on success.
    :ivar failure: A fixed ``FactCheckError`` message on a mapped failure.
    :ivar error: An unmapped exception, re-raised in the caller (``DS302`` contains it, M5).
    """

    def __init__(self):
        """Create an attempt with no outcome yet."""
        self.abandoned = threading.Event()
        self.body: Optional[bytes] = None
        self.failure: Optional[str] = None
        self.error: Optional[Exception] = None


class LenzFactCheckClient:
    """``FactCheckClient`` for the documented Lenz ``POST /assess`` endpoint.

    Construct one per scan and reuse it for every claim (decision U4); call :meth:`close` when
    done. Every constant below is fixed and read from no configuration, environment variable or
    CLI flag (plan contract C4).

    :ivar name: The backend name, ``lenz``.
    :ivar API_KEY_ENV_VAR: The variable ``DS302`` reads the key from (plan contract C3).
    :ivar BASE_URL: The fixed API base.
    :ivar ASSESS_URL: The only URL a request is ever sent to (E1).
    :ivar REQUEST_TIMEOUT_SECONDS: The ``httpx`` per-operation timeout and the hard per-request
        wall-clock deadline (E4).
    :ivar MAX_RESPONSE_BYTES: The cap on raw response body bytes (E5).
    :ivar MAX_CLAIM_CHARS: The most code points of claim text sent (E8).
    :ivar MIN_API_KEY_CHARS: The shortest accepted key (E7).
    :ivar MAX_API_KEY_CHARS: The longest accepted key (E7).
    """

    name: ClassVar[str] = "lenz"
    API_KEY_ENV_VAR: ClassVar[str] = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"
    BASE_URL: ClassVar[str] = "https://lenz.io/api/v1"
    ASSESS_URL: ClassVar[str] = BASE_URL + "/assess"
    REQUEST_TIMEOUT_SECONDS: ClassVar[float] = 30.0
    MAX_RESPONSE_BYTES: ClassVar[int] = 65_536
    MAX_CLAIM_CHARS: ClassVar[int] = 1000
    MIN_API_KEY_CHARS: ClassVar[int] = 16
    MAX_API_KEY_CHARS: ClassVar[int] = 256

    def __init__(self, api_key: str, *, transport: Optional[httpx.BaseTransport] = None):
        """Validate the key and build the one ``httpx.Client`` of this backend.

        :param api_key: The Lenz API key: a ``str`` of :attr:`MIN_API_KEY_CHARS` to
            :attr:`MAX_API_KEY_CHARS` printable ASCII characters with no whitespace. It is never
            stripped or repaired, and is kept only in the ``httpx`` header store.
        :param transport: **Test seam only** (threat model E11): an ``httpx`` transport such as
            ``httpx.MockTransport`` that replaces the network. No production code passes it;
            ``DS302`` constructs the client as ``cls(api_key=...)``. A test transport must return a
            streamed body (``httpx.Response(..., stream=...)``): a ``content=`` response is already
            read and decoded by ``httpx`` and is refused as a request failure.
        :raises FactCheckError: When the key is missing or malformed, before any ``httpx`` object
            exists; the message never contains the key.
        """
        if not isinstance(api_key, str) or _API_KEY_RE.fullmatch(api_key) is None:
            raise FactCheckError(KEY_MESSAGE)
        self._closed = False
        self._client = httpx.Client(
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": "docsentinel",
                "Authorization": f"Bearer {api_key}",
            },
            timeout=self.REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def __repr__(self) -> str:
        """Return a fixed representation that never reveals the key.

        :return: ``LenzFactCheckClient(base_url='https://lenz.io/api/v1')``.
        """
        return "LenzFactCheckClient(base_url='https://lenz.io/api/v1')"

    __str__ = __repr__

    def check_claim(self, claim: str) -> FactCheckResult:
        """Assess one claim with ``POST /assess``.

        The request body is exactly ``{"claim": claim}``. The call returns or raises within
        :attr:`REQUEST_TIMEOUT_SECONDS` plus thread-scheduling slack (E4). No retry is made.

        :param claim: The claim sentence: a non-blank ``str`` of at most :attr:`MAX_CLAIM_CHARS`
            code points that encodes as UTF-8.
        :return: The validated result. ``unverifiable`` at confidence ``0.0`` when the backend
            found no checkable claim.
        :raises FactCheckError: On every per-claim failure, with a fixed message and no exception
            chain.
        """
        if self._closed:
            raise FactCheckError(CLOSED_MESSAGE)
        if not self._claim_is_sendable(claim):
            raise FactCheckError(CLAIM_MESSAGE)
        deadline = _monotonic() + self.REQUEST_TIMEOUT_SECONDS
        attempt = _Attempt()
        worker = threading.Thread(
            target=self._fetch, args=(claim, deadline, attempt), name="docsentinel-lenz-request", daemon=True
        )
        worker.start()
        worker.join(timeout=max(deadline - _monotonic(), 0.0))
        if worker.is_alive():
            attempt.abandoned.set()
            logger.debug("lenz /assess: request abandoned at the time limit")
            raise FactCheckError(TIME_MESSAGE)
        if attempt.error is not None:
            raise attempt.error
        if attempt.failure is not None:
            raise FactCheckError(attempt.failure)
        if attempt.body is None:
            raise FactCheckError(SHAPE_MESSAGE)
        try:
            return _parse_assess(attempt.body, self.name)
        except FactCheckError as exc:
            # Fixed message (E12): safe for the log file, names the rejecting check.
            logger.debug("lenz /assess: response rejected: %s", exc)
            raise

    def close(self) -> "None":
        """Release the ``httpx.Client``. Idempotent and never raises (E12).

        A failure of ``httpx.Client.close`` is logged at DEBUG by exception type name only.
        """
        if self._closed:
            return
        self._closed = True
        try:
            self._client.close()
        except BaseException as exc:  # close() never raises (E12); only the type name is logged
            if not isinstance(exc, Exception):
                raise
            logger.debug("lenz client close failed (%s)", type(exc).__name__)

    def _claim_is_sendable(self, claim: object) -> bool:
        """Return whether ``claim`` may be sent (E8).

        :param claim: The candidate claim, of any type.
        :return: ``True`` for a non-blank ``str`` of at most :attr:`MAX_CLAIM_CHARS` code points
            that encodes as UTF-8.
        """
        if not isinstance(claim, str) or not claim.strip() or len(claim) > self.MAX_CLAIM_CHARS:
            return False
        encodable = True
        try:
            claim.encode("utf-8")
        except UnicodeEncodeError:
            encodable = False  # a lone surrogate
        return encodable

    def _fetch(self, claim: str, deadline: float, attempt: _Attempt):
        """Send the request and read the capped body; runs in the request thread (E4).

        The outcome is written to ``attempt``. The response is always closed on leaving the
        ``stream`` block, and an unfinished read closes the connection instead of pooling it.

        :param claim: The validated claim text.
        :param deadline: The monotonic deadline of this call.
        :param attempt: The shared outcome holder.
        """
        try:
            self._client.cookies.clear()
            with self._client.stream("POST", self.ASSESS_URL, json={"claim": claim}) as response:
                failure = self._check_head(response)
                if failure is None:
                    self._read_capped(response, deadline, attempt)
                else:
                    attempt.failure = failure
            self._client.cookies.clear()
        except (httpx.HTTPError, httpx.StreamError, httpx.InvalidURL, ValueError, OverflowError, RecursionError) as exc:
            attempt.failure = _request_failed_message(exc)
        except BaseException as exc:  # re-raised by the caller; DS302 keeps only its type name (M5)
            if not isinstance(exc, Exception):
                raise
            attempt.error = exc
        if attempt.abandoned.is_set():
            attempt.body = None

    def _check_head(self, response: httpx.Response) -> Optional[str]:
        """Check the status and framing headers before any body byte is read (E2, E5).

        :param response: The streamed response.
        :return: A fixed failure message, or ``None`` when the body may be read.
        """
        status = response.status_code
        logger.debug("lenz /assess: HTTP %d", status)
        if status != 200:
            return _status_message(status)
        tokens = [
            token.strip().casefold()
            for value in response.headers.get_list("content-encoding")
            for token in value.split(",")
        ]
        if any(token != "identity" for token in tokens):
            return ENCODING_MESSAGE
        for value in response.headers.get_list("content-length"):
            length = value.strip()
            if _CONTENT_LENGTH_RE.fullmatch(length) is None:
                if length.isascii() and length.isdigit():
                    return SIZE_MESSAGE
                continue
            if int(length) > self.MAX_RESPONSE_BYTES:
                return SIZE_MESSAGE
        return None

    def _read_capped(self, response: httpx.Response, deadline: float, attempt: _Attempt):
        """Read the raw body up to :attr:`MAX_RESPONSE_BYTES` within the deadline (E4, E5).

        Only ``iter_raw()`` is used, so no content decoder ever runs; the running total counts the
        actual bytes received, whatever ``Content-Length`` claimed.

        :param response: The streamed, identity-encoded, status-200 response.
        :param deadline: The monotonic deadline of this call.
        :param attempt: The shared outcome holder; receives ``body`` or ``failure``.
        """
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_raw():
            if attempt.abandoned.is_set() or _monotonic() >= deadline:
                attempt.failure = TIME_MESSAGE
                return
            total += len(chunk)
            if total > self.MAX_RESPONSE_BYTES:
                attempt.failure = SIZE_MESSAGE
                return
            chunks.append(chunk)
        if attempt.abandoned.is_set() or _monotonic() >= deadline:
            attempt.failure = TIME_MESSAGE
            return
        attempt.body = b"".join(chunks)
        logger.debug("lenz /assess: %d byte(s) read", total)


#: Register the one shipped backend; :func:`docsentinel.fact_check.protocol.load_backend` imports
#: this module only through its fixed literal importer, after both consent gates are satisfied.
FACT_CHECK_BACKENDS[LenzFactCheckClient.name] = LenzFactCheckClient
