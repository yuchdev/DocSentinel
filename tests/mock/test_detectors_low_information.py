"""Mock tests for DS203 where the fitted vectorizer is replaced by a ``MagicMock``."""

from unittest.mock import MagicMock

import pytest

pytest.importorskip("sklearn")

import numpy as np
import scipy.sparse as sp

from docsentinel.detectors.standard import low_information
from docsentinel.detectors.standard.corpus import CorpusModel, Paragraph


def test_reuses_corpus_model_without_refitting():
    """
    [Unit] detectors low information: verifies reuses corpus model without refitting.

    Scenario:
        Given test inputs and fixtures for reuses corpus model without refitting
        When test_reuses_corpus_model_without_refitting executes the target flow
        Then the expected outcome for reuses corpus model without refitting is confirmed.

    Boundaries:
        - Focus: reuses corpus model without refitting
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to reuses corpus model without refitting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors low information
    """
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
