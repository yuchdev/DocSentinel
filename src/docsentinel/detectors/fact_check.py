"""DS302: send high-salience claims to an external fact-check backend (ADR 0007).

``DS302`` is a deep-profile, advisory-only rule that self-gates. It needs both consent gates of
plan contract C1: the profile-wide ``deep_confirm`` (checked by the engine before any deep analyzer
runs) and the invoker-only gate 2 resolved here, which is ``use_external_api`` (the CLI flag
``--use-external-api``, the ``scan(use_external_api=True)`` keyword, or
``DOCSENTINEL_USE_EXTERNAL_API`` set to exactly ``"1"``) plus a non-empty API-key environment
variable of the configured backend. Consent is never read from ``Config`` (threat model 0010 M1).

This module is the only one under ``src/docsentinel/`` that reads ``DOCSENTINEL_USE_EXTERNAL_API``
or a ``DOCSENTINEL_FACTCHECK_*`` variable (threat model 0010 M8). The key is read once, inside the
backend constructor call, and is never logged, stored on this module or put in a finding.

Imports: the standard library, ``docsentinel`` internals, ``docsentinel.mining.nlp`` and
``docsentinel.fact_check.protocol`` only. ``docsentinel.mining.claims`` is imported lazily on the
gate-open path, and a backend module (with ``httpx``) only through ``load_backend``, so a closed
gate, ``import docsentinel`` and every fast or standard scan import neither.

Candidate selection is :func:`trace_candidates`, the one extraction loop shared with
``engine.extract_facts`` (plan contract C11), over the pure ``mining.salience.trace_salience``
(Story 02.0 decision T8, Story 05.0 decision X2), imported lazily so a closed gate never imports
scikit-learn. ``DS302`` uses :func:`collect_candidates`, which takes no policy.

The only backend is ``lenz`` (Story 03.0, ``docsentinel.fact_check.lenz``). It registers itself in
``FACT_CHECK_BACKENDS`` when imported, and only ``load_backend`` imports it, after egress was
requested and the key is present. When that import fails (for example a missing ``httpx``), the
gate stays closed with the reason ``backend lenz not available`` and no claim leaves the machine.
"""

from __future__ import annotations

import importlib
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Final, Optional

from docsentinel import models, rules
from docsentinel.config import FACT_CHECK_BACKEND_NAMES, Config, ConfigError, validate_fact_check_option
from docsentinel.fact_check.protocol import (
    FACT_CHECK_BACKENDS,
    REPORTABLE_VERDICTS,
    FactCheckClient,
    FactCheckError,
    FactCheckResult,
    expected_api_key_env_var,
    load_backend,
)
from docsentinel.log import safe
from docsentinel.mining import nlp

if TYPE_CHECKING:
    from docsentinel.mining.claims import Claim

DS302 = rules.register_rule(
    rules.Rule(
        code="DS302",
        profile="deep",
        title="External fact-check disagreement",
        description=("A high-salience claim is rated false or mixed by an external fact-checking backend."),
        severity="warning",
    )
)

logger = logging.getLogger(__name__)

#: Gate 2's environment-variable form; only the exact value ``"1"`` opens it (threat model M2).
USE_EXTERNAL_API_ENV: Final = "DOCSENTINEL_USE_EXTERNAL_API"

#: ``ConfigError`` text for a ``use_external_api`` value that is not a ``bool`` (threat model M3).
USE_EXTERNAL_API_TYPE_MESSAGE: Final = "use_external_api must be True or False"

#: Gate reason when neither the flag, the keyword nor the environment variable asked for egress.
_NOT_REQUESTED_REASON: Final = "pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1)"

#: Most characters of one candidate's text sent to a backend (Story 02.0 Task 03).
MAX_CANDIDATE_CHARS: Final = 1000

#: Salience weights of ``DS302`` (Story 02.0 Task 01; fixed policy, never configurable). They are
#: plain floats so importing this detector never imports ``mining.salience``; Task 03's
#: ``select_candidates()`` builds the ``SalienceWeights`` from them. Constraints pinned by tests:
#: (a) they sum to 1.0, (b) ``_W_DISTINCT < 0.5``, (c) a fully distinctive three-token object with
#: one number and one entity scores at least 0.5, (d) the score is monotonic in each signal.
#: Numbers are the claim shape a fact-checking backend scores best, so they carry real weight.
_W_NUMERIC: Final[float] = 0.3
#: Named entities (products, versions, organisations) are the other checkable shape; equal to numbers.
_W_ENTITY: Final[float] = 0.3
#: Distinctiveness penalizes boilerplate, but stays below 0.5 so it alone never clears the default
#: ``fact_check_min_salience = 0.5`` (decision T6).
_W_DISTINCT: Final[float] = 0.4

#: Near-duplicate clustering threshold of ``DS302`` (decision T2): two claim sentences with a TF-IDF
#: cosine similarity strictly above it cost one check. Fixed and never configurable, because a lower
#: value could inflate the candidate count (Story 02.0 Security notes).
_DEDUP_THRESHOLD: Final[float] = 0.92


@dataclass(frozen=True)
class SelectionPolicy:
    """The non-configurable ``DS302`` selection policy, or an ``extract-facts`` exploration of it.

    The values are plain numbers, validated only when a selection runs (``SalienceWeights`` and
    ``mining.salience.trace_salience`` raise ``ValueError``), so building a policy never imports
    ``mining.salience``. A policy comes only from :data:`DS302_POLICY` or an invoker's library
    keyword or CLI flag (Story 05.0, decision X5), never from a configuration layer or the
    environment, and ``DS302`` never receives one (:func:`collect_candidates` has no ``policy``).

    :ivar weights: The ``(numeric, entity, distinctiveness)`` salience weights.
    :ivar dedup_threshold: The near-duplicate clustering threshold, in ``(0, 1]``.
    """

    weights: tuple[float, float, float]
    dedup_threshold: float


#: The fixed ``DS302`` policy, built from the constants above.
DS302_POLICY: Final[SelectionPolicy] = SelectionPolicy((_W_NUMERIC, _W_ENTITY, _W_DISTINCT), _DEDUP_THRESHOLD)

#: The ``fact_check_*`` values :func:`select_candidates` reads; every one is re-validated.
_SELECTION_OPTIONS: Final = (
    "fact_check_min_salience",
    "fact_check_max_claims_per_document",
    "fact_check_max_claims_total",
)

#: Most characters of the candidate text quoted in a finding ``message`` (ADR 0007 Contract 9).
_SNIPPET_CHARS: Final = 200

#: The finding type of every ``DS302`` finding (``docs/specs/finding-types.md``).
FINDING_TYPE: Final = "unverified claim"


def external_api_requested(use_external_api: bool) -> bool:
    """Return whether the invoker asked for external-API egress (gate 2, first half).

    The request is the ``use_external_api`` argument or ``DOCSENTINEL_USE_EXTERNAL_API`` set to
    exactly ``"1"``; the value is compared as is, never stripped, lowered or converted.

    :param use_external_api: The invoker's flag or keyword; must be a real ``bool``.
    :returns: A real ``bool``.
    :raises ConfigError: When ``use_external_api`` is not a ``bool``.
    """
    if not isinstance(use_external_api, bool):
        raise ConfigError(USE_EXTERNAL_API_TYPE_MESSAGE)
    return use_external_api is True or os.environ.get(USE_EXTERNAL_API_ENV) == "1"


@dataclass(frozen=True)
class ExternalApiGate:
    """The resolved state of gate 2 for one backend (ADR 0007 Contract 3).

    It holds no key value, only whether the key variable is set and not empty.

    :ivar requested: Whether the invoker asked for egress.
    :ivar backend: The validated backend name.
    :ivar key_env_var: The backend's API-key variable name (plan contract C3).
    :ivar key_present: Whether that variable is set and not empty.
    :ivar backend_available: Whether the backend class can be loaded. Only probed once egress was
        requested and the key is present; an unavailable backend counts as a closed gate (owner
        ruling 2026-11-23), so nothing claims ``DS302`` checked anything.
    """

    requested: bool
    backend: str
    key_env_var: str
    key_present: bool
    backend_available: bool = True

    @property
    def open(self) -> bool:
        """Whether gate 2 is open.

        ``True`` when egress was requested, the key is present and the backend loads.
        """
        return self.requested and self.key_present and self.backend_available

    def reasons(self) -> tuple[str, ...]:
        """Return what is missing to open the gate, in a fixed order.

        :returns: Fixed text, the key variable name and the validated backend name only, empty
            when the gate is open.
        """
        missing: list[str] = []
        if not self.requested:
            missing.append(_NOT_REQUESTED_REASON)
        if not self.key_present:
            missing.append(f"set {self.key_env_var}")
        if not self.backend_available:
            missing.append(f"backend {self.backend} not available")
        return tuple(missing)

    def skip_message(self) -> str:
        """Return the gate WARNING and ``pending`` text.

        :returns: ``DS302 skipped: `` followed by the reasons joined with ``; ``.
        """
        return "DS302 skipped: " + "; ".join(self.reasons())


def _validated_backend(config: Config) -> str:
    """Return ``config.fact_check_backend`` when it names a known backend, else fail closed.

    Membership is checked before any name is derived from the value (threat model M7). The known
    names are the configuration vocabulary plus any registered class (a test fake).

    :param config: The effective, possibly injected, configuration.
    :returns: The backend name.
    :raises ConfigError: When the name is not known.
    """
    known = FACT_CHECK_BACKEND_NAMES.union(FACT_CHECK_BACKENDS)
    backend = config.fact_check_backend
    if not isinstance(backend, str) or backend not in known:
        raise ConfigError(f"fact_check_backend must be one of: {', '.join(sorted(known))}")
    return backend


def resolve_external_api_gate(config: Config, *, use_external_api: bool) -> ExternalApiGate:
    """Resolve gate 2 from the invoker consent, the environment and the configured backend.

    :param config: The effective configuration; only ``fact_check_backend`` is read.
    :param use_external_api: The invoker's flag or keyword; must be a real ``bool``.
    :returns: The gate state; once egress is requested and the key is present, the backend is
        loaded too, and a backend that cannot be loaded closes the gate.
    :raises ConfigError: When ``use_external_api`` is not a ``bool`` or the backend is unknown.
    """
    requested = external_api_requested(use_external_api)
    backend = _validated_backend(config)
    key_env_var = expected_api_key_env_var(backend)
    key_present = bool(os.environ.get(key_env_var))
    return ExternalApiGate(
        requested=requested,
        backend=backend,
        key_env_var=key_env_var,
        key_present=key_present,
        backend_available=_backend_loadable(backend) if requested and key_present else True,
    )


def _backend_loadable(backend: str) -> bool:
    """Return whether the backend class loads and fits the protocol.

    Called only when egress was requested and the key is present, so a closed gate never imports a
    backend module (threat model 0010 M9). The exception text is never kept or logged.

    :param backend: The validated backend name.
    :returns: ``False`` when :func:`load_backend` raises ``ImportError``, ``KeyError`` or
        ``TypeError``.
    """
    try:
        load_backend(backend)
    except (ImportError, KeyError, TypeError) as exc:
        logger.debug("DS302: backend %s cannot be loaded (%s)", backend, type(exc).__name__)
        return False
    return True


def validate_selection_policy(policy: SelectionPolicy) -> SelectionPolicy:
    """Validate a selection policy with the salience module's own checks, before any extraction.

    The weights go through ``SalienceWeights`` (finite non-``bool`` numbers in ``[0, 1]`` summing
    to ``1.0``) and the threshold through the ``trace_salience`` threshold check, so a bad
    exploration setting fails before a document is parsed (threat model 0010 extract-facts E6).

    :param policy: The policy to check.
    :returns: The policy with its numbers as ``float``.
    :raises ValueError: When ``weights`` is not three valid weights or the threshold is invalid.
    """
    weights = policy.weights
    if not isinstance(weights, tuple) or len(weights) != 3:
        raise ValueError("weights must be a tuple of three numbers (numeric, entity, distinctiveness)")
    salience = importlib.import_module("docsentinel.mining.salience")
    checked = salience.SalienceWeights(numeric=weights[0], entity=weights[1], distinctiveness=weights[2])
    threshold = salience.require_dedup_threshold(policy.dedup_threshold)
    return SelectionPolicy((float(checked.numeric), float(checked.entity), float(checked.distinctiveness)), threshold)


@dataclass(frozen=True)
class CandidateClaim:
    """One claim selected for a fact-check (Story 02.0 data contract).

    :ivar claim: The extracted claim it was built from.
    :ivar text: The exact text sent to the backend: the stripped sentence, at most
        :data:`MAX_CANDIDATE_CHARS` characters.
    :ivar score: The salience score in ``[0, 1]``, used for ordering and counts only.
    :ivar numeric: The numeric density signal, in ``[0, 1]``.
    :ivar entity: The entity density signal, in ``[0, 1]``.
    :ivar distinctiveness: The corpus distinctiveness signal, in ``[0, 1]``.
    :ivar cluster_id: The near-duplicate cluster id.
    :ivar cluster_size: The number of canonical claims in that cluster, ``>= 1``.

    The five signal and cluster fields (Story 05.0) default to neutral values so a hand-built
    candidate (a test double) needs only the Story 02.0 fields; the trace always sets all five.
    """

    claim: Claim
    text: str
    score: float
    numeric: float = 0.0
    entity: float = 0.0
    distinctiveness: float = 0.0
    cluster_id: int = 0
    cluster_size: int = 1

    def __post_init__(self):
        """Bound the text that can leave the machine, whoever built the candidate.

        :raises ValueError: When ``text`` is not a ``str`` of at most :data:`MAX_CANDIDATE_CHARS`
            characters.
        """
        if not isinstance(self.text, str) or len(self.text) > MAX_CANDIDATE_CHARS:
            raise ValueError(f"candidate text must be a string of at most {MAX_CANDIDATE_CHARS} characters")


def _candidate_text(claim: Claim) -> str:
    """Return the text sent for a claim: its sentence stripped, cut to the send bound.

    :param claim: The extracted claim.
    :returns: ``claim.raw_sentence.strip()`` cut to :data:`MAX_CANDIDATE_CHARS` code points.
    """
    return claim.raw_sentence.strip()[:MAX_CANDIDATE_CHARS]


def _trace_selection(
    claims: tuple[Claim, ...], config: Config, policy: SelectionPolicy
) -> tuple[tuple[CandidateClaim, str], ...]:
    """Trace the selection of ``claims`` under ``policy`` and the three config values.

    :param claims: Every extracted claim.
    :param config: The effective configuration; only the three selection values are read.
    :param policy: The selection policy.
    :returns: ``(candidate, disposition)`` for every canonical claim, in trace order.
    :raises ConfigError: When a selection value of ``config`` is invalid.
    :raises ValueError: When ``policy`` holds an invalid weight or threshold.
    """
    values = {name: validate_fact_check_option(name, getattr(config, name)) for name in _SELECTION_OPTIONS}
    salience = importlib.import_module("docsentinel.mining.salience")
    numeric, entity, distinctiveness = policy.weights
    weights = salience.SalienceWeights(numeric=numeric, entity=entity, distinctiveness=distinctiveness)
    traced = salience.trace_salience(
        claims,
        weights=weights,
        dedup_threshold=policy.dedup_threshold,
        min_salience=values["fact_check_min_salience"],
        max_per_document=int(values["fact_check_max_claims_per_document"]),
        max_total=int(values["fact_check_max_claims_total"]),
    )
    return tuple(
        (
            CandidateClaim(
                claim=entry.claim,
                text=_candidate_text(entry.claim),
                score=entry.score,
                numeric=entry.numeric,
                entity=entry.entity,
                distinctiveness=entry.distinctiveness,
                cluster_id=entry.cluster_id,
                cluster_size=entry.cluster_size,
            ),
            entry.disposition,
        )
        for entry in traced
    )


def select_candidates(
    claims: tuple[Claim, ...], config: Config, *, policy: SelectionPolicy = DS302_POLICY
) -> tuple[CandidateClaim, ...]:
    """Select the claims ``DS302`` may send, in send order (Story 02.0 Task 03).

    The three numeric selection values of ``config`` are re-validated with the loader's own
    validator, so an injected ``Config`` fails closed before ``mining`` is imported. Selection is
    the ``selected`` subsequence of ``mining.salience.trace_salience`` with the ``policy`` weights
    and dedup threshold (the fixed ``DS302`` values by default); its order is kept as returned,
    never re-sorted, filtered or truncated here. Only those three ``fact_check_*`` values are
    read: never ``use_external_api``, the time budget, the environment or a secret.

    :param claims: Every extracted claim of the scan.
    :param config: The effective configuration.
    :param policy: The selection policy; ``DS302`` always uses :data:`DS302_POLICY`.
    :returns: The selected candidates, in send order.
    :raises ConfigError: When a selection value of ``config`` is invalid.
    :raises ValueError: When ``policy`` holds an invalid weight or threshold.
    """
    return tuple(
        candidate for candidate, disposition in _trace_selection(claims, config, policy) if disposition == "selected"
    )


@dataclass(frozen=True)
class CandidateTrace:
    """Every canonical claim of one extraction with its selection disposition (plan contract C11).

    :ivar entries: ``(candidate, disposition)`` pairs in trace order; the disposition is one of
        ``mining.salience.DISPOSITIONS``.
    :ivar documents_read: The number of Markdown documents read.
    :ivar claims_extracted: The number of claims extracted before selection.
    """

    entries: tuple[tuple[CandidateClaim, str], ...]
    documents_read: int
    claims_extracted: int

    @property
    def selected(self) -> tuple[CandidateClaim, ...]:
        """The selected candidates in send order.

        The candidates whose disposition is ``selected``, in trace order.
        """
        return tuple(candidate for candidate, disposition in self.entries if disposition == "selected")


def trace_candidates(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Config,
    *,
    policy: SelectionPolicy = DS302_POLICY,
) -> CandidateTrace:
    """Extract the claims of every Markdown document and trace their selection (plan contract C11).

    This is the only extraction loop shared by ``DS302`` and ``extract_facts``. Extraction is the
    one ``DS301`` uses (plan contract C7): the lazily imported ``docsentinel.mining.claims``, the
    shared ``mining.nlp`` pipeline, the ``.md`` filter and a strict UTF-8 read. It reads no
    environment, resolves no consent gate and imports no backend.

    :param root: The scan root.
    :param documents: The readable documents, in scan order.
    :param config: The effective configuration; only the three selection values are read.
    :param policy: The selection policy; ``DS302`` always uses :data:`DS302_POLICY`.
    :returns: The trace of every canonical claim plus the document and claim counts.
    :raises ConfigError: When a selection value of ``config`` is invalid.
    :raises ValueError: When ``policy`` holds an invalid weight or threshold.
    """
    extract_claims = importlib.import_module("docsentinel.mining.claims").extract_claims
    pipeline = nlp.load_pipeline()
    all_claims: list[Claim] = []
    documents_read = 0
    for doc in documents:
        if not doc.path.endswith(".md"):
            continue
        with (root / doc.path).open("r", encoding="utf-8") as stream:
            text = stream.read()
        documents_read += 1
        all_claims.extend(extract_claims(pipeline, text, doc.path))
    claims = tuple(all_claims)
    return CandidateTrace(
        entries=_trace_selection(claims, config, policy),
        documents_read=documents_read,
        claims_extracted=len(claims),
    )


def collect_candidates(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Config,
) -> tuple[CandidateClaim, ...]:
    """Return the ``DS302`` candidates: ``trace_candidates(root, documents, config).selected``.

    It takes no ``policy``, so ``DS302`` can never send under an exploration policy.

    :param root: The scan root.
    :param documents: The readable documents of the scan, in scan order.
    :param config: The effective configuration.
    :returns: The candidates to send, in send order.
    """
    return trace_candidates(root, documents, config).selected


def _finding(candidate: CandidateClaim, result: FactCheckResult) -> models.Finding:
    """Build the finding for one reportable verdict (ADR 0007 Contract 9).

    Only the validated verdict, the ``.2f`` confidence, the validated backend name and the
    candidate text are used; ``result.citations`` never reaches a finding (threat model M11).

    :param candidate: The candidate that was sent.
    :param result: The backend's validated result.
    :returns: The finding; the confidence is only in the report-only ``value``.
    """
    snippet = candidate.text[:_SNIPPET_CHARS]
    return models.Finding(
        rule=DS302.code,
        path=candidate.claim.path,
        message=f"external fact-check: '{snippet}' rated {result.verdict} by {result.backend} - review to confirm",
        severity=DS302.severity,
        value=f"{result.verdict} (confidence {result.confidence:.2f}): {candidate.text}",
        type=FINDING_TYPE,
    )


def _check_candidates(
    client: FactCheckClient,
    candidates: tuple[CandidateClaim, ...],
    config: Config,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[models.Finding, ...]:
    """Send each candidate to the backend, in order, within the time budget.

    A ``FactCheckError`` skips that claim with one WARNING naming the document only. Any other
    exception from ``check_claim`` stops the loop and is replaced by a type-name-only
    ``RuntimeError`` with no exception chain (threat model M5). One INFO line with counts only is
    logged from a ``finally`` block (threat model M10).

    :param client: The constructed backend client.
    :param candidates: The candidates, in send order.
    :param config: The effective configuration; the time budget, the confidence floor and the
        backend name are re-validated.
    :param clock: A monotonic clock; a test seam only.
    :returns: The findings, sorted by ``(path, message)``.
    :raises ConfigError: When a re-validated configuration value is invalid.
    :raises RuntimeError: When ``check_claim`` raises anything but ``FactCheckError``.
    """
    budget = int(validate_fact_check_option("fact_check_time_budget_seconds", config.fact_check_time_budget_seconds))
    min_confidence = validate_fact_check_option("fact_check_min_confidence", config.fact_check_min_confidence)
    backend = _validated_backend(config)
    total = len(candidates)
    findings: list[models.Finding] = []
    sent = failed = not_sent = 0
    sent_paths: set[str] = set()
    per_document: dict[str, int] = {}
    escaped: Optional[str] = None
    try:
        deadline = clock() + budget if candidates else 0.0
        for index, candidate in enumerate(candidates):
            if clock() >= deadline:
                not_sent = total - index
                logger.warning(
                    "DS302: time budget of %d s exhausted; %d of %d claim(s) not checked", budget, not_sent, total
                )
                break
            path = candidate.claim.path
            sent += 1
            sent_paths.add(path)
            per_document[path] = per_document.get(path, 0) + 1
            try:
                result = client.check_claim(candidate.text)
            except FactCheckError as exc:
                failed += 1
                # Type name only: a backend message may echo request headers (M5, FC-5).
                logger.warning("DS302: fact-check failed for a claim in %s (%s)", safe(path), type(exc).__name__)
                continue
            except BaseException as exc:  # contained below: only the type name survives (M5)
                if isinstance(exc, KeyboardInterrupt):
                    raise
                escaped = type(exc).__name__
                break
            if result.verdict in REPORTABLE_VERDICTS and result.confidence >= min_confidence:
                findings.append(_finding(candidate, result))
        if escaped is not None:
            # Raised outside the handler, so there is no __cause__ and no __context__.
            raise RuntimeError(f"DS302: backend {backend} raised {escaped}")
    finally:
        logger.info(
            "DS302: sent %d claim(s) from %d document(s) to backend %s; %d failed, %d reported, %d not sent (time budget)",
            sent,
            len(sent_paths),
            backend,
            failed,
            len(findings),
            not_sent,
        )
    findings.sort(key=lambda finding: (finding.path, finding.message))
    logger.debug("DS302: %d candidate(s), %d sent, %d failed, %d reported", total, sent, failed, len(findings))
    for path in sorted(per_document):
        logger.debug("DS302: %s: %d claim(s) sent", safe(path), per_document[path])
    return tuple(findings)


def _construct_client(client_cls: type[FactCheckClient]) -> Optional[FactCheckClient]:
    """Construct the backend client with the key read inside the constructor call.

    :param client_cls: The verified backend class.
    :returns: The client, or ``None`` when the key variable is unset or empty now.
    """
    if not os.environ.get(client_cls.API_KEY_ENV_VAR):
        return None
    return client_cls(api_key=os.environ.get(client_cls.API_KEY_ENV_VAR, ""))


def _close_client(client: FactCheckClient) -> Optional[str]:
    """Call the client's optional ``close()`` and contain any exception.

    :param client: The backend client.
    :returns: The type name of an exception ``close()`` raised, else ``None``.
    """
    close = getattr(client, "close", None)
    if not callable(close):
        return None
    failure: Optional[str] = None
    try:
        close()
    except BaseException as exc:  # contained by the caller: only the type name survives (M5)
        if isinstance(exc, KeyboardInterrupt):
            raise
        failure = type(exc).__name__
    return failure


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Config,
    *,
    use_external_api: bool = False,
) -> tuple[models.Finding, ...]:
    """Fact-check the selected claims against the configured backend (ADR 0007 Contract 2).

    A closed gate logs one WARNING and returns before any document is read or heavy module is
    imported. An unavailable backend, a backend constructor ``FactCheckError`` or a key that
    vanished since the gate each log one fixed WARNING and return no findings. Any other
    exception from construction, ``check_claim`` or ``close()`` becomes
    ``RuntimeError("DS302: backend <name> raised <type>")`` without exception chaining.

    :param root: The scan root.
    :param documents: The readable documents of the scan, in scan order.
    :param config: The effective configuration.
    :param use_external_api: The invoker's consent; must be a real ``bool``.
    :returns: The findings, sorted by ``(path, message)``.
    :raises ConfigError: When ``use_external_api`` is not a ``bool`` or a ``fact_check_*`` value of
        an injected ``Config`` is invalid.
    :raises RuntimeError: When the backend raises anything but ``FactCheckError``.
    """
    gate = resolve_external_api_gate(config, use_external_api=use_external_api)
    if not gate.open:
        logger.warning(gate.skip_message())
        return ()
    for name in ("fact_check_time_budget_seconds", "fact_check_min_confidence"):
        validate_fact_check_option(name, getattr(config, name))
    backend = gate.backend
    try:
        client_cls = load_backend(backend)
    except (ImportError, KeyError, TypeError):
        # Only if the backend stopped loading since the gate probed it; same fixed text.
        logger.warning(replace(gate, backend_available=False).skip_message())
        return ()
    escaped: Optional[str] = None
    try:
        client = _construct_client(client_cls)
    except FactCheckError:
        logger.warning("DS302 skipped: backend %s could not be initialised (FactCheckError)", backend)
        return ()
    except BaseException as exc:  # contained below: only the type name survives (M5)
        if isinstance(exc, KeyboardInterrupt):
            raise
        escaped = type(exc).__name__
    if escaped is not None:
        raise RuntimeError(f"DS302: backend {backend} raised {escaped}")
    if client is None:
        logger.warning(
            replace(
                resolve_external_api_gate(config, use_external_api=use_external_api), key_present=False
            ).skip_message()
        )
        return ()
    try:
        candidates = collect_candidates(root, documents, config)
        findings = _check_candidates(client, candidates, config)
    finally:
        escaped = _close_client(client)
    if escaped is not None:
        raise RuntimeError(f"DS302: backend {backend} raised {escaped}")
    return findings


rules.ANALYZERS[DS302.code] = detect
