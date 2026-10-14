"""Detect low-information content paragraphs across the documentation corpus.

DS203 flags paragraphs that are both lexically thin (low type-token ratio) and
non-distinctive (low maximum TF-IDF weight). Both signals are combined via their
geometric mean into an information score in [0, 1]. Paragraphs scoring below
the configured `min_information_score` (default 0.15) are reported.

Tokenization consistency:
The type-token ratio is computed using the same word token pattern as the shared
corpus vectorizer (?u)\\b\\w+\\b to ensure that TTR and TF-IDF describe the same tokens.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Optional

import numpy as np
import scipy.sparse as sp

from docsentinel import models, rules
from docsentinel.config import Config, load_config
from docsentinel.detectors.standard.corpus import CorpusModel, build_corpus_model

DS203 = rules.register_rule(
    rules.Rule(
        code="DS203",
        profile="standard",
        title="Low-information content",
        description="A paragraph is both lexically thin and non-distinctive.",
        severity="warning",
    )
)

_TTR_REF: float = 0.5
_TFIDF_REF: float = 0.3
_WORD_PATTERN = re.compile(r"(?u)\b\w+\b")


def type_token_ratio(text: str) -> float:
    """Calculate the type-token ratio (distinct words / total words) of a text.

    Uses the same regex tokenizer as the corpus vectorizer on lowercased text.
    Returns 0.0 for empty text.
    """
    tokens = _WORD_PATTERN.findall(text.lower())
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)


def information_score(ttr: float, max_tfidf: float) -> float:
    """Calculate the combined information score as the geometric mean of normalized signals.

    norm_ttr = min(ttr / _TTR_REF, 1.0)
    norm_distinctiveness = min(max_tfidf / _TFIDF_REF, 1.0)
    score = sqrt(norm_ttr * norm_distinctiveness)
    """
    if ttr <= 0.0 or max_tfidf <= 0.0:
        return 0.0
    norm_ttr = min(ttr / _TTR_REF, 1.0)
    norm_distinctiveness = min(max_tfidf / _TFIDF_REF, 1.0)
    return math.sqrt(norm_ttr * norm_distinctiveness)


def low_information_chunks(
    model: CorpusModel,
    threshold: float,
) -> tuple[tuple[int, float], ...]:
    """Find paragraph chunks with an information score strictly below threshold.

    Returns sorted (chunk_index, score) pairs.
    """
    chunks = model.paragraphs
    if not chunks:
        return ()

    matrix = model.tfidf_matrix
    results: list[tuple[int, float]] = []

    for i, chunk in enumerate(chunks):
        max_tfidf = 0.0
        if matrix is not None and hasattr(matrix, "shape") and matrix.shape[0] > i and matrix.shape[1] > 0:
            if sp.issparse(matrix):
                row = matrix.getrow(i)
                if row.data.size > 0:
                    max_tfidf = float(row.data.max())
            elif isinstance(matrix, np.ndarray):
                row = matrix[i]
                if row.size > 0:
                    max_tfidf = float(np.max(row))

        ttr = type_token_ratio(chunk.text)
        score = information_score(ttr, max_tfidf)
        if score < threshold:
            results.append((i, score))

    results.sort(key=lambda item: item[0])
    return tuple(results)


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Config | None = None,
) -> tuple[models.Finding, ...]:
    """Return DS203 findings for low-information paragraphs across documents."""
    config = config or load_config(root)
    model = build_corpus_model(root, documents)
    flagged = low_information_chunks(model, config.min_information_score)
    findings: list[models.Finding] = []
    chunks = model.paragraphs

    for i, score in flagged:
        chunk = chunks[i]
        line_num: Optional[int] = chunk.line
        findings.append(
            models.Finding(
                rule=DS203.code,
                path=chunk.doc_path,
                message=(
                    f"low-information paragraph (score {score:.2f} < {config.min_information_score:.2f}): '{chunk.preview}'"
                ),
                severity=DS203.severity,
                line=line_num,
            )
        )

    return tuple(findings)


rules.ANALYZERS[DS203.code] = detect
