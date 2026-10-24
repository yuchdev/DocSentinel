"""Shared corpus vectorizer and paragraph chunking for standard profile detectors.

This module provides the shared substrate for DS202 (duplicate text) and DS203 (low information).
Both detectors require the corpus broken into paragraph-level chunks with provenance, along with
a shared TfidfVectorizer fitted once across all chunks.

Note on coupling:
DS201 (complexity.py) extracts whole-document prose for readability scoring, whereas DS202/DS203
extract paragraph-level prose chunks with provenance. The markdown stripping logic is maintained
independently in this module to avoid coupling paragraph chunking concerns to DS201.

Paragraph size floors are configurable: `build_corpus_model` accepts `min_paragraph_chars`
(default 30) and `min_paragraph_words` (default 5), which form part of the memoization cache
key so distinct settings never share a stale corpus. The TfidfVectorizer settings (English
stop words, sublinear term frequency, word token pattern) are fixed calibration internals and
are not exposed as configuration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer

from docsentinel import models

_MIN_PARAGRAPH_CHARS: int = 30
_MIN_PARAGRAPH_WORDS: int = 5
_MIN_CHUNK_WORDS: int = 20

_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`+[^`\n]+`+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_HEADER_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^\s*>+\s?", re.MULTILINE)
_LIST_MARKER_RE = re.compile(r"^\s*([-*+]|\d+\.)\s+", re.MULTILINE)


@dataclass(frozen=True)
class Paragraph:
    """A paragraph of prose extracted from a document with provenance."""

    doc_path: str
    index: int
    text: str
    line: int

    @property
    def path(self) -> str:
        """Alias for doc_path to maintain locator consistency."""
        return self.doc_path

    @property
    def preview(self) -> str:
        """First ~60 characters on a single line for findings preview."""
        single_line = " ".join(self.text.split())
        return single_line[:60]


# Alias Chunk to Paragraph for story roadmap compatibility
Chunk = Paragraph


@dataclass(frozen=True)
class CorpusModel:
    """The fitted TF-IDF state and extracted paragraphs shared across detectors."""

    documents: tuple[models.Document, ...]
    paragraphs: tuple[Paragraph, ...]
    tfidf_matrix: Any
    vectorizer: Any

    @property
    def chunks(self) -> tuple[Paragraph, ...]:
        """Alias for paragraphs."""
        return self.paragraphs

    @property
    def matrix(self) -> Any:
        """Alias for tfidf_matrix."""
        return self.tfidf_matrix

    @property
    def vocabulary(self) -> dict[str, int]:
        """Vocabulary mapping feature names to matrix column indices."""
        if hasattr(self.vectorizer, "vocabulary_") and self.vectorizer.vocabulary_ is not None:
            return self.vectorizer.vocabulary_
        return {}

    @property
    def idf(self) -> Any:
        """Inverse document frequency vector."""
        if hasattr(self.vectorizer, "idf_") and self.vectorizer.idf_ is not None:
            return self.vectorizer.idf_
        return None


def _strip_fenced_blocks(text: str) -> str:
    """Return text with fenced code blocks blanked while preserving line offsets."""
    stripped_lines: list[str] = []
    in_fence = False
    fence_marker: Optional[str] = None

    for line in text.splitlines(keepends=True):
        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)[0]
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence, fence_marker = False, None

        if in_fence or fence:
            blank_line = "".join(character if character in "\r\n" else " " for character in line)
            stripped_lines.append(blank_line)
        else:
            stripped_lines.append(line)

    return "".join(stripped_lines)


def _strip_comments(text: str) -> str:
    """Return text with HTML comments blanked while preserving line offsets."""

    def _blank_match(match: re.Match[str]) -> str:
        """Replace non-newline characters in matched comments with spaces."""
        s = match.group(0)
        return "".join(c if c in "\r\n" else " " for c in s)

    return _COMMENT_RE.sub(_blank_match, text)


def _strip_markdown_markers(text: str) -> str:
    """Strip inline code, HTML tags, images, link urls, headers, quotes, and list markers."""
    text = _INLINE_CODE_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)
    text = _IMAGE_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _HEADER_RE.sub("", text)
    text = _BLOCKQUOTE_RE.sub("", text)
    text = _LIST_MARKER_RE.sub("", text)
    return " ".join(text.split())


def _read_doc_text(
    doc: models.Document,
    root: Optional[Path] = None,
    text: Optional[str] = None,
) -> str:
    """Read document text from string, document attribute, or disk."""
    if text is not None:
        return text
    doc_content = getattr(doc, "content", None)
    if isinstance(doc_content, str):
        return doc_content
    doc_text = getattr(doc, "text", None)
    if isinstance(doc_text, str):
        return doc_text
    target = Path(root) / doc.path if root is not None else Path(doc.path)
    with target.open(encoding="utf-8") as stream:
        return stream.read()


def extract_paragraphs(
    doc: models.Document,
    root: Optional[Path] = None,
    text: Optional[str] = None,
    min_chars: int = _MIN_PARAGRAPH_CHARS,
    min_words: int = _MIN_PARAGRAPH_WORDS,
) -> tuple[Paragraph, ...]:
    """Parse document text into paragraph chunks with provenance and line numbers.

    Fenced code blocks and HTML comments are ignored, markdown markers are stripped,
    and paragraphs shorter than min_chars or min_words are skipped.
    """
    raw_text = _read_doc_text(doc, root=root, text=text)
    masked_text = _strip_comments(_strip_fenced_blocks(raw_text))

    paragraphs: list[Paragraph] = []
    current_lines: list[str] = []
    start_line: Optional[int] = None
    paragraph_index = 0

    lines = masked_text.splitlines()
    for line_number, line_str in enumerate(lines, start=1):
        if line_str.strip():
            if start_line is None:
                start_line = line_number
            current_lines.append(line_str)
        else:
            if current_lines and start_line is not None:
                raw_block = "\n".join(current_lines)
                cleaned = _strip_markdown_markers(raw_block)
                words = cleaned.split()
                if len(cleaned) >= min_chars and len(words) >= min_words:
                    paragraphs.append(
                        Paragraph(
                            doc_path=doc.path,
                            index=paragraph_index,
                            text=cleaned,
                            line=start_line,
                        )
                    )
                    paragraph_index += 1
                current_lines = []
                start_line = None

    if current_lines and start_line is not None:
        raw_block = "\n".join(current_lines)
        cleaned = _strip_markdown_markers(raw_block)
        words = cleaned.split()
        if len(cleaned) >= min_chars and len(words) >= min_words:
            paragraphs.append(
                Paragraph(
                    doc_path=doc.path,
                    index=paragraph_index,
                    text=cleaned,
                    line=start_line,
                )
            )

    return tuple(paragraphs)


def iter_chunks(
    root: Path,
    documents: tuple[models.Document, ...],
    min_words: int = _MIN_CHUNK_WORDS,
) -> tuple[Chunk, ...]:
    """Extract chunks across sorted documents dropping blocks under min_words."""
    sorted_docs = tuple(sorted(documents, key=lambda item: item.path))
    chunks: list[Chunk] = []
    for doc in sorted_docs:
        if not doc.path.endswith(".md"):
            continue
        doc_chunks = extract_paragraphs(doc, root=root, min_chars=0, min_words=min_words)
        chunks.extend(doc_chunks)
    return tuple(chunks)


def _create_vectorizer() -> TfidfVectorizer:
    """Create the standardized TfidfVectorizer instance."""
    return TfidfVectorizer(
        stop_words="english",
        token_pattern=r"(?u)\b\w+\b",
        sublinear_tf=True,
    )


@lru_cache(maxsize=1)
def build_corpus_model(
    root: Optional[Union[Path, str, tuple[models.Document, ...]]] = None,
    documents: tuple[models.Document, ...] = (),
    min_paragraph_chars: int = _MIN_PARAGRAPH_CHARS,
    min_paragraph_words: int = _MIN_PARAGRAPH_WORDS,
) -> CorpusModel:
    """Build or retrieve a cached CorpusModel across all supplied documents.

    Accepts both build_corpus_model(documents) and build_corpus_model(root, documents).

    The paragraph size floors participate in the memoization key, so two scans
    with different floors in one process never share a stale corpus; two scans
    with identical floors reuse the single cached entry.

    :param root: The scan root, or the documents tuple in the legacy call form.
    :param documents: The documents to model when ``root`` is a path.
    :param min_paragraph_chars: Minimum visible-character count for a paragraph
        to be analysed.
    :param min_paragraph_words: Minimum prose-word count for a paragraph to be
        analysed.
    :returns: The fitted, cached :class:`CorpusModel`.
    """
    if isinstance(root, (tuple, list)):
        actual_docs = tuple(root)
        actual_root = None
    elif isinstance(root, str):
        actual_root = Path(root)
        actual_docs = documents
    else:
        actual_root = root
        actual_docs = documents

    sorted_docs = tuple(sorted(actual_docs, key=lambda item: item.path))
    all_paragraphs: list[Paragraph] = []

    for doc in sorted_docs:
        if not doc.path.endswith(".md"):
            continue
        doc_paragraphs = extract_paragraphs(
            doc,
            root=actual_root,
            min_chars=min_paragraph_chars,
            min_words=min_paragraph_words,
        )
        all_paragraphs.extend(doc_paragraphs)

    paragraphs = tuple(all_paragraphs)
    vectorizer = _create_vectorizer()

    if not paragraphs:
        empty_matrix = sp.csr_matrix((0, 0), dtype=np.float64)
        return CorpusModel(
            documents=sorted_docs,
            paragraphs=(),
            tfidf_matrix=empty_matrix,
            vectorizer=vectorizer,
        )

    paragraph_texts = [p.text for p in paragraphs]
    try:
        tfidf_matrix = vectorizer.fit_transform(paragraph_texts)
    except ValueError:
        tfidf_matrix = sp.csr_matrix((len(paragraphs), 0), dtype=np.float64)

    return CorpusModel(
        documents=sorted_docs,
        paragraphs=paragraphs,
        tfidf_matrix=tfidf_matrix,
        vectorizer=vectorizer,
    )


def clear_corpus_cache():
    """Clear memoized corpus models."""
    build_corpus_model.cache_clear()
