"""Unit tests for the shared corpus module's text-level logic (paragraph extraction and markdown masking).

Paragraph extraction is driven through the ``text=`` argument so no files are read. Model building over
documents on disk is covered by ``tests/integration/test_corpus_model_ds202.py``.
"""

import pytest

pytest.importorskip("sklearn")

from docsentinel import models
from docsentinel.detectors.standard import corpus


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear corpus caches automatically before each test execution."""
    corpus.clear_corpus_cache()


def _extract(path: str, content: str, **kwargs: int) -> tuple[corpus.Paragraph, ...]:
    """Extract paragraphs from in-memory text attributed to a document path."""
    document = models.Document(path=path, bytes=len(content.encode("utf-8")))
    return corpus.extract_paragraphs(document, text=content, **kwargs)


def test_extract_paragraphs_splits_on_blank_lines():
    """
    [Unit] detectors corpus: verifies extract paragraphs splits on blank lines.

    Scenario:
        Given test inputs and fixtures for extract paragraphs splits on blank lines
        When test_extract_paragraphs_splits_on_blank_lines executes the target flow
        Then the expected outcome for extract paragraphs splits on blank lines is confirmed.

    Boundaries:
        - Focus: extract paragraphs splits on blank lines
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to extract paragraphs splits on blank lines
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors corpus
    """
    content = (
        "This is the first distinct paragraph with sufficient word count.\n"
        "It spans across two physical lines in the document.\n\n\n"
        "This is the second distinct paragraph which is also sufficiently long.\n"
        "It contains multiple descriptive terms and facts.\n"
    )

    paragraphs = _extract("split_test.md", content)

    assert len(paragraphs) == 2
    assert paragraphs[0].index == 0
    assert paragraphs[0].doc_path == "split_test.md"
    assert "first distinct paragraph" in paragraphs[0].text
    assert paragraphs[1].index == 1
    assert paragraphs[1].doc_path == "split_test.md"
    assert "second distinct paragraph" in paragraphs[1].text


def test_extract_paragraphs_ignores_code_blocks():
    """
    [Unit] detectors corpus: verifies extract paragraphs ignores code blocks.

    Scenario:
        Given test inputs and fixtures for extract paragraphs ignores code blocks
        When test_extract_paragraphs_ignores_code_blocks executes the target flow
        Then the expected outcome for extract paragraphs ignores code blocks is confirmed.

    Boundaries:
        - Focus: extract paragraphs ignores code blocks
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to extract paragraphs ignores code blocks
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors corpus
    """
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

    paragraphs = _extract("code_blocks.md", content)

    assert len(paragraphs) == 2
    for p in paragraphs:
        assert "ignored_code_function" not in p.text
        assert "rare_identifier_xyz" not in p.text
        assert "another ignored block" not in p.text
        assert "```" not in p.text
        assert "~~~" not in p.text


def test_extract_paragraphs_records_one_based_line_numbers():
    """
    [Unit] detectors corpus: verifies extract paragraphs records one based line numbers.

    Scenario:
        Given test inputs and fixtures for extract paragraphs records one based line numbers
        When test_extract_paragraphs_records_one_based_line_numbers executes the target flow
        Then the expected outcome for extract paragraphs records one based line numbers is confirmed.

    Boundaries:
        - Focus: extract paragraphs records one based line numbers
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to extract paragraphs records one based line numbers
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors corpus
    """
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

    paragraphs = _extract("line_numbers.md", content)

    assert len(paragraphs) == 2
    assert paragraphs[0].line == 3
    assert paragraphs[1].line == 11


def test_extract_paragraphs_skips_short_paragraphs():
    """
    [Unit] detectors corpus: verifies extract paragraphs skips short paragraphs.

    Scenario:
        Given test inputs and fixtures for extract paragraphs skips short paragraphs
        When test_extract_paragraphs_skips_short_paragraphs executes the target flow
        Then the expected outcome for extract paragraphs skips short paragraphs is confirmed.

    Boundaries:
        - Focus: extract paragraphs skips short paragraphs
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to extract paragraphs skips short paragraphs
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors corpus
    """
    content = (
        "# Short Header\n\n"
        "Too short.\n\n"
        "A few words.\n\n"
        "This is a proper and informative paragraph containing enough words to be analyzed.\n\n"
        "End note.\n"
    )

    paragraphs = _extract("short.md", content)

    assert len(paragraphs) == 1
    assert "proper and informative paragraph" in paragraphs[0].text
    assert paragraphs[0].index == 0


def test_extract_paragraphs_strips_html_comments_and_markdown():
    """
    [Unit] detectors corpus: verifies extract paragraphs strips html comments and markdown.

    Scenario:
        Given test inputs and fixtures for extract paragraphs strips html comments and markdown
        When test_extract_paragraphs_strips_html_comments_and_markdown executes the target flow
        Then the expected outcome for extract paragraphs strips html comments and markdown is confirmed.

    Boundaries:
        - Focus: extract paragraphs strips html comments and markdown
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to extract paragraphs strips html comments and markdown
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors corpus
    """
    content = (
        "<!-- Stray HTML comment that should not appear in prose -->\n\n"
        "Here is a paragraph with [hyperlink text](https://example.com/target) and `inline_code()`.\n"
        "It also features **bold text**, *italic text*, and <span class='tag'>HTML</span> elements.\n"
    )

    paragraphs = _extract("formatting.md", content)

    assert len(paragraphs) == 1
    text = paragraphs[0].text
    assert "Stray HTML comment" not in text
    assert "https://example.com/target" not in text
    assert "hyperlink text" in text
    assert "inline_code" not in text
    assert "<span" not in text
    assert "HTML" in text


def test_extract_paragraphs_honours_min_chars_and_min_words_overrides():
    """
    [Unit] detectors corpus: verifies extract paragraphs honours min chars and min words overrides.

    Scenario:
        Given test inputs and fixtures for extract paragraphs honours min chars and min words overrides
        When test_extract_paragraphs_honours_min_chars_and_min_words_overrides executes the target flow
        Then the expected outcome for extract paragraphs honours min chars and min words overrides is confirmed.

    Boundaries:
        - Focus: extract paragraphs honours min chars and min words overrides
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to extract paragraphs honours min chars and min words overrides
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors corpus
    """
    content = "Tiny paragraph here.\n\nAnother small one.\n"

    assert _extract("tiny.md", content) == ()

    relaxed = _extract("tiny.md", content, min_chars=0, min_words=1)
    assert [p.text for p in relaxed] == ["Tiny paragraph here.", "Another small one."]


def test_strip_markdown_markers_removes_links_images_quotes_and_list_markers():
    """
    [Unit] detectors corpus: verifies strip markdown markers removes links images quotes and list markers.

    Scenario:
        Given test inputs and fixtures for strip markdown markers removes links images quotes and list markers
        When test_strip_markdown_markers_removes_links_images_quotes_and_list_markers executes the target flow
        Then the expected outcome for strip markdown markers removes links images quotes and list markers is confirmed.

    Boundaries:
        - Focus: strip markdown markers removes links images quotes and list markers
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to strip markdown markers removes links images quotes and list markers
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors corpus
    """
    raw = "> Quoted [label](https://example.com) text\n- item ![logo](img.png) end\n## Heading"

    assert corpus._strip_markdown_markers(raw) == "Quoted label text item end Heading"


def test_strip_comments_blanks_comment_text_but_keeps_newlines():
    """
    [Unit] detectors corpus: verifies strip comments blanks comment text but keeps newlines.

    Scenario:
        Given test inputs and fixtures for strip comments blanks comment text but keeps newlines
        When test_strip_comments_blanks_comment_text_but_keeps_newlines executes the target flow
        Then the expected outcome for strip comments blanks comment text but keeps newlines is confirmed.

    Boundaries:
        - Focus: strip comments blanks comment text but keeps newlines
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to strip comments blanks comment text but keeps newlines
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors corpus
    """
    text = "before <!-- a\nb --> after\n"

    stripped = corpus._strip_comments(text)

    assert len(stripped) == len(text)
    assert stripped.count("\n") == text.count("\n")
    assert "<!--" not in stripped
    assert stripped.startswith("before ")
    assert stripped.rstrip().endswith("after")


def test_paragraph_preview_property():
    """
    [Unit] detectors corpus: verifies paragraph preview property.

    Scenario:
        Given test inputs and fixtures for paragraph preview property
        When test_paragraph_preview_property executes the target flow
        Then the expected outcome for paragraph preview property is confirmed.

    Boundaries:
        - Focus: paragraph preview property
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to paragraph preview property
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors corpus
    """
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


def test_build_corpus_model_empty_documents():
    """
    [Unit] detectors corpus: verifies build corpus model empty documents.

    Scenario:
        Given test inputs and fixtures for build corpus model empty documents
        When test_build_corpus_model_empty_documents executes the target flow
        Then the expected outcome for build corpus model empty documents is confirmed.

    Boundaries:
        - Focus: build corpus model empty documents
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to build corpus model empty documents
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors corpus
    """
    model = corpus.build_corpus_model(())

    assert model.documents == ()
    assert model.paragraphs == ()
    assert model.chunks == ()
    assert model.tfidf_matrix.shape == (0, 0)
    assert model.matrix.shape == (0, 0)
    assert model.vocabulary == {}
    assert model.idf is None
