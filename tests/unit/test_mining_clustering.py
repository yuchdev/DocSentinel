"""Unit tests for ``docsentinel.mining.clustering`` (corpus-wide near-duplicate clustering).

Every case runs through the real ``mining.corpus.create_vectorizer()`` factory with tiny inline
strings, so the ``0.92`` threshold's acceptance cases exercise the calibration DS202/DS203 share.
"""

import ast
import logging
import math
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

from sklearn.feature_extraction.text import TfidfVectorizer

from docsentinel.mining import clustering
from docsentinel.mining.clustering import (
    ROUND_DECIMALS,
    SIMILARITY_CHUNK_ROWS,
    TextCluster,
    cluster_near_duplicates,
    cluster_sizes,
)
from docsentinel.mining.corpus import create_vectorizer

#: The fixed DS302 policy threshold the caller passes (Story 02.0, decision T2).
_THRESHOLD = 0.92

_BASE = (
    "the service stores uploaded invoices in regional buckets encrypted with customer managed "
    "keys rotated every ninety days by the scheduler"
)
#: Similarity to ``_BASE`` is about 0.943 through the real factory (above 0.92).
_NEAR = _BASE + " automatically"
#: Similarity to ``_BASE`` is about 0.776 through the real factory (below 0.92).
_FAR = _BASE.replace("ninety", "thirty").replace("regional", "central")
_OTHER = "the cache expires entries after ten minutes"

#: A chain: A~B and B~C are about 0.773, A~C about 0.570.
_CHAIN = (
    "alpha beta gamma delta epsilon zeta eta theta",
    "alpha beta gamma delta epsilon zeta eta iota",
    "alpha beta gamma delta epsilon zeta kappa iota",
)


def _pair_similarity(left: str, right: str) -> float:
    """Return the rounded cosine similarity of two texts exactly as the module computes it.

    :param left: The first text.
    :param right: The second text.
    :returns: The similarity used for the ``> threshold`` comparison.
    """
    matrix = clustering._l2_normalize(create_vectorizer().fit_transform([left, right]))
    _, block = next(clustering._similarity_blocks(matrix, 2))
    return float(block[0, 1])


def test_factory_parameters_are_pinned():
    """
    [Unit] mining clustering: pins the shared TF-IDF factory parameters.

    Scenario:
        Given the shared vectorizer factory in mining.corpus
        When its parameters are compared with the calibrated configuration
        Then they equal English stop words, the word token pattern and sublinear TF, defaults otherwise.

    Boundaries:
        - Focus: create_vectorizer() calibration shared by DS202, DS203 and DS302 (decision T4)
        - Fixtures/params: none
        - Scope: a parameter change here recalibrates three rules and must be deliberate

    On failure, first check:
        - Whether mining/corpus.py create_vectorizer() parameters changed
        - Whether a scikit-learn upgrade changed TfidfVectorizer defaults
    """
    expected = TfidfVectorizer(stop_words="english", token_pattern=r"(?u)\b\w+\b", sublinear_tf=True)
    assert create_vectorizer().get_params() == expected.get_params()
    assert create_vectorizer() is not create_vectorizer()


def test_pair_above_threshold_shares_a_cluster():
    """
    [Unit] mining clustering: links two texts whose similarity exceeds 0.92.

    Scenario:
        Given a sentence and a near copy (similarity ~0.943) plus an unrelated sentence
        When cluster_near_duplicates runs with threshold 0.92
        Then the two near copies share cluster 0 and the unrelated sentence is cluster 2.

    Boundaries:
        - Focus: strict > threshold linking, smallest-index cluster id
        - Fixtures/params: inline strings through the real factory
        - Scope: one call

    On failure, first check:
        - Similarity of _BASE and _NEAR through create_vectorizer()
        - Union-find root selection in clustering._union
    """
    assert _pair_similarity(_BASE, _NEAR) > _THRESHOLD
    result = cluster_near_duplicates([_BASE, _NEAR, _OTHER], threshold=_THRESHOLD)
    assert [item.cluster_id for item in result] == [0, 0, 2]
    assert cluster_sizes(result) == (2, 2, 1)


def test_pair_below_threshold_stays_apart():
    """
    [Unit] mining clustering: does not link two texts below 0.92.

    Scenario:
        Given a sentence and an edited copy (similarity ~0.776)
        When cluster_near_duplicates runs with threshold 0.92
        Then each text is its own cluster and its distinctiveness is 1 - similarity.

    Boundaries:
        - Focus: no link below threshold; distinctiveness from the nearest outside text
        - Fixtures/params: inline strings through the real factory
        - Scope: one call

    On failure, first check:
        - Similarity of _BASE and _FAR through create_vectorizer()
        - The outside-cluster mask in the distinctiveness pass
    """
    similarity = _pair_similarity(_BASE, _FAR)
    assert similarity < _THRESHOLD
    result = cluster_near_duplicates([_BASE, _FAR], threshold=_THRESHOLD)
    expected = round(1.0 - similarity, ROUND_DECIMALS)
    assert result == (TextCluster(0, expected), TextCluster(1, expected))


def test_similarity_equal_to_threshold_is_not_linked():
    """
    [Unit] mining clustering: a similarity exactly equal to the threshold does not link.

    Scenario:
        Given two texts whose computed similarity is s, and two identical texts (similarity 1.0)
        When the threshold is exactly s (or 1.0), and then just below s
        Then the texts stay apart at the threshold and are linked just below it.

    Boundaries:
        - Focus: the strict > comparison at the boundary (0.92 itself is not linked)
        - Fixtures/params: inline strings; threshold derived from the module's own rounding
        - Scope: three calls

    On failure, first check:
        - Whether the comparison became >= instead of >
        - The similarity rounding in clustering._similarity_blocks
    """
    similarity = _pair_similarity(_BASE, _NEAR)
    at_boundary = cluster_near_duplicates([_BASE, _NEAR], threshold=similarity)
    assert [item.cluster_id for item in at_boundary] == [0, 1]
    below = cluster_near_duplicates([_BASE, _NEAR], threshold=similarity - 1e-9)
    assert [item.cluster_id for item in below] == [0, 0]
    identical = cluster_near_duplicates([_BASE, _BASE], threshold=1.0)
    assert identical == (TextCluster(0, 0.0), TextCluster(1, 0.0))


def test_linking_is_transitive():
    """
    [Unit] mining clustering: A~B and B~C put A, B and C in one cluster.

    Scenario:
        Given a chain where A~B and B~C are above the threshold but A~C is below it
        When cluster_near_duplicates runs with a threshold between the two similarities
        Then all three texts share cluster 0, whose distinctiveness is 1.0 (no other cluster).

    Boundaries:
        - Focus: connected components, not pairwise cliques
        - Fixtures/params: inline strings, threshold 0.7
        - Scope: one call

    On failure, first check:
        - Chain similarities (A~B, B~C ~0.773; A~C ~0.570)
        - Union-find path handling in clustering._find
    """
    assert _pair_similarity(_CHAIN[0], _CHAIN[2]) < 0.7
    result = cluster_near_duplicates(list(_CHAIN), threshold=0.7)
    assert result == (TextCluster(0, 1.0), TextCluster(0, 1.0), TextCluster(0, 1.0))
    reordered = cluster_near_duplicates([_CHAIN[2], _CHAIN[0], _CHAIN[1]], threshold=0.7)
    assert [item.cluster_id for item in reordered] == [0, 0, 0]


def test_identical_texts_cluster_corpus_wide_and_index_aligned():
    """
    [Unit] mining clustering: identical sentences far apart in the input share one cluster.

    Scenario:
        Given the same sentence at indexes 1 and 3 (as if from two documents) between others
        When cluster_near_duplicates runs with threshold 0.92
        Then indexes 1 and 3 share cluster 1, output is index-aligned, and reversing input reverses output.

    Boundaries:
        - Focus: corpus-wide scope (owner ruling D7), index alignment, order dependence only
        - Fixtures/params: inline strings
        - Scope: two calls

    On failure, first check:
        - Whether clustering started looking at document boundaries
        - Cluster id = smallest input index
    """
    texts = [_OTHER, _BASE, _FAR, _BASE]
    result = cluster_near_duplicates(texts, threshold=_THRESHOLD)
    assert len(result) == len(texts)
    assert [item.cluster_id for item in result] == [0, 1, 2, 1]
    assert result[1] == result[3]
    reversed_result = cluster_near_duplicates(texts[::-1], threshold=_THRESHOLD)
    assert [item.distinctiveness for item in reversed_result] == [item.distinctiveness for item in result][::-1]
    assert [item.cluster_id for item in reversed_result] == [0, 1, 0, 3]


def test_empty_and_single_inputs():
    """
    [Unit] mining clustering: empty input returns (), a single text gets distinctiveness 1.0.

    Scenario:
        Given no texts, a list with one text, and a tuple input
        When cluster_near_duplicates runs
        Then () and (TextCluster(0, 1.0),) are returned.

    Boundaries:
        - Focus: edge cases of the input size
        - Fixtures/params: none
        - Scope: three calls

    On failure, first check:
        - The early return for an empty input
        - The "no other cluster" branch of the distinctiveness pass
    """
    assert cluster_near_duplicates([], threshold=_THRESHOLD) == ()
    assert cluster_near_duplicates([_BASE], threshold=_THRESHOLD) == (TextCluster(0, 1.0),)
    assert cluster_near_duplicates((_OTHER,), threshold=_THRESHOLD) == (TextCluster(0, 1.0),)


def test_empty_vocabulary_gives_zero_and_logs_counts_only(caplog):
    """
    [Unit] mining clustering: a stop-word-only corpus gives singleton clusters at 0.0.

    Scenario:
        Given texts made only of English stop words
        When cluster_near_duplicates runs
        Then no exception is raised, each text is its own cluster at 0.0, and the log holds no text.

    Boundaries:
        - Focus: the conservative empty-vocabulary fallback and the no-text logging rule
        - Fixtures/params: caplog at DEBUG
        - Scope: one call

    On failure, first check:
        - The ValueError handler around fit_transform
        - Whether a log line started echoing an input text
    """
    texts = ["the of and", "is it a", "the"]
    with caplog.at_level(logging.DEBUG, logger="docsentinel.mining.clustering"):
        result = cluster_near_duplicates(texts, threshold=_THRESHOLD)
    assert result == (TextCluster(0, 0.0), TextCluster(1, 0.0), TextCluster(2, 0.0))
    assert any("3 texts" in record.getMessage() for record in caplog.records)
    for record in caplog.records:
        assert "the of and" not in record.getMessage()


def test_no_text_is_logged_on_the_normal_path(caplog):
    """
    [Unit] mining clustering: log records carry counts, never input text.

    Scenario:
        Given ordinary sentences
        When cluster_near_duplicates runs at DEBUG
        Then no log message contains any word of the input.

    Boundaries:
        - Focus: security rule "no text is logged at any level"
        - Fixtures/params: caplog at DEBUG
        - Scope: one call

    On failure, first check:
        - New logger calls in mining/clustering.py
    """
    with caplog.at_level(logging.DEBUG, logger="docsentinel.mining.clustering"):
        cluster_near_duplicates([_BASE, _NEAR, _OTHER], threshold=_THRESHOLD)
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "invoices" not in messages
    assert "cache" not in messages


def test_chunked_similarity_never_builds_dense_square(monkeypatch):
    """
    [Unit] mining clustering: chunk_rows=2 bounds every similarity block and changes nothing.

    Scenario:
        Given five texts and a spy on the similarity block generator
        When cluster_near_duplicates runs with chunk_rows=2 and with the default chunk size
        Then every block has at most 2 rows (never 5 x 5) and both results are equal.

    Boundaries:
        - Focus: O(chunk x n) peak memory and chunk-size independence of the output
        - Fixtures/params: monkeypatch spy on clustering._similarity_blocks
        - Scope: two calls

    On failure, first check:
        - Whether a full similarity matrix is computed outside _similarity_blocks
        - Row offsets (start) in the two passes
    """
    texts = [_BASE, _OTHER, _NEAR, _FAR, _BASE]
    shapes: list[tuple[int, int]] = []
    original = clustering._similarity_blocks

    def _spy(matrix, chunk_rows):
        """Record each block's shape and pass it through."""
        for start, block in original(matrix, chunk_rows):
            shapes.append(block.shape)
            yield start, block

    monkeypatch.setattr(clustering, "_similarity_blocks", _spy)
    chunked = cluster_near_duplicates(texts, threshold=_THRESHOLD, chunk_rows=2)
    assert shapes
    assert all(rows <= 2 and columns == len(texts) for rows, columns in shapes)
    monkeypatch.setattr(clustering, "_similarity_blocks", original)
    assert chunked == cluster_near_duplicates(texts, threshold=_THRESHOLD)
    assert SIMILARITY_CHUNK_ROWS == 512


def test_distinctiveness_is_rounded_and_in_range():
    """
    [Unit] mining clustering: distinctiveness lies in [0, 1] with ROUND_DECIMALS places.

    Scenario:
        Given a mixed corpus with near and far duplicates
        When cluster_near_duplicates runs
        Then each value is within [0, 1] and equals its own rounding to 6 places.

    Boundaries:
        - Focus: clamping and fixed rounding (same as combined_score)
        - Fixtures/params: inline strings
        - Scope: one call

    On failure, first check:
        - ROUND_DECIMALS and the clamp in cluster_near_duplicates
    """
    result = cluster_near_duplicates([_BASE, _NEAR, _FAR, _OTHER], threshold=_THRESHOLD)
    assert ROUND_DECIMALS == 6
    for item in result:
        assert 0.0 <= item.distinctiveness <= 1.0
        assert item.distinctiveness == round(item.distinctiveness, ROUND_DECIMALS)
    assert result[3].distinctiveness == 1.0


@pytest.mark.parametrize(
    "threshold",
    [0, 0.0, -0.1, 1.0000001, 2, math.nan, math.inf, -math.inf, True, False, "0.92", None],
)
def test_invalid_threshold_raises(threshold):
    """
    [Unit] mining clustering: a threshold outside (0, 1], non-finite or non-numeric is refused.

    Scenario:
        Given an invalid threshold value
        When cluster_near_duplicates is called (even with an empty input)
        Then ValueError is raised.

    Boundaries:
        - Focus: threshold validation, bool refused
        - Fixtures/params: parametrized invalid values
        - Scope: one call per case

    On failure, first check:
        - clustering._validate
    """
    with pytest.raises(ValueError, match="threshold"):
        cluster_near_duplicates([], threshold=threshold)


@pytest.mark.parametrize("chunk_rows", [0, -1, 1.0, 2.5, True, False, "2", None])
def test_invalid_chunk_rows_raises(chunk_rows):
    """
    [Unit] mining clustering: a chunk_rows that is not an int >= 1 is refused.

    Scenario:
        Given an invalid chunk_rows value
        When cluster_near_duplicates is called
        Then ValueError is raised.

    Boundaries:
        - Focus: chunk_rows validation, bool refused
        - Fixtures/params: parametrized invalid values
        - Scope: one call per case

    On failure, first check:
        - clustering._validate
    """
    with pytest.raises(ValueError, match="chunk_rows"):
        cluster_near_duplicates([_BASE], threshold=_THRESHOLD, chunk_rows=chunk_rows)


def test_valid_boundary_parameters_are_accepted():
    """
    [Unit] mining clustering: threshold 1 (int) and chunk_rows 1 are valid.

    Scenario:
        Given the inclusive upper threshold bound and the smallest chunk size
        When cluster_near_duplicates runs
        Then it returns one cluster per text without raising.

    Boundaries:
        - Focus: inclusive bounds of the parameter validation
        - Fixtures/params: none
        - Scope: one call

    On failure, first check:
        - clustering._validate bounds
    """
    result = cluster_near_duplicates([_BASE, _OTHER], threshold=1, chunk_rows=1)
    assert [item.cluster_id for item in result] == [0, 1]


def test_cluster_sizes_is_index_aligned():
    """
    [Unit] mining clustering: cluster_sizes counts members per cluster id, index-aligned.

    Scenario:
        Given a hand-built cluster tuple and an empty one
        When cluster_sizes runs
        Then each entry gets its cluster's member count, and () gives ().

    Boundaries:
        - Focus: Story 05.0 cluster_size (>= 1)
        - Fixtures/params: none
        - Scope: pure function

    On failure, first check:
        - clustering.cluster_sizes
    """
    clusters = (TextCluster(0, 0.1), TextCluster(1, 1.0), TextCluster(0, 0.1), TextCluster(0, 0.1))
    assert cluster_sizes(clusters) == (3, 1, 3, 3)
    assert cluster_sizes(()) == ()


def test_vectorizer_comes_only_from_the_shared_factory(monkeypatch):
    """
    [Unit] mining clustering: builds its vectorizer only through mining.corpus.create_vectorizer().

    Scenario:
        Given the clustering module source and a counting spy on the create_vectorizer it uses
        When the source is parsed and cluster_near_duplicates runs once on three texts
        Then the source names no scikit-learn vectorizer class or sklearn import, and the spy was
            called exactly once with a result equal to the unspied run

    Boundaries:
        - Focus: Story 02.0 acceptance (vectorizer only via the factory), decision T4
        - Fixtures/params: monkeypatch spy on clustering.create_vectorizer
        - Scope: AST plus one call

    On failure, first check:
        - A direct TfidfVectorizer/CountVectorizer construction added to mining/clustering.py
    """
    tree = ast.parse(Path(clustering.__file__).read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not names & {"TfidfVectorizer", "CountVectorizer", "HashingVectorizer", "TfidfTransformer"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] != "sklearn" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "sklearn"

    texts = [_BASE, _NEAR, _OTHER]
    expected = cluster_near_duplicates(texts, threshold=_THRESHOLD)
    calls: list[int] = []
    original = clustering.create_vectorizer

    def _spy() -> TfidfVectorizer:
        """Count the call and delegate to the real factory."""
        calls.append(1)
        return original()

    monkeypatch.setattr(clustering, "create_vectorizer", _spy)
    assert cluster_near_duplicates(texts, threshold=_THRESHOLD) == expected
    assert calls == [1]
