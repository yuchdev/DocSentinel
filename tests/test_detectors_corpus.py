"""Unit tests for the shared corpus model and paragraph chunking module."""

from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("sklearn")

from docsentinel import models
from docsentinel.detectors.standard import corpus


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    corpus.clear_corpus_cache()


def _create_doc(tmp_path: Path, relative_path: str, content: str) -> models.Document:
    full_path = tmp_path / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return models.Document(path=relative_path, bytes=len(content.encode("utf-8")))


def test_extract_paragraphs_splits_on_blank_lines(tmp_path: Path) -> None:
    content = (
        "This is the first distinct paragraph with sufficient word count.\n"
        "It spans across two physical lines in the document.\n\n\n"
        "This is the second distinct paragraph which is also sufficiently long.\n"
        "It contains multiple descriptive terms and facts.\n"
    )
    doc = _create_doc(tmp_path, "split_test.md", content)
    paragraphs = corpus.extract_paragraphs(doc, root=tmp_path)

    assert len(paragraphs) == 2
    assert paragraphs[0].index == 0
    assert paragraphs[0].doc_path == "split_test.md"
    assert "first distinct paragraph" in paragraphs[0].text
    assert paragraphs[1].index == 1
    assert paragraphs[1].doc_path == "split_test.md"
    assert "second distinct paragraph" in paragraphs[1].text


def test_extract_paragraphs_ignores_code_blocks(tmp_path: Path) -> None:
    content = (
        "Here is valid documentation prose explaining how to execute functions.\n"
        "We describe the architecture clearly for engineers.\n\n"
        "```python\n"
        "def ignored_code_function():\n"
        "    rare_identifier_xyz = 12345\n"
        "    return 'should not be in corpus'\n"
        "```\n\n"
        "And here is another valid paragraph of prose following the code block.\n"
        "It provides additional helpful operational guidance.\n\n"
        "~~~bash\n"
        "echo 'another ignored block'\n"
        "~~~\n"
    )
    doc = _create_doc(tmp_path, "code_blocks.md", content)
    paragraphs = corpus.extract_paragraphs(doc, root=tmp_path)

    assert len(paragraphs) == 2
    for p in paragraphs:
        assert "ignored_code_function" not in p.text
        assert "rare_identifier_xyz" not in p.text
        assert "another ignored block" not in p.text
        assert "```" not in p.text
        assert "~~~" not in p.text


def test_extract_paragraphs_records_one_based_line_numbers(tmp_path: Path) -> None:
    content = (
        "# Title\n"  # Line 1 (short -> skipped)
        "\n"  # Line 2
        "This is paragraph one starting at line three of the document.\n"  # Line 3
        "It continues on line four with informative text.\n"  # Line 4
        "\n"  # Line 5
        "```python\n"  # Line 6
        "x = 1\n"  # Line 7
        "y = 2\n"  # Line 8
        "```\n"  # Line 9
        "\n"  # Line 10
        "This is paragraph two starting on line eleven following the code.\n"  # Line 11
        "It also carries enough tokens to pass the minimum threshold.\n"  # Line 12
    )
    doc = _create_doc(tmp_path, "line_numbers.md", content)
    paragraphs = corpus.extract_paragraphs(doc, root=tmp_path)

    assert len(paragraphs) == 2
    assert paragraphs[0].line == 3
    assert paragraphs[1].line == 11


def test_extract_paragraphs_skips_short_paragraphs(tmp_path: Path) -> None:
    content = (
        "# Short Header\n\n"
        "Too short.\n\n"
        "A few words.\n\n"
        "This is a proper and informative paragraph containing enough words to be analyzed.\n\n"
        "End note.\n"
    )
    doc = _create_doc(tmp_path, "short.md", content)
    paragraphs = corpus.extract_paragraphs(doc, root=tmp_path)

    assert len(paragraphs) == 1
    assert "proper and informative paragraph" in paragraphs[0].text
    assert paragraphs[0].index == 0


def test_extract_paragraphs_strips_html_comments_and_markdown(tmp_path: Path) -> None:
    content = (
        "<!-- Stray HTML comment that should not appear in prose -->\n\n"
        "Here is a paragraph with [hyperlink text](https://example.com/target) and `inline_code()`.\n"
        "It also features **bold text**, *italic text*, and <span class='tag'>HTML</span> elements.\n"
    )
    doc = _create_doc(tmp_path, "formatting.md", content)
    paragraphs = corpus.extract_paragraphs(doc, root=tmp_path)

    assert len(paragraphs) == 1
    text = paragraphs[0].text
    assert "Stray HTML comment" not in text
    assert "https://example.com/target" not in text
    assert "hyperlink text" in text
    assert "inline_code" not in text
    assert "<span" not in text
    assert "HTML" in text


def test_paragraph_preview_property() -> None:
    paragraph = corpus.Paragraph(
        doc_path="guide.md",
        index=0,
        text="First line of paragraph text.\nSecond line of paragraph text with extra details.",
        line=1,
    )
    assert paragraph.path == "guide.md"
    assert "\n" not in paragraph.preview
    assert len(paragraph.preview) <= 60
    assert paragraph.preview == "First line of paragraph text. Second line of paragraph text "


def test_build_corpus_model_empty_documents() -> None:
    model = corpus.build_corpus_model(())

    assert model.documents == ()
    assert model.paragraphs == ()
    assert model.chunks == ()
    assert model.tfidf_matrix.shape == (0, 0)
    assert model.matrix.shape == (0, 0)
    assert model.vocabulary == {}
    assert model.idf is None


def test_build_corpus_model_single_document(tmp_path: Path) -> None:
    content = (
        "DocSentinel provides deterministic documentation quality assurance.\n"
        "It inspects markdown links, text complexity, and corpus statistics.\n\n"
        "The standard profile includes duplicate paragraph and low information detectors.\n"
        "All detectors produce actionable finding objects with diagnostic messages.\n"
    )
    doc = _create_doc(tmp_path, "overview.md", content)
    model = corpus.build_corpus_model(tmp_path, (doc,))

    assert len(model.documents) == 1
    assert len(model.paragraphs) == 2
    assert model.tfidf_matrix.shape[0] == 2
    assert model.tfidf_matrix.shape[1] > 0
    assert len(model.vocabulary) > 0
    assert model.idf is not None
    assert len(model.idf) == model.tfidf_matrix.shape[1]


def test_build_corpus_model_multi_document_matrix_shape(tmp_path: Path) -> None:
    doc1_content = (
        "Architectural components handle document discovery and invariant verification.\n"
        "Each engine pass runs deterministic analyzers in sequence across documents.\n"
    )
    doc2_content = (
        "Configuration conventions allow tuning thresholds for grade level and similarity.\n"
        "Invalid configurations raise informative errors early during initialization.\n"
    )
    doc1 = _create_doc(tmp_path, "arch.md", doc1_content)
    doc2 = _create_doc(tmp_path, "config.md", doc2_content)

    model = corpus.build_corpus_model(tmp_path, (doc1, doc2))

    assert len(model.documents) == 2
    assert len(model.paragraphs) == 2
    assert model.tfidf_matrix.shape[0] == 2
    assert model.paragraphs[0].doc_path == "arch.md"
    assert model.paragraphs[1].doc_path == "config.md"


def test_build_corpus_model_deterministic(tmp_path: Path) -> None:
    doc1_content = (
        "First document prose describing repository maintenance workflows.\n"
        "Includes instructions for running unit tests and linters.\n"
    )
    doc2_content = (
        "Second document prose describing release management procedures.\n"
        "Details version bumping and package distribution steps.\n"
    )
    doc1 = _create_doc(tmp_path, "a.md", doc1_content)
    doc2 = _create_doc(tmp_path, "b.md", doc2_content)

    corpus.build_corpus_model.cache_clear()
    model1 = corpus.build_corpus_model(tmp_path, (doc2, doc1))
    corpus.build_corpus_model.cache_clear()
    model2 = corpus.build_corpus_model(tmp_path, (doc1, doc2))

    assert [p.doc_path for p in model1.paragraphs] == [p.doc_path for p in model2.paragraphs]
    assert [p.text for p in model1.paragraphs] == [p.text for p in model2.paragraphs]
    assert model1.vocabulary == model2.vocabulary
    assert (model1.tfidf_matrix.toarray() == model2.tfidf_matrix.toarray()).all()


def test_build_corpus_model_fits_once(tmp_path: Path) -> None:
    content = "DocSentinel verifies documentation quality deterministically using TF-IDF statistics."
    doc = _create_doc(tmp_path, "doc.md", content)

    corpus.build_corpus_model.cache_clear()
    with patch.object(
        corpus.TfidfVectorizer, "fit_transform", autospec=True, side_effect=corpus.TfidfVectorizer.fit_transform
    ) as mock_fit:
        model = corpus.build_corpus_model(tmp_path, (doc,))
        assert mock_fit.call_count == 1
        assert model.tfidf_matrix.shape[0] == 1


def test_build_corpus_model_is_cached_for_identical_inputs(tmp_path: Path) -> None:
    content = (
        "DocSentinel provides deterministic documentation quality assurance.\n"
        "It inspects markdown links, text complexity, and corpus statistics.\n"
    )
    doc = _create_doc(tmp_path, "doc.md", content)
    corpus.build_corpus_model.cache_clear()
    with patch.object(
        corpus.TfidfVectorizer, "fit_transform", autospec=True, side_effect=corpus.TfidfVectorizer.fit_transform
    ) as mock_fit:
        model1 = corpus.build_corpus_model(tmp_path, (doc,))
        model2 = corpus.build_corpus_model(tmp_path, (doc,))
        assert model1 is model2
        assert mock_fit.call_count == 1
    corpus.build_corpus_model.cache_clear()


def test_cache_busts_on_changed_documents(tmp_path: Path) -> None:
    content1 = "DocSentinel provides deterministic documentation quality assurance with unique content."
    content2 = "DocSentinel provides deterministic documentation quality assurance with altered contents."
    doc1 = _create_doc(tmp_path, "doc1.md", content1)
    doc2 = _create_doc(tmp_path, "doc2.md", content2)
    corpus.build_corpus_model.cache_clear()
    model1 = corpus.build_corpus_model(tmp_path, (doc1,))
    model2 = corpus.build_corpus_model(tmp_path, (doc2,))
    assert model1 is not model2
    corpus.build_corpus_model.cache_clear()


def test_build_corpus_model_all_code_returns_empty_model(tmp_path: Path) -> None:
    code_content = "```python\ndef only_code():\n    return 42\n```\n"
    doc = _create_doc(tmp_path, "code_only.md", code_content)
    model = corpus.build_corpus_model(tmp_path, (doc,))

    assert model.paragraphs == ()
    assert model.tfidf_matrix.shape == (0, 0)
    assert model.vocabulary == {}


def test_iter_chunks_helper(tmp_path: Path) -> None:
    content = (
        "This is paragraph one with at least twenty words to satisfy the chunk threshold for DS202 and DS203 detectors properly.\n\n"
        "Short paragraph.\n\n"
        "This is paragraph two which also has enough descriptive prose words to pass the twenty words requirement easily without issues.\n"
    )
    doc = _create_doc(tmp_path, "chunks.md", content)
    chunks = corpus.iter_chunks(tmp_path, (doc,), min_words=20)

    assert len(chunks) == 2
    assert chunks[0].index == 0
    assert chunks[1].index == 1
