"""Tests for DS203 low-information content detector."""

import math
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import scipy.sparse as sp

pytest.importorskip("sklearn")

from docsentinel import models
from docsentinel.detectors.standard import corpus, low_information
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

_PARA_B = (
    "Python packaging uses pyproject configuration tables to manage project metadata and build dependencies. "
    "Standardized tool sections allow linters and formatters to share configuration parameters cleanly. "
    "Virtual environments isolate installation artifacts to prevent dependency conflicts across projects."
)

_FILLER_PARA = (
    "This is because there is and it was as it has been there before. "
    "This is because there is and it was as it has been there before. "
    "This is because there is and it was as it has been there before. "
    "This is because there is and it was as it has been there before."
)

_KEYWORD_PARA = (
    "Kubernetes Terraform OpenTelemetry Elasticsearch "
    "Kubernetes Terraform OpenTelemetry Elasticsearch "
    "Kubernetes Terraform OpenTelemetry Elasticsearch."
)


def test_rule_metadata() -> None:
    assert low_information.DS203.code == "DS203"
    assert low_information.DS203.profile == "standard"
    assert low_information.DS203.title == "Low-information content"
    assert low_information.DS203.description == "A paragraph is both lexically thin and non-distinctive."
    assert low_information.DS203.severity == "warning"


def test_type_token_ratio() -> None:
    assert low_information.type_token_ratio("") == 0.0
    assert low_information.type_token_ratio("   ") == 0.0
    assert low_information.type_token_ratio("word word word") == pytest.approx(1 / 3)
    assert low_information.type_token_ratio("Word word WORD") == pytest.approx(1 / 3)
    assert low_information.type_token_ratio("one two three") == pytest.approx(1.0)


def test_information_score_is_geometric_mean() -> None:
    # Zero in either signal produces zero
    assert low_information.information_score(0.0, 0.9) == 0.0
    assert low_information.information_score(0.5, 0.0) == 0.0
    assert low_information.information_score(0.0, 0.0) == 0.0
    assert low_information.information_score(-0.1, 0.5) == 0.0
    assert low_information.information_score(0.5, -0.1) == 0.0

    # Reference values scale to 1.0
    assert low_information.information_score(0.5, 0.3) == pytest.approx(1.0)
    assert low_information.information_score(1.0, 1.0) == pytest.approx(1.0)

    # Intermediate value matches sqrt of normalized product
    expected = math.sqrt((0.25 / 0.5) * (0.15 / 0.3))
    assert low_information.information_score(0.25, 0.15) == pytest.approx(expected)

    # Monotonic in TTR
    assert low_information.information_score(0.1, 0.2) < low_information.information_score(0.2, 0.2)
    assert low_information.information_score(0.2, 0.2) < low_information.information_score(0.4, 0.2)

    # Monotonic in max TF-IDF
    assert low_information.information_score(0.3, 0.05) < low_information.information_score(0.3, 0.15)
    assert low_information.information_score(0.3, 0.15) < low_information.information_score(0.3, 0.25)


def test_filler_paragraph_is_flagged(tmp_path: Path) -> None:
    doc_a = _create_doc(tmp_path, "a.md", _PARA_A)
    doc_b = _create_doc(tmp_path, "b.md", _PARA_B)
    doc_filler = _create_doc(tmp_path, "filler.md", _FILLER_PARA)

    findings = low_information.detect(tmp_path, (doc_a, doc_b, doc_filler))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS203"
    assert finding.path == "filler.md"
    assert finding.severity == "warning"
    assert finding.line == 1
    assert "low-information paragraph (score 0.00 < 0.15)" in finding.message


def test_informative_paragraph_is_clean(tmp_path: Path) -> None:
    doc_a = _create_doc(tmp_path, "a.md", _PARA_A)
    doc_b = _create_doc(tmp_path, "b.md", _PARA_B)

    findings = low_information.detect(tmp_path, (doc_a, doc_b))
    assert findings == ()


def test_keyword_list_not_flagged_despite_low_ttr(tmp_path: Path) -> None:
    doc_a = _create_doc(tmp_path, "a.md", _PARA_A)
    doc_b = _create_doc(tmp_path, "b.md", _PARA_B)
    doc_keywords = _create_doc(tmp_path, "keywords.md", _KEYWORD_PARA)

    findings = low_information.detect(tmp_path, (doc_a, doc_b, doc_keywords))
    assert findings == ()


def test_threshold_is_configurable(tmp_path: Path) -> None:
    doc_a = _create_doc(tmp_path, "a.md", _PARA_A)
    doc_b = _create_doc(tmp_path, "b.md", _PARA_B)

    # 16 distinct terms repeated 12 times: TTR = 16/192 = 0.083, max_tfidf = 1/sqrt(16) = 0.25
    # norm_ttr = 0.083/0.5 = 0.167, norm_dist = 0.25/0.3 = 0.833 -> score ≈ 0.37
    words = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi"
    borderline_text = " ".join([words] * 12)
    doc_borderline = _create_doc(tmp_path, "borderline.md", borderline_text)

    # With higher threshold (0.40), borderline paragraph is flagged
    config_file = tmp_path / "doc_sentinel.toml"
    config_file.write_text("min_information_score = 0.40\n", encoding="utf-8")
    findings_strict = low_information.detect(tmp_path, (doc_a, doc_b, doc_borderline))
    assert len(findings_strict) == 1
    assert findings_strict[0].path == "borderline.md"

    # With very low threshold (0.01), it is not flagged
    config_file.write_text("min_information_score = 0.01\n", encoding="utf-8")
    findings_loose = low_information.detect(tmp_path, (doc_a, doc_b, doc_borderline))
    assert findings_loose == ()


def test_reuses_corpus_model_without_refitting() -> None:
    mock_vectorizer = MagicMock()
    matrix = sp.csr_matrix(np.array([[0.5, 0.0], [0.0, 0.5]]))
    paragraphs = (
        Paragraph(doc_path="doc1.md", index=0, text="First text with enough words", line=1),
        Paragraph(doc_path="doc2.md", index=0, text="Second text with enough words", line=1),
    )
    model = CorpusModel(
        documents=(),
        paragraphs=paragraphs,
        tfidf_matrix=matrix,
        vectorizer=mock_vectorizer,
    )

    result = low_information.low_information_chunks(model, threshold=0.15)
    assert result == ()
    mock_vectorizer.fit.assert_not_called()
    mock_vectorizer.fit_transform.assert_not_called()


def test_empty_and_single_chunk_corpus_produce_no_findings(tmp_path: Path) -> None:
    # Empty documents tuple
    assert low_information.detect(tmp_path, ()) == ()

    # Single document with one informative chunk
    doc = _create_doc(tmp_path, "single.md", _PARA_A)
    assert low_information.detect(tmp_path, (doc,)) == ()

    # Non-markdown document
    doc_txt = _create_doc(tmp_path, "notes.txt", _PARA_A)
    assert low_information.detect(tmp_path, (doc_txt,)) == ()
