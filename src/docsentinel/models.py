"""Stable data contracts shared by the CLI and library."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Document:
    """Discovered documentation document metadata."""

    path: str
    bytes: int


@dataclass(frozen=True)
class Finding:
    """A single rule violation finding.

    The identity of a finding is ``rule``, ``path``, ``message``, ``severity`` and
    ``line``. The optional enrichment fields ``column``, ``value`` and ``type``
    (Milestone 0007) are report-only attributes: they are excluded from equality and
    hashing (``compare=False``) and from baseline fingerprints, so a detector that
    starts populating them never changes ``Finding``/``ScanResult`` equality or a
    recorded baseline.

    :ivar rule: The producing rule code, for example ``DS101``.
    :ivar path: The document path relative to the scan root.
    :ivar message: The full detector message.
    :ivar severity: ``error`` or ``warning``.
    :ivar line: 1-based source line, or ``None`` when not located.
    :ivar column: 1-based column (in code points) of the offending token on
        ``line``, or ``None`` when the detector does not extract it.
    :ivar value: The offending token the detector already echoes in ``message``
        (a link target, a path), never a surrounding snippet; ``None`` when not
        extracted. Untrusted: it originates in scanned content.
    :ivar type: Short finding category such as ``dangling link``; ``None`` when the
        detector gives none (the report model then derives it from the rule title).
    """

    rule: str
    path: str
    message: str
    severity: str = "warning"
    line: Optional[int] = None
    column: Optional[int] = field(default=None, compare=False)
    value: Optional[str] = field(default=None, compare=False)
    type: Optional[str] = field(default=None, compare=False)


@dataclass(frozen=True, kw_only=True)
class ScanResult:
    """The result of a documentation scan.

    :ivar rules_evaluated: Number of active rules that genuinely evaluated (an
        active opt-in rule whose policy is off is not counted). ``0`` when no rule
        ran. ``notice`` is built from this value.
    :ivar opt_in_off: ``(code, option)`` pairs, in rule-code order, for active
        opt-in policy rules whose enabling option is not set. ``notice`` is built
        from this value.
    """

    schema_version: int = 1
    profile: str
    documents: tuple[Document, ...]
    findings: tuple[Finding, ...]
    enabled_rules: tuple[str, ...]
    pending: tuple[str, ...]
    notice: str = "Detection rules are not implemented in M0; this is an inventory only."
    rules_evaluated: int = 0
    opt_in_off: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ExtractedFact:
    """One claim listed by ``extract_facts`` (Milestone 0010 Story 05.0).

    :ivar rank: 1-based position in the listed order.
    :ivar path: The document path relative to the scan root (untrusted).
    :ivar paragraph_index: The claim's 0-based paragraph split index (no line number).
    :ivar text: The text ``DS302`` would send: the stripped sentence, bounded (untrusted).
    :ivar score: The combined salience score, in ``[0, 1]``.
    :ivar numeric: The numeric density signal, in ``[0, 1]``.
    :ivar entity: The entity density signal, in ``[0, 1]``.
    :ivar distinctiveness: The corpus distinctiveness signal, in ``[0, 1]``.
    :ivar cluster_id: The near-duplicate cluster id.
    :ivar cluster_size: The number of canonical claims in that cluster, ``>= 1``.
    :ivar numbers: The numbers in the claim's object (untrusted).
    :ivar entities: The named entities in the claim's object, as ``LABEL:text`` (untrusted).
    :ivar disposition: ``selected``, or with ``include_rejected`` why the claim was dropped
        (``duplicate``, ``below_floor``, ``document_cap``, ``total_cap``).
    """

    rank: int
    path: str
    paragraph_index: int
    text: str
    score: float
    numeric: float
    entity: float
    distinctiveness: float
    cluster_id: int
    cluster_size: int
    numbers: tuple[str, ...]
    entities: tuple[str, ...]
    disposition: str


@dataclass(frozen=True)
class FactSettings:
    """The effective selection settings of one ``extract_facts`` run.

    :ivar min_salience: The inclusive salience floor.
    :ivar max_per_document: The most facts selected per document.
    :ivar max_total: The most facts selected overall.
    :ivar weights: The ``(numeric, entity, distinctiveness)`` salience weights.
    :ivar dedup_threshold: The near-duplicate clustering threshold.
    """

    min_salience: float
    max_per_document: int
    max_total: int
    weights: tuple[float, float, float]
    dedup_threshold: float


@dataclass(frozen=True)
class FactExtractionResult:
    """The result of an offline ``extract_facts`` run (no gate, no network, no backend).

    :ivar documents: The discovered inventory, as in ``ScanResult``.
    :ivar documents_unreadable: The discovered documents skipped as unreadable.
    :ivar claims_extracted: The number of claims extracted before selection.
    :ivar facts: The selected facts, or every claim with ``include_rejected``, in listed order.
    :ivar settings: The effective selection settings.
    :ivar matches_ds302: Whether the selected subset is the set ``DS302`` would send for the
        effective configuration (no override or exploration setting differs).
    :ivar include_rejected: Whether rejected claims are listed too.
    :ivar notice: A fixed heuristic/offline notice built from engine constants (trusted).
    """

    documents: tuple[Document, ...]
    documents_unreadable: int
    claims_extracted: int
    facts: tuple[ExtractedFact, ...]
    settings: FactSettings
    matches_ds302: bool
    include_rejected: bool
    notice: str

    @property
    def selected(self) -> tuple[ExtractedFact, ...]:
        """The selected facts in rank order.

        The facts whose disposition is ``selected``.
        """
        return tuple(fact for fact in self.facts if fact.disposition == "selected")
