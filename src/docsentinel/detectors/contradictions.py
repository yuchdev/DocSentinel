"""Detect candidate fact contradictions across documentation files.

Known limitations:
- False positives: SVO extraction may mis-parse; the same subject string can name
  different things across documents; numbers in different units look contradictory;
  valid version-specific or context-specific statements look contradictory.
  DS301 is a candidate generator feeding docs-reviewer triage, not ground truth.
- False negatives: Paraphrase, pronoun or cross-sentence subjects, claims without
  an extractable SVO triple, and disagreements in free prose without numbers or entities
  will not be flagged.
- Model determinism: Output is stable only for the pinned en_core_web_sm version;
  a model upgrade may add, remove, or change candidate findings.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from docsentinel import deep_support, models, rules

if TYPE_CHECKING:
    from docsentinel.detectors._triples import Claim

DS301 = rules.register_rule(
    rules.Rule(
        code="DS301",
        profile="deep",
        title="Fact-contradiction candidate",
        description="Two documents make differing numeric or named-entity claims about the same subject.",
        severity="warning",
    )
)


def _disagree(a: Claim, b: Claim) -> bool:
    """Return True if two claims from different documents make conflicting statements."""
    if a.path == b.path:
        return False

    if a.object_numbers and b.object_numbers and not set(a.object_numbers).intersection(set(b.object_numbers)):
        return True

    if a.object_entities and b.object_entities and not set(a.object_entities).intersection(set(b.object_entities)):
        return True

    return False


def _candidate_findings(claims: tuple[Claim, ...]) -> tuple[models.Finding, ...]:
    """Compare claims across documents and return deduplicated, sorted candidate findings."""
    groups: dict[tuple[str, str], list[Claim]] = {}
    for claim in claims:
        if not claim.subject_key or not claim.predicate_key:
            continue
        key = (claim.subject_key, claim.predicate_key)
        groups.setdefault(key, []).append(claim)

    seen: set[tuple[str, str, str, str, str, str]] = set()
    findings: list[models.Finding] = []

    for (subj_key, pred_key), group in groups.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                claim_a = group[i]
                claim_b = group[j]
                if _disagree(claim_a, claim_b):
                    if claim_a.path > claim_b.path:
                        greater, lesser = claim_a, claim_b
                    else:
                        greater, lesser = claim_b, claim_a

                    dedup_key = (
                        subj_key,
                        pred_key,
                        lesser.path,
                        greater.path,
                        lesser.raw_object,
                        greater.raw_object,
                    )
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    message = (
                        f"candidate contradiction: subject '{greater.raw_subject}' "
                        f"claimed as '{lesser.raw_object}' in {lesser.path} "
                        f"but '{greater.raw_object}' in {greater.path} - review to confirm"
                    )
                    findings.append(
                        models.Finding(
                            rule=DS301.code,
                            path=greater.path,
                            message=message,
                            severity=DS301.severity,
                        )
                    )

    findings.sort(key=lambda f: (f.path, f.message))
    return tuple(findings)


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
) -> tuple[models.Finding, ...]:
    """Extract claims and detect contradiction candidates across documents.

    The spaCy-backed triple extractor is imported lazily here (first deep scan) via
    :func:`importlib.import_module` so that importing :mod:`docsentinel` -- and every
    fast or standard scan -- never pulls in spaCy/textacy. The DS301 rule metadata and
    this analyzer are still registered eagerly at import time, so ``docsentinel rules``,
    ``doctor``, ``enabled_rules`` and rule selection are unchanged.
    """
    extract_claims = importlib.import_module("docsentinel.detectors._triples").extract_claims
    pipeline = deep_support.load_pipeline()
    all_claims: list[Claim] = []

    for doc in documents:
        if not doc.path.endswith(".md"):
            continue
        target = root / doc.path
        with target.open("r", encoding="utf-8") as stream:
            text = stream.read()
        claims = extract_claims(pipeline, text, doc.path)
        all_claims.extend(claims)

    return _candidate_findings(tuple(all_claims))


rules.ANALYZERS[DS301.code] = detect
