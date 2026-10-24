"""Unit tests for DS113 missing local media/document asset recognition (``assets.py``).

These exercise the detector with tiny inline Markdown strings and ``tmp_path`` roots,
never loading ``tests/assets`` (Story 10.0 Task 02 commits those fixtures and Task 03
runs them). They cover each algorithm bullet, exclusion, and ruling R1-R5 from the
task briefing and the standing threat model: image/HTML/srcset/href recognition, the
srcset/data-URI split, external schemes, protocol-relative ``//host``, fragment-only
and template targets, Windows-form deferral to DS116, root-escape and in-root
symlink-out deferral to DS116, the ``os.stat``/``S_ISREG`` existence/type check that
never opens content (including a runtime FIFO), in-root symlink validity (R3),
case-insensitive extension matching, the bounded repr-escaped echo, the config
toggles and ``missing_asset_policy``, source ordering/de-duplication, and the
linear-time bound for every new loop in single-line and multi-line flood forms.

``DS113`` is **registered** as an always-active fast rule in Task 02, so these tests
still call ``check_text``/``detect`` directly to isolate the algorithm; a dedicated
test pins the registered state so the Milestone 0005 fixture catalog enforces every
committed ``tests/assets/ds113/*`` scenario.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.detectors import assets
from tests.timing_helpers import assert_scales_linearly

_DOC = "README.md"


def _messages(findings: tuple[models.Finding, ...]) -> list[str]:
    """Return the message strings of findings in order.

    :param findings: The findings to project.
    :returns: Each finding's message in order.
    """
    return [finding.message for finding in findings]


def _root(tmp_path: Path) -> Path:
    """Return the canonical form of a ``tmp_path`` scan root.

    :param tmp_path: The pytest temporary directory.
    :returns: The realpath-canonicalised root, matching what ``detect`` uses.
    """
    return Path(os.path.realpath(tmp_path))


def _symlink_or_skip(link: Path, target: str):
    """Create a symlink or skip the test with an explicit unavailable reason.

    :param link: The symlink path to create.
    :param target: The symlink's target string.
    """
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors assets: verifies DS113 metadata and that Task 02 registers it.

    Scenario:
        Given the module-level DS113 rule object and the global registries
        When its fields and the registries are inspected
        Then it is a fast, error-severity, non-opt-in rule registered in RULES and ANALYZERS.

    Boundaries:
        - Focus: rule identity and the Task 02 "registered always-active fast rule" contract
        - Fixtures/params: none

    On failure, first check:
        - Whether register_rule and the ANALYZERS wiring landed in assets.py
        - Whether the Rule fields drifted from the story contract
    """
    assert assets.DS113.code == "DS113"
    assert assets.DS113.profile == "fast"
    assert assets.DS113.severity == "error"
    assert assets.DS113.opt_in_option == ""
    assert rules.RULES["DS113"] is assets.DS113
    assert rules.ANALYZERS["DS113"] is assets.detect


def test_existing_markdown_image_is_clean(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a Markdown image resolving to a real file is clean.

    Scenario:
        Given a Markdown image whose relative target exists as a regular file
        When check_text runs with defaults
        Then no finding is produced.

    Boundaries:
        - Focus: algorithm bullet 1-2 (resolve relative, check existence/type), the happy path
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether os.stat / S_ISREG classified the regular file as usable
    """
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "logo.svg").write_text("<svg/>", encoding="utf-8")

    assert assets.check_text("![logo](images/logo.svg)\n", _DOC, _root(tmp_path)) == ()


def test_missing_markdown_image_is_a_finding(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a missing Markdown image is one error finding.

    Scenario:
        Given a Markdown image whose target does not exist in root
        When check_text runs with defaults
        Then exactly one DS113 error finding names the raw target at its one-based line.

    Boundaries:
        - Focus: the core missing-asset finding, severity, path, line, and bounded echo
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the resolver returned RESOLVED and os.stat raised for the absent file
    """
    findings = assets.check_text("intro\n\n![flow](diagrams/flow.svg)\n", _DOC, _root(tmp_path))

    assert findings == (
        models.Finding(
            rule="DS113",
            path=_DOC,
            message="missing asset: diagrams/flow.svg",
            severity="error",
            line=3,
        ),
    )


def test_missing_html_image_src_is_a_finding(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a missing HTML <img src> is a finding.

    Scenario:
        Given an HTML ``<img src>`` pointing at an absent local file
        When check_text runs with defaults
        Then one DS113 error finding is produced for the src target.

    Boundaries:
        - Focus: HTML media tag recognition via the shared scanner image tokens
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the scanner tagged the image attribute as ``src`` and check_html_asset_tags is on
    """
    assert _messages(assets.check_text('<img src="media/missing.png">\n', _DOC, _root(tmp_path))) == [
        "missing asset: media/missing.png"
    ]


def test_srcset_reports_only_the_absent_candidate(tmp_path: Path):
    """
    [Unit] detectors assets: verifies srcset candidate splitting flags only the missing one.

    Scenario:
        Given an ``<img srcset>`` whose low-DPI candidate exists and high-DPI candidate is absent
        When check_text runs with defaults
        Then exactly one finding names the absent high-DPI candidate.

    Boundaries:
        - Focus: srcset candidate splitting and per-candidate existence
        - Fixtures/params: tmp_path

    On failure, first check:
        - _srcset_urls splitting and the srcset attribute gating
    """
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "small.png").write_text("x", encoding="utf-8")

    assert _messages(
        assets.check_text('<img srcset="images/small.png 1x, images/big.png 2x">\n', _DOC, _root(tmp_path))
    ) == ["missing asset: images/big.png"]


def test_known_accuracy_gaps_are_pinned(tmp_path: Path):
    """
    [Unit] detectors assets: verifies the documented accuracy gaps stay explicit.

    Scenario:
        Given an image in an indented code block, and a shortcut reference image
        When DS113 recognition runs over each
        Then the indented one is reported (known false positive) and the shortcut one is not
            (known false negative), exactly as docs/dev/markdown_dialect.md states.

    Boundaries:
        - Focus: the security-review gaps are pinned so a scanner change cannot flip them silently
        - Fixtures/params: tmp_path as the scan root

    On failure, first check:
        - Whether the scanner started modelling indented code or shortcut references
        - Whether docs/dev/markdown_dialect.md and the threat model were updated to match
    """
    indented = assets.check_text("    ![x](missing.png)\n", "README.md", tmp_path)
    shortcut = assets.check_text("![ref]\n\n[ref]: missing.png\n", "README.md", tmp_path)
    collapsed = assets.check_text("![ref][]\n\n[ref]: missing.png\n", "README.md", tmp_path)

    assert [finding.line for finding in indented] == [1]
    assert shortcut == ()
    assert [finding.line for finding in collapsed] == [3]


def test_srcset_data_uri_is_never_probed(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a data: URI srcset candidate yields no filesystem probe.

    Scenario:
        Given an ``<img srcset>`` mixing a ``data:`` URI (with an internal comma) and a real file
        When check_text runs with defaults and the real file exists
        Then there are zero findings, so no base64 fragment became a spurious missing-asset probe.

    Boundaries:
        - Focus: the HIGH srcset/data-URI split fix seen through DS113
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the data URI stayed one EXTERNAL candidate after the WHATWG split
    """
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "real.png").write_text("x", encoding="utf-8")

    assert (
        assets.check_text(
            '<img srcset="data:image/png;base64,iVBORw0KGgo= 1x, images/real.png 2x">\n', _DOC, _root(tmp_path)
        )
        == ()
    )


@pytest.mark.parametrize(
    "target",
    (
        "https://example.com/logo.png",
        "http://example.com/logo.png",
        "data:image/png;base64,iVBORw0KGgo=",
        "//host/logo.png",
        "#section",
        "${IMAGE}",
        "{asset_path}",
        "assets/*.png",
    ),
)
def test_external_fragment_template_and_glob_targets_are_skipped(tmp_path: Path, target: str):
    """
    [Unit] detectors assets: verifies non-local targets are never checked as assets.

    Scenario:
        Given an image whose target is a URL scheme, data URI, protocol-relative host, fragment-only,
            template, or glob
        When check_text runs with defaults
        Then no finding is produced, because none is a resolvable local asset.

    Boundaries:
        - Focus: the explicit exclusions (external, data, protocol-relative, fragment, template, glob)
        - Fixtures/params: parametrized over each excluded target shape

    On failure, first check:
        - Whether resolve_local_reference classified the target as EXTERNAL / UNSUPPORTED rather than RESOLVED
    """
    assert assets.check_text(f"![a]({target})\n", _DOC, _root(tmp_path)) == ()


@pytest.mark.parametrize(
    "target",
    (
        "../../secrets.png",
        r"C:\Windows\logo.png",
        "c:/logo.png",
        r"\\server\share\logo.png",
        r"a\b.png",
    ),
)
def test_ds116_owned_targets_are_deferred_and_never_stated(tmp_path: Path, target: str):
    """
    [Unit] detectors assets: verifies escaping and Windows-form targets are deferred to DS116.

    Scenario:
        Given an image target that lexically escapes the root or is a Windows drive/UNC/backslash form
        When check_text runs with defaults
        Then DS113 emits nothing, leaving the unsafe category to DS116 (ruling R2).

    Boundaries:
        - Focus: the is_ds116_owned containment gate before any filesystem call
        - Fixtures/params: parametrized over each DS116-owned category

    On failure, first check:
        - Whether is_ds116_owned returned True for the category and short-circuited before os.stat
    """
    (tmp_path / "docs").mkdir()
    assert assets.check_text(f"![a]({target})\n", "docs/README.md", _root(tmp_path)) == ()


def test_alt_text_path_is_not_treated_as_the_asset(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a path-like alt text is not resolved as an asset.

    Scenario:
        Given a Markdown image whose alt text contains a path-like string and whose real target exists
        When check_text runs with defaults
        Then no finding is produced, because only the destination (not the alt text) is an asset.

    Boundaries:
        - Focus: the "do not guess filenames in prose" exclusion
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the destination token (not the bracket alt text) was resolved
    """
    (tmp_path / "real.png").write_text("x", encoding="utf-8")

    assert assets.check_text("![see docs/missing.md for details](real.png)\n", _DOC, _root(tmp_path)) == ()


def test_image_inside_code_span_and_comment_and_fence_is_ignored(tmp_path: Path):
    """
    [Unit] detectors assets: verifies masked-region images are never reported.

    Scenario:
        Given missing-image markup inside an inline code span, inside an HTML comment, and inside a
            fenced code block, plus one live missing image
        When check_text runs with defaults
        Then only the live missing image is reported, matching what a CommonMark renderer makes live.

    Boundaries:
        - Focus: scanner-evasion parity (mask only what CommonMark hides), requirement 7
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _coalesced_masked_ranges covered inline code and comments and fenced lines were skipped
    """
    text = (
        "![live](live.png)\n"
        "Inline `![c](in_code.png)` span.\n"
        "<!-- ![k](in_comment.png) -->\n"
        "```\n![f](in_fence.png)\n```\n"
    )

    assert _messages(assets.check_text(text, _DOC, _root(tmp_path))) == ["missing asset: live.png"]


def test_two_missing_images_produce_two_ordered_findings(tmp_path: Path):
    """
    [Unit] detectors assets: verifies distinct missing images yield deterministic ordered findings.

    Scenario:
        Given two distinct nonexistent images on consecutive lines
        When check_text runs with defaults
        Then two findings are produced in source-line order, each naming its own target.

    Boundaries:
        - Focus: stable source ordering and one finding per distinct reference
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether candidates are sorted by offset and (line, message) de-duplication is intact
    """
    findings = assets.check_text("![a](a.png)\n![b](b.png)\n", _DOC, _root(tmp_path))

    assert [(finding.line, finding.message) for finding in findings] == [
        (1, "missing asset: a.png"),
        (2, "missing asset: b.png"),
    ]


def test_duplicate_reference_on_one_line_is_collapsed(tmp_path: Path):
    """
    [Unit] detectors assets: verifies an identical reference repeated on a line collapses to one finding.

    Scenario:
        Given the same missing image written twice on one line
        When check_text runs with defaults
        Then exactly one finding is produced for that (line, message) pair.

    Boundaries:
        - Focus: duplicate (line, message) collapse and single-stat memoisation
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the seen-set de-duplication and the per-path stat cache are intact
    """
    assert _messages(assets.check_text("![a](same.png) and ![b](same.png)\n", _DOC, _root(tmp_path))) == [
        "missing asset: same.png"
    ]


def test_percent_encoded_target_resolves_and_is_echoed_raw(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a percent-encoded relative target decodes to a missing file.

    Scenario:
        Given an image whose target is percent-encoded and whose decoded file is absent
        When check_text runs with defaults
        Then one finding is produced and its message echoes the author's raw (still-encoded) target.

    Boundaries:
        - Focus: decode-once resolution and raw-target echo (never the resolved path)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the resolver decoded once and whether the message echoes the raw target verbatim
    """
    assert _messages(assets.check_text("![a](images/my%20file.png)\n", _DOC, _root(tmp_path))) == [
        "missing asset: images/my%20file.png"
    ]


def test_nested_document_relative_path_resolves_inside_root(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a ../ path from a nested document resolves inside root.

    Scenario:
        Given a nested ``docs/README.md`` whose image climbs one level to an existing ``images/plot.svg``
        When check_text runs with defaults
        Then no finding is produced, because the path stays inside the root and exists.

    Boundaries:
        - Focus: document-relative resolution from a subdirectory
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the document directory was used as the join base
    """
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "plot.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "docs").mkdir()

    assert assets.check_text("![plot](../images/plot.svg)\n", "docs/README.md", _root(tmp_path)) == ()


def test_reference_definition_is_checked_only_when_used_and_asset_typed(tmp_path: Path):
    """
    [Unit] detectors assets: verifies ruling R1 for reference-style definitions.

    Scenario:
        Given a used reference-style image whose definition points at a missing asset-typed file, a
            used definition whose target exists, and an unused definition pointing at a missing file
        When check_text runs with defaults
        Then only the used, missing, asset-typed definition is a finding.

    Boundaries:
        - Focus: R1 (check a definition only when used and its extension is an asset extension)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether reference_uses labels were joined to reference_definitions and the extension gate applied
    """
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "ok.svg").write_text("<svg/>", encoding="utf-8")
    text = (
        "![missing chart][m]\n"
        "![present chart][p]\n\n"
        "[m]: images/missing.svg\n"
        "[p]: images/ok.svg\n"
        "[u]: images/unused.svg\n"
    )

    assert _messages(assets.check_text(text, _DOC, _root(tmp_path))) == ["missing asset: images/missing.svg"]


def test_html_href_is_gated_by_asset_extension(tmp_path: Path):
    """
    [Unit] detectors assets: verifies HTML <a href> is checked only for asset extensions.

    Scenario:
        Given an HTML ``<a href>`` to a missing ``.pdf`` and another to a missing ``.md``, with pdf in
            asset_extensions
        When check_text runs with that config
        Then only the ``.pdf`` href is a finding; the ``.md`` link is left to DS101 (ruling R5).

    Boundaries:
        - Focus: R5 extension gate for link-shaped HTML references
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the LocalReference.html flag and the asset-extension gate are both applied
    """
    config = Config(asset_extensions=("pdf",))
    text = '<a href="manual.pdf">m</a>\n<a href="guide.md">g</a>\n'

    assert _messages(assets.check_text(text, _DOC, _root(tmp_path), config)) == ["missing asset: manual.pdf"]


def test_extension_matching_is_case_insensitive(tmp_path: Path):
    """
    [Unit] detectors assets: verifies the asset-extension gate matches case-insensitively.

    Scenario:
        Given an HTML href to a missing ``report.PDF`` with asset_extensions configured as ``pdf``
        When check_text runs
        Then the href is still recognised as an asset reference and reported missing.

    Boundaries:
        - Focus: requirement 8, case-insensitive extension scope (not the filesystem case policy)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether both the configured extension and the path suffix are lower-cased before comparing
    """
    config = Config(asset_extensions=("pdf",))

    assert _messages(assets.check_text('<a href="report.PDF">r</a>\n', _DOC, _root(tmp_path), config)) == [
        "missing asset: report.PDF"
    ]


def test_directory_target_is_a_non_regular_finding(tmp_path: Path):
    """
    [Unit] detectors assets: verifies an existing directory at an asset path is a finding.

    Scenario:
        Given an image target that resolves to an existing directory
        When check_text runs with defaults
        Then one finding reports it is not a regular file, without disclosing the specific type.

    Boundaries:
        - Focus: ruling R3 (a present non-regular path is a finding, not a silent pass)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether S_ISREG was false and the generic non-regular message was used
    """
    (tmp_path / "gallery").mkdir()

    assert _messages(assets.check_text("![a](gallery)\n", _DOC, _root(tmp_path))) == [
        "asset is not a regular file: gallery"
    ]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="os.mkfifo unavailable on this platform")
def test_fifo_target_is_reported_without_opening(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a FIFO at an asset path is a non-regular finding and is never opened.

    Scenario:
        Given a runtime-created FIFO at an in-root asset path
        When check_text runs with defaults
        Then one non-regular-file finding is produced promptly, proving the check used os.stat and never
            opened the FIFO (an open would block forever).

    Boundaries:
        - Focus: the HIGH special-files control (stat + S_ISREG only, never open/read)
        - Fixtures/params: tmp_path; skipped with a reason when os.mkfifo is unavailable

    On failure, first check:
        - Whether os.stat (not open) decided the type and S_ISREG was false
    """
    os.mkfifo(tmp_path / "pipe.png")

    assert _messages(assets.check_text("![a](pipe.png)\n", _DOC, _root(tmp_path))) == [
        "asset is not a regular file: pipe.png"
    ]


def test_in_root_symlink_to_regular_file_is_valid(tmp_path: Path):
    """
    [Unit] detectors assets: verifies an in-root symlink to an in-root regular file is clean (R3).

    Scenario:
        Given an in-root symlink whose target is an in-root regular file
        When check_text runs with defaults
        Then no finding is produced, because following in-root hops lands on a regular file.

    Boundaries:
        - Focus: ruling R3 (follow in-root symlink hops, test S_ISREG on the final in-root target)
        - Fixtures/params: tmp_path; skipped with a reason when symlinks are unavailable

    On failure, first check:
        - Whether escapes_via_symlink stayed in-root and os.stat followed to the regular file
    """
    (tmp_path / "real.png").write_text("x", encoding="utf-8")
    _symlink_or_skip(tmp_path / "link.png", "real.png")

    assert assets.check_text("![a](link.png)\n", _DOC, _root(tmp_path)) == ()


def test_in_root_symlink_escaping_outside_is_deferred_to_ds116(tmp_path: Path):
    """
    [Unit] detectors assets: verifies an in-root symlink pointing outside root is not a DS113 finding.

    Scenario:
        Given an in-root symlink whose target resolves above the root to a real outside file
        When check_text runs with defaults
        Then DS113 emits nothing and never stats the outside target, leaving the escape to DS116 (R2).

    Boundaries:
        - Focus: escapes_via_symlink gate before any stat
        - Fixtures/params: tmp_path; skipped with a reason when symlinks are unavailable

    On failure, first check:
        - Whether escapes_via_symlink returned True for the in-root symlink and short-circuited
    """
    root = tmp_path / "root"
    (root / "docs").mkdir(parents=True)
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.png").write_text("s", encoding="utf-8")
    _symlink_or_skip(root / "docs" / "evil.png", "../../outside/secret.png")

    assert assets.check_text("![a](evil.png)\n", "docs/README.md", Path(os.path.realpath(root))) == ()


def test_broken_in_root_symlink_is_missing(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a broken in-root symlink reads as missing.

    Scenario:
        Given an in-root symlink whose in-root target does not exist
        When check_text runs with defaults
        Then one missing-asset finding is produced (the following os.stat raised in-root).

    Boundaries:
        - Focus: a broken in-root symlink is "missing", not an escape
        - Fixtures/params: tmp_path; skipped with a reason when symlinks are unavailable

    On failure, first check:
        - Whether os.stat raised for the broken in-root target and was caught as missing
    """
    _symlink_or_skip(tmp_path / "broken.png", "nope.png")

    assert _messages(assets.check_text("![a](broken.png)\n", _DOC, _root(tmp_path))) == ["missing asset: broken.png"]


def test_escaped_bang_image_is_an_accepted_over_detection(tmp_path: Path):
    """
    [Unit] detectors assets: verifies ruling R4 (``\\![alt](x)`` is still seen as an image).

    Scenario:
        Given a backslash-escaped image ``\\![alt](missing.png)`` the scanner does not model as escaped
        When check_text runs with defaults
        Then DS113 reports the missing image, an accepted over-detection rather than a hidden escape.

    Boundaries:
        - Focus: R4 (accept the scanner's non-modelling of backslash escapes outside tables)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the scanner still emits an image token for the escaped bang (if not, update R4 docs)
    """
    assert _messages(assets.check_text("\\![alt](missing.png)\n", _DOC, _root(tmp_path))) == [
        "missing asset: missing.png"
    ]


def test_long_target_is_bounded_and_echo_never_leaks_the_resolved_path(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a long missing target is echoed bounded, never as the resolved path.

    Scenario:
        Given a missing image whose in-root relative target is 10,000 characters long
        When check_text runs with defaults
        Then the single finding's message stays well under the bound, ends with the truncation marker,
            and never contains the resolved absolute root path.

    Boundaries:
        - Focus: the bounded echo and the no-resolved-path disclosure control (MEDIUM)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _echo bounded to _MAX_ECHO and the resolved absolute path stayed out of the message
    """
    root = _root(tmp_path)
    raw = "images/" + "a" * 10_000 + ".png"
    findings = assets.check_text(f"![x]({raw})\n", _DOC, root)

    assert len(findings) == 1
    message = findings[0].message
    assert message.endswith("...")
    assert len(message) < 120
    assert str(root) not in message


def test_non_ascii_bytes_in_target_are_repr_escaped(tmp_path: Path):
    """
    [Unit] detectors assets: verifies non-ASCII bytes in an echoed target are neutralised.

    Scenario:
        Given a missing image whose in-root target carries a non-ASCII character and an RTL override
        When check_text runs with defaults
        Then the message contains no raw non-ASCII byte (each is rendered as a printable escape), so the
            report sinks receive only printable ASCII.

    Boundaries:
        - Focus: unicode_escape neutralisation of non-ASCII / control-display bytes before the sinks
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _echo encoded the target with unicode_escape before building the message
    """
    findings = assets.check_text("![x](images/café‮.png)\n", _DOC, _root(tmp_path))

    assert len(findings) == 1
    message = findings[0].message
    assert message.isascii()
    assert "\\xe9" in message and "\\u202e" in message


def test_control_byte_target_is_deferred_and_never_echoed(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a control-byte target is deferred to DS116, never echoed by DS113.

    Scenario:
        Given a missing image whose target carries NUL and ESC control bytes
        When check_text runs with defaults
        Then DS113 emits nothing (the resolver classifies control bytes as a DS116-owned category), so no
            control byte can ever reach a DS113 report sink.

    Boundaries:
        - Focus: control bytes are a DS116-owned category (R2), so DS113 never echoes them
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether is_ds116_owned returned True for the control category and short-circuited DS113
    """
    assert assets.check_text("![x](images/a\x00\x1bb.png)\n", _DOC, _root(tmp_path)) == ()


def test_missing_asset_policy_off_is_silent_and_does_no_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors assets: verifies missing_asset_policy=off short-circuits with no filesystem access.

    Scenario:
        Given a missing image and ``missing_asset_policy="off"`` with os.stat wired to fail if called
        When check_text runs
        Then no finding is produced and os.stat is never invoked.

    Boundaries:
        - Focus: the off policy suppresses the rule with zero I/O (mirrors root_escape_policy)
        - Fixtures/params: tmp_path, monkeypatch

    On failure, first check:
        - Whether the off short-circuit runs before scan_markdown and any stat
    """

    def _boom(*_args: object, **_kwargs: object) -> object:
        """Fail loudly if any os.stat is attempted under the off policy."""
        raise AssertionError("os.stat called under missing_asset_policy=off")

    monkeypatch.setattr(os, "stat", _boom)

    assert assets.check_text("![a](missing.png)\n", _DOC, _root(tmp_path), Config(missing_asset_policy="off")) == ()


def test_missing_asset_policy_warn_downgrades_severity(tmp_path: Path):
    """
    [Unit] detectors assets: verifies missing_asset_policy=warn emits warning-severity findings.

    Scenario:
        Given a missing image and ``missing_asset_policy="warn"``
        When check_text runs
        Then the finding is produced at ``warning`` severity while the rule metadata severity stays error.

    Boundaries:
        - Focus: the warn policy downgrade
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether check_text mapped the policy to the emitted severity and left DS113.severity unchanged
    """
    findings = assets.check_text("![a](missing.png)\n", _DOC, _root(tmp_path), Config(missing_asset_policy="warn"))

    assert [finding.severity for finding in findings] == ["warning"]
    assert assets.DS113.severity == "error"


@pytest.mark.parametrize(
    ("config", "clean"),
    (
        (Config(check_markdown_images=False), "![a](missing.png)\n"),
        (Config(check_html_asset_tags=False), '<img src="missing.png">\n'),
        (Config(check_html_asset_tags=False, check_srcset=True), '<img srcset="missing.png 1x">\n'),
        (Config(check_srcset=False), '<img srcset="missing.png 1x">\n'),
    ),
)
def test_check_toggles_disable_their_reference_kind(tmp_path: Path, config: Config, clean: str):
    """
    [Unit] detectors assets: verifies each check_* toggle suppresses exactly its reference kind.

    Scenario:
        Given a missing reference of a given kind and the matching toggle disabled (and, for srcset,
            that disabling the HTML media tags also removes srcset)
        When check_text runs with that config
        Then no finding is produced for the disabled kind.

    Boundaries:
        - Focus: wiring of check_markdown_images / check_html_asset_tags / check_srcset
        - Fixtures/params: parametrized over the toggle/reference combinations

    On failure, first check:
        - Whether _collect_candidates honoured the toggle for that image attribute
    """
    assert assets.check_text(clean, _DOC, _root(tmp_path), config) == ()


def test_src_still_checked_when_only_srcset_disabled(tmp_path: Path):
    """
    [Unit] detectors assets: verifies disabling check_srcset leaves <img src> checks active.

    Scenario:
        Given a missing ``<img src>`` with ``check_srcset=False`` but ``check_html_asset_tags=True``
        When check_text runs
        Then the src target is still reported, so the srcset toggle is independent of plain src.

    Boundaries:
        - Focus: srcset toggle independence from src via the image attribute field
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the Image.attribute of a plain src is "src" (not "srcset")
    """
    assert _messages(
        assets.check_text('<img src="missing.png">\n', _DOC, _root(tmp_path), Config(check_srcset=False))
    ) == ["missing asset: missing.png"]


def test_detect_reads_only_markdown_documents_in_order(tmp_path: Path):
    """
    [Unit] detectors assets: verifies detect canonicalises the root and scans documents in order.

    Scenario:
        Given two Markdown documents each referencing a distinct missing image and one non-Markdown file
        When detect runs over them
        Then findings appear in document then source order and the non-Markdown file is ignored.

    Boundaries:
        - Focus: the detect entry point (realpath once, per-document check_text)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether detect filtered to .md and preserved supplied document order
    """
    (tmp_path / "a.md").write_text("![a](a.png)\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("![b](b.png)\n", encoding="utf-8")
    (tmp_path / "c.txt").write_text("![c](c.png)\n", encoding="utf-8")
    documents = (models.Document("a.md", 0), models.Document("b.md", 0), models.Document("c.txt", 0))

    findings = assets.detect(tmp_path, documents)

    assert [(finding.path, finding.message) for finding in findings] == [
        ("a.md", "missing asset: a.png"),
        ("b.md", "missing asset: b.png"),
    ]


def _multi_line(unit_for: Callable[[int], str]) -> Callable[[int], str]:
    """Return a builder producing ``size`` lines, each a distinct unit.

    :param unit_for: A ``index -> str`` callable producing a distinct unit per index.
    :returns: A ``size -> str`` builder for the multi-line flood.
    """

    def build(size: int) -> str:
        """Build ``size`` newline-separated distinct unit lines.

        :param size: The number of lines to emit.
        :returns: The multi-line flood source.
        """
        return "".join(unit_for(index) + "\n" for index in range(size))

    return build


def test_many_images_multi_line_flood_is_linear(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a multi-line flood of distinct missing images stays linear.

    Scenario:
        Given a doubling series of documents each carrying ``size`` distinct missing Markdown images on
            their own lines
        When check_text runs over each
        Then the run stays under the shared linear bound and produces exactly ``size`` findings per size.

    Boundaries:
        - Focus: O(total bytes) handling and one finding per distinct reference across many lines
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether candidate collection, sorting, or stat memoisation introduced a super-linear shape
    """

    root = _root(tmp_path)
    assert_scales_linearly(
        _multi_line(lambda index: f"![a{index}](missing{index}.png)"),
        lambda text: assets.check_text(text, _DOC, root),
        (1_000, 2_000, 4_000, 8_000),
        expected_count=lambda size: size,
        label="ds113-images-multiline",
    )


def test_srcset_single_line_candidate_flood_is_linear(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a single-line srcset candidate flood stays linear.

    Scenario:
        Given a doubling series of one-line ``<img srcset>`` attributes holding ``size`` distinct missing
            candidates each
        When check_text runs over each
        Then the run stays under the shared linear bound and produces exactly ``size`` findings per size,
            proving _srcset_urls and the per-candidate stat stay O(total bytes).

    Boundaries:
        - Focus: srcset candidate-flood linearity on one line
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _srcset_urls or the per-candidate classification became super-linear
    """

    root = _root(tmp_path)

    def build(size: int) -> str:
        """Build one ``<img srcset>`` line with ``size`` distinct missing candidates.

        :param size: The number of srcset candidates.
        :returns: The single-line srcset flood source.
        """
        candidates = ", ".join(f"m{index}.png {index + 1}x" for index in range(size))
        return f'<img srcset="{candidates}">\n'

    assert_scales_linearly(
        build,
        lambda text: assets.check_text(text, _DOC, root),
        (500, 1_000, 2_000, 4_000),
        expected_count=lambda size: size,
        label="ds113-srcset-singleline",
    )


def test_srcset_multi_line_flood_is_linear(tmp_path: Path):
    """
    [Unit] detectors assets: verifies a multi-line srcset flood stays linear.

    Scenario:
        Given a doubling series of documents with ``size`` distinct one-candidate ``<img srcset>`` lines
        When check_text runs over each
        Then the run stays under the shared linear bound and produces exactly ``size`` findings per size.

    Boundaries:
        - Focus: srcset linearity across many lines
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether per-line srcset extraction or candidate collection became super-linear
    """

    root = _root(tmp_path)
    assert_scales_linearly(
        _multi_line(lambda index: f'<img srcset="m{index}.png 1x">'),
        lambda text: assets.check_text(text, _DOC, root),
        (1_000, 2_000, 4_000, 8_000),
        expected_count=lambda size: size,
        label="ds113-srcset-multiline",
    )
