"""DS302: send high-salience claims to an external fact-check backend (ADR 0007).

``DS302`` is a deep-profile, advisory-only rule that self-gates. It runs only when the
invoker-only consent gate resolved here is open, which is ``use_external_api`` (the CLI flag
``--use-external-api``, the ``scan(use_external_api=True)`` keyword, or
``DOCSENTINEL_USE_EXTERNAL_API`` set to exactly ``"1"``) plus a non-empty API-key environment
variable of the configured backend. Consent is never read from ``Config`` (threat model 0010 M1).

This module is the only one under ``src/docsentinel/`` that reads ``DOCSENTINEL_USE_EXTERNAL_API``,
a ``DOCSENTINEL_FACTCHECK_*`` variable or its fallback, the backend's standard key variable (the
same name without the ``DOCSENTINEL_FACTCHECK_`` prefix; threat model 0010 M8). The key is read when the gate is resolved
and again for the backend constructor call, and is never logged, stored on this module or put in a
finding.

Imports: the standard library, ``docsentinel`` internals, ``docsentinel.mining.nlp`` and
``docsentinel.fact_check.protocol`` only. ``docsentinel.mining.claims`` is imported lazily on the
gate-open path, and a backend module (with ``httpx``) only through ``load_backend``, so a closed
gate, ``import docsentinel`` and every fast or standard scan import neither.

Candidate selection is :func:`trace_candidates`, the one extraction loop shared with
``engine.extract_facts`` (plan contract C11), over the pure ``mining.salience.trace_salience``
(Story 02.0 decision T8, Story 05.0 decision X2), imported lazily so a closed gate never imports
scikit-learn. ``DS302`` uses :func:`collect_candidates` with :data:`DS302_POLICY`, unless the
invoker gave ``--weights`` or ``--dedup-threshold`` for the run (owner ruling of 2026-11-27).

The only backend is ``lenz`` (Story 03.0, ``docsentinel.fact_check.lenz``). It registers itself in
``FACT_CHECK_BACKENDS`` when imported, and only ``load_backend`` imports it, after egress was
requested and the key is present. When that import fails (for example a missing ``httpx``), the
gate stays closed with the reason ``backend lenz not available`` and no claim leaves the machine.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Final, Optional, Union

from docsentinel import models, rules
from docsentinel.config import (
    FACT_CHECK_BACKEND_NAMES,
    FACT_COMBINATION_ALL,
    FACT_COMBINATION_EACH,
    Config,
    ConfigError,
    parse_fact_combination,
    validate_fact_check_option,
)
from docsentinel.fact_check.protocol import (
    FACT_CHECK_BACKENDS,
    REPORTABLE_VERDICTS,
    FactCheckClient,
    FactCheckError,
    FactCheckResult,
    expected_api_key_env_var,
    load_backend,
)
from docsentinel.log import quote_start, safe
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
    environment. ``DS302`` uses an invoker policy only for the run the invoker gave it in
    (``scan``/``baseline`` ``--weights``/``--dedup-threshold``, owner ruling of 2026-11-27).

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
            standard = self.key_env_var.removeprefix("DOCSENTINEL_FACTCHECK_")
            missing.append(f"set {self.key_env_var} or {standard}")
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
    key_present = bool(_read_api_key(key_env_var))
    return ExternalApiGate(
        requested=requested,
        backend=backend,
        key_env_var=key_env_var,
        key_present=key_present,
        backend_available=_backend_loadable(backend) if requested and key_present else True,
    )


def _read_api_key(key_env_var: str) -> str:
    """Return the API key: the DocSentinel variable, else the backend's standard variable.

    The fallback is the same name without the ``DOCSENTINEL_FACTCHECK_`` prefix (the vendor's
    standard variable). A variable that is unset or empty counts as undefined. The value is never logged or echoed.

    :param key_env_var: The ``DOCSENTINEL_FACTCHECK_<NAME>_API_KEY`` variable name.
    :returns: The key, or an empty string when neither variable is set.
    """
    value = os.environ.get(key_env_var)
    if value:
        return value
    return os.environ.get(key_env_var.removeprefix("DOCSENTINEL_FACTCHECK_"), "")


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
    :param policy: The selection policy; :data:`DS302_POLICY` unless the invoker changed it.
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

    This is the only extraction loop shared by ``DS302`` and ``extract_facts``. It uses the module
    and pipeline ``DS301`` uses (plan contract C7): the lazily imported ``docsentinel.mining.claims``,
    the shared ``mining.nlp`` pipeline, the ``.md`` filter and a strict UTF-8 read, but calls
    ``extract_statements`` rather than ``extract_claims``: one self-contained, declarative,
    non-quoted, non-hedged statement per candidate instead of one subject-verb-object triple. It
    reads no environment, resolves no consent gate and imports no backend.

    :param root: The scan root.
    :param documents: The readable documents, in scan order.
    :param config: The effective configuration; only the three selection values are read.
    :param policy: The selection policy; :data:`DS302_POLICY` unless the invoker changed it.
    :returns: The trace of every canonical claim plus the document and claim counts.
    :raises ConfigError: When a selection value of ``config`` is invalid.
    :raises ValueError: When ``policy`` holds an invalid weight or threshold.
    """
    extract_statements = importlib.import_module("docsentinel.mining.claims").extract_statements
    pipeline = nlp.load_pipeline()
    all_claims: list[Claim] = []
    documents_read = 0
    for doc in documents:
        if not doc.path.endswith(".md"):
            continue
        with (root / doc.path).open("r", encoding="utf-8") as stream:
            text = stream.read()
        documents_read += 1
        all_claims.extend(extract_statements(pipeline, text, doc.path))
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
    *,
    policy: SelectionPolicy = DS302_POLICY,
) -> tuple[CandidateClaim, ...]:
    """Return the ``DS302`` candidates, in send order.

    The ``selected`` entries of :func:`trace_candidates`; under ``fact_check_combination = "all"``
    every claim above the salience floor instead.

    :param root: The scan root.
    :param documents: The readable documents of the scan, in scan order.
    :param config: The effective configuration.
    :param policy: The selection policy; the fixed :data:`DS302_POLICY` unless the invoker gave
        ``scan --weights`` or ``--dedup-threshold`` for this run.
    :returns: The candidates to send, in send order.
    """
    trace = trace_candidates(root, documents, config, policy=policy)
    if config.fact_check_combination == FACT_COMBINATION_ALL:
        # ``all`` joins every claim above the salience floor: the per-document and total caps do
        # not apply (owner ruling of 2026-11-27). Duplicates and below-floor claims stay out.
        return tuple(candidate for candidate, disposition in trace.entries if disposition in ALL_DISPOSITIONS)
    return trace.selected


#: The dispositions ``fact_check_combination = "all"`` sends: selected plus the two cap rejections.
ALL_DISPOSITIONS: Final[frozenset[str]] = frozenset({"selected", "document_cap", "total_cap"})


def _pack_all(candidates: tuple[CandidateClaim, ...]) -> tuple[tuple[int, int], ...]:
    """Split all candidates into consecutive 1-based ranges whose joined text fits one request.

    Whole claims only: a range grows while the joined text stays within
    :data:`MAX_CANDIDATE_CHARS`, so ``all`` is one fact when it fits and several otherwise.

    :param candidates: The candidates, in send order.
    :returns: The ``(start, end)`` ranges, in order, covering every candidate.
    """
    ranges: list[tuple[int, int]] = []
    start = 1
    length = 0
    for position, candidate in enumerate(candidates, start=1):
        added = len(candidate.text) + (1 if position > start else 0)
        if position > start and length + added > MAX_CANDIDATE_CHARS:
            ranges.append((start, position - 1))
            start = position
            added = len(candidate.text)
            length = 0
        length += added
    if candidates:
        ranges.append((start, len(candidates)))
    return tuple(ranges)


@dataclass(frozen=True)
class FactGroup:
    """One fact sent to the backend: one or more candidates joined in send order.

    :ivar members: The candidates, in send order; at least one.
    :ivar label: The 1-based send-order positions it covers, ``"3"`` or ``"1-6"``.
    """

    members: tuple[CandidateClaim, ...]
    label: str

    @property
    def text(self) -> str:
        """The exact text sent: the member texts joined by one space."""
        return " ".join(member.text for member in self.members)

    @property
    def paths(self) -> tuple[str, ...]:
        """The distinct documents of the members, in first-seen order."""
        return tuple(dict.fromkeys(member.claim.path for member in self.members))


def combine_candidates(candidates: tuple[CandidateClaim, ...], combination: str) -> tuple[FactGroup, ...]:
    """Group the candidates into the facts ``DS302`` sends (``fact_check_combination``).

    ``each`` makes one fact per candidate. ``all`` joins every candidate (under ``all``,
    :func:`collect_candidates` gives every claim above the salience floor, caps ignored), split by
    :func:`_pack_all` into consecutive facts of whole claims whose joined text stays within
    :data:`MAX_CANDIDATE_CHARS`. For ranges, positions are 1-based in send order; a range is
    clipped to the candidates there are, a range starting past the last candidate is dropped and
    a candidate no range names is its own fact. Groups keep send order (by their first position).

    :param candidates: The candidates from :func:`collect_candidates`, in send order.
    :param combination: The ``fact_check_combination`` value.
    :returns: The facts to send, in send order.
    :raises ConfigError: When ``combination`` is invalid.
    """
    parsed = parse_fact_combination(combination)
    count = len(candidates)
    if parsed == FACT_COMBINATION_EACH:
        ranges: tuple[tuple[int, int], ...] = ()
    elif parsed == FACT_COMBINATION_ALL:
        ranges = _pack_all(candidates)
    else:
        ranges = tuple((start, min(end, count)) for start, end in parsed if start <= count)
    groups: list[FactGroup] = []
    position = 1
    for start, end in (*ranges, (count + 1, count)):
        while position < start:
            groups.append(FactGroup((candidates[position - 1],), str(position)))
            position += 1
        if start <= end:
            label = str(start) if start == end else f"{start}-{end}"
            groups.append(FactGroup(candidates[start - 1 : end], label))
            position = end + 1
    return tuple(groups)


def _finding(candidate: CandidateClaim, result: FactCheckResult, *, path: Optional[str] = None) -> models.Finding:
    """Build the finding for one reportable verdict (ADR 0007 Contract 9).

    Only the validated verdict, the ``.2f`` confidence, the validated backend name and the
    candidate text are used; ``result.citations`` never reaches a finding (threat model M11).

    :param candidate: The candidate that was sent (for a combined fact, one whose ``text`` is the
        combined text).
    :param result: The backend's validated result.
    :param path: The document to report on; ``candidate.claim.path`` when ``None``.
    :returns: The finding; the confidence is only in the report-only ``value``.
    """
    snippet = candidate.text[:_SNIPPET_CHARS]
    return models.Finding(
        rule=DS302.code,
        path=candidate.claim.path if path is None else path,
        message=f"external fact-check: '{snippet}' rated {result.verdict} by {result.backend} - review to confirm",
        severity=DS302.severity,
        value=f"{result.display} (confidence {result.confidence:.2f}): {candidate.text}",
        type=FINDING_TYPE,
    )


def _group_findings(group: FactGroup, result: FactCheckResult) -> list[models.Finding]:
    """Build the findings of one reportable fact: one per document the fact drew claims from.

    :param group: The fact that was sent.
    :param result: The backend's validated result.
    :returns: The findings, in the order of :attr:`FactGroup.paths`.
    """
    if len(group.members) == 1:
        return [_finding(group.members[0], result)]
    combined = replace(group.members[0], text=group.text)
    return [_finding(combined, result, path=path) for path in group.paths]


def _check_candidates(
    client: FactCheckClient,
    candidates: tuple[CandidateClaim, ...],
    config: Config,
    *,
    clock: Callable[[], float] = time.monotonic,
    fact_checks: Optional[list[models.FactCheck]] = None,
) -> tuple[models.Finding, ...]:
    """Send each fact to the backend, in order, within the time budget.

    The candidates are first grouped by ``config.fact_check_combination``
    (:func:`combine_candidates`; ``each``, the default, makes one fact per candidate). A combined
    fact longer than :data:`MAX_CANDIDATE_CHARS` is not sent (one WARNING; it is never truncated),
    and a reportable combined fact gives one finding per document it drew claims from. The counts
    in the INFO line are facts. A ``FactCheckError`` skips that fact with one WARNING naming the
    document only. Any other exception from ``check_claim`` stops the loop and is replaced by a
    type-name-only ``RuntimeError`` with no exception chain (threat model M5). Before sending, one
    INFO line names each selected claim (its first ten words and document), and one INFO line per
    checked fact names its verdict, confidence and whether it is reported (owner ruling of
    2026-11-27). One INFO line with counts only is logged from a ``finally`` block (threat model
    M10).

    :param client: The constructed backend client.
    :param candidates: The candidates, in send order.
    :param config: The effective configuration; the time budget, the confidence floor and the
        backend name are re-validated.
    :param clock: A monotonic clock; a test seam only.
    :param fact_checks: When given, one :class:`~docsentinel.models.FactCheck` is appended per
        checked fact, whatever its verdict.
    :returns: The findings, sorted by ``(path, message)``.
    :raises ConfigError: When a re-validated configuration value is invalid.
    :raises RuntimeError: When ``check_claim`` raises anything but ``FactCheckError``.
    """
    budget = int(validate_fact_check_option("fact_check_time_budget_seconds", config.fact_check_time_budget_seconds))
    min_confidence = validate_fact_check_option("fact_check_min_confidence", config.fact_check_min_confidence)
    backend = _validated_backend(config)
    groups = combine_candidates(candidates, config.fact_check_combination)
    total = len(groups)
    findings: list[models.Finding] = []
    sent = failed = not_sent = too_long = 0
    sent_paths: set[str] = set()
    per_document: dict[str, int] = {}
    escaped: Optional[str] = None
    if config.fact_check_combination != FACT_COMBINATION_EACH:
        logger.info(
            "DS302: fact combination %s: %d claim(s) grouped into %d fact(s)",
            safe(config.fact_check_combination, limit=80),
            len(candidates),
            total,
        )
    # The list of selected claims, in send order: the first words of each (owner ruling 2026-11-27).
    for number, candidate in enumerate(candidates, start=1):
        logger.info(
            "DS302: claim %d/%d %s in %s",
            number,
            len(candidates),
            quote_start(candidate.text),
            safe(candidate.claim.path),
        )
    try:
        deadline = clock() + budget if groups else 0.0
        for index, group in enumerate(groups):
            if clock() >= deadline:
                not_sent = total - index
                logger.warning(
                    "DS302: time budget of %d s exhausted; %d of %d claim(s) not checked", budget, not_sent, total
                )
                break
            text = group.text
            if len(text) > MAX_CANDIDATE_CHARS:
                too_long += 1
                logger.warning(
                    "DS302: combined fact %s is %d characters, over the %d-character limit; not sent",
                    group.label,
                    len(text),
                    MAX_CANDIDATE_CHARS,
                )
                continue
            path = group.members[0].claim.path
            sent += 1
            sent_paths.update(group.paths)
            for member_path in group.paths:
                per_document[member_path] = per_document.get(member_path, 0) + 1
            try:
                result = client.check_claim(text)
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
            reportable = result.verdict in REPORTABLE_VERDICTS and result.confidence >= min_confidence
            # One trace line per checked fact, with the first words of its text (owner ruling 2026-11-27).
            logger.info(
                "DS302: fact %d/%d (%s) %s in %s: verdict %s, confidence %.2f, %s",
                index + 1,
                len(groups),
                group.label,
                quote_start(text),
                safe(path),
                result.display,
                result.confidence,
                "reported" if reportable else "not reported",
            )
            if fact_checks is not None:
                fact_checks.append(
                    models.FactCheck(
                        path=path,
                        fact=text,
                        verdict=result.display,
                        confidence=result.confidence,
                        backend=result.backend,
                        reported=reportable,
                        claims=tuple(
                            models.FactCheckClaim(part.claim, part.label, part.confidence) for part in result.claims
                        ),
                    )
                )
            if reportable:
                findings.extend(_group_findings(group, result))
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
        if too_long:
            logger.info("DS302: %d combined fact(s) not sent: over %d characters", too_long, MAX_CANDIDATE_CHARS)
    findings.sort(key=lambda finding: (finding.path, finding.message))
    logger.debug("DS302: %d candidate(s), %d sent, %d failed, %d reported", total, sent, failed, len(findings))
    for path in sorted(per_document):
        logger.debug("DS302: %s: %d claim(s) sent", safe(path), per_document[path])
    return tuple(findings)


#: Largest facts file ``--include-facts`` reads, in bytes.
MAX_FACTS_FILE_BYTES: Final = 1_048_576

#: Most facts one facts file may hold.
MAX_FACTS_FILE_ENTRIES: Final = 500

#: The ``schema`` and ``schema_version`` of the ``facts-json`` output of ``extract-facts``.
FACTS_FILE_SCHEMA: Final = ("docsentinel-facts", 1)


@dataclass(frozen=True)
class FileClaim:
    """The origin of a fact read from a facts file: the two fields ``DS302`` uses of a claim.

    :ivar path: The document path the file names for the fact (untrusted).
    :ivar paragraph_index: The paragraph index the file names, ``0`` when absent.
    """

    path: str
    paragraph_index: int = 0


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object, refusing a duplicate key.

    :param pairs: The decoded key/value pairs of one object.
    :returns: The object.
    :raises ValueError: When a key occurs twice.
    """
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def load_facts_file(source: Union[Path, str]) -> tuple[CandidateClaim, ...]:
    """Read the facts ``DS302`` sends from a ``facts-json`` file (``scan --include-facts``).

    The file is the ``facts-json`` output of ``docsentinel extract-facts`` (schema
    ``docsentinel-facts`` 1), possibly edited by hand. Every listed fact is taken, in file order,
    whatever its ``disposition``: the file is the selection. Only ``text`` and ``path`` are
    required of an entry. The path is a trusted invoker path, relative to the current directory.

    :param source: The facts file.
    :returns: The candidates, in file order.
    :raises ConfigError: When the file cannot be read, is over :data:`MAX_FACTS_FILE_BYTES`, is
        not strict UTF-8 JSON of the expected schema, holds more than
        :data:`MAX_FACTS_FILE_ENTRIES` facts, or an entry has no usable ``text`` or ``path``.
    """
    shown = safe(source)
    try:
        with open(source, "rb") as stream:
            raw = stream.read(MAX_FACTS_FILE_BYTES + 1)
    except OSError as exc:
        raise ConfigError(f"facts file {shown}: cannot read it ({type(exc).__name__})") from None
    if len(raw) > MAX_FACTS_FILE_BYTES:
        raise ConfigError(f"facts file {shown}: larger than {MAX_FACTS_FILE_BYTES} bytes")
    try:
        payload = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_unique_json_object)
    except (ValueError, RecursionError):
        raise ConfigError(f"facts file {shown}: not valid UTF-8 JSON") from None
    if not isinstance(payload, dict) or (payload.get("schema"), payload.get("schema_version")) != FACTS_FILE_SCHEMA:
        raise ConfigError(
            f"facts file {shown}: not a facts-json file (schema {FACTS_FILE_SCHEMA[0]} {FACTS_FILE_SCHEMA[1]}); "
            "create one with docsentinel extract-facts --format facts-json"
        )
    entries = payload.get("facts")
    if not isinstance(entries, list):
        raise ConfigError(f"facts file {shown}: facts must be a list")
    if len(entries) > MAX_FACTS_FILE_ENTRIES:
        raise ConfigError(f"facts file {shown}: more than {MAX_FACTS_FILE_ENTRIES} facts")
    candidates: list[CandidateClaim] = []
    for number, entry in enumerate(entries, start=1):
        text = entry.get("text") if isinstance(entry, dict) else None
        path = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_CANDIDATE_CHARS:
            raise ConfigError(
                f"facts file {shown}: fact {number} needs a text of 1 to {MAX_CANDIDATE_CHARS} characters"
            )
        if not isinstance(path, str) or not path or len(path) > 1024:
            raise ConfigError(f"facts file {shown}: fact {number} needs a path")
        index = entry.get("paragraph_index")
        score = entry.get("score")
        candidates.append(
            CandidateClaim(
                claim=FileClaim(path, index if type(index) is int else 0),
                text=text.strip(),
                score=float(score) if type(score) in (int, float) and 0.0 <= score <= 1.0 else 0.0,
            )
        )
    return tuple(candidates)


def _construct_client(client_cls: type[FactCheckClient]) -> Optional[FactCheckClient]:
    """Construct the backend client with the key read inside the constructor call.

    :param client_cls: The verified backend class.
    :returns: The client, or ``None`` when the key variable is unset or empty now.
    """
    key = _read_api_key(client_cls.API_KEY_ENV_VAR)
    if not key:
        return None
    return client_cls(api_key=key)


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
    fact_checks: Optional[list[models.FactCheck]] = None,
    policy: SelectionPolicy = DS302_POLICY,
    facts: Optional[tuple[CandidateClaim, ...]] = None,
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
    :param fact_checks: A list the engine passes to collect one record per checked fact.
    :param policy: The claim-selection policy; :data:`DS302_POLICY` unless the invoker changed it.
    :param facts: Facts read from a facts file (``scan --include-facts``). When given, no document
        is read and no claim is extracted or selected: exactly these facts are sent, one request
        each, and ``policy`` and the selection and combination settings are ignored.
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
    parse_fact_combination(config.fact_check_combination)
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
        if facts is not None:
            candidates = facts
            config = replace(config, fact_check_combination=FACT_COMBINATION_EACH)
            logger.info("DS302: %d fact(s) taken from the facts file; no extraction or selection", len(facts))
        else:
            candidates = collect_candidates(root, documents, config, policy=validate_selection_policy(policy))
        findings = _check_candidates(client, candidates, config, fact_checks=fact_checks)
    finally:
        escaped = _close_client(client)
    if escaped is not None:
        raise RuntimeError(f"DS302: backend {backend} raised {escaped}")
    return findings


rules.ANALYZERS[DS302.code] = detect
