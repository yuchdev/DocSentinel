"""Mock tests: DS124 never probes outside its boundaries (threat model 0009 M1-M4, M7, M9, M16).

``os.stat``, ``os.lstat`` and ``os.readlink`` are wrapped so every call is recorded with its
path, then each recorded path is checked against the boundary of the step that made it: the
scan root on step 1, the link root on step 2. Trees (symlinks included) are built in the test
body under ``tmp_path``; no asset is loaded.
"""

from __future__ import annotations

import builtins
import dataclasses
import io
import logging
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from docsentinel import models
from docsentinel.config import Config
from docsentinel.detectors import mentions, path_boundaries


class _Probes(list):
    """Recorded ``(name, path)`` filesystem calls, with a kernel-aware containment check.

    The one permitted ``realpath`` of the trusted root (``canonical_root``) is not recorded
    as a probe: the fixture pauses recording for its duration and logs its argument in
    :attr:`canonicalised` instead, so :meth:`inside` needs no allowance for the root's
    ancestors (security re-review 2026-11-16, R-1). Any probe a mention causes on the
    boundary itself or above it therefore fails the containment check.
    """

    def __init__(self):
        """Start with no calls, no canonicalised roots and recording enabled."""
        super().__init__()
        self.paused = False
        self.canonicalised: list[str] = []

    def inside(self, path: str, boundary: Path) -> bool:
        """Return whether the kernel resolves ``path``'s parent at or below ``boundary``.

        A recorded ``lstat``/``readlink``/``stat(follow_symlinks=False)`` acts on the last
        component itself but lets the kernel follow every symlink in the parent, so the
        parent is resolved with the real ``realpath`` (recording paused). A path that is
        contained as a string but escapes through an intermediate symlink fails, and so
        does a probe of the boundary itself or of any of its ancestors.

        :param path: A recorded path.
        :param boundary: The allowed boundary directory.
        :returns: ``True`` when the kernel-resolved parent is the boundary or below it.
        """
        normal = os.path.normpath(path)
        self.paused = True
        try:
            parent = os.path.realpath(os.path.dirname(normal))
            base = os.path.realpath(boundary)
        finally:
            self.paused = False
        return parent == base or parent.startswith(base + os.sep)

    def all_inside(self, boundary: Path) -> bool:
        """Return whether every call stays inside ``boundary`` and only the boundary was canonicalised.

        :param boundary: The allowed boundary directory.
        :returns: ``True`` when no recorded call escapes and every ``canonical_root``
            argument is ``boundary`` or a directory below it (never a target outside).
        """
        base = os.path.normpath(os.fspath(boundary))
        roots_ok = all(
            os.path.normpath(root) == base or os.path.normpath(root).startswith(base + os.sep)
            for root in self.canonicalised
        )
        return roots_ok and all(self.inside(path, boundary) for _, path in list(self))

    def clear(self):
        """Forget every recorded call and canonicalised root."""
        super().clear()
        self.canonicalised.clear()


@pytest.fixture
def probes(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Probes]:
    """Record every ``os.stat``/``os.lstat``/``os.readlink`` call as ``(name, path)``.

    ``canonical_root`` (imported by name into both ``mentions`` and ``path_boundaries``)
    is wrapped in both modules so its ``realpath`` of the trusted root runs with
    recording paused; its argument is kept in ``canonicalised`` for the tests to check.
    """
    calls = _Probes()

    def wrap(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
        """Return a recording wrapper of one os function."""

        def recorder(path: Any, *args: Any, **kwargs: Any) -> Any:
            """Record the call (unless paused), then delegate."""
            if not calls.paused:
                calls.append((name, os.fspath(path)))
            return original(path, *args, **kwargs)

        return recorder

    original_canonical = path_boundaries.canonical_root

    def paused_canonical_root(root: Path) -> Path:
        """Record the canonicalised root, then canonicalise it with recording paused."""
        calls.canonicalised.append(os.fspath(root))
        previous = calls.paused
        calls.paused = True
        try:
            return original_canonical(root)
        finally:
            calls.paused = previous

    for name in ("stat", "lstat", "readlink"):
        monkeypatch.setattr(os, name, wrap(name, getattr(os, name)))
    monkeypatch.setattr(path_boundaries, "canonical_root", paused_canonical_root)
    monkeypatch.setattr(mentions, "canonical_root", paused_canonical_root)
    yield calls


def _write(path: Path, text: str):
    """Write ``text`` to ``path``, creating its parent directories.

    :param path: The file to write.
    :param text: Its content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _doc(root: Path, relative: str, text: str) -> models.Document:
    """Write ``relative`` under ``root`` and return its Document.

    :param root: The scan root.
    :param relative: POSIX relative path of the document.
    :param text: The document text.
    :returns: The Document.
    """
    _write(root / relative, text)
    return models.Document(path=relative, bytes=len(text.encode("utf-8")))


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    """Return ``(link_root, scan_root)``: a canonical ``repo`` and its ``docs`` subdirectory.

    :param tmp_path: The pytest scratch directory.
    :returns: The link root and the scan root.
    """
    link_root = tmp_path.resolve() / "repo"
    scan_root = link_root / "docs"
    scan_root.mkdir(parents=True)
    return link_root, scan_root


def test_step1_never_probes_outside_scan_root(tmp_path: Path, probes: _Probes):
    """
    [Unit] DS124 step 1: every filesystem call stays inside the scan root.

    Scenario:
        Given a scan root equal to the link root and missing, present and escaping mentions
        When DS124 runs with every os.stat/lstat/readlink recorded
        Then every recorded path lies inside the scan root.

    Boundaries:
        - Focus: M1 containment before the only stat
        - Fixtures/params: probes fixture

    On failure, first check:
        - That _Resolver stats only the path contained_path returned
    """
    _, scan_root = _repo(tmp_path)
    _doc(scan_root, "guide.md", "# G\n")
    document = _doc(scan_root, "sub/README.md", "@../guide.md @missing.md @../../../../etc/passwd.md @x/../../y.md\n")
    probes.clear()

    findings = mentions.detect(scan_root, (document,), Config(), link_root=scan_root)

    assert [finding.value for finding in findings] == ["@missing.md"]
    assert probes, "the resolver must have probed in-root paths"
    assert probes.all_inside(scan_root), probes


def test_step2_never_probes_outside_link_root(tmp_path: Path, probes: _Probes):
    """
    [Unit] DS124 step 2: the fallback probes only inside the link root.

    Scenario:
        Given a link root above the scan root, a mention resolved by the fallback, a missing one,
            and one whose fallback climbs above the link root
        When DS124 runs
        Then step-1 calls stay in the scan root, every call stays in the link root, and the
            climbing mention gives no finding.

    Boundaries:
        - Focus: M2 boundary choice (link root on step 2, never the scan root's parent chain)
        - Fixtures/params: probes fixture

    On failure, first check:
        - The link_root= passed to resolve_local_reference and contained_path on step 2
    """
    link_root, scan_root = _repo(tmp_path)
    _doc(link_root, "AGENTS.md", "# A\n")
    document = _doc(scan_root, "a/b/README.md", "@AGENTS.md @gone.md @../../q.md\n")
    probes.clear()

    findings = mentions.detect(scan_root, (document,), Config(), link_root=link_root)

    assert [finding.value for finding in findings] == ["@gone.md"]
    assert probes.all_inside(link_root), probes
    assert any(probes.inside(path, link_root) and not probes.inside(path, scan_root) for _, path in list(probes))


def test_outside_root_step1_does_not_fall_through_to_step2(
    tmp_path: Path, probes: _Probes, monkeypatch: pytest.MonkeyPatch
):
    """
    [Unit] DS124 ownership: a DS116-owned step 1 never reaches the link-root fallback.

    Scenario:
        Given a lexical escape and a symlink-out mention, with a link root above the scan root
        When DS124 runs with resolve_local_reference spied
        Then no "/"-prefixed (step-2) target is ever resolved, no probe leaves the scan root,
            and no DS124 finding is produced.

    Boundaries:
        - Focus: M1/M5 "a step 1 that DS116 owns ends processing"
        - Fixtures/params: probes fixture, an in-root symlink to a sibling outside the scan root

    On failure, first check:
        - The early return on mention_ds116_reason in _Resolver._resolve
    """
    link_root, scan_root = _repo(tmp_path)
    (link_root / "elsewhere").mkdir()
    _doc(link_root, "elsewhere/x.md", "# X\n")
    try:
        (scan_root / "out").symlink_to(link_root / "elsewhere", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable: the platform or its permissions refused a symlink")
    document = _doc(scan_root, "README.md", "@../elsewhere/x.md @out/x.md\n")
    targets: list[str] = []
    original = mentions.resolve_local_reference

    def spy(root: Path, document_path: str, target: str, **kwargs: Any) -> Any:
        """Record the resolved target, then delegate."""
        targets.append(target)
        return original(root, document_path, target, **kwargs)

    monkeypatch.setattr(mentions, "resolve_local_reference", spy)
    probes.clear()

    findings = mentions.detect(scan_root, (document,), Config(), link_root=link_root)

    assert findings == ()
    assert not any(target.startswith("/") for target in targets), targets
    assert probes.all_inside(scan_root), probes


def test_escaping_mention_no_probe_when_ds116_ignored(tmp_path: Path, probes: _Probes):
    """
    [Unit] DS124 containment does not depend on DS116 being enabled.

    Scenario:
        Given root_escape_policy = "off" (DS116 inert) and an escaping mention to an existing file
        When DS124 runs
        Then nothing outside the scan root is probed and no DS124 finding is produced.

    Boundaries:
        - Focus: M3 "holds even when DS116 is ignored, deselected or off"
        - Fixtures/params: probes fixture

    On failure, first check:
        - That mention_ds116_reason uses fixed settings, not the scan's root_escape_policy
    """
    link_root, scan_root = _repo(tmp_path)
    _doc(link_root, "secret.md", "# S\n")
    document = _doc(scan_root, "README.md", "@../secret.md @../../../etc/hosts.md\n")
    config = dataclasses.replace(Config(), root_escape_policy="off")
    probes.clear()

    findings = mentions.detect(scan_root, (document,), config, link_root=link_root)

    assert findings == ()
    assert probes.all_inside(scan_root), probes


def test_step2_symlink_out_no_outside_lstat_no_finding(tmp_path: Path, probes: _Probes):
    """
    [Unit] DS124 step 2: a link-root symlink that leaves the link root is refused without following it.

    Scenario:
        Given repo/shared -> a directory outside the link root that holds x.md
        When DS124 checks @shared/x.md from the docs scan root
        Then every lstat/readlink/stat stays inside the link root and there is no finding (ruling R1).

    Boundaries:
        - Focus: M4/M6 step-2 symlink containment
        - Fixtures/params: probes fixture; symlink built in the test body

    On failure, first check:
        - contained_path(link_root, ...) and the escapes_via_symlink refusal branch
    """
    link_root, scan_root = _repo(tmp_path)
    outside = tmp_path.resolve() / "outside"
    outside.mkdir()
    (outside / "x.md").write_text("# X\n", encoding="utf-8")
    try:
        (link_root / "shared").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable: the platform or its permissions refused a symlink")
    document = _doc(scan_root, "README.md", "@shared/x.md\n")
    probes.clear()

    findings = mentions.detect(scan_root, (document,), Config(), link_root=link_root)

    assert findings == ()
    assert probes
    assert probes.all_inside(link_root), probes


def test_home_and_absolute_mentions_cause_no_filesystem_call(
    tmp_path: Path, probes: _Probes, monkeypatch: pytest.MonkeyPatch
):
    """
    [Unit] DS124 kinds: home and absolute mentions make no filesystem or expansion call.

    Scenario:
        Given only home (@~/...) and absolute (@/...) mentions, in prose and code spans
        When DS124 runs with expanduser, expandvars and Path.home made to fail loudly
        Then they add no call to the run's one root canonicalisation, nothing is expanded and
            nothing is reported.

    Boundaries:
        - Focus: M7 branch on kind before any resolver or filesystem call
        - Fixtures/params: probes fixture

    On failure, first check:
        - The kind check at the top of the per-mention loop in mentions._check_text
    """

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        """Fail the test on any expansion attempt."""
        raise AssertionError("home or environment expansion was attempted")

    monkeypatch.setattr(os.path, "expanduser", forbidden)
    monkeypatch.setattr(os.path, "expandvars", forbidden)
    monkeypatch.setattr(Path, "home", forbidden)
    monkeypatch.setattr(Path, "expanduser", forbidden)
    _, scan_root = _repo(tmp_path)
    document = _doc(scan_root, "README.md", "@~/.ssh/id.pub @~/notes/me.md @/etc/hosts.txt `@//server/x.md`\n")
    plain = _doc(scan_root, "plain.md", "No mention here.\n")
    probes.clear()
    mentions.detect(scan_root, (plain,), Config(), link_root=scan_root)
    # The run's one canonicalisation of the trusted scan root is paused by the fixture,
    # so a document without mentions causes no recorded call at all.
    root_only = list(probes)
    probes.clear()

    findings = mentions.detect(scan_root, (document,), Config(), link_root=scan_root)

    assert findings == ()
    assert root_only == []
    assert list(probes) == []
    assert probes.canonicalised == [os.fspath(scan_root)]


def test_repeated_mention_probes_once(tmp_path: Path, probes: _Probes):
    """
    [Unit] DS124 memoisation: 1,000 identical mentions cost the same probes as one.

    Scenario:
        Given one document with a missing mention once, and one with it on 1,000 lines
        When DS124 runs on each
        Then the recorded call count is equal, while each line still gets its finding.

    Boundaries:
        - Focus: M9 per-(directory, target) memo and per-path stat cache
        - Fixtures/params: probes fixture

    On failure, first check:
        - _Resolver._outcomes and _Resolver._regular
    """
    _, scan_root = _repo(tmp_path)
    single = _doc(scan_root, "one.md", "@deep/a/b/missing.md\n")
    many = _doc(scan_root, "many.md", "@deep/a/b/missing.md\n" * 1_000)

    probes.clear()
    one_findings = mentions.detect(scan_root, (single,), Config(), link_root=scan_root)
    one_count = len(probes)
    probes.clear()
    many_findings = mentions.detect(scan_root, (many,), Config(), link_root=scan_root)

    assert len(one_findings) == 1
    assert len(many_findings) == 1_000
    assert len(probes) == one_count


def test_target_never_opened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] DS124 never opens, reads or lists a target (only the document itself is read).

    Scenario:
        Given a resolving, a missing and a directory target
        When DS124 runs with every open/read/list entry point recorded
        Then the only path opened is the scanned document, and nothing is listed.

    Boundaries:
        - Focus: M16
        - Fixtures/params: patched builtins.open, io.open, os.open, Path.open/read_text/read_bytes,
            os.scandir, os.listdir

    On failure, first check:
        - Any new read of a resolved target in mentions.py
    """
    _, scan_root = _repo(tmp_path)
    _doc(scan_root, "guide.md", "# G\n")
    (scan_root / "folder.md").mkdir()
    document = _doc(scan_root, "README.md", "@guide.md @missing.md @folder.md\n")
    opened: list[str] = []

    def wrap(original: Callable[..., Any]) -> Callable[..., Any]:
        """Return a recording wrapper of one open/list entry point."""

        def recorder(target: Any, *args: Any, **kwargs: Any) -> Any:
            """Record the opened path, then delegate."""
            opened.append(os.fspath(target) if not isinstance(target, int) else str(target))
            return original(target, *args, **kwargs)

        return recorder

    for owner, name in (
        (builtins, "open"),
        (io, "open"),
        (os, "open"),
        (Path, "open"),
        (Path, "read_text"),
        (Path, "read_bytes"),
        (os, "scandir"),
        (os, "listdir"),
    ):
        monkeypatch.setattr(owner, name, wrap(getattr(owner, name)))

    findings = mentions.detect(scan_root, (document,), Config(), link_root=scan_root)

    assert [finding.value for finding in findings] == ["@missing.md", "@folder.md"]
    assert opened
    assert set(opened) == {os.fspath(scan_root / "README.md")}, opened


def test_debug_records_carry_no_mention_text(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS124 logging: the per-document DEBUG summary and refusals never echo the mention.

    Scenario:
        Given a document with a uniquely named missing mention and a step-2 refusal
        When DS124 runs with DEBUG captured
        Then no record contains the unique marker.

    Boundaries:
        - Focus: M14 at the unit level (the integration test covers the CLI log file)
        - Fixtures/params: caplog

    On failure, first check:
        - The logger.debug calls in mentions.py
    """
    _, scan_root = _repo(tmp_path)
    document = _doc(scan_root, "a/b/README.md", "@zqxmarker91.md @../zqxmarker92.md\n")

    with caplog.at_level(logging.DEBUG, logger="docsentinel"):
        mentions.detect(scan_root, (document,), Config(), link_root=scan_root)

    assert any("DS124" in record.getMessage() for record in caplog.records)
    assert not any("zqxmarker" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("policy", ("error", "off"), ids=("ds116_on", "ds116_off"))
def test_hidden_intermediate_symlink_no_outside_probe(tmp_path: Path, probes: _Probes, policy: str):
    """
    [Unit] DS124/DS116 containment: a symlink hidden inside a relative symlink target is never followed.

    Scenario:
        Given root/a -> ../outside, root/l -> a/b (lexically "in root") and a mention @l/x.md,
            with outside/b a symlink to an absolute host directory
        When DS124 and DS116 run, with DS116 on and with root_escape_policy = "off"
        Then every recorded lstat/readlink/stat stays inside the scan root as the kernel resolves it,
            DS124 reports nothing, and DS116 (when on) reports one symlink escape.

    Boundaries:
        - Focus: security review H1 (component-by-component walk of symlink targets)
        - Fixtures/params: probes fixture; symlinks built in the test body; DS116 on and off

    On failure, first check:
        - The shared walker in path_boundaries (escapes_via_symlink / contained_path)
    """
    base = tmp_path.resolve()
    outside = base / "outside"
    outside.mkdir()
    scan_root = base / "docs"
    scan_root.mkdir()
    try:
        (outside / "b").symlink_to(base, target_is_directory=True)
        (scan_root / "a").symlink_to("../outside", target_is_directory=True)
        (scan_root / "l").symlink_to("a/b", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable: the platform or its permissions refused a symlink")
    document = _doc(scan_root, "README.md", "@l/x.md\n")
    config = dataclasses.replace(Config(), root_escape_policy=policy)
    probes.clear()

    ds124 = mentions.detect(scan_root, (document,), config, link_root=scan_root)
    ds116 = path_boundaries.detect(scan_root, (document,), config, link_root=scan_root)

    assert probes.all_inside(scan_root), probes
    assert ds124 == ()
    expected = 0 if policy == "off" else 1
    assert [finding.message for finding in ds116] == [
        "reference resolves through a symlink that escapes the documentation root: @l/x.md"
    ] * expected


def test_repeated_mention_ds116_probes_once(tmp_path: Path, probes: _Probes):
    """
    [Unit] DS116 memoisation: 1,000 identical mentions cost the same probes as one.

    Scenario:
        Given one document with a deep mention once, and one with it on 1,000 lines
        When DS116 runs on each
        Then the recorded call count is equal.

    Boundaries:
        - Focus: security review L2 (per-(directory, target) memo of the mention classification)
        - Fixtures/params: probes fixture

    On failure, first check:
        - The mention memo passed from path_boundaries.detect to check_text
    """
    _, scan_root = _repo(tmp_path)
    mention = "@" + "d/" * 40 + "x.md\n"
    single = _doc(scan_root, "one.md", mention)
    many = _doc(scan_root, "many.md", mention * 1_000)

    probes.clear()
    path_boundaries.detect(scan_root, (single,), Config(), link_root=scan_root)
    one_count = len(probes)
    probes.clear()
    path_boundaries.detect(scan_root, (many,), Config(), link_root=scan_root)

    assert one_count > 0
    assert len(probes) == one_count
