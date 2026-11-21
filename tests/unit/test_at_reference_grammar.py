"""Unit tests for the shared scanner's ``@``-document mention grammar.

These pin the normative "At-reference grammar" of Milestone 0009 Story 01.0
(including the examples block and threat-model amendment A2) as implemented by
:func:`docsentinel.markdown_blocks.scan_markdown`: both forms, the three kinds,
every rejection rule, punctuation stripping, the escaped-space decoding (M12, M13),
the 1,024-character cap (M8), the exclusion masks (M19), positions, and that the
new :attr:`MarkdownBlockIndex.at_references` field leaves every existing field
unchanged. Timing guards live in ``test_at_reference_grammar_timing.py``.
"""

from __future__ import annotations

import dataclasses

import pytest

from docsentinel import markdown_blocks as mb

#: The grammar alphabet of a decoded target: the token characters plus U+0020.
_TARGET_CHARSET = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._~+-/ ")


def _mentions(text: str) -> tuple[mb.AtReference, ...]:
    """Return the ``@``-mentions the scanner records for ``text``.

    :param text: Markdown source.
    :returns: The recorded mentions in source order.
    """
    return mb.scan_markdown(text, "doc.md").at_references


def _targets(text: str) -> list[str]:
    """Return the decoded targets of every recorded mention of ``text``.

    :param text: Markdown source.
    :returns: Targets in source order.
    """
    return [mention.target for mention in _mentions(text)]


# --- examples block -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "target", "raw", "kind"),
    (
        ("@docs/dev/python_coding_standard.md", "docs/dev/python_coding_standard.md", None, "relative"),
        ("(@AGENTS.md)", "AGENTS.md", None, "relative"),
        ('"@Design\\ Docs/x.md"', "Design Docs/x.md", "@Design\\ Docs/x.md", "relative"),
        ("@~/notes/me.md", "~/notes/me.md", None, "home"),
        ("@/etc/hosts.txt", "/etc/hosts.txt", None, "absolute"),
        ("@example.com", "example.com", None, "relative"),
    ),
    ids=("relative_path", "parenthesised", "escaped_space", "home", "absolute", "extension_filtered_later"),
)
def test_examples_block_recognised_rows(text: str, target: str, raw: str, kind: str):
    """
    [Unit] at-reference grammar: each recognised row of the examples block is recorded.

    Scenario:
        Given one recognised example of the README examples block on its own line
        When the shared scanner scans it
        Then exactly one prose mention is recorded with the expected target, raw and kind
            (``@example.com`` is recorded too: extension filtering is the consumer's job).

    Boundaries:
        - Focus: the "Recognised", "never resolved" and "Filtered by extension" rows
        - Fixtures/params: one row per case

    On failure, first check:
        - _at_token (kind classification, decoding) and _AT_BOUNDARY_CHARS
    """
    (mention,) = _mentions(text)

    assert mention.target == target
    assert mention.raw == (raw if raw is not None else "@" + target)
    assert mention.kind == kind
    assert mention.in_code_span is False


def test_examples_block_full_recognised_line():
    """
    [Unit] at-reference grammar: the examples block "Recognised (relative)" line yields three mentions.

    Scenario:
        Given the literal recognised line of the examples block
        When it is scanned
        Then the three relative mentions are recorded in source order.

    Boundaries:
        - Focus: several mentions on one line, source order
        - Fixtures/params: none

    On failure, first check:
        - The resume offset of _find_prose_at_references
    """
    line = 'Recognised (relative):     @docs/dev/python_coding_standard.md    (@AGENTS.md)    "@Design\\ Docs/x.md"'

    assert _targets(line) == ["docs/dev/python_coding_standard.md", "AGENTS.md", "Design Docs/x.md"]


def test_examples_block_code_span_row():
    """
    [Unit] at-reference grammar: the code-span row is recorded with in_code_span=True.

    Scenario:
        Given the code-span example of the examples block
        When it is scanned
        Then one mention is recorded whose span is exactly the inline-code span.

    Boundaries:
        - Focus: code-span form and span identity with InlineCode (DS116 matching, A1)
        - Fixtures/params: none

    On failure, first check:
        - _code_span_at_reference and the span passed in scan_markdown
    """
    index = mb.scan_markdown("Code-span form: `@docs/dev/python_coding_standard.md`", "doc.md")

    (mention,) = index.at_references
    (code,) = index.inline_code
    assert mention.target == "docs/dev/python_coding_standard.md"
    assert mention.raw == "@docs/dev/python_coding_standard.md"
    assert mention.kind == "relative"
    assert mention.in_code_span is True
    assert mention.span == code.span


@pytest.mark.parametrize(
    "text",
    ("user@example.org", "@octocat", "@types/node", "@1.2.3", "\\@docs/x.md"),
    ids=("email", "handle", "scoped_package", "version", "backslash_escape"),
)
def test_examples_block_not_recognised_rows(text: str):
    """
    [Unit] at-reference grammar: every "Not recognised" example records nothing.

    Scenario:
        Given one "Not recognised" example of the examples block
        When it is scanned
        Then no mention is recorded.

    Boundaries:
        - Focus: letter-before-@ rejection, missing or letterless extension, backslash escape
        - Fixtures/params: one row per case

    On failure, first check:
        - _AT_BOUNDARY_CHARS and the extension check in _at_token
    """
    assert _mentions(text) == ()


def test_examples_block_not_recognised_line():
    """
    [Unit] at-reference grammar: the full "Not recognised" line of the examples block records nothing.

    Scenario:
        Given the literal "Not recognised" line
        When it is scanned
        Then no mention is recorded.

    Boundaries:
        - Focus: the row as written in the README
        - Fixtures/params: none

    On failure, first check:
        - Boundary checks reading the source line, not the masked line
    """
    line = "Not recognised:            user@example.org   @octocat   @types/node   @1.2.3   \\@docs/x.md"

    assert _mentions(line) == ()


# --- boundaries and rejections --------------------------------------------------------


@pytest.mark.parametrize("prefix", ("", " ", "\t", "(", "[", '"', "'"), ids=repr)
def test_accepted_boundaries(prefix: str):
    """
    [Unit] at-reference grammar: an ``@`` at line start or after the six boundary characters is recognised.

    Scenario:
        Given ``x`` (or nothing) then a boundary character then ``@a.md``
        When it is scanned
        Then one mention ``a.md`` is recorded.

    Boundaries:
        - Focus: line start, space, tab and the four opening characters
        - Fixtures/params: one per boundary

    On failure, first check:
        - _AT_BOUNDARY_CHARS
    """
    text = ("x" + prefix if prefix else "") + "@a.md"

    assert _targets(text) == ["a.md"]


@pytest.mark.parametrize(
    "prefix",
    ("x", "Z", "7", "@", "\\", "*", "_", "`", ">", "-", "/", ":", "\u00e9"),
    ids=repr,
)
def test_rejected_boundaries(prefix: str):
    """
    [Unit] at-reference grammar: an ``@`` after any other character is not a mention.

    Scenario:
        Given a non-boundary character immediately before ``@a.md``
        When it is scanned
        Then nothing is recorded.

    Boundaries:
        - Focus: letter, digit, ``@``, backslash, emphasis and other punctuation, non-ASCII letter
        - Fixtures/params: one per preceding character

    On failure, first check:
        - _find_prose_at_references reads content[position - 1]
    """
    assert _mentions("see " + prefix + "@a.md") == ()


@pytest.mark.parametrize("space", ("\u00a0", "\u2003", "\u3000", "\u2028", "\u200b", "\x0b", "\x0c"), ids=repr)
def test_unicode_space_before_at_not_a_boundary(space: str):
    """
    [Unit] at-reference grammar: Unicode or non-tab ASCII spacing before ``@`` is not a boundary (M19).

    Scenario:
        Given a non-ASCII space (or vertical tab / form feed) immediately before ``@a.md``
        When it is scanned
        Then nothing is recorded, because only ASCII space and tab count as whitespace.

    Boundaries:
        - Focus: recognition never depends on str.isspace() Unicode tables
        - Fixtures/params: NBSP, EM SPACE, IDEOGRAPHIC SPACE, LINE SEPARATOR, ZWSP, VT, FF

    On failure, first check:
        - _AT_BOUNDARY_CHARS must stay an explicit ASCII set
    """
    assert _mentions("x" + space + "@a.md") == ()


def test_inside_fenced_code_not_recognised():
    """
    [Unit] at-reference grammar: mentions inside fenced code blocks are ignored.

    Scenario:
        Given ``@a.md`` inside a backtick fence and a tilde fence, and ``@b.md`` after them
        When the document is scanned
        Then only ``b.md`` is recorded.

    Boundaries:
        - Focus: fenced-line skip
        - Fixtures/params: none

    On failure, first check:
        - The fenced[index] guard in scan_markdown
    """
    text = "```\n@a.md\n```\n~~~md\n(@a.md)\n~~~\n@b.md\n"

    assert _targets(text) == ["b.md"]


def test_inside_html_comment_not_recognised():
    """
    [Unit] at-reference grammar: mentions inside closed and multi-line HTML comments are ignored.

    Scenario:
        Given an inline comment, a multi-line comment and a mention after each
        When the document is scanned
        Then only the mentions outside the comments are recorded.

    Boundaries:
        - Focus: reuse of the CommonMark-accurate comment mask
        - Fixtures/params: none

    On failure, first check:
        - The masked-line ``@`` search in _find_prose_at_references
    """
    text = "x <!-- @a.md --> @b.md\n<!--\n@c.md\n-->\n@d.md\n"

    assert _targets(text) == ["b.md", "d.md"]


def test_mention_after_unclosed_midline_comment_opener_recognised():
    """
    [Unit] at-reference grammar: an unclosed mid-line ``<!--`` does not hide later mentions (M19).

    Scenario:
        Given a paragraph with a mid-line ``<!--`` and no ``-->``, then a mention, then another paragraph
        When it is scanned
        Then both mentions are recorded, because CommonMark renders that opener as text.

    Boundaries:
        - Focus: no over-masking (DS116-TM comment-masking evasion ruling)
        - Fixtures/params: none

    On failure, first check:
        - _scan_comments mid-line paragraph bound
    """
    text = "text <!-- oops @a.md\n\nlater @b.md\n"

    assert _targets(text) == ["a.md", "b.md"]


def test_mention_after_code_span_containing_comment_opener_recognised():
    """
    [Unit] at-reference grammar: a ``<!--`` inside a code span masks nothing after it (M19).

    Scenario:
        Given a code span holding ``<!--`` followed on the same and next line by mentions
        When it is scanned
        Then both mentions are recorded.

    Boundaries:
        - Focus: code spans are literal and can never open an HTML comment
        - Fixtures/params: none

    On failure, first check:
        - _comment_mask blanks code spans before searching for comment openers
    """
    text = "write `<!--` then @a.md\n@b.md\n"

    assert _targets(text) == ["a.md", "b.md"]


@pytest.mark.parametrize(
    "text",
    (
        "[@a.md](x.md)",
        "[see @a.md](x.md)",
        "[x](@a.md)",
        "[x]( @a.md)",
        "![@a.md](x.png)",
        "![alt](<@a.md>)",
        "[![@a.md](i.png)](x.md)",
        "[x][@a.md]",
        "[@a.md][]",
        "[@a.md]: target.md",
        '<span title="x @a.md">',
        "<a href='@a.md'>x</a>",
        "<img src=x alt='(@a.md)'>",
        "</div @a.md>",
        "`@a.md b`",
        "`x @a.md`",
    ),
    ids=(
        "link_text_start",
        "link_text_mid",
        "link_destination",
        "link_destination_space",
        "image_alt",
        "image_angle_destination",
        "nested_image_in_link",
        "full_reference_label",
        "collapsed_reference_label",
        "reference_definition_label",
        "html_tag_attribute",
        "html_anchor_href",
        "html_img_attribute",
        "html_closing_tag",
        "code_span_with_space",
        "code_span_text_before",
    ),
)
def test_excluded_contexts_not_recognised(text: str):
    """
    [Unit] at-reference grammar: no mention in link text, destinations, labels, raw HTML tags or partial code spans.

    Scenario:
        Given a mention placed in one excluded context
        When it is scanned
        Then nothing is recorded.

    Boundaries:
        - Focus: every "Never recognised" context of the grammar
        - Fixtures/params: one per context

    On failure, first check:
        - The ``excluded`` ranges built in scan_markdown, _find_html_tags, _code_span_at_reference
    """
    assert _mentions(text) == ()


def test_mention_beside_excluded_context_still_recognised():
    """
    [Unit] at-reference grammar: exclusions cover only their own range on the line.

    Scenario:
        Given mentions before and after a link, a reference use, an HTML tag and a code span
        When the line is scanned
        Then every mention outside those ranges is recorded.

    Boundaries:
        - Focus: no over-masking beyond the README exclusions (M19)
        - Fixtures/params: none

    On failure, first check:
        - _merge_ranges and the forward pointer in _find_prose_at_references
    """
    text = "@a.md [x](y.md) @b.md [t][r] @c.md <b>bold</b> @d.md `code` @e.md a < b @f.md"

    assert _targets(text) == ["a.md", "b.md", "c.md", "d.md", "e.md", "f.md"]


def test_full_reference_text_is_not_a_label():
    """
    [Unit] at-reference grammar: the text bracket of a full reference use is not a label.

    Scenario:
        Given ``[@a.md][ref]`` (the mention is the text, ``ref`` is the label)
        When it is scanned
        Then ``a.md`` is recorded, because only the label is excluded by the grammar.

    Boundaries:
        - Focus: literal reading of "a reference-style link label" (no extra mask, M19)
        - Fixtures/params: none

    On failure, first check:
        - The label range computed for reference uses in scan_markdown
    """
    assert _targets("[@a.md][ref]") == ["a.md"]


def test_autolink_and_comment_opener_are_not_html_tags():
    """
    [Unit] at-reference grammar: ``<`` that does not open a tag masks nothing.

    Scenario:
        Given an autolink, a declaration-like ``<!x`` and a lone ``<`` before mentions
        When scanned
        Then the mentions are recorded.

    Boundaries:
        - Focus: _find_html_tags tag shape
        - Fixtures/params: none

    On failure, first check:
        - _find_html_tags requires a letter and then whitespace, ``/`` or ``>``
    """
    text = "<https://x.org> @a.md <!x @b.md> <3 @c.md"

    assert _targets(text) == ["a.md", "b.md", "c.md"]


# --- token shape ----------------------------------------------------------------------


@pytest.mark.parametrize("punct", (".", ",", ";", ":", "!", "?", "...", ".!?", ".,"), ids=repr)
def test_trailing_punctuation_stripped(punct: str):
    """
    [Unit] at-reference grammar: trailing dots, commas, semicolons, colons, ``!`` and ``?`` are stripped.

    Scenario:
        Given ``see @a.md`` followed by trailing punctuation
        When scanned
        Then the target and raw exclude the punctuation and the span ends before it.

    Boundaries:
        - Focus: punctuation strip
        - Fixtures/params: each punctuation character and some runs

    On failure, first check:
        - _AT_TRAILING_PUNCTUATION
    """
    (mention,) = _mentions("see @a.md" + punct)

    assert mention.target == "a.md"
    assert mention.raw == "@a.md"
    assert mention.span.end_offset - mention.span.start_offset == len("@a.md")


@pytest.mark.parametrize(
    "stop", ("#", "%", "\\x", ")", "]", '"', "'", ">", "<", "*", "=", "&", "|", "\u202e"), ids=repr
)
def test_token_ends_at_non_token_character(stop: str):
    """
    [Unit] at-reference grammar: any non-token character ends the token; ``#`` and ``%`` are never decoded.

    Scenario:
        Given ``@a.md`` immediately followed by a non-token character and more text
        When scanned
        Then the target is ``a.md`` exactly.

    Boundaries:
        - Focus: token alphabet, fragment and percent termination
        - Fixtures/params: one per stop character

    On failure, first check:
        - _AT_TOKEN_CHARS and _consume_at_token
    """
    assert _targets("(@a.md" + stop + "rest.txt") == ["a.md"]


@pytest.mark.parametrize(
    "text",
    ("@README", "@v1.2", "@a.1", "@a/b.c/d", "@.bashrc", "@~/.profile", "@a.", "@..", "@../..", "@", "@ a.md"),
    ids=repr,
)
def test_extension_must_contain_a_letter(text: str):
    """
    [Unit] at-reference grammar: a token is recorded only when its last component has a letter-bearing extension.

    Scenario:
        Given a token with no extension, a digit-only extension, an extension on a parent only,
            a hidden file, or no token at all
        When scanned
        Then nothing is recorded.

    Boundaries:
        - Focus: the "version strings are not mentions" rule
        - Fixtures/params: one per shape

    On failure, first check:
        - The last-component extension check in _at_token
    """
    assert _mentions(text) == ()


@pytest.mark.parametrize(
    ("text", "kind"),
    (
        ("@a.md", "relative"),
        ("@./a.md", "relative"),
        ("@../a.md", "relative"),
        ("@~a.md", "relative"),
        ("@~/a.md", "home"),
        ("@/a.md", "absolute"),
        ("@//a.md", "absolute"),
    ),
    ids=repr,
)
def test_kind_classification(text: str, kind: str):
    """
    [Unit] at-reference grammar: kind is ``home`` for ``~/``, ``absolute`` for ``/``, else ``relative``.

    Scenario:
        Given a mention starting with each prefix
        When scanned
        Then its kind matches the grammar's classification.

    Boundaries:
        - Focus: kind classification
        - Fixtures/params: one per prefix

    On failure, first check:
        - _at_token kind branch
    """
    (mention,) = _mentions(text)

    assert mention.kind == kind


def test_escaped_space_decodes_to_space_only():
    """
    [Unit] at-reference grammar: each backslash-space pair decodes to one space, nothing else (M12).

    Scenario:
        Given a token with several escaped spaces, including adjacent ones
        When scanned
        Then each pair becomes exactly one U+0020 in target and raw keeps the escapes as written.

    Boundaries:
        - Focus: literal, single-pass decode
        - Fixtures/params: none

    On failure, first check:
        - The str.replace in _at_token
    """
    (mention,) = _mentions("@My\\ Docs/a\\ \\ b.md")

    assert mention.target == "My Docs/a  b.md"
    assert mention.raw == "@My\\ Docs/a\\ \\ b.md"
    assert "\\" not in mention.target


@pytest.mark.parametrize(
    ("text", "target"),
    (
        ("@a.md\\nb.txt", "a.md"),
        ("@a.md\\tb.txt", "a.md"),
        ("@a.md\\\\ b.txt", "a.md"),
        ("@a.md\\", "a.md"),
        ("@a.md\\\tb.txt", "a.md"),
        ("@a.md\\u0041.txt", "a.md"),
        ("@a.md\\x41.txt", "a.md"),
        ("@a.md\\&amp;.txt", "a.md"),
        ("@a.md\\%41.txt", "a.md"),
    ),
    ids=repr,
)
def test_backslash_other_character_ends_token(text: str, target: str):
    """
    [Unit] at-reference grammar: a backslash not followed by a space ends the token and is never decoded (M12).

    Scenario:
        Given a token followed by a backslash and a character other than a space (or end of line)
        When scanned
        Then the token ends before the backslash and the target holds no decoded character.

    Boundaries:
        - Focus: no unicode_escape, regex substitution or html.unescape semantics
        - Fixtures/params: escape-like sequences after a backslash

    On failure, first check:
        - The backslash branch of _consume_at_token
    """
    (mention,) = _mentions(text)

    assert mention.target == target
    assert mention.raw == "@" + target


def test_decoded_target_charset():
    """
    [Unit] at-reference grammar: an exhaustive sweep keeps every decoded target inside the alphabet plus U+0020 (M12).

    Scenario:
        Given, for every ASCII and C1 code point, that character placed after a backslash inside a token,
            and every alphabet character inside a token
        When each is scanned
        Then every recorded target contains only alphabet characters and U+0020, and a backslash
            appears in raw only as part of a backslash-space pair.

    Boundaries:
        - Focus: decoded charset bound
        - Fixtures/params: code points U+0000 to U+009F

    On failure, first check:
        - _consume_at_token and the decode in _at_token
    """
    for code_point in range(0xA0):
        char = chr(code_point)
        for text in (f"@x{char}.md", f"@x\\{char}y.md", f"@x.md\\{char}", f"@a\\ x{char}b.md"):
            for mention in _mentions(text):
                assert set(mention.target) <= _TARGET_CHARSET, (code_point, text, mention)
                assert mention.raw.replace("\\ ", "").count("\\") == 0, (code_point, text, mention)
                assert mention.raw.isascii()


def test_backslash_space_inside_token_after_sweep_is_space():
    """
    [Unit] at-reference grammar: only the space after a backslash survives as part of the target.

    Scenario:
        Given ``@x\\ y.md`` (the sweep's U+0020 case) on its own
        When scanned
        Then the target is ``x y.md``.

    Boundaries:
        - Focus: the single admitted escape
        - Fixtures/params: none

    On failure, first check:
        - _AT_ESCAPED_SPACE
    """
    assert _targets("@x\\ y.md") == ["x y.md"]


@pytest.mark.parametrize(
    "text",
    ("@\\ a.md", "@a.md\\ ", "@a.md\\ .", "@a.md\\ !?", "@\\ \\ a.md", "@a.md\\ \\ ", "`@\\ a.md`", "`@a.md\\ `"),
    ids=repr,
)
def test_leading_or_trailing_escaped_space_not_recognised(text: str):
    """
    [Unit] at-reference grammar: a token that starts or ends with an escaped space is not recognised (M13, A2).

    Scenario:
        Given a token whose first or last raw pair (after punctuation stripping) is an escaped space
        When scanned
        Then nothing is recorded, so the resolver's whitespace strip can never change the name.

    Boundaries:
        - Focus: amendment A2 escaped-space edges, prose and code-span forms
        - Fixtures/params: leading, trailing, trailing before punctuation, doubled

    On failure, first check:
        - The startswith/endswith checks in _at_token run after rstrip
    """
    assert _mentions(text) == ()


@pytest.mark.parametrize(
    "text",
    (
        "@a\u202e.md",
        "@\u2066a.md",
        "@a.md\u200b",
        "\ufeff@a.md",
        "@a\u2028b.md",
        "@a\x00b.md",
        "@a\x1bb.md",
    ),
    ids=repr,
)
def test_bidi_and_zero_width_never_enter_raw(text: str):
    """
    [Unit] at-reference grammar: bidi, zero-width, separator and control characters never enter raw (T8).

    Scenario:
        Given such a character before, inside or after a token
        When scanned
        Then every recorded raw is ASCII from the token alphabet (plus ``@``).

    Boundaries:
        - Focus: the alphabet bound that keeps finding values neutral
        - Fixtures/params: U+202E, U+2066, U+200B, U+FEFF, U+2028, NUL, ESC

    On failure, first check:
        - _AT_TOKEN_CHARS must stay ASCII
    """
    for mention in _mentions(text):
        assert set(mention.raw[1:]) <= _TARGET_CHARSET | {"\\"}
        assert mention.raw.isascii()


# --- cap ------------------------------------------------------------------------------


def test_cap_exactly_1024_raw_characters_recognised():
    """
    [Unit] at-reference grammar: a 1,024-character token is recognised and a 1,025-character one is not (M8).

    Scenario:
        Given tokens of exactly 1,024 and 1,025 raw characters
        When scanned
        Then only the 1,024-character one is recorded.

    Boundaries:
        - Focus: the cap boundary
        - Fixtures/params: none

    On failure, first check:
        - AT_TOKEN_MAX_CHARS and the comparison in _at_token
    """
    exact = "a" * (mb.AT_TOKEN_MAX_CHARS - 3) + ".md"
    over = "a" * (mb.AT_TOKEN_MAX_CHARS - 2) + ".md"

    assert _targets("@" + exact) == [exact]
    assert _mentions("@" + over) == ()


def test_cap_counts_escaped_space_as_two():
    """
    [Unit] at-reference grammar: each escaped space counts as two raw characters toward the cap (A2).

    Scenario:
        Given a token of 1,024 raw characters including an escaped space, and one of 1,025
        When scanned
        Then only the 1,024-character token is recorded (its target is one character shorter).

    Boundaries:
        - Focus: raw length as written, not decoded length
        - Fixtures/params: none

    On failure, first check:
        - The cap is checked on the raw run, before decoding
    """
    exact = "a\\ " + "b" * (mb.AT_TOKEN_MAX_CHARS - 6) + ".md"
    over = "a\\ " + "b" * (mb.AT_TOKEN_MAX_CHARS - 5) + ".md"

    assert len(exact) == mb.AT_TOKEN_MAX_CHARS
    (mention,) = _mentions("@" + exact)
    assert len(mention.target) == mb.AT_TOKEN_MAX_CHARS - 1
    assert _mentions("@" + over) == ()


def test_overlong_run_skipped_whole_and_scan_resumes_after_it():
    """
    [Unit] at-reference grammar: an over-long run is not recognised, not even a prefix, and later mentions still are.

    Scenario:
        Given an over-long token run (whose strip would bring it under the cap) and a mention after it
        When scanned
        Then no part of the long run is recorded and the later mention is.

    Boundaries:
        - Focus: the cap applies to the run as written; scanning resumes after the run
        - Fixtures/params: none

    On failure, first check:
        - _find_prose_at_references resume offset; cap checked before the strip
    """
    long_run = "a" * 1000 + ".md" + "." * 100

    assert _targets("@" + long_run + " then @b.md") == ["b.md"]


def test_overlong_code_span_not_recognised():
    """
    [Unit] at-reference grammar: the code-span form obeys the same cap.

    Scenario:
        Given a code span of ``@`` plus 1,025 token characters
        When scanned
        Then no mention is recorded, while the inline-code record is unchanged.

    Boundaries:
        - Focus: cap on the code-span form
        - Fixtures/params: none

    On failure, first check:
        - _code_span_at_reference delegates to _at_token
    """
    index = mb.scan_markdown("`@" + "a" * (mb.AT_TOKEN_MAX_CHARS - 2) + ".md`", "doc.md")

    assert index.at_references == ()
    assert len(index.inline_code) == 1


# --- code-span form -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "target", "raw"),
    (
        ("`@a.md`", "a.md", "@a.md"),
        ("` @a.md `", "a.md", "@a.md"),
        ("`\t@a.md  `", "a.md", "@a.md"),
        ("``@a.md``", "a.md", "@a.md"),
        ("`@My\\ Docs/a.md`", "My Docs/a.md", "@My\\ Docs/a.md"),
        ("`@~/a.md`", "~/a.md", "@~/a.md"),
    ),
    ids=repr,
)
def test_code_span_form_recognised(text: str, target: str, raw: str):
    """
    [Unit] at-reference grammar: a code span that is exactly ``@`` plus one token is a mention.

    Scenario:
        Given a code span whose trimmed text is ``@`` and one token
        When scanned
        Then one in-code-span mention is recorded with the span of the inline-code record.

    Boundaries:
        - Focus: trimming of ASCII space/tab, double backticks, escaped space
        - Fixtures/params: one per shape

    On failure, first check:
        - _code_span_at_reference
    """
    index = mb.scan_markdown("x " + text + " y", "doc.md")

    (mention,) = index.at_references
    assert (mention.target, mention.raw, mention.in_code_span) == (target, raw, True)
    assert mention.span == index.inline_code[0].span


@pytest.mark.parametrize(
    "text",
    (
        "`@a.md.`",
        "`@a.md,`",
        "`@a.md #x`",
        "`@a.md@b.md`",
        "`@@a.md`",
        "`a@b.md`",
        "`@../../../../etc/passwd`",
        "`@../../v1.2`",
        "`@`",
        "`@\u00a0a.md`",
    ),
    ids=repr,
)
def test_code_span_form_rejected(text: str):
    """
    [Unit] at-reference grammar: a code span holding anything besides one whole token is not a mention.

    Scenario:
        Given a code span with trailing punctuation, extra text, a second ``@``, no extension,
            a digit-only extension, or a non-ASCII space
        When scanned
        Then no mention is recorded (DS116 keeps such spans as code-span candidates, A1).

    Boundaries:
        - Focus: "token consumes the whole span"
        - Fixtures/params: one per shape

    On failure, first check:
        - The full-consumption checks in _code_span_at_reference
    """
    assert _mentions(text) == ()


# --- positions ------------------------------------------------------------------------


def test_lines_offsets_and_columns_across_terminators():
    """
    [Unit] at-reference grammar: each mention carries its line and the character offset of its ``@``.

    Scenario:
        Given mentions on lines terminated by LF, CRLF and CR, with a non-ASCII character before one
        When scanned
        Then start_line/end_line match the physical line, start_offset is the ``@`` and
            the 1-based code-point column is start_offset minus the line start plus one.

    Boundaries:
        - Focus: span arithmetic for DS124's line/column
        - Fixtures/params: none

    On failure, first check:
        - The ``start + at_start`` offsets in scan_markdown
    """
    text = "@a.md\r\nx  (@b.md)\rcaf\u00e9 @c.md\n`@d.md`"
    line_starts = [0, 7, 18, 29]

    mentions = _mentions(text)

    assert [m.target for m in mentions] == ["a.md", "b.md", "c.md", "d.md"]
    assert [(m.span.start_line, m.span.end_line) for m in mentions] == [(1, 1), (2, 2), (3, 3), (4, 4)]
    columns = [m.span.start_offset - line_starts[m.span.start_line - 1] + 1 for m in mentions]
    assert columns == [1, 5, 6, 1]
    for mention in mentions[:3]:
        assert text[mention.span.start_offset : mention.span.end_offset] == mention.raw
    assert text[mentions[3].span.start_offset : mentions[3].span.end_offset] == "`@d.md`"
    assert all(m.span.path == "doc.md" for m in mentions)


def test_source_order_mixes_both_forms():
    """
    [Unit] at-reference grammar: prose and code-span mentions on one line keep source order.

    Scenario:
        Given a line with a prose mention, a code-span mention, then another prose mention
        When scanned
        Then they are recorded in that order with the right in_code_span flags.

    Boundaries:
        - Focus: per-line merge of both forms
        - Fixtures/params: none

    On failure, first check:
        - The line_mentions sort in scan_markdown
    """
    mentions = _mentions("@a.md `@b.md` @c.md")

    assert [(m.target, m.in_code_span) for m in mentions] == [("a.md", False), ("b.md", True), ("c.md", False)]


def test_repeated_mention_recorded_per_occurrence():
    """
    [Unit] at-reference grammar: the scanner records every occurrence; de-duplication is DS124's job.

    Scenario:
        Given the same mention twice on one line and once on the next
        When scanned
        Then three records are kept with distinct spans.

    Boundaries:
        - Focus: scanner stays a faithful token index
        - Fixtures/params: none

    On failure, first check:
        - No dedup was added to scan_markdown
    """
    mentions = _mentions("@a.md @a.md\n@a.md")

    assert len(mentions) == 3
    assert len({m.span for m in mentions}) == 3


@pytest.mark.parametrize("text", ("@a.md@b.md", "see @a.md@b.md here", "@a.md@b.md @c.md"), ids=repr)
def test_glued_second_at_is_not_a_boundary(text: str):
    """
    [Unit] at-reference grammar: in ``@a.md@b.md`` only the first mention is recorded.

    Scenario:
        Given ``@a.md`` immediately followed by ``@b.md`` with no separator
        When scanned
        Then ``a.md`` is recorded once with raw ``@a.md`` (the ``@`` ends the token), ``b.md`` is
            never recorded because a token character is not an accepted boundary, and a later
            properly separated mention on the same line is still recorded.

    Boundaries:
        - Focus: "@" is not in the token alphabet and not in _AT_BOUNDARY_CHARS
        - Fixtures/params: bare, mid-prose, and followed by a separated mention

    On failure, first check:
        - _AT_TOKEN_CHARS (must not gain "@") and _AT_BOUNDARY_CHARS (must not gain token characters)
    """
    mentions = _mentions(text)
    start = text.index("@a.md")

    assert [(m.target, m.raw) for m in mentions if m.target != "c.md"] == [("a.md", "@a.md")]
    assert mentions[0].span.start_offset == start
    assert mentions[0].span.end_offset == start + len("@a.md")
    assert "b.md" not in [m.target for m in mentions]
    assert [m.target for m in mentions] == (["a.md", "c.md"] if "@c.md" in text else ["a.md"])


@pytest.mark.parametrize(
    "text",
    ("@Doc/ß.md", "@ß.md", "@Docß/x.md", "`@Doc/ß.md`", "see @Doc/été.md here"),
    ids=repr,
)
def test_non_ascii_target_is_not_a_mention(text: str):
    """
    [Unit] at-reference grammar: a target with a non-ASCII character is not a mention at all.

    Scenario:
        Given a prose or code-span mention whose path contains a non-ASCII letter (ß, é)
        When scanned
        Then nothing is recorded: the token stops at the first non-ASCII character, and the
            ASCII prefix left (``@Doc/``, ``@``, ``@Doc``) has no extension, so no truncated
            target such as ``Doc/`` is ever recorded.

    Boundaries:
        - Focus: the ASCII-only token alphabet (_AT_TOKEN_CHARS) plus the extension rule
        - Fixtures/params: non-ASCII in the file name, as the whole name, in a directory name,
            in a code span, and mid-prose

    On failure, first check:
        - _AT_TOKEN_CHARS gaining non-ASCII letters (e.g. str.isalnum) or _at_token accepting a
            token without an extension
    """
    assert _mentions(text) == ()


def test_non_ascii_mention_does_not_hide_a_later_mention():
    """
    [Unit] at-reference grammar: a rejected non-ASCII mention does not stop the scan of the line.

    Scenario:
        Given ``@Doc/ß.md`` followed on the same line by ``@ok.md``
        When scanned
        Then exactly ``ok.md`` is recorded.

    Boundaries:
        - Focus: scan resumes after a rejected token
        - Fixtures/params: none

    On failure, first check:
        - The per-line loop in the at-reference scan returning early on a rejected token
    """
    assert _targets("@Doc/ß.md x @ok.md") == ["ok.md"]


def test_mention_in_table_cell_and_heading_recognised():
    """
    [Unit] at-reference grammar: mentions in table cells, headings, lists and blockquotes are recognised.

    Scenario:
        Given mentions in a heading, a list item, a blockquote and a table cell
        When scanned
        Then each is recorded and the table rows are unchanged.

    Boundaries:
        - Focus: README edge case "a mention inside a Markdown table cell is recognised"
        - Fixtures/params: none

    On failure, first check:
        - Recognition runs on every non-fenced line
    """
    text = "# Title @h.md\n\n- @l.md\n> @q.md\n\n| a | b |\n|---|---|\n| @t.md | x |\n"
    index = mb.scan_markdown(text, "doc.md")

    assert [m.target for m in index.at_references] == ["h.md", "l.md", "q.md", "t.md"]
    assert index.table_rows[-1].cells == ("@t.md", "x")


# --- existing fields unchanged --------------------------------------------------------


_RICH_DOCUMENT = (
    "# Title\n\nSome [link](a.md#x) and ![img](i.png) and [ref][r].\n\n"
    "[r]: target.md\n\n<a id='anchor' href='h.md'>x</a> <img src='s.png'>\n\n"
    "`code` <!-- comment -->\n\n```py\nprint(1)\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nSetext\n---\n"
)


def test_document_without_mentions_has_empty_field_and_default():
    """
    [Unit] at-reference grammar: a document without mentions has ``at_references == ()`` and every other field set.

    Scenario:
        Given a document exercising every scanner token kind but no ``@``
        When scanned
        Then at_references is empty, replacing it with the default is a no-op, and the
            default index carries an empty tuple.

    Boundaries:
        - Focus: the new field is additive and defaulted
        - Fixtures/params: none

    On failure, first check:
        - The MarkdownBlockIndex field default
    """
    index = mb.scan_markdown(_RICH_DOCUMENT, "doc.md")

    assert index.at_references == ()
    assert dataclasses.replace(index, at_references=()) == index
    assert mb.MarkdownBlockIndex(path="x.md").at_references == ()
    assert index.headings and index.local_references and index.images and index.reference_uses
    assert index.inline_code and index.comments and index.fences and index.table_rows
    assert index.explicit_anchors and index.reference_definitions


def test_mentions_do_not_change_existing_fields():
    """
    [Unit] at-reference grammar: adding mentions to a document leaves every other field unchanged.

    Scenario:
        Given the rich document, and the same document with mentions appended on new lines
        When both are scanned
        Then every field except at_references (and table rows/headings that include new lines) is equal.

    Boundaries:
        - Focus: recognition never alters links, images, code, comments, anchors or references
        - Fixtures/params: none

    On failure, first check:
        - That the mention pass only reads the existing per-line results
    """
    plain = mb.scan_markdown(_RICH_DOCUMENT, "doc.md")
    with_mentions = mb.scan_markdown(_RICH_DOCUMENT + "\n@x.md and `@y.md`\n", "doc.md")

    assert len(with_mentions.at_references) == 2
    for name in (
        "headings",
        "fences",
        "comments",
        "reference_definitions",
        "reference_uses",
        "local_references",
        "images",
        "table_rows",
        "html_anchors",
        "explicit_anchors",
    ):
        assert getattr(with_mentions, name) == getattr(plain, name), name
    assert with_mentions.inline_code[: len(plain.inline_code)] == plain.inline_code


# --- link labels, definition targets and comments (Task 05 ruling) ---------------------


@pytest.mark.parametrize(
    "text",
    (
        "[@a.md]\n\n[@a.md]: target.md\n",
        "[@A.md] here\n\n[@a.MD]: target.md\n",
        "[see @a.md]\n\n[see @a.md]: target.md\n",
        "[@a.md]: target.md\n\n[@a.md]\n",
        "[`@a.md`]\n\n[`@a.md`]: target.md\n",
    ),
    ids=("defined_after", "label_case_folded", "label_with_text", "defined_before", "code_span_label"),
)
def test_defined_shortcut_reference_label_not_recognised(text: str):
    """
    [Unit] at-reference grammar: a shortcut reference whose label is defined is a link label, not a mention.

    Scenario:
        Given ``[@a.md]`` (or a label holding it) and a matching definition anywhere in the document
        When it is scanned
        Then no mention is recorded, because DS108/DS101 own the label.

    Boundaries:
        - Focus: ruling (a) of the Task 05 briefing, label normalisation as DS108 does it
        - Fixtures/params: definition before/after, case, text around the mention, code-span form

    On failure, first check:
        - _find_shortcut_labels and the defined-label filter at the end of scan_markdown
    """
    assert _mentions(text) == ()


def test_undefined_shortcut_reference_label_stays_a_mention():
    """
    [Unit] at-reference grammar: ``[@a.md]`` with no matching definition is still a mention.

    Scenario:
        Given ``[@a.md]`` and a definition for a different label
        When it is scanned
        Then ``a.md`` is recorded as a prose mention.

    Boundaries:
        - Focus: the filter only drops labels that a definition makes live
        - Fixtures/params: none

    On failure, first check:
        - The defined-label set built from reference_definitions
    """
    assert _targets("[@a.md] and [@b.md]\n\n[other]: x.md\n") == ["a.md", "b.md"]


@pytest.mark.parametrize(
    "text",
    ("[r]: @a.md", '[r]: @a.md "title"', "> [r]: @a.md"),
    ids=("plain", "with_title", "in_block_quote"),
)
def test_reference_definition_target_not_recognised(text: str):
    """
    [Unit] at-reference grammar: a reference-definition destination is a link target, never a mention.

    Scenario:
        Given a reference definition whose target is ``@a.md``
        When it is scanned
        Then no mention is recorded (DS101/DS113 own link destinations).

    Boundaries:
        - Focus: ruling (b) of the Task 05 briefing
        - Fixtures/params: plain, titled and block-quoted definitions

    On failure, first check:
        - The definition-target range added to ``excluded`` in scan_markdown
    """
    assert _mentions(text) == ()


@pytest.mark.parametrize(
    "text",
    ("<!-- `@a.md` -->", "<!--\n`@a.md`\n-->", "[`@a.md`](x.md)", "[x][`@a.md`]", '<b title="`@a.md`">'),
    ids=("comment_inline", "comment_multiline", "link_text", "reference_label", "html_tag"),
)
def test_code_span_form_obeys_the_exclusions(text: str):
    """
    [Unit] at-reference grammar: the code-span form is not recognised in comments, link text, labels or tags.

    Scenario:
        Given a whole-span mention inside an HTML comment, link text, a reference label or a raw HTML tag
        When it is scanned
        Then nothing is recorded, as for the prose form.

    Boundaries:
        - Focus: "Never recognised" applies to both forms
        - Fixtures/params: one per context

    On failure, first check:
        - The comment-range check and the merged ``excluded`` filter applied to code-span mentions
    """
    assert _mentions(text) == ()


def test_shortcut_label_scan_is_linear_on_nested_openers():
    """
    [Unit] at-reference grammar: many nested ``[`` before one ``]`` keep the label scan bounded.

    Scenario:
        Given 20,000 ``[`` then ``@a.md]`` and a matching definition
        When it is scanned
        Then it finishes and the defined label still drops the mention.

    Boundaries:
        - Focus: the reused closing bracket in _find_shortcut_labels (no rescan per opener)
        - Fixtures/params: none

    On failure, first check:
        - That the inner ``[`` search is bounded by the known closing bracket
    """
    assert _mentions("[" * 20_000 + "@a.md]\n\n[@a.md]: x.md\n") == ()
