"""Detect duplicated or near-duplicated paragraphs across the documentation corpus.

DS202 flags pairs of paragraphs whose TF-IDF cosine similarity meets or exceeds the
configured `duplicate_similarity` threshold (default 0.85). Each pair is reported once,
attributed to the later paragraph and referencing the earlier one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sklearn.metrics.pairwise import cosine_similarity

from docsentinel import models, rules
from docsentinel.config import Config, load_config
from docsentinel.detectors.standard.corpus import CorpusModel, build_corpus_model

DS202 = rules.register_rule(
    rules.Rule(
        code="DS202",
        profile="standard",
        title="Duplicated text or facts",
        description="A paragraph is a near-duplicate of another paragraph in the corpus.",
        severity="warning",
    )
)


def duplicate_pairs(
    model: CorpusModel,
    threshold: float,
) -> tuple[tuple[int, int, float], ...]:
    """Find pairs of paragraphs with cosine similarity at or above threshold.

    Returns sorted (i, j, similarity) for every pair i < j with similarity >= threshold.
    For an empty or single-paragraph model, returns an empty tuple.
    """
    chunks = model.paragraphs
    if len(chunks) < 2 or model.tfidf_matrix.shape[0] < 2:
        return ()

    if model.tfidf_matrix.shape[1] == 0:
        return ()

    sim_matrix = cosine_similarity(model.tfidf_matrix)
    pairs: list[tuple[int, int, float]] = []

    for i in range(len(chunks)):
        for j in range(i + 1, len(chunks)):
            sim = float(sim_matrix[i, j])
            if sim >= threshold:
                pairs.append((i, j, sim))

    pairs.sort(key=lambda item: (item[0], item[1]))
    return tuple(pairs)


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Config | None = None,
) -> tuple[models.Finding, ...]:
    """Return DS202 findings for near-duplicate paragraph chunks across documents."""
    config = config or load_config(root)
    model = build_corpus_model(root, documents)
    pairs = duplicate_pairs(model, config.duplicate_similarity)
    findings: list[models.Finding] = []
    chunks = model.paragraphs

    for i, j, sim in pairs:
        earlier = chunks[i]
        later = chunks[j]
        line_num: Optional[int] = later.line
        findings.append(
            models.Finding(
                rule=DS202.code,
                path=later.doc_path,
                message=(
                    f"near-duplicate of {earlier.doc_path}#chunk{earlier.index} (cosine {sim:.2f}): '{later.preview}'"
                ),
                severity=DS202.severity,
                line=line_num,
            )
        )

    return tuple(findings)


rules.ANALYZERS[DS202.code] = detect
