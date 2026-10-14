"""Unit tests for DS202 function logic: rule metadata and similarity pair selection.

Detection over documents is covered by ``tests/integration/test_detectors_duplication_ds202.py``.
"""

import pytest

pytest.importorskip("sklearn")

import numpy as np
import scipy.sparse as sp

from docsentinel.detectors.standard import duplication
from docsentinel.detectors.standard.corpus import CorpusModel, Paragraph


def test_rule_metadata():
    """
    [Unit] detectors duplication: verifies rule metadata.

    Scenario:
        Given test inputs and fixtures for rule metadata
        When test_rule_metadata executes the target flow
        Then the expected outcome for rule metadata is confirmed.

    Boundaries:
        - Focus: rule metadata
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to rule metadata
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors duplication
    """
    assert duplication.DS202.code == "DS202"
    assert duplication.DS202.profile == "standard"
    assert duplication.DS202.title == "Duplicated text or facts"
    assert duplication.DS202.severity == "warning"


def test_duplicate_pairs_is_pure():
    # Hand-built CorpusModel with normalized TF-IDF rows
    # Vector 0: [1, 0]
    # Vector 1: [1, 0] (identical to 0 -> sim = 1.0)
    # Vector 2: [0, 1] (orthogonal -> sim = 0.0)
    """
    [Unit] detectors duplication: verifies duplicate pairs is pure.

    Scenario:
        Given test inputs and fixtures for duplicate pairs is pure
        When test_duplicate_pairs_is_pure executes the target flow
        Then the expected outcome for duplicate pairs is pure is confirmed.

    Boundaries:
        - Focus: duplicate pairs is pure
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to duplicate pairs is pure
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors duplication
    """
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
