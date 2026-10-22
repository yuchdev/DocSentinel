"""Integration tests that the comment-masking fix un-hides references for every rule.

The shared scanner used to treat an unclosed ``<!--`` - inside an inline code span,
or as literal mid-line text - as a comment running to end of document, so every
later link, image, reference definition, heading, section, fence, and table was
masked out and invisible to DS101/DS103/DS104/DS105/DS106/DS110/DS116/DS117. This
suite proves the fix at the detector level: an escaping reference placed after each
literal opener form IS now reported by DS116; one placed after a genuine closed
comment IS reported; one placed INSIDE a closed comment is still correctly hidden;
and a construct after an unclosed inline ``<!--`` is seen again by each fast rule.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docsentinel import models
from docsentinel.config import Config
from docsentinel.detectors import path_boundaries as pb
from docsentinel.engine import scan

#: An escaping link that DS116 must report (root escape above a depth-3 document).
_ESCAPE_LINK = "[x](../../../../etc/passwd)"

#: Literal ``<!--`` forms that must NOT hide a later reference (each pairs the form
#: with a one-line note of why CommonMark keeps the later reference live).
_LITERAL_FORMS: dict[str, str] = {
    "inline_code_span_opener": "See `<!--` in code.",
    "mid_line_literal_opener": "A mid-line a <!-- b note.",
    "same_line_after_literal_opener": f"a <!-- {_ESCAPE_LINK}",
}


def _ds116(root: Path, document: str) -> tuple[models.Finding, ...]:
    """Return the DS116 findings for one document under the default error policy.

    :param root: The scan root.
    :param document: The document's root-relative path.
    :returns: The DS116 findings.
    """
    findings = pb.detect(root, (models.Document(document, 0),), Config(root_escape_policy="error"))
    return tuple(finding for finding in findings if finding.rule == "DS116")


@pytest.mark.parametrize("form", sorted(_LITERAL_FORMS))
def test_escaping_reference_after_a_literal_opener_is_reported(form: str, tmp_path: Path):
    """
    [Integration] comment masking evasion ds116 smoke: verifies literal openers no longer hide a link.

    Scenario:
        Given a document whose paragraph carries a literal ``<!--`` (inside a code span, as mid-line
            text, or on the same line immediately before the link) followed by an escaping link
        When DS116 runs at depth three
        Then the escaping link is reported, because the literal opener masks nothing.

    Boundaries:
        - Focus: the evasion fix at the DS116 level for each literal opener form
        - Fixtures/params: parametrized over the literal opener forms; tmp_path

    On failure, first check:
        - Whether _scan_comments re-masked the literal opener to end of document
        - Whether the inline-code span blanking stopped running before the opener scan
    """
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b").mkdir()
    docs = tmp_path / "a" / "b"
    line = _LITERAL_FORMS[form]
    body = f"# H\n\n{line}\n" if form == "same_line_after_literal_opener" else f"# H\n\n{line}\n\n{_ESCAPE_LINK}\n"
    (docs / "README.md").write_text(body, encoding="utf-8")

    findings = _ds116(tmp_path, "a/b/README.md")

    assert len(findings) == 1
    assert "etc/passwd" in findings[0].message


def test_escaping_reference_after_a_closed_comment_is_reported_but_inside_is_hidden(tmp_path: Path):
    """
    [Integration] comment masking evasion ds116 smoke: verifies closed-comment masking stays correct.

    Scenario:
        Given one document with an escaping link after a closed comment and another with the escaping
            link inside a closed comment
        When DS116 runs at depth three
        Then the link after the comment is reported and the link inside the comment is not - masking is
            exactly the closed comment's own range.

    Boundaries:
        - Focus: genuine closed comments still mask their own content and nothing more
        - Fixtures/params: tmp_path

    On failure, first check:
        - The closed-comment range and the consumed-until cursor in _scan_comments
    """
    (tmp_path / "a" / "b").mkdir(parents=True)
    docs = tmp_path / "a" / "b"
    docs.joinpath("after.md").write_text(f"# H\n\n<!-- note -->\n\n{_ESCAPE_LINK}\n", encoding="utf-8")
    docs.joinpath("inside.md").write_text(f"# H\n\n<!-- {_ESCAPE_LINK} -->\n", encoding="utf-8")

    assert len(_ds116(tmp_path, "a/b/after.md")) == 1
    assert _ds116(tmp_path, "a/b/inside.md") == ()


def test_every_fast_rule_sees_its_construct_after_an_unclosed_inline_opener(tmp_path: Path):
    """
    [Integration] comment masking evasion ds116 smoke: verifies all fast rules see past an unclosed opener.

    Scenario:
        Given one document that, after a paragraph containing an unclosed inline ``<!--`` code span,
            carries a dangling link (DS101), a bad path code span (DS103), colliding explicit anchors
            (DS104), a heading-level skip (DS105), an empty section (DS106), an unlabelled fence (DS110,
            policy on), an escaping link (DS116) and a malformed pipe table (DS117)
        When a full fast scan runs with the DS110 policy enabled
        Then each rule reports its own construct, proving the unclosed inline opener no longer blinds any
            scanner consumer to the rest of the document.

    Boundaries:
        - Focus: the evasion fix restores visibility for every fast rule, not just DS116
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _scan_comments still masks content after the unclosed inline opener
        - Which rule is missing from the reported set
    """
    body = (
        "# Title\n"
        "\n"
        "Intro with an unclosed `<!--` inline code span that used to hide the rest.\n"
        "\n"
        "A [dangling](missing-doc.md) link.\n"
        "\n"
        "Inline `../../nope.md` path span.\n"
        "\n"
        '<a name="dup"></a>\n'
        '<a name="dup"></a>\n'
        "\n"
        "### Skipped level three\n"
        "\n"
        "An [escape](../../../../etc/passwd) reference.\n"
        "\n"
        "```\n"
        "unlabelled fence body\n"
        "```\n"
        "\n"
        "| a | b |\n"
        "| --- |\n"
        "| 1 | 2 |\n"
        "\n"
        "## Empty trailing section\n"
    )
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "README.md").write_text(body, encoding="utf-8")

    result = scan(tmp_path, config=Config(profile="fast", require_fence_languages=True))
    fired = {finding.rule for finding in result.findings}

    for rule in ("DS101", "DS103", "DS104", "DS105", "DS106", "DS110", "DS116", "DS117"):
        assert rule in fired, f"{rule} did not see its construct after the unclosed inline opener: {sorted(fired)}"
