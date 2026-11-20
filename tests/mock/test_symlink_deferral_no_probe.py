"""Mock tests: DS101, DS113, DS116 and DS124 never probe or open outside the root on symlink-out layouts.

Milestone 0009 Story 01.0 story-close review, SC-4. For the nested, deep-prefix and
round-trip (``rt -> ../outside/../root/d``) layouts of ``tests/symlink_layout_helpers.py``,
every ``os.stat``/``os.lstat``/``os.readlink``/``os.scandir``/``os.listdir`` and every
``os.path.realpath`` of anything other than the trusted scan root is recorded, then judged
the way the kernel does with :meth:`_Probes.inside` from
``tests/mock/test_at_reference_no_probe.py`` (strict: the realpath of the probe's parent
must be the root or below it, no ancestor allowance). The one permitted ``realpath`` of
the trusted root (``canonical_root`` in DS116/DS124, the inline ``os.path.realpath(root)``
in DS101/DS113) runs with recording paused. Every ``open`` is recorded too: the only file
any rule may open is the scanned README.

The round trip is the sharp case: the kernel would land back inside the root, so a probe
"through" ``rt`` would look harmless as a string, yet its parent passes through
``outside``; the walker must stop at the first ``..`` above the root without following.
"""

from __future__ import annotations

import builtins
import io
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from docsentinel.config import Config
from docsentinel.detectors import assets, links, mentions, path_boundaries
from tests.mock.test_at_reference_no_probe import _Probes
from tests.symlink_layout_helpers import LAYOUTS, SymlinkLayout


class _Recorder:
    """The strict probe list plus the opened paths, with the trusted root to exempt."""

    def __init__(self):
        """Start paused, with no probes, no opens and no trusted root."""
        self.probes = _Probes()
        self.probes.paused = True
        self.opened: list[str] = []
        self.trusted_root = ""

    def start(self, root: Path):
        """Forget everything the test setup did, trust ``root`` and start recording.

        :param root: The canonical scan root whose own ``realpath`` is exempt.
        """
        self.probes.clear()
        self.opened.clear()
        self.trusted_root = os.path.normpath(os.fspath(root))
        self.probes.paused = False

    def stop(self):
        """Stop recording so the assertions' own filesystem calls are not recorded."""
        self.probes.paused = True


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Recorder]:
    """Record every filesystem probe and open; pause only for a realpath of the trusted root.

    :param monkeypatch: The pytest monkeypatch fixture.
    :returns: The recorder, paused; call :meth:`_Recorder.start` after building the tree.
    """
    state = _Recorder()
    probes = state.probes

    def wrap_probe(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
        """Return a recording wrapper of one os probe function."""

        def wrapper(path: Any, *args: Any, **kwargs: Any) -> Any:
            """Record the path argument (unless paused), then delegate."""
            if not probes.paused and isinstance(path, (str, os.PathLike)):
                probes.append((name, os.fspath(path)))
            return original(path, *args, **kwargs)

        return wrapper

    original_realpath = os.path.realpath

    def recording_realpath(path: Any, *args: Any, **kwargs: Any) -> Any:
        """Canonicalise the trusted root with recording paused; record any other realpath as a probe.

        A non-root ``realpath`` runs unpaused, so the ``os.lstat`` calls it makes internally
        are recorded and judged as well.
        """
        if probes.paused:
            return original_realpath(path, *args, **kwargs)
        if state.trusted_root and os.path.normpath(os.fspath(path)) == state.trusted_root:
            probes.canonicalised.append(os.fspath(path))
            probes.paused = True
            try:
                return original_realpath(path, *args, **kwargs)
            finally:
                probes.paused = False
        probes.append(("realpath", os.fspath(path)))
        return original_realpath(path, *args, **kwargs)

    def wrap_open(original: Callable[..., Any]) -> Callable[..., Any]:
        """Return a recording wrapper of one open entry point."""

        def wrapper(target: Any, *args: Any, **kwargs: Any) -> Any:
            """Record the opened path, then delegate."""
            if not probes.paused and isinstance(target, (str, os.PathLike)):
                state.opened.append(os.path.normpath(os.fspath(target)))
            return original(target, *args, **kwargs)

        return wrapper

    for name in ("stat", "lstat", "readlink", "scandir", "listdir"):
        monkeypatch.setattr(os, name, wrap_probe(name, getattr(os, name)))
    monkeypatch.setattr(os.path, "realpath", recording_realpath)
    for owner, name in ((builtins, "open"), (io, "open"), (os, "open")):
        monkeypatch.setattr(owner, name, wrap_open(getattr(owner, name)))
    yield state


@pytest.mark.parametrize("build", tuple(LAYOUTS.values()), ids=tuple(LAYOUTS))
def test_symlink_out_layout_never_probes_or_opens_outside_root(
    tmp_path: Path, recorder: _Recorder, build: Callable[[Path], SymlinkLayout]
):
    """
    [Unit] symlink deferral: no rule probes or opens a path the kernel places outside the root.

    Scenario:
        Given a README that links to S.md, embeds S.png and mentions @S.md through a nested
            symlink-out, a symlink-out after 70 plain directories, or the round-trip symlink
            rt -> ../outside/../root/d
        When DS101, DS113, DS124 and DS116 run with every stat/lstat/readlink/scandir/listdir,
            every non-root realpath and every open recorded
        Then the rules did probe in-root paths, the kernel-resolved parent of every recorded
            path is the root or below it, only the trusted root was canonicalised, the only
            file opened is README.md, and DS116 alone reports (link, image, mention).

    Boundaries:
        - Focus: SC-4 no outside probe for every walker consumer; strict _Probes.inside, no
            ancestor allowance; trusted-root realpath exempt (amended M3)
        - Fixtures/params: recorder fixture; one layout per case; symlink-less platforms skip

    On failure, first check:
        - A probe whose parent passes through root/a, outside or root/rt: _walk followed a
            symlink target instead of re-walking its components
        - A recorded realpath of a target: a Path.resolve() crept into links/assets/mentions
    """
    layout = build(tmp_path)
    root, documents = layout.root, layout.documents
    readme = os.path.normpath(os.fspath(root / "README.md"))
    recorder.start(root)

    ds101 = links.detect(root, documents, Config(), link_root=root)
    ds113 = assets.detect(root, documents, Config(), link_root=root)
    ds124 = mentions.detect(root, documents, Config(), link_root=root)
    ds116 = path_boundaries.detect(root, documents, Config(), link_root=root)
    recorder.stop()

    probes = recorder.probes
    assert (ds101, ds113, ds124) == ((), (), ())
    assert [(finding.line, finding.message) for finding in ds116] == layout.expected_ds116()
    assert probes, "the walker must have probed in-root components"
    escaping = [(name, path) for name, path in list(probes) if not probes.inside(path, root)]
    assert escaping == [], escaping
    assert probes.canonicalised, "the trusted root must have been canonicalised"
    assert {os.path.normpath(path) for path in probes.canonicalised} == {recorder.trusted_root}
    assert set(recorder.opened) == {readme}, recorder.opened
