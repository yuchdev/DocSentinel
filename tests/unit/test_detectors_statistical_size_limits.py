"""Unit tests wiring the statistical size-limit config keys into DS201/DS202/DS203.

Exercises ``complexity.check_document`` (DS201), ``corpus.extract_paragraphs`` and the
memoized ``corpus.build_corpus_model`` (DS202/DS203), using tiny inline text and
``tmp_path``; no committed assets are loaded.
"""

from pathlib import Path

import pytest

pytest.importorskip("sklearn")
pytest.importorskip("textstat")

from docsentinel import models
from docsentinel.detectors.standard import complexity, corpus

# A single long, polysyllabic sentence: Flesch-Kincaid grade well above 14.
_COMPLEX_SENTENCE = (
    "The comprehensive institutional documentation methodology necessitates "
    "considerable interdisciplinary collaboration between numerous organizational "
    "stakeholders whose administrative responsibilities encompass sophisticated "
    "technological infrastructure alongside multifaceted procedural considerations "
    "requiring extraordinarily meticulous verification."
)


def _word_count(text: str) -> int:
    """Return the whitespace-delimited word count of ``text``.

    :param text: Prose to count.
    :returns: The number of words.
    """
    return len(text.split())


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the shared corpus cache before and after each test."""
    corpus.clear_corpus_cache()
    yield
    corpus.clear_corpus_cache()


def _write_doc(root: Path, name: str, content: str) -> models.Document:
    """Write ``content`` to ``root/name`` and return its Document.

    :param root: Directory the document is written under.
    :param name: Relative file name.
    :param content: Markdown text to write.
    :returns: The matching :class:`models.Document`.
    """
    target = root / name
    target.write_text(content, encoding="utf-8")
    return models.Document(path=name, bytes=len(content.encode("utf-8")))


def test_ds201_skips_document_below_default_word_floor(tmp_path: Path):
    """
    [Unit] DS201: a short complex document is skipped at the default 50-word floor.

    Scenario:
        Given a complex sentence of fewer than 50 words
        When check_document runs with the default min_words
        Then no finding is produced even with a low max_grade.

    Boundaries:
        - Focus: the ``len(words) < min_words`` skip
        - Fixtures/params: tmp_path
        - Scope: assertions in this test only

    On failure, first check:
        - The min_words gate in check_document
    """
    assert _word_count(_COMPLEX_SENTENCE) < 50
    doc = _write_doc(tmp_path, "short.md", _COMPLEX_SENTENCE)
    assert complexity.check_document(tmp_path, doc, max_grade=1.0) == ()


def test_ds201_evaluates_short_document_when_floor_lowered(tmp_path: Path):
    """
    [Unit] DS201: the same short document is scored once min_words is lowered.

    Scenario:
        Given the same sub-50-word complex sentence
        When check_document runs with a lowered min_words and a low max_grade
        Then it is scored and flagged.

    Boundaries:
        - Focus: min_words wiring into the skip gate
        - Fixtures/params: tmp_path
        - Scope: assertions in this test only

    On failure, first check:
        - That min_words is threaded from config into check_document
    """
    doc = _write_doc(tmp_path, "short.md", _COMPLEX_SENTENCE)
    findings = complexity.check_document(tmp_path, doc, max_grade=1.0, min_words=10)
    assert len(findings) == 1
    assert findings[0].rule == "DS201"


def test_ds201_flags_long_complex_document_at_default(tmp_path: Path):
    """
    [Unit] DS201: a long complex document is flagged at the default floor and grade.

    Scenario:
        Given a complex passage of more than 50 words
        When check_document runs with the default min_words and max_grade 14.0
        Then it is flagged as exceeding the grade threshold.

    Boundaries:
        - Focus: normal case above both floors
        - Fixtures/params: tmp_path
        - Scope: assertions in this test only

    On failure, first check:
        - The readability metric and default thresholds
    """
    content = _COMPLEX_SENTENCE + " " + _COMPLEX_SENTENCE
    assert _word_count(content) >= 50
    doc = _write_doc(tmp_path, "long.md", content)
    findings = complexity.check_document(tmp_path, doc)
    assert len(findings) == 1
    assert findings[0].rule == "DS201"


def test_paragraph_word_floor_gates_corpus(tmp_path: Path):
    """
    [Unit] DS202/DS203: a 4-word paragraph is excluded by default, included when lowered.

    Scenario:
        Given a 4-word paragraph longer than 30 characters
        When extract_paragraphs runs at the default and a lowered word floor
        Then the paragraph is absent by default and present once lowered.

    Boundaries:
        - Focus: the min_words paragraph floor in isolation
        - Fixtures/params: tmp_path
        - Scope: assertions in this test only

    On failure, first check:
        - extract_paragraphs min_words handling
    """
    text = "antidisestablishmentarianism quux corge grault\n"
    doc = models.Document(path="p.md", bytes=len(text.encode("utf-8")))
    default = corpus.extract_paragraphs(doc, text=text)
    lowered = corpus.extract_paragraphs(doc, text=text, min_words=4)
    assert default == ()
    assert len(lowered) == 1


def test_paragraph_char_floor_gates_corpus(tmp_path: Path):
    """
    [Unit] DS202/DS203: a 6-word 11-char paragraph is excluded by default, included when lowered.

    Scenario:
        Given a paragraph with enough words but fewer than 30 characters
        When extract_paragraphs runs at the default and a lowered char floor
        Then the paragraph is absent by default and present once lowered.

    Boundaries:
        - Focus: the min_chars paragraph floor in isolation
        - Fixtures/params: tmp_path
        - Scope: assertions in this test only

    On failure, first check:
        - extract_paragraphs min_chars handling
    """
    text = "a b c d e f\n"
    doc = models.Document(path="p.md", bytes=len(text.encode("utf-8")))
    default = corpus.extract_paragraphs(doc, text=text)
    lowered = corpus.extract_paragraphs(doc, text=text, min_chars=10)
    assert default == ()
    assert len(lowered) == 1


def test_raising_paragraph_word_floor_excludes_formerly_included(tmp_path: Path):
    """
    [Unit] DS202/DS203: raising the word floor drops a formerly-analysed paragraph.

    Scenario:
        Given a paragraph that qualifies under the default floors
        When extract_paragraphs runs with a raised word floor
        Then the paragraph is excluded.

    Boundaries:
        - Focus: the reverse direction of the word floor
        - Fixtures/params: tmp_path
        - Scope: assertions in this test only

    On failure, first check:
        - extract_paragraphs min_words handling
    """
    text = "alpha beta gamma delta epsilon zeta\n"
    doc = models.Document(path="p.md", bytes=len(text.encode("utf-8")))
    assert len(corpus.extract_paragraphs(doc, text=text)) == 1
    assert corpus.extract_paragraphs(doc, text=text, min_words=10) == ()


def test_corpus_cache_keys_on_paragraph_floors(tmp_path: Path):
    """
    [Unit] corpus: distinct paragraph floors never share a stale cached model.

    Scenario:
        Given one document scanned twice in a process with different floors
        When build_corpus_model is called with each floor
        Then the paragraph sets differ (no stale cache leak).

    Boundaries:
        - Focus: the lru_cache key includes the floors
        - Fixtures/params: tmp_path
        - Scope: assertions in this test only

    On failure, first check:
        - That the floors are parameters of build_corpus_model, not module constants
    """
    doc = _write_doc(
        tmp_path,
        "doc.md",
        "A fully qualifying paragraph with plenty of words and characters here today.\n\n"
        "antidisestablishmentarianism quux corge grault\n",
    )
    documents = (doc,)
    default_model = corpus.build_corpus_model(tmp_path, documents)
    lowered_model = corpus.build_corpus_model(tmp_path, documents, min_paragraph_words=4)
    assert len(default_model.paragraphs) == 1
    assert len(lowered_model.paragraphs) == 2


def test_corpus_cache_is_shared_for_equal_floors(tmp_path: Path):
    """
    [Unit] corpus: equal floors reuse the single cached model (a cache hit).

    Scenario:
        Given identical arguments including identical floors
        When build_corpus_model is called twice
        Then the second call is a cache hit and clear_corpus_cache resets it.

    Boundaries:
        - Focus: cache sharing and clearing
        - Fixtures/params: tmp_path
        - Scope: assertions in this test only

    On failure, first check:
        - build_corpus_model.cache_info() hit accounting
        - clear_corpus_cache wiring
    """
    doc = _write_doc(
        tmp_path,
        "doc.md",
        "A fully qualifying paragraph with plenty of words and characters here today.\n",
    )
    documents = (doc,)
    corpus.clear_corpus_cache()
    first = corpus.build_corpus_model(tmp_path, documents, min_paragraph_words=5)
    hits_before = corpus.build_corpus_model.cache_info().hits
    second = corpus.build_corpus_model(tmp_path, documents, min_paragraph_words=5)
    assert corpus.build_corpus_model.cache_info().hits == hits_before + 1
    assert first is second
    corpus.clear_corpus_cache()
    assert corpus.build_corpus_model.cache_info().currsize == 0
