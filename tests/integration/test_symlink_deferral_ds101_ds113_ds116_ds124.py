"""Integration tests: DS101, DS113 and DS124 defer every symlink-out layout to DS116.

Milestone 0009 Story 01.0 story-close review, SC-4. The shared component walker
(``path_boundaries._walk``) decides, for links, images and ``@``-mentions alike, when a
reference leaves the scan root through a symlink. Three layouts had no regression test
for every consumer: a symlink nested inside a symlink target, a symlink-out reached after
more than 64 plain components, and a symlink whose target climbs out and back in
(``rt -> ../outside/../root/d``). In every layout DS116 must report the link, the image and
the mention once each, and DS101, DS113 and DS124 must report nothing: a regression that
went back to collapsing symlink targets lexically would make DS116 silent on the round trip,
and one that stopped deferring would make DS101/DS113 report the nested and deep-prefix
targets (which do not exist where the kernel lands).

The plain link spelling ``../outside/../root/d/x.md`` was already a lexical DS116 escape
before this story; only the *symlink target* of that shape is new and pinned here. The
no-probe guarantee for the same layouts lives in
``tests/mock/test_symlink_deferral_no_probe.py``. Trees are built under ``tmp_path`` by
``tests/symlink_layout_helpers.py``; no asset is loaded.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

import docsentinel
from docsentinel.config import Config
from docsentinel.detectors import assets, links, mentions, path_boundaries
from tests.symlink_layout_helpers import LAYOUTS, SYMLINK_ESCAPE, SymlinkLayout, build_round_trip


@pytest.mark.parametrize("build", tuple(LAYOUTS.values()), ids=tuple(LAYOUTS))
def test_symlink_out_layout_defers_to_ds116(tmp_path: Path, build: Callable[[Path], SymlinkLayout]):
    """
    [Integration] symlink deferral: DS101, DS113 and DS124 stay silent where DS116 reports a symlink escape.

    Scenario:
        Given a README that links to S.md, embeds S.png and mentions @S.md, where S passes
            through a nested symlink-out, a symlink-out after 70 plain directories, or a
            round-trip symlink rt -> ../outside/../root/d
        When DS101, DS113, DS124 and DS116 run directly with the default config
        Then DS101, DS113 and DS124 return no finding, and DS116 returns exactly one
            symlink-escape error per form (lines 1, 2 and 3) echoing the raw target.

    Boundaries:
        - Focus: SC-4 deferral of every walker consumer to DS116 (nested, deep_prefix, round_trip)
        - Fixtures/params: one layout per case, built in the test body; symlink-less platforms skip

    On failure, first check:
        - links.detect -> contained_path and assets.detect -> escapes_via_symlink (both run _walk)
        - The hop counter (deep_prefix) and the first-".."-above-root refusal (round_trip) in _walk
    """
    layout = build(tmp_path)
    root, documents = layout.root, layout.documents

    ds101 = links.detect(root, documents, Config(), link_root=root)
    ds113 = assets.detect(root, documents, Config(), link_root=root)
    ds124 = mentions.detect(root, documents, Config(), link_root=root)
    ds116 = path_boundaries.detect(root, documents, Config(), link_root=root)

    assert ds101 == ()
    assert ds113 == ()
    assert ds124 == ()
    assert [(finding.line, finding.message) for finding in ds116] == layout.expected_ds116()
    assert {(finding.rule, finding.path, finding.severity) for finding in ds116} == {("DS116", "README.md", "error")}


def test_round_trip_symlink_target_scan_reports_only_ds116(tmp_path: Path):
    """
    [Integration] symlink deferral: a full fast scan of the round-trip layout reports DS116 only.

    Scenario:
        Given root/rt -> ../outside/../root/d over a real root/d holding x.md and x.png, and a
            README that links to rt/x.md, embeds rt/x.png and mentions @rt/x.md
        When the engine scans root with the default fast profile
        Then the only findings are the three DS116 errors on README.md (link, image, mention),
            DS101, DS113 and DS124 are enabled yet silent, and the symlinked directory's files
            are not inventoried as documents.

    Boundaries:
        - Focus: SC-4 case (c) through the engine (rule selection, link-root wiring, discovery)
        - Fixtures/params: round-trip layout built in the test body; symlink-less platforms skip

    On failure, first check:
        - _walk refusing the first ".." above the root inside a symlink target
        - discovery descending into the rt symlink (would add rt/x.md as a document)
    """
    layout = build_round_trip(tmp_path)

    result = docsentinel.scan(layout.root)

    assert [(f.rule, f.path, f.line, f.severity, f.message) for f in result.findings] == [
        ("DS116", "README.md", 1, "error", f"{SYMLINK_ESCAPE}rt/x.md"),
        ("DS116", "README.md", 2, "error", f"{SYMLINK_ESCAPE}rt/x.png"),
        ("DS116", "README.md", 3, "error", f"{SYMLINK_ESCAPE}@rt/x.md"),
    ]
    assert {"DS101", "DS113", "DS116", "DS124"} <= set(result.enabled_rules)
    assert [document.path for document in result.documents] == ["README.md", "d/x.md"]
