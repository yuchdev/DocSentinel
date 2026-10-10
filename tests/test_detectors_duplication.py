"""Tests for DS202 duplicate text detector."""

from pathlib import Path

import numpy as np
import pytest
import scipy.sparse as sp

pytest.importorskip("sklearn")

from docsentinel import models
from docsentinel.detectors.standard import corpus, duplication
from docsentinel.detectors.standard.corpus import CorpusModel, Paragraph


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    corpus.clear_corpus_cache()


def _create_doc(tmp_path: Path, relative_path: str, content: str) -> models.Document:
    full_path = tmp_path / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return models.Document(path=relative_path, bytes=len(content.encode("utf-8")))


_PARA_A = (
    "DocSentinel provides deterministic documentation analysis and link validation. "
    "It scans markdown files across the entire workspace to identify broken references and formatting errors. "
    "Every finding contains precise file path and line number provenance for automated remediation."
)

_PARA_A_NEAR = (
    "DocSentinel provides deterministic documentation analysis and link validation. "
    "It scans markdown files across the entire workspace to identify broken references and formatting issues. "
    "Every finding contains precise file path and line provenance for automated remediation."
)

_PARA_DISTINCT = (
    "Python packaging uses pyproject configuration tables to manage project metadata and build dependencies. "
    "Standardized tool sections allow linters and formatters to share configuration parameters cleanly. "
    "Virtual environments isolate installation artifacts to prevent dependency conflicts across projects."
)


def test_rule_metadata() -> None:
    assert duplication.DS202.code == "DS202"
    assert duplication.DS202.profile == "standard"
    assert duplication.DS202.title == "Duplicated text or facts"
    assert duplication.DS202.severity == "warning"


def test_identical_paragraphs_in_two_docs_are_flagged(tmp_path: Path) -> None:
    doc_a = _create_doc(tmp_path, "a.md", _PARA_A)
    doc_b = _create_doc(tmp_path, "b.md", _PARA_A)

    findings = duplication.detect(tmp_path, (doc_a, doc_b))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS202"
    assert finding.path == "b.md"
    assert finding.severity == "warning"
    assert finding.line == 1
    assert "near-duplicate of a.md#chunk0 (cosine 1.00)" in finding.message


def test_near_duplicate_above_threshold_is_flagged(tmp_path: Path) -> None:
    doc_a = _create_doc(tmp_path, "a.md", _PARA_A)
    doc_b = _create_doc(tmp_path, "b.md", _PARA_A_NEAR)

    findings = duplication.detect(tmp_path, (doc_a, doc_b))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS202"
    assert finding.path == "b.md"
    assert "near-duplicate of a.md#chunk0" in finding.message


def test_distinct_paragraphs_below_threshold_are_clean(tmp_path: Path) -> None:
    doc_a = _create_doc(tmp_path, "a.md", _PARA_A)
    doc_b = _create_doc(tmp_path, "b.md", _PARA_DISTINCT)

    findings = duplication.detect(tmp_path, (doc_a, doc_b))
    assert findings == ()


def test_within_document_duplication_is_flagged(tmp_path: Path) -> None:
    content = f"# Section 1\n\n{_PARA_A}\n\n# Section 2\n\n{_PARA_A_NEAR}\n"
    doc = _create_doc(tmp_path, "single.md", content)

    findings = duplication.detect(tmp_path, (doc,))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS202"
    assert finding.path == "single.md"
    assert finding.line == 7
    assert "near-duplicate of single.md#chunk0" in finding.message


def test_threshold_is_configurable(tmp_path: Path) -> None:
    doc_a = _create_doc(tmp_path, "a.md", _PARA_A)
    doc_b = _create_doc(tmp_path, "b.md", _PARA_A_NEAR)

    # With high threshold (0.99), near-duplicate is not flagged
    config_file = tmp_path / "doc_sentinel.toml"
    config_file.write_text("duplicate_similarity = 0.99\n", encoding="utf-8")
    findings_strict = duplication.detect(tmp_path, (doc_a, doc_b))
    assert findings_strict == ()

    # With lower threshold (0.50), it is flagged
    config_file.write_text("duplicate_similarity = 0.50\n", encoding="utf-8")
    findings_loose = duplication.detect(tmp_path, (doc_a, doc_b))
    assert len(findings_loose) == 1


def test_pair_reported_once_not_twice(tmp_path: Path) -> None:
    doc_a = _create_doc(tmp_path, "a.md", _PARA_A)
    doc_b = _create_doc(tmp_path, "b.md", _PARA_A)
    doc_c = _create_doc(tmp_path, "c.md", _PARA_A)

    findings = duplication.detect(tmp_path, (doc_a, doc_b, doc_c))
    # 3 combinations: (a, b), (a, c), (b, c) -> 3 findings, not 6
    assert len(findings) == 3
    assert tuple((f.path, f.message[:25]) for f in findings) == (
        ("b.md", "near-duplicate of a.md#ch"),
        ("c.md", "near-duplicate of a.md#ch"),
        ("c.md", "near-duplicate of b.md#ch"),
    )


def test_empty_and_single_chunk_corpus_produce_no_findings(tmp_path: Path) -> None:
    # Empty documents tuple
    assert duplication.detect(tmp_path, ()) == ()

    # Single document with one chunk
    doc = _create_doc(tmp_path, "single.md", _PARA_A)
    assert duplication.detect(tmp_path, (doc,)) == ()

    # Non-markdown document
    doc_txt = _create_doc(tmp_path, "notes.txt", _PARA_A)
    assert duplication.detect(tmp_path, (doc_txt,)) == ()


def test_duplicate_pairs_is_pure() -> None:
    # Hand-built CorpusModel with normalized TF-IDF rows
    # Vector 0: [1, 0]
    # Vector 1: [1, 0] (identical to 0 -> sim = 1.0)
    # Vector 2: [0, 1] (orthogonal -> sim = 0.0)
    matrix = sp.csr_matrix(np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]))
    paragraphs = (
        Paragraph(doc_path="doc1.md", index=0, text="First text", line=1),
        Paragraph(doc_path="doc2.md", index=0, text="Second text", line=1),
        Paragraph(doc_path="doc3.md", index=0, text="Third text", line=1),
    )
    model = CorpusModel(
        documents=(),
        paragraphs=paragraphs,
        tfidf_matrix=matrix,
        vectorizer=None,
    )

    pairs = duplication.duplicate_pairs(model, threshold=0.85)
    assert len(pairs) == 1
    assert pairs[0][0] == 0
    assert pairs[0][1] == 1
    assert abs(pairs[0][2] - 1.0) < 1e-6

    # Lower threshold to 0.0 includes all pairs
    pairs_all = duplication.duplicate_pairs(model, threshold=0.0)
    assert len(pairs_all) == 3

    # Empty model returns ()
    empty_model = CorpusModel(
        documents=(),
        paragraphs=(),
        tfidf_matrix=sp.csr_matrix((0, 0)),
        vectorizer=None,
    )
    assert duplication.duplicate_pairs(empty_model, threshold=0.85) == ()
