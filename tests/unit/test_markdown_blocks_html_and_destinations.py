"""Unit tests for the shared scanner's HTML-attribute and destination handling.

These pin the Story 11.0 close-gate scanner fixes so a renderer-visible escaping
reference can no longer slip past the tokenizer: HTML ``<a href>`` and
``<img>``/``<source>`` ``srcset`` extraction, CommonMark ``<...>`` destination
unwrapping for inline links and reference definitions, HTML-entity decoding in the
shared resolver, balanced-bracket matching so a nested image-in-link-text exposes
the outer destination, and reference definitions inside a block quote. They assert
the scanner tokens and resolver classification directly (tiny inline strings, no
assets), plus the linear-time bound for every new regex in single-line and
multi-line flood forms, and pin the remaining known gaps as explicit false
negatives so DS116 is never treated as a complete containment control.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import markdown_blocks as mb
from docsentinel.markdown_blocks import ReferenceStatus, resolve_local_reference, scan_markdown
from tests.timing_helpers import assert_scales_linearly

_ROOT = Path("/scanroot")
_DOC = "sub/doc.md"


def test_html_anchor_href_is_extracted_as_a_local_reference():
    """
    [Unit] markdown blocks html and destinations: verifies <a href> becomes a local reference.

    Scenario:
        Given an ``<a href="../x">`` tag
        When the scanner runs
        Then the href is recorded as an ordinary local reference carrying the raw target.

    Boundaries:
        - Focus: href extraction (previously only id/name were taken from <a>)
        - Fixtures/params: none

    On failure, first check:
        - The _HTML_HREF_ATTR_RE extraction wired into scan_markdown
    """
    index = scan_markdown('<a href="../x">link</a>\n', _DOC)
    assert [reference.raw_target for reference in index.local_references] == ["../x"]


def test_html_img_and_source_srcset_each_candidate_is_an_image():
    """
    [Unit] markdown blocks html and destinations: verifies srcset candidates become HTML images.

    Scenario:
        Given an ``<img srcset>`` with two candidates and a ``<source srcset>`` with one
        When the scanner runs
        Then each candidate URL (the first token of each comma-separated candidate) is an HTML image.

    Boundaries:
        - Focus: srcset extraction and candidate splitting for img and source tags
        - Fixtures/params: none

    On failure, first check:
        - _srcset_urls splitting and the _HTML_SRCSET_ATTR_RE wiring
    """
    index = scan_markdown('<img srcset="a.png 1x, b.png 2x">\n<source srcset="c.png">\n', _DOC)
    html_images = [image.raw_target for image in index.images if image.html]
    assert html_images == ["a.png", "b.png", "c.png"]


def test_srcset_data_uri_candidate_is_not_split_on_its_internal_comma():
    """
    [Unit] markdown blocks html and destinations: verifies a data: URI srcset candidate is one URL.

    Scenario:
        Given an ``<img srcset>`` whose first candidate is a ``data:`` URI containing a comma and
            whose second candidate is a real file
        When the scanner runs
        Then the data URI stays a single candidate (no base64 fragment becomes a separate URL) and
            the real candidate is extracted, closing the HIGH srcset/data-URI split in the DS113 model.

    Boundaries:
        - Focus: the _srcset_urls WHATWG non-whitespace-run fix (regression for the split bug)
        - Fixtures/params: none

    On failure, first check:
        - Whether _srcset_urls still collects each URL as a whitespace-delimited run
        - Whether value.split(",") crept back in and corrupted the data URI
    """
    index = scan_markdown('<img srcset="data:image/png;base64,iVBORw0KGgoAAAA== 1x, real.png 2x">\n', _DOC)
    html_images = [image.raw_target for image in index.images if image.html]
    assert html_images == ["data:image/png;base64,iVBORw0KGgoAAAA==", "real.png"]


def test_srcset_data_uri_candidate_never_classifies_as_an_in_root_path():
    """
    [Unit] markdown blocks html and destinations: verifies DS116 never probes a data-URI srcset fragment.

    Scenario:
        Given the data-URI ``srcset`` candidate from the split-bug reproduction
        When each extracted candidate is classified by the shared resolver
        Then the data URI classifies EXTERNAL (never RESOLVED as an in-root path), so no base64
            fragment can become a filesystem probe for DS116 or DS113.

    Boundaries:
        - Focus: resolver classification of the fixed srcset candidates (DS116 regression)
        - Fixtures/params: none

    On failure, first check:
        - Whether the data URI is one candidate and keeps its ``data:`` scheme
        - Whether a bare base64 fragment leaked through as a RESOLVED candidate
    """
    index = scan_markdown('<img srcset="data:image/png;base64,iVBORw0KGgoAAAA== 1x, real.png 2x">\n', _DOC)
    statuses = {
        image.raw_target: resolve_local_reference(_ROOT, _DOC, image.raw_target).status
        for image in index.images
        if image.html
    }
    assert statuses["data:image/png;base64,iVBORw0KGgoAAAA=="] is ReferenceStatus.EXTERNAL
    assert statuses["real.png"] is ReferenceStatus.RESOLVED


def test_angle_bracket_destination_is_unwrapped_for_links_and_refdefs():
    """
    [Unit] markdown blocks html and destinations: verifies <...> destinations are unwrapped.

    Scenario:
        Given an inline link and a reference definition each using a ``<...>`` destination
        When the scanner runs
        Then the stored target drops the angle-bracket delimiters, per CommonMark.

    Boundaries:
        - Focus: _strip_angle_brackets applied to link targets and refdef targets
        - Fixtures/params: none

    On failure, first check:
        - The _strip_angle_brackets calls in scan_markdown for links and reference definitions
    """
    link_index = scan_markdown("[a](<../x>)\n", _DOC)
    assert [reference.raw_target for reference in link_index.local_references] == ["../x"]

    def_index = scan_markdown("[r]: <../x>\n", _DOC)
    assert [definition.target for definition in def_index.reference_definitions] == ["../x"]


def test_nested_image_in_link_text_exposes_the_outer_destination():
    """
    [Unit] markdown blocks html and destinations: verifies the outer destination of a nested link.

    Scenario:
        Given ``[![alt](inner.png)](../outer)`` where an image sits in the link text
        When the scanner runs
        Then both the inner image target and the outer link destination are recorded.

    Boundaries:
        - Focus: balanced-bracket matching so the outer destination is no longer missed
        - Fixtures/params: none

    On failure, first check:
        - The bracket-stack matcher in _find_inline_links
    """
    index = scan_markdown("[![alt](inner.png)](../outer)\n", _DOC)
    targets = {reference.raw_target for reference in index.local_references}
    image_targets = {image.raw_target for image in index.images}
    assert "../outer" in targets
    assert "inner.png" in image_targets


def test_block_quote_reference_definition_is_recognized():
    """
    [Unit] markdown blocks html and destinations: verifies a block-quoted reference definition.

    Scenario:
        Given a reference definition prefixed by a block-quote marker ``> [r]: ../x``
        When the scanner runs
        Then it is recognized as a reference definition with the correct label and target.

    Boundaries:
        - Focus: the optional block-quote prefix in _REF_DEF_RE
        - Fixtures/params: none

    On failure, first check:
        - The ``(?:>\\s?)*`` prefix in _REF_DEF_RE
    """
    index = scan_markdown("> [r]: ../x\n", _DOC)
    assert [(definition.label, definition.target) for definition in index.reference_definitions] == [("r", "../x")]


@pytest.mark.parametrize(
    ("raw_target", "status"),
    [
        ("&#46;&#46;/&#46;&#46;/x", ReferenceStatus.OUTSIDE_ROOT),
        ("&period;&period;/&period;&period;/x", ReferenceStatus.OUTSIDE_ROOT),
        ("<../../x>", ReferenceStatus.OUTSIDE_ROOT),
        ("&#46;&#46;/&#46;&#46;/&#46;&#46;/x", ReferenceStatus.OUTSIDE_ROOT),
        ("&#46;&#46;/x", ReferenceStatus.RESOLVED),
        ("&amp;keep/x", ReferenceStatus.RESOLVED),
    ],
)
def test_resolver_decodes_entities_and_unwraps_angle_before_classifying(raw_target: str, status: ReferenceStatus):
    """
    [Unit] markdown blocks html and destinations: verifies the resolver decodes entities and angle wrappers.

    Scenario:
        Given destinations using numeric/named character references, an angle-bracket wrapper, a numeric
            reference whose ``#`` would otherwise read as a fragment delimiter, and a benign ``&amp;``
        When the shared resolver classifies each against a depth-one document
        Then the escaping forms are OUTSIDE_ROOT (a renderer would make them live) while ``&amp;keep``
            stays an in-root RESOLVED literal.

    Boundaries:
        - Focus: one-pass html.unescape before the fragment split and before percent-decoding, plus
          angle-bracket unwrapping, all in resolve_local_reference
        - Fixtures/params: parametrized over the entity/angle forms

    On failure, first check:
        - The ``_html.unescape(... )`` ordering before the ``#`` partition in resolve_local_reference
    """
    assert resolve_local_reference(_ROOT, _DOC, raw_target).status is status


def test_multi_line_link_and_nested_paren_destination_are_known_gaps():
    """
    [Unit] markdown blocks html and destinations: pins the line-based and nested-paren known gaps.

    Scenario:
        Given a link split across physical lines and a destination whose escape is buried in a balanced
            inner parenthesis
        When the scanner runs
        Then the multi-line link yields no local reference (the scanner is line-based) and the inner
            parenthesis truncates the destination at the first ``)`` - both are documented known
            limitations, pinned so DS116 is never presented as a complete containment control.

    Boundaries:
        - Focus: honestly pinning the multi-line and nested-paren destination limitations
        - Non-goal: fixing them (documented in path_boundaries.py and the threat model)
        - Fixtures/params: none

    On failure, first check:
        - Whether multi-line link support or balanced-paren destinations were added (update the docs/pins)
    """
    multi_line = scan_markdown("[a](\n../x\n)\n", _DOC)
    assert multi_line.local_references == ()

    nested_paren = scan_markdown("[a](x(../../y)z.md)\n", _DOC)
    # The destination is truncated at the first ``)``, so the stored target is ``x(../../y`` rather than
    # the renderer's full ``x(../../y)z.md``; both normalise in-root here, so no finding is lost in this
    # case, but the truncation is a parsing approximation documented as a known gap.
    assert [reference.raw_target for reference in nested_paren.local_references] == ["x(../../y"]


def _single_line(unit: str) -> Callable[[int], str]:
    """Return a builder repeating ``unit`` ``n`` times on one line.

    :param unit: The fragment to repeat.
    :returns: A ``size -> source`` builder.
    """

    def build(size: int) -> str:
        """Return the one-line flood for ``size`` repetitions.

        :param size: Repetition count.
        :returns: The Markdown source.
        """
        return unit * size + "\n"

    return build


def _multi_line(unit: str) -> Callable[[int], str]:
    """Return a builder repeating ``unit`` as ``n`` separate lines.

    :param unit: The fragment to repeat (a newline is appended per line).
    :returns: A ``size -> source`` builder.
    """

    def build(size: int) -> str:
        """Return ``size`` lines of the unit.

        :param size: Line count.
        :returns: The Markdown source.
        """
        return (unit + "\n") * size

    return build


#: Flood shapes for the new regexes, mapped to a builder. Counts are not asserted
#: (the resolver/consumer counts are covered elsewhere); these pin that the new
#: href/srcset/entity/angle/nested-bracket scanning stays linear in the scanner,
#: which is where a catastrophic regex or per-match rescan would show up.
_FLOOD_UNITS: dict[str, str] = {
    "href_single": '<a href="../x">y</a> ',
    "srcset_single": '<img srcset="a.png 1x"> ',
    "entity_single": "[a](&#46;&#46;/x) ",
    "angle_single": "[a](<../x>) ",
    "nested_bracket_single": "[![a](i.png)](../x) ",
    "quote_refdef_lines": "> [r]: ../x",
    "angle_refdef_lines": "[r]: <../x>",
}


@pytest.mark.parametrize("name", sorted(_FLOOD_UNITS))
def test_new_destination_regexes_stay_linear(name: str):
    """
    [Unit] markdown blocks html and destinations: verifies the new scanning stays linear.

    Scenario:
        Given a doubling series of href, srcset, entity, angle-bracket, nested-bracket, and block-quote
            reference-definition floods, in single-line and multi-line forms
        When the scanner tokenizes each
        Then the scan stays under the shared linear bound, so none of the new regexes or the bracket
            stack introduced a catastrophic or quadratic shape.

    Boundaries:
        - Focus: linear-time scanning for every close-gate regex (single-line and multi-line)
        - Fixtures/params: parametrized over the flood shapes

    On failure, first check:
        - Whether a new attribute regex backtracks or the bracket stack rescans
        - _srcset_urls and _strip_angle_brackets staying O(len)
    """
    unit = _FLOOD_UNITS[name]
    builder = _multi_line(unit) if name.endswith("_lines") else _single_line(unit)
    assert_scales_linearly(
        builder,
        lambda source: mb.scan_markdown(source, _DOC).local_references,
        (4_000, 8_000, 16_000, 32_000),
        label=f"destinations-{name}",
    )
