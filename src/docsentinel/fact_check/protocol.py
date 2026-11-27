"""Backend-independent fact-check contract (Milestone 0010 Story 01.0 Task 04, ADR 0007 Contract 4).

Rule ``DS302`` and every fact-check backend are written against this module: the
:data:`Verdict` vocabulary, the one backend exception :class:`FactCheckError`, the validated
:class:`FactCheckResult` value object, the structural :class:`FactCheckClient` protocol (plan
contract C2) and the two-part backend registry.

Layering (plan contract C9): standard library and ``typing`` only. No ``config``, ``detectors``,
``mining`` or ``httpx`` import, so ``DS302`` may import this module eagerly. No function here reads
the environment (threat model 0010 M8): a backend receives its API key only through its
constructor, and ``DS302`` alone reads the key variable named by :func:`expected_api_key_env_var`.

Registry split (threat model 0010 M7): ``config.py`` validates ``fact_check_backend`` against its
own ``FACT_CHECK_BACKEND_NAMES`` and never imports this package. :data:`FACT_CHECK_BACKEND_MODULES`
is the static, read-only map of backend name to module and the only source of module names that
are ever imported; :data:`FACT_CHECK_BACKENDS` is filled by each backend module when it is
imported. :func:`load_backend` imports a module only through :data:`_MODULE_IMPORTERS`, whose
entries each call ``importlib.import_module`` with one fixed literal, so a configuration value is
never an import argument.
"""

import importlib
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Final, Literal, Protocol, runtime_checkable

#: A backend's judgement of one claim.
Verdict = Literal["true", "false", "mixed", "unverifiable"]

#: Every value of :data:`Verdict`.
VERDICTS: Final[frozenset[str]] = frozenset({"true", "false", "mixed", "unverifiable"})

#: The verdicts ``DS302`` reports as findings.
REPORTABLE_VERDICTS: Final[frozenset[str]] = frozenset({"false", "mixed"})

#: The explicit verdict labels shown to the user, from most to least severe (owner ruling of
#: 2026-11-27): a report and a log line always name one of these.
VERDICT_LABELS: Final[tuple[str, ...]] = ("False", "Mostly False", "Mixed", "Unverifiable", "Mostly True", "True")

#: The label of a :data:`Verdict` when the backend gives no finer one.
VERDICT_DEFAULT_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {"true": "True", "false": "False", "mixed": "Mixed", "unverifiable": "Unverifiable"}
)

#: Most rated claims one result may carry.
MAX_RESULT_CLAIMS: Final = 64

#: Longest claim text of one rated claim, in characters.
MAX_RESULT_CLAIM_CHARS: Final = 1000

#: Backend name grammar (plan contract C3). Always applied with ``re.fullmatch`` (threat model
#: 0010 M7): under ``re.match`` the ``$`` would also match before a final ``\n``.
BACKEND_NAME_PATTERN: Final[str] = r"^[a-z][a-z0-9]{0,31}$"

#: :data:`BACKEND_NAME_PATTERN`, compiled once.
_BACKEND_NAME_RE: Final[re.Pattern[str]] = re.compile(BACKEND_NAME_PATTERN)

#: Upper bound on :attr:`FactCheckResult.citations` entries.
MAX_CITATIONS: Final[int] = 8

#: Upper bound on the length of one citation, in characters.
MAX_CITATION_CHARS: Final[int] = 500


class FactCheckError(RuntimeError):
    """The one exception a fact-check backend may raise.

    A backend raises it from ``check_claim`` for any per-claim failure (timeout, non-2xx status,
    malformed or oversized response), and may raise it from its constructor (for example when the
    API key has an invalid shape). ``DS302`` catches it and skips that claim, or the whole backend
    when construction fails (plan contract C8).

    Message contract (threat model 0010 M5): the message is fixed text of at most 200
    characters. It never contains a response body, a request header, the API key or the claim
    text. Raise it without exception chaining (``raise FactCheckError(...) from None``), because a
    transport exception (``h11``/``httpx``) can carry the full ``Authorization`` header value in its
    own message. Callers still pass the message through ``docsentinel.log.safe`` before logging it.
    """


def _is_backend_name(value: object) -> bool:
    """Return whether ``value`` is a ``str`` that fully matches :data:`BACKEND_NAME_PATTERN`.

    :param value: The candidate backend name, of any type.
    :return: ``True`` only for a well-formed backend name.
    """
    return isinstance(value, str) and _BACKEND_NAME_RE.fullmatch(value) is not None


@dataclass(frozen=True)
class ClaimVerdict:
    """The backend's rating of one claim inside a checked fact.

    :ivar claim: The claim text as the backend states it (untrusted third-party text), at most
        :data:`MAX_RESULT_CLAIM_CHARS` characters.
    :ivar label: One of :data:`VERDICT_LABELS`.
    :ivar confidence: A finite number in ``[0.0, 1.0]``.
    """

    claim: str
    label: str
    confidence: float

    def __post_init__(self):
        """Validate every field.

        :raises FactCheckError: When any field breaks the contract described on the class.
        """
        if not isinstance(self.claim, str) or len(self.claim) > MAX_RESULT_CLAIM_CHARS:
            raise FactCheckError("fact-check result: a rated claim text is not a bounded string")
        if self.label not in VERDICT_LABELS:
            raise FactCheckError("fact-check result: a rated claim label is not a known label")
        confidence = self.confidence
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence)
            or not 0.0 <= confidence <= 1.0
        ):
            raise FactCheckError("fact-check result: a rated claim confidence is not a number in [0.0, 1.0]")


@dataclass(frozen=True)
class FactCheckResult:
    """A backend's validated verdict on one claim.

    Construction validates every field and raises :class:`FactCheckError` (not ``ValueError``), so
    a result built by a buggy backend still fails soft inside ``DS302``'s per-claim loop. The
    messages are fixed text and never echo a field value.

    :ivar verdict: One of :data:`VERDICTS`.
    :ivar confidence: The backend's confidence, a finite ``int`` or ``float`` in ``[0.0, 1.0]``
        (never a ``bool``).
    :ivar backend: The producing backend's name, fully matching :data:`BACKEND_NAME_PATTERN`.
    :ivar citations: At most :data:`MAX_CITATIONS` source strings of at most
        :data:`MAX_CITATION_CHARS` characters each. ``DS302`` does not use them yet.
    :ivar label: The explicit label of the verdict, one of :data:`VERDICT_LABELS`, or ``""`` for
        the default label of ``verdict`` (see :attr:`display`).
    :ivar claims: The backend's rating of each claim it found in the fact, at most
        :data:`MAX_RESULT_CLAIMS`; empty when the backend rates the fact as a whole.
    """

    verdict: Verdict
    confidence: float
    backend: str
    citations: tuple[str, ...] = ()
    label: str = ""
    claims: tuple[ClaimVerdict, ...] = ()

    @property
    def display(self) -> str:
        """The explicit verdict label: ``label``, else the default label of ``verdict``."""
        return self.label or VERDICT_DEFAULT_LABELS[self.verdict]

    def __post_init__(self):
        """Validate every field.

        :raises FactCheckError: When any field breaks the contract described on the class.
        """
        if not isinstance(self.verdict, str) or self.verdict not in VERDICTS:
            raise FactCheckError("fact-check result: verdict is not a known verdict")
        confidence = self.confidence
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence)
            or not 0.0 <= confidence <= 1.0
        ):
            raise FactCheckError("fact-check result: confidence is not a number in [0.0, 1.0]")
        if not _is_backend_name(self.backend):
            raise FactCheckError("fact-check result: backend is not a valid backend name")
        citations = self.citations
        if not isinstance(citations, tuple) or not all(isinstance(entry, str) for entry in citations):
            raise FactCheckError("fact-check result: citations is not a tuple of strings")
        if len(citations) > MAX_CITATIONS:
            raise FactCheckError("fact-check result: too many citations")
        if any(len(entry) > MAX_CITATION_CHARS for entry in citations):
            raise FactCheckError("fact-check result: a citation is too long")
        if self.label != "" and self.label not in VERDICT_LABELS:
            raise FactCheckError("fact-check result: label is not a known label")
        claims = self.claims
        if not isinstance(claims, tuple) or not all(isinstance(entry, ClaimVerdict) for entry in claims):
            raise FactCheckError("fact-check result: claims is not a tuple of rated claims")
        if len(claims) > MAX_RESULT_CLAIMS:
            raise FactCheckError("fact-check result: too many rated claims")


@runtime_checkable
class FactCheckClient(Protocol):
    """Structural contract of a fact-check backend (plan contract C2, PEP 544).

    A backend needs no shared base class and no registration decorator, only this shape. An
    optional ``close(self) -> None`` method is duck-typed: ``DS302`` calls it when present.

    Conventions the protocol cannot express (threat model 0010 M5, M8):

    * The class is constructible as ``cls(api_key=<str>)``. The constructor may raise
      :class:`FactCheckError` under the same message contract as ``check_claim``.
    * The key is stored only in a private attribute, and ``__repr__`` never reveals it.
    * The backend never reads ``os.environ`` or calls ``os.getenv``: the key arrives only through
      the constructor. It never reads another tool's key variable either.
    * ``check_claim`` raises nothing but :class:`FactCheckError`.

    :ivar name: The backend name, a value of ``fact_check_backend`` fully matching
        :data:`BACKEND_NAME_PATTERN`.
    :ivar API_KEY_ENV_VAR: The variable ``DS302`` reads the key from; equal to
        ``expected_api_key_env_var(name)`` (plan contract C3).
    """

    name: str
    API_KEY_ENV_VAR: ClassVar[str]

    def check_claim(self, claim: str) -> FactCheckResult:
        """Return the backend's verdict on one claim.

        :param claim: The claim sentence to check.
        :return: The validated result.
        :raises FactCheckError: On any failure; never another exception type.
        """
        ...


def expected_api_key_env_var(name: str) -> str:
    """Return the API-key environment variable name of a backend (plan contract C3).

    The result is ``DOCSENTINEL_FACTCHECK_<NAME>_API_KEY`` with ``<NAME>`` the upper-cased backend
    name. Callers handling a configuration value check membership in the known backend names
    first, so the ``ValueError`` never reaches a user for a configured name.

    :param name: The backend name.
    :return: The environment variable name.
    :raises ValueError: When ``name`` is not a ``str`` fully matching :data:`BACKEND_NAME_PATTERN`.
    """
    if not _is_backend_name(name):
        raise ValueError("fact-check backend name does not match the backend name pattern")
    return f"DOCSENTINEL_FACTCHECK_{name.upper()}_API_KEY"


#: Static map of backend name to backend module: the only module names that are ever imported.
#: ``config.FACT_CHECK_BACKEND_NAMES`` holds the same names (drift test).
FACT_CHECK_BACKEND_MODULES: Final[Mapping[str, str]] = MappingProxyType({"lenz": "docsentinel.fact_check.lenz"})

#: Registered backend classes, filled by each backend module when it is imported. Tests may
#: register a fake here.
FACT_CHECK_BACKENDS: dict[str, type[FactCheckClient]] = {}


def _import_lenz():
    """Import the Lenz backend module (Story 03.0), which registers itself.

    :raises ImportError: When the module or its dependency is missing.
    """
    importlib.import_module("docsentinel.fact_check.lenz")


#: One importer per value of :data:`FACT_CHECK_BACKEND_MODULES`, each with a fixed literal module
#: name, so the dynamic-import tripwire can pin every import site (threat model 0010 M7).
_MODULE_IMPORTERS: Final[Mapping[str, Callable[[], None]]] = MappingProxyType(
    {"docsentinel.fact_check.lenz": _import_lenz}
)


def _verify_backend(name: str, cls: object) -> type[FactCheckClient]:
    """Check that a registered class fits the backend contract for ``name``.

    :param name: The name the class is registered under.
    :param cls: The registered object.
    :return: ``cls``, typed as a backend class.
    :raises TypeError: When ``cls`` is not a class, its ``name`` differs from ``name``, its
        ``API_KEY_ENV_VAR`` does not follow plan contract C3, or ``check_claim`` is not callable.
    """
    if not isinstance(cls, type):
        raise TypeError("registered fact-check backend is not a class")
    if not _is_backend_name(name) or getattr(cls, "name", None) != name:
        raise TypeError("registered fact-check backend has a mismatched name")
    if getattr(cls, "API_KEY_ENV_VAR", None) != expected_api_key_env_var(name):
        raise TypeError("registered fact-check backend has a non-conforming API_KEY_ENV_VAR")
    if not callable(getattr(cls, "check_claim", None)):
        raise TypeError("registered fact-check backend has no callable check_claim")
    return cls


def load_backend(name: str) -> type[FactCheckClient]:
    """Return the backend class registered under ``name``, importing its module when needed.

    A registered class is returned without any import. Otherwise, when ``name`` is a key of
    :data:`FACT_CHECK_BACKEND_MODULES`, exactly that mapped module is imported (it registers
    itself) and the registry is read again. Nothing derived from ``name`` is ever passed to
    ``importlib``.

    :param name: The backend name, normally the validated ``fact_check_backend`` value.
    :return: The verified backend class.
    :raises KeyError: When ``name`` is neither registered nor a key of the static map, or its
        module did not register it.
    :raises TypeError: When the class does not fit the backend contract.
    :raises ImportError: When the mapped module (or its dependency) cannot be imported.
    """
    if not isinstance(name, str):
        raise KeyError("unknown fact-check backend")
    cls = FACT_CHECK_BACKENDS.get(name)
    if cls is None:
        module = FACT_CHECK_BACKEND_MODULES.get(name)
        if module is None:
            raise KeyError("unknown fact-check backend")
        _MODULE_IMPORTERS[module]()
        cls = FACT_CHECK_BACKENDS.get(name)
        if cls is None:
            raise KeyError("fact-check backend module did not register the backend")
    return _verify_backend(name, cls)
