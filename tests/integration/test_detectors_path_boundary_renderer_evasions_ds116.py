"""Regression tests for DS116 renderer-evasion fixes (Story 11.0 close-gate).

A feature-reviewer and security-auditor sweep against a ``markdown-it`` oracle
found six input shapes where a CommonMark renderer makes a live escaping reference
but DS116 reported nothing: HTML ``<a href>`` and ``<img>`` ``srcset`` attributes
that the scanner never extracted, angle-bracket destinations whose ``<...>`` wrapper
was kept, HTML entity and numeric character-reference destinations, a nested
image-in-link-text whose outer destination was missed, and a reference definition
inside a block quote. Each is now committed as its own ``tests/assets/ds116``
fixture and asserted here against an explicit, checked-in expectation table (never
derived from the analyzer) through both the pure ``detect`` entry point and the
shared ``scan`` engine.

The expectations match the oracle scripts in the review scratchpad
(``cases.py``/``oracle.py``), which compare a real ``markdown-it`` render's live
escaping references against DS116: after these fixes the oracle reports zero
evasions across its 58-case corpus. The ownership split still holds - the only
non-DS116 findings are the legitimate DS101 dangling-link and DS113 missing-asset
reports for the in-root inner image of ``nested_image_link_escape``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import models
from docsentinel.config import Config
from docsentinel.detectors import path_boundaries as pb
from docsentinel.engine import scan
from tests.asset_helpers import AssetCase

#: Each committed evasion fixture mapped to the one-based line of the offending
#: reference and its DS116 violation category. Every one is a FINDING; all escape
#: the root, so the category is ``escape`` and the fixed message prefix is
#: "reference escapes the documentation root". Transcribed from the fixtures and
#: the oracle, not read back from the analyzer.
EVASION_FIXTURES: dict[str, tuple[int, str]] = {
    "html_anchor_href_escape": (3, "escape"),
    "html_img_srcset_escape": (3, "escape"),
    "angle_bracket_destination_escape": (3, "escape"),
    "entity_encoded_destination_escape": (3, "escape"),
    "nested_image_link_escape": (3, "escape"),
    "quoted_refdef_escape": (3, "escape"),
}

#: Fixed DS116 message prefix for a root escape.
_ESCAPE_MESSAGE = "reference escapes the documentation root"

#: Legitimate non-DS116 findings a full fast scan adds. Only the nested
#: image-in-link fixture has them: its inner ``diagram.png`` is an in-root image
#: that does not exist, so DS101 reports a dangling link and DS113 reports a missing
#: asset at line 3, while DS116 owns the outer escaping destination.
EXPECTED_SIBLINGS: dict[str, tuple[tuple[str, int], ...]] = {
    "nested_image_link_escape": (("DS101", 3), ("DS113", 3)),
}


def _ds116(findings: tuple[models.Finding, ...]) -> tuple[models.Finding, ...]:
    """Return only the DS116 findings from a mixed tuple, preserving order.

    :param findings: Findings from a detector or scan.
    :returns: The DS116 subset in the original order.
    """
    return tuple(finding for finding in findings if finding.rule == "DS116")


@pytest.mark.parametrize("case", sorted(EVASION_FIXTURES))
def test_detect_catches_each_renderer_evasion(case: str, asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors path boundary renderer evasions ds116: verifies detect catches each evasion.

    Scenario:
        Given one committed renderer-evasion fixture materialized into a fresh tmp_path
        When path_boundaries.detect runs over its README.md with the default error policy
        Then exactly one DS116 error finding is produced at the expected one-based line, carrying the
        root-escape message - the reference a CommonMark renderer would make live is no longer hidden.

    Boundaries:
        - Focus: the six close-gate evasion fixes at the pure detect entry point
        - Fixtures/params: parametrized over every evasion fixture; asset_case

    On failure, first check:
        - Whether the scanner extracts href/srcset, strips angle brackets, decodes entities, balances
          nested brackets, or handles the block-quote refdef prefix for this case
        - Whether the fixture Markdown was altered (it must stay byte-for-byte)
    """
    loaded = asset_case("ds116", case)
    findings = _ds116(pb.detect(loaded.root, loaded.documents()))
    line, _category = EVASION_FIXTURES[case]

    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].line == line
    assert findings[0].message.startswith(_ESCAPE_MESSAGE + ": ")


@pytest.mark.parametrize("case", sorted(EVASION_FIXTURES))
def test_scan_catches_each_evasion_with_ownership_split(case: str, asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors path boundary renderer evasions ds116: verifies full-scan ownership split.

    Scenario:
        Given one committed evasion fixture scanned under the full fast profile
        When DS101-DS117 run together
        Then DS116 reports the escape at the expected line and the only non-DS116 finding is the
        documented EXPECTED_SIBLINGS entry, so no other rule double-reports the evasion.

    Boundaries:
        - Focus: cross-rule ownership for the evasion fixtures (DS116 owns the escape)
        - Fixtures/params: parametrized over every evasion fixture; asset_case

    On failure, first check:
        - Whether a new sibling finding appeared beyond the documented EXPECTED_SIBLINGS overlap
        - Whether DS116 stopped reporting the escape
    """
    loaded = asset_case("ds116", case)
    result = scan(loaded.root, config=Config(profile="fast"))
    line, _category = EVASION_FIXTURES[case]

    own = _ds116(result.findings)
    assert len(own) == 1
    assert own[0].line == line
    assert own[0].message.startswith(_ESCAPE_MESSAGE + ": ")

    siblings = tuple(sorted((finding.rule, finding.line) for finding in result.findings if finding.rule != "DS116"))
    assert siblings == EXPECTED_SIBLINGS.get(case, ())


def test_html_srcset_reports_every_escaping_candidate(tmp_path: Path):
    """
    [Integration] detectors path boundary renderer evasions ds116: verifies multi-candidate srcset handling.

    Scenario:
        Given an ``<img srcset>`` whose comma-separated candidate list holds two distinct escaping URLs
        When DS116 runs at depth three
        Then both candidate URLs are reported, proving srcset is split into candidates and the first
        token of each is validated.

    Boundaries:
        - Focus: srcset candidate splitting (first token of each comma-separated candidate)
        - Fixtures/params: tmp_path

    On failure, first check:
        - _srcset_urls splitting on commas then whitespace
        - Whether only the first candidate was checked
    """
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "README.md").write_text(
        '# H\n\n<img srcset="../../../one.png 1x, ../../../two.png 2x">\n', encoding="utf-8"
    )

    findings = _ds116(pb.detect(tmp_path, (models.Document("a/b/README.md", 0),)))

    targets = sorted(finding.message.split(": ", 1)[1] for finding in findings)
    assert targets == ["../../../one.png", "../../../two.png"]


def test_srcset_data_uri_candidate_is_not_a_boundary_probe(tmp_path: Path):
    """
    [Integration] detectors path boundary renderer evasions ds116: verifies the data-URI srcset fix.

    Scenario:
        Given an ``<img srcset>`` mixing a ``data:`` URI candidate (whose base64 payload carries a
            comma) with one genuinely escaping candidate
        When DS116 runs
        Then only the escaping candidate is reported and the data URI yields no finding, so the
            _srcset_urls split fix did not turn a base64 fragment into a boundary probe (the HIGH
            srcset/data-URI split shared with DS113).

    Boundaries:
        - Focus: DS116 regression for the shared _srcset_urls data-URI split fix
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the data URI stays one EXTERNAL candidate after the WHATWG split
        - Whether a base64 fragment leaked through as an in-root or escaping probe
    """
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "README.md").write_text(
        '# H\n\n<img srcset="data:image/png;base64,iVBORw0KGgo= 1x, ../../../two.png 2x">\n', encoding="utf-8"
    )

    findings = _ds116(pb.detect(tmp_path, (models.Document("a/b/README.md", 0),)))

    targets = sorted(finding.message.split(": ", 1)[1] for finding in findings)
    assert targets == ["../../../two.png"]


def test_multi_line_link_is_a_known_false_negative(tmp_path: Path):
    """
    [Integration] detectors path boundary renderer evasions ds116: pins the multi-line-link known gap.

    Scenario:
        Given a link whose destination is split across physical lines (``[a](\\n../../../etc/passwd\\n)``)
        When DS116 runs
        Then nothing is reported, because the shared scanner is line-based and does not join a link
        across lines - this is a documented known false negative, pinned so any future change that
        closes it is deliberate and visible, and so DS116 is never presented as a complete containment
        control.

    Boundaries:
        - Focus: honestly pinning the line-based scanner's multi-line-link limitation
        - Non-goal: fixing multi-line links (documented in path_boundaries.py and the threat model)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the scanner gained multi-line link support (update this pin and the docs if so)
    """
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "README.md").write_text("# H\n\n[a](\n../../../etc/passwd\n)\n", encoding="utf-8")

    assert _ds116(pb.detect(tmp_path, (models.Document("a/b/README.md", 0),))) == ()
