"""Integration tests for the shared corpus model (substrate of DS202/DS203) over ``tests/assets/ds202`` cases.

The corpus cases are filed under ``ds202`` because duplicate-text detection is the model's primary consumer;
DS203 reuses the same fitted model.
"""

from collections.abc import Callable
from unittest.mock import patch

import pytest

pytest.importorskip("sklearn")

from docsentinel.detectors.standard import corpus
from tests.asset_helpers import AssetCase


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear corpus caches automatically before each test execution."""
    corpus.clear_corpus_cache()


def test_build_corpus_model_single_document(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] corpus model ds202: verifies build corpus model single document.

    Scenario:
        Given test inputs and fixtures for build corpus model single document
        When test_build_corpus_model_single_document executes the target flow
        Then the expected outcome for build corpus model single document is confirmed.

    Boundaries:
        - Focus: build corpus model single document
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to build corpus model single document
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by corpus model ds202
    """
    case = asset_case("ds202", "corpus_single_document")

    model = corpus.build_corpus_model(case.root, case.documents("overview.md"))

    assert len(model.documents) == 1
    assert len(model.paragraphs) == 2
    assert model.tfidf_matrix.shape[0] == 2
    assert model.tfidf_matrix.shape[1] > 0
    assert len(model.vocabulary) > 0
    assert model.idf is not None
    assert len(model.idf) == model.tfidf_matrix.shape[1]


def test_build_corpus_model_multi_document_matrix_shape(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] corpus model ds202: verifies build corpus model multi document matrix shape.

    Scenario:
        Given test inputs and fixtures for build corpus model multi document matrix shape
        When test_build_corpus_model_multi_document_matrix_shape executes the target flow
        Then the expected outcome for build corpus model multi document matrix shape is confirmed.

    Boundaries:
        - Focus: build corpus model multi document matrix shape
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to build corpus model multi document matrix shape
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by corpus model ds202
    """
    case = asset_case("ds202", "corpus_multi_document")

    model = corpus.build_corpus_model(case.root, case.documents("arch.md", "config.md"))

    assert len(model.documents) == 2
    assert len(model.paragraphs) == 2
    assert model.tfidf_matrix.shape[0] == 2
    assert model.paragraphs[0].doc_path == "arch.md"
    assert model.paragraphs[1].doc_path == "config.md"


def test_build_corpus_model_deterministic(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] corpus model ds202: verifies build corpus model deterministic.

    Scenario:
        Given test inputs and fixtures for build corpus model deterministic
        When test_build_corpus_model_deterministic executes the target flow
        Then the expected outcome for build corpus model deterministic is confirmed.

    Boundaries:
        - Focus: build corpus model deterministic
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to build corpus model deterministic
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by corpus model ds202
    """
    case = asset_case("ds202", "corpus_deterministic")
    doc1 = case.document("a.md")
    doc2 = case.document("b.md")

    corpus.build_corpus_model.cache_clear()
    model1 = corpus.build_corpus_model(case.root, (doc2, doc1))
    corpus.build_corpus_model.cache_clear()
    model2 = corpus.build_corpus_model(case.root, (doc1, doc2))

    assert [p.doc_path for p in model1.paragraphs] == [p.doc_path for p in model2.paragraphs]
    assert [p.text for p in model1.paragraphs] == [p.text for p in model2.paragraphs]
    assert model1.vocabulary == model2.vocabulary
    assert (model1.tfidf_matrix.toarray() == model2.tfidf_matrix.toarray()).all()


def test_build_corpus_model_fits_once(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] corpus model ds202: verifies build corpus model fits once.

    Scenario:
        Given test inputs and fixtures for build corpus model fits once
        When test_build_corpus_model_fits_once executes the target flow
        Then the expected outcome for build corpus model fits once is confirmed.

    Boundaries:
        - Focus: build corpus model fits once
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to build corpus model fits once
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by corpus model ds202
    """
    case = asset_case("ds202", "corpus_fits_once")
    document = case.document("doc.md")

    corpus.build_corpus_model.cache_clear()
    with patch.object(
        corpus.TfidfVectorizer, "fit_transform", autospec=True, side_effect=corpus.TfidfVectorizer.fit_transform
    ) as mock_fit:
        model = corpus.build_corpus_model(case.root, (document,))
        assert mock_fit.call_count == 1
        assert model.tfidf_matrix.shape[0] == 1


def test_build_corpus_model_is_cached_for_identical_inputs(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] corpus model ds202: verifies build corpus model is cached for identical inputs.

    Scenario:
        Given test inputs and fixtures for build corpus model is cached for identical inputs
        When test_build_corpus_model_is_cached_for_identical_inputs executes the target flow
        Then the expected outcome for build corpus model is cached for identical inputs is confirmed.

    Boundaries:
        - Focus: build corpus model is cached for identical inputs
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to build corpus model is cached for identical inputs
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by corpus model ds202
    """
    case = asset_case("ds202", "corpus_cached_for_identical_inputs")
    document = case.document("doc.md")

    corpus.build_corpus_model.cache_clear()
    with patch.object(
        corpus.TfidfVectorizer, "fit_transform", autospec=True, side_effect=corpus.TfidfVectorizer.fit_transform
    ) as mock_fit:
        model1 = corpus.build_corpus_model(case.root, (document,))
        model2 = corpus.build_corpus_model(case.root, (document,))
        assert model1 is model2
        assert mock_fit.call_count == 1
    corpus.build_corpus_model.cache_clear()


def test_cache_busts_on_changed_documents(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] corpus model ds202: verifies cache busts on changed documents.

    Scenario:
        Given test inputs and fixtures for cache busts on changed documents
        When test_cache_busts_on_changed_documents executes the target flow
        Then the expected outcome for cache busts on changed documents is confirmed.

    Boundaries:
        - Focus: cache busts on changed documents
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cache busts on changed documents
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by corpus model ds202
    """
    case = asset_case("ds202", "corpus_cache_busts_on_change")
    doc1 = case.document("doc1.md")
    doc2 = case.document("doc2.md")

    corpus.build_corpus_model.cache_clear()
    model1 = corpus.build_corpus_model(case.root, (doc1,))
    model2 = corpus.build_corpus_model(case.root, (doc2,))

    assert model1 is not model2
    corpus.build_corpus_model.cache_clear()


def test_build_corpus_model_all_code_returns_empty_model(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] corpus model ds202: verifies build corpus model all code returns empty model.

    Scenario:
        Given test inputs and fixtures for build corpus model all code returns empty model
        When test_build_corpus_model_all_code_returns_empty_model executes the target flow
        Then the expected outcome for build corpus model all code returns empty model is confirmed.

    Boundaries:
        - Focus: build corpus model all code returns empty model
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to build corpus model all code returns empty model
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by corpus model ds202
    """
    case = asset_case("ds202", "corpus_all_code")

    model = corpus.build_corpus_model(case.root, case.documents("code_only.md"))

    assert model.paragraphs == ()
    assert model.tfidf_matrix.shape == (0, 0)
    assert model.vocabulary == {}


def test_iter_chunks_helper(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] corpus model ds202: verifies iter chunks helper.

    Scenario:
        Given test inputs and fixtures for iter chunks helper
        When test_iter_chunks_helper executes the target flow
        Then the expected outcome for iter chunks helper is confirmed.

    Boundaries:
        - Focus: iter chunks helper
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to iter chunks helper
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by corpus model ds202
    """
    case = asset_case("ds202", "corpus_iter_chunks")

    chunks = corpus.iter_chunks(case.root, case.documents("chunks.md"), min_words=20)

    assert len(chunks) == 2
    assert chunks[0].index == 0
    assert chunks[1].index == 1
