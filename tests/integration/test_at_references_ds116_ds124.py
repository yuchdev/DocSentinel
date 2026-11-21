"""Integration tests for the DS116/DS124 ownership split over ``@``-mentions (threat model 0009 T2, T6).

Every recognised ``relative`` mention must end in exactly one state: it resolves, it gets one
DS116 finding, or it gets one DS124 finding. The single documented exception is a step-2
refusal (ruling R1). Symlink trees are built in the test body under ``tmp_path``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import Union

import pytest

import docsentinel
from docsentinel import models
from docsentinel.config import Config
from docsentinel.detectors import mentions, path_boundaries
from tests.asset_helpers import AssetCase

AssetLoader = Callable[[str, str], AssetCase]


def _symlink(link: Path, target: Union[Path, str], *, directory: bool = True):
    """Create a symlink or skip the test when the platform refuses.

    :param link: The link path to create.
    :param target: What it points at.
    :param directory: Whether the target is a directory.
    """
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError:
        pytest.skip("symlinks unavailable: the platform or its permissions refused a symlink")


def _by_rule(result: models.ScanResult, rule: str) -> list[models.Finding]:
    """Return the findings of one rule.

    :param result: A scan result.
    :param rule: The rule code.
    :returns: Its findings in order.
    """
    return [finding for finding in result.findings if finding.rule == rule]


def _shape(finding: models.Finding) -> tuple[object, ...]:
    """Return every reported field of a finding.

    :param finding: A finding.
    :returns: ``(rule, path, line, column, value, type, severity, message)``.
    """
    return (
        finding.rule,
        finding.path,
        finding.line,
        finding.column,
        finding.value,
        finding.type,
        finding.severity,
        finding.message,
    )


def _ds124(path: str, line: int, column: int, raw: str) -> tuple[object, ...]:
    """Return the expected shape of a DS124 finding (ADR 0004 Contract 3).

    :param path: The referring document.
    :param line: The 1-based line of the ``@``.
    :param column: The 1-based column of the ``@``.
    :param raw: The bounded raw mention.
    :returns: The expected field tuple.
    """
    return ("DS124", path, line, column, raw, "dangling document mention", "warning", f"dangling @-reference -> {raw}")


def _ds116(line: int, message: str) -> tuple[object, ...]:
    """Return the expected shape of a DS116 finding on README.md (DS116 sets no column, value or type).

    :param line: The 1-based line.
    :param message: The DS116 message.
    :returns: The expected field tuple.
    """
    return ("DS116", "README.md", line, None, None, None, "error", message)


def _tree(tmp_path: Path) -> Path:
    """Return a canonical scan root ``docs`` with an ``outside`` sibling holding x.md.

    :param tmp_path: The pytest scratch directory.
    :returns: The scan root.
    """
    base = tmp_path.resolve()
    (base / "outside").mkdir()
    (base / "outside" / "x.md").write_text("# X\n", encoding="utf-8")
    root = base / "docs"
    root.mkdir()
    return root


def test_symlink_out_step1_is_ds116_only(tmp_path: Path):
    """
    [Integration] ownership: a mention through an in-root symlink leaving the root is DS116 only.

    Scenario:
        Given docs/out -> ../outside and a prose mention @out/x.md (the file exists outside)
        When docs/ is scanned
        Then one DS116 symlink finding and zero DS124 findings.

    Boundaries:
        - Focus: M5 shared predicate on step 1
        - Fixtures/params: symlink built in the test body

    On failure, first check:
        - mention_ds116_reason and the early return in mentions._Resolver._resolve
    """
    root = _tree(tmp_path)
    _symlink(root / "out", root.parent / "outside")
    (root / "README.md").write_text("@out/x.md\n", encoding="utf-8")

    result = docsentinel.scan(root)

    assert [_shape(finding) for finding in result.findings] == [
        _ds116(1, "reference resolves through a symlink that escapes the documentation root: @out/x.md")
    ]


def test_symlink_cycle_mention_is_one_ds124_finding(tmp_path: Path):
    """
    [Integration] ownership: a mention through an in-root symlink cycle is exactly one DS124 finding.

    Scenario:
        Given docs/loop -> loop and a mention @loop/x.md
        When docs/ is scanned
        Then zero DS116 findings and exactly one DS124 finding.

    Boundaries:
        - Focus: T2(b) no silent gap (M5)
        - Fixtures/params: symlink cycle built in the test body

    On failure, first check:
        - That a contained_path refusal that is not an escape falls through to "missing"
    """
    root = _tree(tmp_path)
    _symlink(root / "loop", "loop")
    (root / "README.md").write_text("@loop/x.md\n", encoding="utf-8")

    result = docsentinel.scan(root)

    assert [_shape(finding) for finding in result.findings] == [_ds124("README.md", 1, 1, "@loop/x.md")]


def test_symlink_chain_over_hop_limit_is_one_ds124_finding(tmp_path: Path):
    """
    [Integration] ownership: a chain of 70 in-root symlinks (over the 64-hop bound) is one DS124 finding.

    Scenario:
        Given docs/l0 -> l1 -> ... -> l69 -> real (a directory holding x.md) and a mention @l0/x.md
        When docs/ is scanned
        Then zero DS116 findings and exactly one DS124 finding.

    Boundaries:
        - Focus: hop overflow is "does not resolve", never silent
        - Fixtures/params: symlink chain built in the test body

    On failure, first check:
        - _MAX_SYMLINK_HOPS handling in contained_path and escapes_via_symlink
    """
    root = _tree(tmp_path)
    (root / "real").mkdir()
    (root / "real" / "x.md").write_text("# X\n", encoding="utf-8")
    _symlink(root / "l69", "real")
    for index in range(68, -1, -1):
        _symlink(root / f"l{index}", f"l{index + 1}")
    (root / "README.md").write_text("@l0/x.md\n", encoding="utf-8")

    result = docsentinel.scan(root, config=dataclasses.replace(Config(), exclude=("l*",)))

    owned = [finding for finding in result.findings if finding.rule in ("DS116", "DS124")]
    assert [_shape(finding) for finding in owned] == [_ds124("README.md", 1, 1, "@l0/x.md")]


def test_extensionless_at_code_span_escape_still_ds116(asset_case: AssetLoader):
    """
    [Integration] A1: an ``@`` code span that is not a mention keeps its DS116 traversal check.

    Scenario:
        Given `@../../../../etc/passwd` (no extension, so no mention)
        When docs/ is scanned
        Then exactly one DS116 escape finding and zero DS124 findings.

    Boundaries:
        - Focus: M11, DS116 never drops a code span by prefix
        - Fixtures/params: ds124/at_code_span_extensionless_escape

    On failure, first check:
        - The span-identity exclusion in path_boundaries.check_text
    """
    case = asset_case("ds124", "at_code_span_extensionless_escape")

    result = docsentinel.scan(case.root / "docs")

    assert [_shape(finding) for finding in result.findings] == [
        _ds116(3, "reference escapes the documentation root: @../../../../etc/passwd")
    ]


def test_code_span_mention_classified_once(tmp_path: Path):
    """
    [Integration] A1: a code-span mention that escapes is one DS116 finding, not two.

    Scenario:
        Given `@../outside/x.md` on one line
        When docs/ is scanned
        Then one DS116 finding (the mention) and the code span is not a second candidate.

    Boundaries:
        - Focus: span-identity exclusion keeps one classification per mention
        - Fixtures/params: none

    On failure, first check:
        - mention_spans in path_boundaries.check_text
    """
    root = _tree(tmp_path)
    (root / "README.md").write_text("`@../outside/x.md`\n", encoding="utf-8")

    result = docsentinel.scan(root)

    assert [_shape(finding) for finding in result.findings] == [
        _ds116(1, "reference escapes the documentation root: @../outside/x.md")
    ]


def test_ds116_policy_off_still_keeps_ds124_out(tmp_path: Path):
    """
    [Integration] ownership: with DS116 off, an escaping mention is still not a DS124 finding.

    Scenario:
        Given root_escape_policy = "off" and @../outside/x.md
        When docs/ is scanned
        Then there is neither a DS116 nor a DS124 finding.

    Boundaries:
        - Focus: M3, the predicate ignores DS116's options
        - Fixtures/params: none

    On failure, first check:
        - _MENTION_SETTINGS in path_boundaries
    """
    root = _tree(tmp_path)
    (root / "README.md").write_text("@../outside/x.md\n", encoding="utf-8")

    result = docsentinel.scan(root, config=dataclasses.replace(Config(), root_escape_policy="off"))

    assert result.findings == ()


def test_every_relative_mention_has_exactly_one_outcome(tmp_path: Path):
    """
    [Integration] ownership sweep: each relative mention resolves, is DS116, or is DS124 -- never two.

    Scenario:
        Given one line per scenario (resolves, missing, escape, symlink-out, cycle, hop overflow,
            directory, code-span escape, step-2 refusal)
        When docs/ is scanned
        Then every line has the expected single outcome, and only the step-2 refusal has none.

    Boundaries:
        - Focus: T2 table-driven sweep of M5/M6
        - Fixtures/params: symlinks built in the test body

    On failure, first check:
        - mentions._Resolver._resolve and path_boundaries.mention_ds116_reason
    """
    root = _tree(tmp_path)
    (root / "a").mkdir()
    (root / "present.md").write_text("# P\n", encoding="utf-8")
    (root / "folder.md").mkdir()
    (root / "real").mkdir()
    _symlink(root / "out", root.parent / "outside")
    _symlink(root / "loop", "loop")
    _symlink(root / "h70", "real")
    for index in range(69, -1, -1):
        _symlink(root / f"h{index}", f"h{index + 1}")
    expected = {
        "@present.md": None,
        "@missing.md": "DS124",
        "@../outside/x.md": "DS116",
        "@out/x.md": "DS116",
        "@loop/x.md": "DS124",
        "@h0/x.md": "DS124",
        "@folder.md": "DS124",
        "`@../outside/y.md`": "DS116",
        "`@gone.md`": "DS124",
    }
    lines = list(expected)
    (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # The documented exception (ruling R1): step 1 stays in the scan root (a/../gone.md is
    # missing), step 2 ("/../gone.md") climbs above the link root, so neither rule reports it.
    (root / "a" / "refusal.md").write_text("@../gone.md\n", encoding="utf-8")

    result = docsentinel.scan(root, config=dataclasses.replace(Config(), exclude=("h*", "loop", "out")))

    outcomes: dict[int, list[str]] = {}
    for finding in result.findings:
        if finding.path == "README.md" and finding.rule in ("DS116", "DS124"):
            outcomes.setdefault(finding.line or 0, []).append(finding.rule)
    for line_number, mention in enumerate(lines, 1):
        want = expected[mention]
        assert outcomes.get(line_number, []) == ([] if want is None else [want]), mention
    assert not [finding for finding in result.findings if finding.path == "a/refusal.md"]


def test_deep_prefix_symlink_out_is_ds116(tmp_path: Path):
    """
    [Integration] ownership: a symlink-out after 70 plain components is still a DS116 escape.

    Scenario:
        Given 70 nested plain directories whose last holds out -> ../outside-like host directory,
            and a mention through all of them
        When docs/ is scanned
        Then exactly one DS116 symlink finding and zero DS124 findings.

    Boundaries:
        - Focus: security review M-A (only followed symlinks count toward the 64-hop cap)
        - Fixtures/params: directories and symlink built in the test body

    On failure, first check:
        - The hop counter of the shared walker in path_boundaries
    """
    root = _tree(tmp_path)
    deep = root.joinpath(*(["d"] * 70))
    deep.mkdir(parents=True)
    _symlink(deep / "out", root.parent / "outside")
    (root / "README.md").write_text("@" + "d/" * 70 + "out/x.md\n", encoding="utf-8")

    result = docsentinel.scan(root, config=dataclasses.replace(Config(), exclude=("d",)))

    assert len(_by_rule(result, "DS116")) == 1
    assert "symlink that escapes" in _by_rule(result, "DS116")[0].message
    assert _by_rule(result, "DS124") == []


def test_symlinked_scan_root_mention_has_one_outcome(tmp_path: Path):
    """
    [Integration] ownership: called through a symlinked scan root, a dangling mention still gets one outcome.

    Scenario:
        Given via -> real as the scan root, and real/abs.md an absolute symlink (spelt canonically)
            to the missing real/missing.md, mentioned as @abs.md
        When DS124 and DS116 are called directly with the symlinked root
        Then DS124 reports it once and DS116 reports nothing (both use the same canonical root).

    Boundaries:
        - Focus: security review L1 (one shared canonical-root helper)
        - Fixtures/params: symlinks built in the test body

    On failure, first check:
        - path_boundaries.canonical_root and its use in mentions.detect and path_boundaries.detect
    """
    base = tmp_path.resolve()
    real = base / "real"
    real.mkdir()
    _symlink(base / "via", real)
    _symlink(real / "abs.md", real / "missing.md", directory=False)
    (real / "README.md").write_text("@abs.md\n", encoding="utf-8")
    documents = (models.Document(path="README.md", bytes=1),)

    ds124 = mentions.detect(base / "via", documents)
    ds116 = path_boundaries.detect(base / "via", documents)

    assert [_shape(finding) for finding in ds124] == [_ds124("README.md", 1, 1, "@abs.md")]
    assert ds116 == ()
