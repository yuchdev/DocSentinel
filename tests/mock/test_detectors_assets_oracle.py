"""Mock tests proving DS113 never touches a path outside the root and never opens an asset.

The DS113 threat model carries two non-negotiable filesystem controls: the analyzer
must perform **no** filesystem access on any path that resolves outside the canonical
scan root (the existence-oracle inherited from DS101/DS103), and it must decide
existence and type with ``os.stat``/``S_ISREG`` only -- **never** opening or reading
asset content, so a committed FIFO/device/huge file can neither block the scan nor be
read. These tests install a recorder over every filesystem entry point DS113 can
reach, run it over an adversarial document (root escapes, Windows forms, an in-root
symlink pointing outside, and a runtime FIFO at an asset path), and assert that no
recorded path argument leaves the canonical root, that the real out-of-root target is
never touched, and that ``open`` is never called on any asset path.

Symlink and FIFO creation are skipped only with an explicit reason when the platform
does not support them; no skip or xfail hides a regression.
"""

from __future__ import annotations

import builtins
import os
from pathlib import Path

import pytest

from docsentinel import models
from docsentinel.detectors import assets

#: Raw adversarial asset targets: lexical escapes, encoded escapes, Windows drive/UNC/
#: backslash forms, external schemes, a data URI, a template, and in-root references.
_CORPUS_TARGETS = (
    "../../../outside/secret.png",
    "%2e%2e/%2e%2e/secret.png",
    r"C:\Windows\logo.png",
    r"\\server\share\logo.png",
    r"a\b.png",
    "https://example.com/x.png",
    "data:image/png;base64,iVBORw0KGgo=",
    "${IMAGE}",
    "missing.png",
    "evil.png",
)


def _symlink_or_skip(link: Path, target: str):
    """Create a symlink or skip the test with an explicit unavailable reason.

    :param link: The symlink path to create.
    :param target: The symlink's target string.
    """
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")


def _build_corpus(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create the scan root, the out-of-root target tree, and the adversarial document.

    :param tmp_path: The pytest temporary directory.
    :returns: ``(root, outside_dir, secret_file)`` as real canonical paths.
    """
    root = tmp_path / "scanroot"
    docs = root / "docs"
    docs.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.png"
    secret.write_text("secret", encoding="utf-8")

    _symlink_or_skip(docs / "evil.png", "../../outside/secret.png")

    body = "".join(f"![t{index}]({target})\n" for index, target in enumerate(_CORPUS_TARGETS))
    (docs / "README.md").write_text(body, encoding="utf-8")
    return (
        Path(os.path.realpath(root)),
        Path(os.path.realpath(outside)),
        Path(os.path.realpath(secret)),
    )


class _Recorder:
    """Records every filesystem path argument the patched entry points receive."""

    def __init__(self):
        """Initialize empty recording sets for all calls and for opened paths."""
        self.paths: set[str] = set()
        self.opened: set[str] = set()

    def note(self, candidate: object):
        """Record one path-like argument, ignoring non-path arguments such as file descriptors.

        :param candidate: The first argument passed to a patched filesystem call.
        """
        if isinstance(candidate, (str, os.PathLike)):
            self.paths.add(os.path.normpath(os.fspath(candidate)))

    def note_open(self, candidate: object):
        """Record one path-like argument passed to an ``open`` entry point.

        :param candidate: The first argument passed to a patched open call.
        """
        if isinstance(candidate, (str, os.PathLike)):
            self.opened.add(os.path.normpath(os.fspath(candidate)))


def _install_recorder(monkeypatch: pytest.MonkeyPatch, recorder: _Recorder):
    """Patch every reachable filesystem entry point to record its path argument.

    Each wrapper records the path, then delegates to the saved original so DS113
    behaves normally; this records Python-level call arguments without changing
    behaviour. ``open`` entry points additionally record into the opened-path set so
    the "never open an asset" control can be asserted directly.

    :param monkeypatch: The pytest monkeypatch fixture.
    :param recorder: The recorder collecting path arguments.
    """
    for module, name in (
        (os, "stat"),
        (os, "lstat"),
        (os, "readlink"),
        (os, "scandir"),
        (os, "listdir"),
        (os.path, "exists"),
        (os.path, "lexists"),
        (os.path, "realpath"),
    ):
        original = getattr(module, name)

        def wrapper(path: object, *args: object, _original=original, **kwargs: object) -> object:
            """Record the path argument then delegate to the original callable."""
            recorder.note(path)
            return _original(path, *args, **kwargs)

        monkeypatch.setattr(module, name, wrapper)

    original_open = builtins.open

    def open_wrapper(path: object, *args: object, _original=original_open, **kwargs: object) -> object:
        """Record the opened path (both sets) then delegate to the original open."""
        recorder.note(path)
        recorder.note_open(path)
        return _original(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", open_wrapper)

    for method in ("stat", "lstat", "exists", "is_file", "is_dir", "resolve", "readlink", "open", "read_text"):
        original_method = getattr(Path, method)

        def method_wrapper(
            self: Path, *args: object, _original=original_method, _name=method, **kwargs: object
        ) -> object:
            """Record the bound Path (and opened set for open) then delegate to the original method."""
            recorder.note(self)
            if _name == "open":
                recorder.note_open(self)
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(Path, method, method_wrapper)


def _is_under(candidate: str, directory: str) -> bool:
    """Return whether a normalized path equals or lives under a directory.

    :param candidate: A normalized path string.
    :param directory: A normalized directory string.
    :returns: ``True`` when ``candidate`` is ``directory`` or a descendant.
    """
    return candidate == directory or candidate.startswith(directory.rstrip(os.sep) + os.sep)


def test_ds113_never_touches_a_path_outside_the_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors assets: verifies DS113 never accesses a path outside the canonical root.

    Scenario:
        Given an adversarial document (lexical and encoded root escapes, Windows drive/UNC/backslash
            forms, an external scheme, a data URI, a template, an in-root reference, and an in-root
            symlink pointing to a real outside secret) scanned under a recorder over every reachable
            filesystem entry point
        When DS113 check_text runs with the default error policy
        Then no recorded path argument lives under the out-of-root tree, every recorded path stays
            within the canonical root (bar the root's own realpath ancestor walk), and the real
            outside secret is never touched -- while DS113 still did run.

    Boundaries:
        - Focus: the HIGH existence-oracle / outside-root-IO control (R2); Python-level path args only
        - Fixtures/params: tmp_path, monkeypatch

    On failure, first check:
        - Whether a target that is DS116-owned or escapes via an in-root symlink was resolved or stat-ed
        - Whether the in-root symlink was followed to its outside target
    """
    root, outside, secret = _build_corpus(tmp_path)
    document = models.Document("docs/README.md", 0)

    # Warm up lazy imports before the recorder is installed so the recorded window
    # holds only DS113's own filesystem calls.
    assets.detect(root, (document,))

    recorder = _Recorder()
    _install_recorder(monkeypatch, recorder)

    assets.detect(root, (document,))

    assert recorder.paths, "recorder captured no filesystem access; DS113 did not run"
    root_str, outside_str, secret_str = (str(root), str(outside), str(secret))
    for recorded in recorder.paths:
        assert recorded != secret_str, f"touched the out-of-root secret file: {recorded}"
        assert not _is_under(recorded, outside_str), f"touched a path under the out-of-root tree: {recorded}"
        allowed = _is_under(recorded, root_str) or _is_under(root_str, recorded)
        assert allowed, f"touched a path outside the scan root: {recorded}"


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="os.mkfifo unavailable on this platform")
def test_ds113_never_opens_an_asset_path_including_a_fifo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors assets: verifies DS113 stats but never opens asset paths, FIFO included.

    Scenario:
        Given a document referencing a present regular image, an absent image, and a runtime FIFO at an
            asset path, scanned under a recorder over every filesystem entry point including ``open``
        When DS113 check_text runs with the default error policy
        Then the scan completes promptly with the expected findings and ``open`` is never called on any
            asset path (only the Markdown document itself may be opened), proving existence/type came
            from os.stat and a FIFO can never block or be read.

    Boundaries:
        - Focus: the HIGH special-files control (stat + S_ISREG only, never open/read)
        - Fixtures/params: tmp_path, monkeypatch; skipped with a reason when os.mkfifo is unavailable

    On failure, first check:
        - Whether _classify_path opened the asset instead of using os.stat
    """
    root = Path(os.path.realpath(tmp_path))
    (root / "real.png").write_text("x", encoding="utf-8")
    os.mkfifo(root / "pipe.png")
    (root / "README.md").write_text("![a](real.png)\n![b](absent.png)\n![c](pipe.png)\n", encoding="utf-8")
    document = models.Document("README.md", 0)

    assets.detect(root, (document,))  # warm up lazy imports

    recorder = _Recorder()
    _install_recorder(monkeypatch, recorder)

    findings = assets.detect(root, (document,))

    messages = sorted(finding.message for finding in findings)
    assert messages == ["asset is not a regular file: pipe.png", "missing asset: absent.png"]

    asset_paths = {os.path.normpath(os.fspath(root / name)) for name in ("real.png", "absent.png", "pipe.png")}
    for opened in recorder.opened:
        assert opened not in asset_paths, f"DS113 opened an asset path: {opened}"
