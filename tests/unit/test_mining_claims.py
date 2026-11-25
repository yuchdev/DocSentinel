"""Unit tests for triple key and number normalization (no NLP model required).

Claim extraction over documents is covered by ``tests/integration/test_mining_claims_ds301.py``.
"""

from docsentinel.mining.claims import (
    _GLUE_CONNECTIVES,
    _RESULT_CONNECTIVES,
    _is_quotation,
    _leading_connective,
    _normalize_key,
    _object_numbers,
    _prose_blocks,
    _statement_text,
    _strip_inline_markdown,
)


def test_subject_key_ignores_articles_and_case():
    """
    [Unit] detectors triples: verifies subject key ignores articles and case.

    Scenario:
        Given test inputs and fixtures for subject key ignores articles and case
        When test_subject_key_ignores_articles_and_case executes the target flow
        Then the expected outcome for subject key ignores articles and case is confirmed.

    Boundaries:
        - Focus: subject key ignores articles and case
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to subject key ignores articles and case
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors triples
    """
    assert _normalize_key("The Cache") == "cache"
    assert _normalize_key("a cache") == "cache"
    assert _normalize_key("an engine") == "engine"
    assert _normalize_key("  the   Distributed   Database... ") == "distributed database"


def test_number_normalization():
    """
    [Unit] detectors triples: verifies number normalization.

    Scenario:
        Given test inputs and fixtures for number normalization
        When test_number_normalization executes the target flow
        Then the expected outcome for number normalization is confirmed.

    Boundaries:
        - Focus: number normalization
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to number normalization
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors triples
    """

    class DummyToken:
        """Dummy token class for mocking spacy token properties."""

        def __init__(self, text: str, like_num: bool = True):
            """Initialize dummy token with text and numeric property."""
            self.text = text
            self.like_num = like_num

    assert _object_numbers([DummyToken("1,024")]) == ("1024",)
    assert _object_numbers([DummyToken("ten")]) == ("10",)
    assert _object_numbers([DummyToken("42")]) == ("42",)


def test_strip_inline_markdown_keeps_code_verbatim_and_records_its_offsets():
    """
    [Unit] mining statements: verifies inline Markdown is removed and code spans keep their text and offsets.

    Scenario:
        Given a run with a label, emphasis, a link, an image and inline code holding emphasis syntax
        When _strip_inline_markdown runs
        Then the label, markers, link target and image are gone, the code text is verbatim and its
        offsets point at it

    Boundaries:
        - Focus: _strip_inline_markdown
        - Fixtures/params: inline string
        - Scope: no NLP model

    On failure, first check:
        - The placeholder parking of inline code in _strip_inline_markdown
    """
    text, spans = _strip_inline_markdown("Note: the **fast** [guide](x.md) ![logo](l.png) calls  `run(**kw)`\n now.")

    assert text == "the fast guide calls run(**kw) now."
    assert [text[start:end] for start, end in spans] == ["run(**kw)"]


def test_prose_blocks_drop_structure_and_split_at_boundaries():
    """
    [Unit] mining statements: verifies headings, pseudo-headings, fences and front matter are dropped as boundaries.

    Scenario:
        Given front matter, an ATX heading, a bold pseudo-heading, a list item, a fence inside a
        paragraph and a closing paragraph
        When _prose_blocks runs
        Then only prose remains, the list marker is stripped, text on either side of the fence is
        two blocks, and each structural line leaves an empty boundary block (or marks the prose
        after it in the same paragraph) so no sentence refers back across it

    Boundaries:
        - Focus: _prose_blocks
        - Fixtures/params: inline string
        - Scope: no NLP model

    On failure, first check:
        - The per-line classification and _flush in _prose_blocks
    """
    text = (
        "---\ntitle: x\n---\n\n# Title\n\n**Section**\n\n- The list item is prose.\n\n"
        "Before the fence.\n```\ncode = 1\n```\nAfter the fence.\n\nLast paragraph\nwrapped.\n"
    )

    blocks = [(b.index, b.text, b.boundary) for b in _prose_blocks(text)]

    assert blocks == [
        (0, "", True),
        (1, "", True),
        (2, "", True),
        (3, "The list item is prose.", False),
        (4, "Before the fence.", False),
        (4, "", True),
        (4, "After the fence.", True),
        (5, "Last paragraph wrapped.", False),
    ]


def test_quotation_and_statement_text_rules():
    """
    [Unit] mining statements: verifies quotation detection and the leading-filler rule of statement text.

    Scenario:
        Given quoted, mostly quoted and plain sentences, and statements opening with a filler or an identifier
        When _is_quotation and _statement_text run
        Then quotes are recognised, a filler is removed and the next word capitalized, and an
        identifier at the start keeps its case

    Boundaries:
        - Focus: _is_quotation, _statement_text
        - Fixtures/params: inline strings
        - Scope: no NLP model

    On failure, first check:
        - _QUOTE_PAIR and _LEADING_FILLER
    """
    assert _is_quotation('"We were able to guide the fields," says Niendorf.')
    assert _is_quotation('He said "the antenna is compatible with every scanner" today.')
    assert not _is_quotation('The antenna, called "Iris", is compatible with existing scanners.')
    assert _statement_text(["Now, a team has built an antenna.", "Its weight is 2 kg."]) == (
        "A team has built an antenna. Its weight is 2 kg."
    )
    assert _statement_text(["scan() returns a ScanResult."]) == "scan() returns a ScanResult."


def test_leading_connective_distinguishes_glue_from_consequence_and_needs_a_comma_for_plain_words():
    """
    [Unit] mining statements: verifies the sentence-initial connective match and its comma rule.

    Scenario:
        Given sentences opening with a multi-word glue connective, a result connective, a one-word
        connective that is also an ordinary word with and without a comma, and a plain sentence
        When _leading_connective runs against the glue and the result tables
        Then the glue and result connectives are told apart, "Still," counts while "Still images"
        does not, "Yet" counts without a comma, and a plain sentence matches nothing

    Boundaries:
        - Focus: _leading_connective
        - Fixtures/params: inline strings
        - Scope: no NLP model

    On failure, first check:
        - The ``needs_comma`` flags in _GLUE_CONNECTIVES and _RESULT_CONNECTIVES
    """
    assert _leading_connective("In addition, the crane weighs 40 tonnes.", _GLUE_CONNECTIVES) == "in addition"
    assert _leading_connective("In addition, the crane weighs 40 tonnes.", _RESULT_CONNECTIVES) is None
    assert _leading_connective("As a result, the quay needed new rails.", _RESULT_CONNECTIVES) == "as a result"
    assert _leading_connective("Still, the quay needed new rails.", _GLUE_CONNECTIVES) == "still"
    assert _leading_connective("Still images need 2 MB each.", _GLUE_CONNECTIVES) is None
    assert _leading_connective("Yet even today the quay is busy.", _GLUE_CONNECTIVES) == "yet"
    assert _leading_connective("So far the quay handled 45 ferries.", _RESULT_CONNECTIVES) is None
    assert _leading_connective("The quay handled 45 ferries.", _GLUE_CONNECTIVES) is None
