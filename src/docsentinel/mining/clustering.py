"""Corpus-wide near-duplicate clustering and TF-IDF distinctiveness of short texts.

The module is text-generic (Story 02.0, decision T7): it takes ``Sequence[str]`` in the
caller's canonical order and returns one :class:`TextCluster` per input text, index-aligned.
It knows nothing about claims, documents or configuration; the caller passes the threshold.

The texts are vectorized with the shared :func:`docsentinel.mining.corpus.create_vectorizer`
factory (decision T4) in a model local to one call: it is never cached across calls and never
shared with the standard profile's cached corpus model. Cosine similarity is computed in row
chunks, so no dense ``n x n`` matrix is ever built. No text is logged at any level.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Final

import numpy as np
import scipy.sparse as sp

from docsentinel.mining.corpus import create_vectorizer

#: Default number of rows per similarity chunk; peak memory is ``O(chunk_rows x n)``.
SIMILARITY_CHUNK_ROWS: Final[int] = 512

#: Decimal places of every distinctiveness value (the same rounding as ``combined_score``).
ROUND_DECIMALS: Final[int] = 6

#: Decimal places a cosine similarity is rounded to before it is compared or used. Rounding
#: removes floating-point noise from the sparse products (identical texts compare as exactly
#: ``1.0``), so the strict ``> threshold`` boundary is stable across chunk sizes.
_SIMILARITY_DECIMALS: Final[int] = 12

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TextCluster:
    """Cluster membership and distinctiveness of one input text.

    :ivar cluster_id: The smallest input index in the text's connected component.
    :ivar distinctiveness: ``1 - max`` similarity to a text outside the cluster, in ``[0, 1]``,
        rounded to :data:`ROUND_DECIMALS` places; ``1.0`` when no other cluster exists.
    """

    cluster_id: int
    distinctiveness: float


def _validate(threshold: object, chunk_rows: object) -> float:
    """Validate the clustering parameters and return the threshold as a float.

    :param threshold: The link threshold; a finite number in ``(0, 1]``, not a ``bool``.
    :param chunk_rows: The similarity chunk size; an ``int >= 1``, not a ``bool``.
    :returns: The threshold as a ``float``.
    :raises ValueError: For a threshold or chunk size out of range or of the wrong type.
    """
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError("threshold must be a finite number in (0, 1]")
    value = float(threshold)
    if not math.isfinite(value) or not 0.0 < value <= 1.0:
        raise ValueError("threshold must be a finite number in (0, 1]")
    if isinstance(chunk_rows, bool) or not isinstance(chunk_rows, int) or chunk_rows < 1:
        raise ValueError("chunk_rows must be an int >= 1")
    return value


def _l2_normalize(matrix: Any) -> sp.csr_matrix:
    """Return ``matrix`` as CSR with every non-zero row scaled to unit L2 norm.

    :param matrix: A sparse TF-IDF matrix.
    :returns: The row-normalized CSR matrix; all-zero rows stay zero.
    """
    csr = sp.csr_matrix(matrix, dtype=np.float64)
    norms = np.sqrt(np.asarray(csr.multiply(csr).sum(axis=1)).ravel())
    scale = np.divide(1.0, norms, out=np.zeros_like(norms), where=norms > 0.0)
    return sp.csr_matrix(sp.diags(scale) @ csr)


#: Upper bound on the cells of one dense similarity block (about 32 MB of float64); the effective
#: row chunk is ``min(chunk_rows, _MAX_BLOCK_CELLS // n)``, at least one row.
_MAX_BLOCK_CELLS: Final[int] = 4_000_000


def _similarity_blocks(matrix: sp.csr_matrix, chunk_rows: int) -> Iterator[tuple[int, np.ndarray]]:
    """Yield dense cosine-similarity row blocks of a row-normalized matrix.

    Each block holds at most ``chunk_rows`` rows against all ``n`` texts, so peak memory is
    ``O(min(chunk_rows, _MAX_BLOCK_CELLS / n) x n)``. Values are clamped to ``[0, 1]`` and rounded to
    :data:`_SIMILARITY_DECIMALS` places.

    :param matrix: The L2-normalized ``n x d`` CSR matrix.
    :param chunk_rows: The maximum number of rows per block, ``>= 1``.
    :returns: An iterator of ``(start_row, block)`` pairs, ``block`` of shape ``(rows, n)``.
    """
    total = matrix.shape[0]
    # Bound a block to _MAX_BLOCK_CELLS cells however large the claim pool is.
    step = max(1, min(chunk_rows, _MAX_BLOCK_CELLS // max(1, total)))
    transposed = matrix.T.tocsc()
    for start in range(0, total, step):
        stop = min(start + step, total)
        block = (matrix[start:stop] @ transposed).toarray()
        np.clip(block, 0.0, 1.0, out=block)
        np.round(block, _SIMILARITY_DECIMALS, out=block)
        yield start, block


def _find(parent: list[int], index: int) -> int:
    """Return the root of ``index`` in a union-find forest, compressing the path.

    :param parent: The parent array of the forest.
    :param index: The element to look up.
    :returns: The root element, which is the smallest index of its component.
    """
    root = index
    while parent[root] != root:
        root = parent[root]
    while parent[index] != root:
        parent[index], index = root, parent[index]
    return root


def _union(parent: list[int], left: int, right: int) -> int:
    """Merge the components of ``left`` and ``right``, keeping the smaller root.

    :param parent: The parent array of the forest.
    :param left: One element.
    :param right: The other element.
    :returns: The root of the merged component; ``parent`` is updated in place.
    """
    left_root = _find(parent, left)
    right_root = _find(parent, right)
    root = min(left_root, right_root)
    parent[left_root] = root
    parent[right_root] = root
    return root


def cluster_near_duplicates(
    texts: Sequence[str],
    *,
    threshold: float,
    chunk_rows: int = SIMILARITY_CHUNK_ROWS,
) -> tuple[TextCluster, ...]:
    """Cluster near-identical texts with TF-IDF cosine similarity.

    Two texts are linked when their cosine similarity is strictly greater than ``threshold``;
    clusters are the connected components of that graph (built with union-find over the input
    order, so linking is transitive and the cluster id is the smallest member index). Document
    boundaries play no part: the caller passes the whole corpus. Each text's distinctiveness is
    ``1 - max`` similarity to any text outside its own cluster, clamped to ``[0, 1]`` and
    rounded to :data:`ROUND_DECIMALS` places, or ``1.0`` when no other cluster exists. When the
    vocabulary is empty after tokenizing, every text is its own cluster with distinctiveness
    ``0.0`` (the conservative choice: less text is selected).

    Complexity: two passes over the similarity matrix in row chunks, ``O(n^2)`` similarity
    entries in time (times the sparse row overlap), and ``O(chunk_rows x n)`` peak memory for a
    similarity block; a dense ``n x n`` matrix is never allocated.

    :param texts: Texts in the caller's canonical order; the output is index-aligned.
    :param threshold: Link two texts when similarity is strictly greater than this,
        in (0, 1].
    :param chunk_rows: Row-chunk size of the similarity computation, >= 1.
    :returns: One :class:`TextCluster` per input text, in input order; ``()`` for no texts.
    :raises ValueError: For a threshold or chunk size out of range.
    """
    limit = _validate(threshold, chunk_rows)
    items = list(texts)
    total = len(items)
    if total == 0:
        return ()

    try:
        tfidf = create_vectorizer().fit_transform(items)
    except ValueError:
        logger.debug("clustering vocabulary is empty: %d texts, each its own cluster", total)
        return tuple(TextCluster(cluster_id=index, distinctiveness=0.0) for index in range(total))

    matrix = _l2_normalize(tfidf)

    parent = list(range(total))
    for start, block in _similarity_blocks(matrix, chunk_rows):
        rows, columns = np.nonzero(block > limit)
        upper = columns > rows + start  # each pair once, self-similarity dropped, before the Python loop
        for row, column in zip(rows[upper].tolist(), columns[upper].tolist(), strict=True):
            _union(parent, start + row, column)
    labels = np.fromiter((_find(parent, index) for index in range(total)), dtype=np.int64, count=total)
    cluster_count = int(np.unique(labels).size)

    distinct = [1.0] * total
    if cluster_count > 1:
        for start, block in _similarity_blocks(matrix, chunk_rows):
            own = labels[start : start + block.shape[0], np.newaxis] == labels[np.newaxis, :]
            outside = np.where(own, 0.0, block).max(axis=1)
            for row, nearest in enumerate(outside.tolist()):
                distinct[start + row] = round(min(1.0, max(0.0, 1.0 - nearest)), ROUND_DECIMALS)

    logger.debug("clustering done: %d texts, %d clusters", total, cluster_count)
    return tuple(TextCluster(cluster_id=int(labels[index]), distinctiveness=distinct[index]) for index in range(total))


def cluster_sizes(clusters: Sequence[TextCluster]) -> tuple[int, ...]:
    """Return the size of each text's cluster, index-aligned with ``clusters``.

    Story 05.0 reports ``cluster_size`` (the number of texts sharing a ``cluster_id``, ``>= 1``)
    next to every claim; this keeps the count in one place.

    :param clusters: The output of :func:`cluster_near_duplicates`.
    :returns: One size per entry, in input order; ``()`` for no clusters.
    """
    counts: dict[int, int] = {}
    for cluster in clusters:
        counts[cluster.cluster_id] = counts.get(cluster.cluster_id, 0) + 1
    return tuple(counts[cluster.cluster_id] for cluster in clusters)
