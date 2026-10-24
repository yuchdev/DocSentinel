"""Mock tests proving DS101/DS103/DS116 never touch the filesystem outside the root.

The standing threat model's HIGH finding is an existence oracle: the old DS101 and
DS103 ``resolve()``/``exists()`` escaping targets, leaking whether an out-of-root
path exists. Story 11.0 routes every target through the shared lexical resolver and
skips escaping or unsafe targets with no filesystem call, handing the policy to
DS116. These tests install a recorder over every filesystem entry point the three
detectors can reach, run them over the whole adversarial corpus from the threat
model (including an in-root symlink that points outside, generated at runtime), and
assert that no recorded path argument leaves the canonical scan root and that the
real out-of-root target files are never touched. The symlink-escape finding and its
in-root-symlink negative are checked separately.

Symlink creation is skipped only with an explicit reason when the filesystem does
not support symlinks; no skip or xfail is used to hide a regression.
"""

from __future__ import annotations

import builtins
import os
from pathlib import Path

import pytest

from docsentinel import models
from docsentinel.config import Config
from docsentinel.detectors import links, path_boundaries, paths

#: Raw adversarial targets from the threat model, rendered as live links. The NUL
#: and ESC control bytes and the fullwidth-dot confusable are embedded literally.
_CORPUS_TARGETS = (
    "../../../etc/passwd",
    "%2e%2e/%2e%2e/x",
    "..%2f..%2fx",
    "%252e%252e/x",
    r"C:\Windows\win.ini",
    "c:/x",
    "C%3A/x",
    r"\\server\share",
    r"\Windows\x",
    "//host/share",
    "file:///etc/passwd",
    "~/x",
    "$HOME/x",
    "/etc/passwd",
    "x.md?../../y",
    "../x.md#a",
    "a\x00b.md",
    "\uff0e\uff0e/x.md",
    "a/../b.md",
    "evil.md",
)


def _symlink_or_skip(link: Path, target: str):
    """Create a symlink or skip the test with an explicit unavailable reason."""
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
    secret = outside / "secret.md"
    secret.write_text("# out of root secret\n", encoding="utf-8")

    _symlink_or_skip(docs / "evil.md", "../../outside/secret.md")

    body = "".join(f"[t{index}]({target})\n" for index, target in enumerate(_CORPUS_TARGETS))
    body += "Inline `../../../etc/shadow` path span.\n"
    (docs / "README.md").write_text(body, encoding="utf-8")
    return (
        Path(os.path.realpath(root)),
        Path(os.path.realpath(outside)),
        Path(os.path.realpath(secret)),
    )


class _Recorder:
    """Records every filesystem path argument the patched entry points receive."""

    def __init__(self):
        """Initialize an empty recording set."""
        self.paths: set[str] = set()

    def note(self, candidate: object):
        """Record one path-like argument, ignoring non-path arguments such as file descriptors.

        :param candidate: The first argument passed to a patched filesystem call.
        """
        if isinstance(candidate, (str, os.PathLike)):
            self.paths.add(os.path.normpath(os.fspath(candidate)))


def _install_recorder(monkeypatch: pytest.MonkeyPatch, recorder: _Recorder):
    """Patch every reachable filesystem entry point to record its path argument.

    Each wrapper records the path, then delegates to the saved original so the
    detectors behave normally; this records Python-level call arguments without
    changing behavior.

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
        (builtins, "open"),
    ):
        original = getattr(module, name)

        def wrapper(path: object, *args: object, _original=original, **kwargs: object) -> object:
            """Record the path argument then delegate to the original callable."""
            recorder.note(path)
            return _original(path, *args, **kwargs)

        monkeypatch.setattr(module, name, wrapper)

    for method in (
        "stat",
        "lstat",
        "exists",
        "is_file",
        "is_dir",
        "resolve",
        "readlink",
        "open",
        "read_text",
        "iterdir",
    ):
        original_method = getattr(Path, method)

        def method_wrapper(self: Path, *args: object, _original=original_method, **kwargs: object) -> object:
            """Record the bound Path then delegate to the original method."""
            recorder.note(self)
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(Path, method, method_wrapper)


def _is_under(candidate: str, directory: str) -> bool:
    """Return whether a normalized path equals or lives under a directory."""
    return candidate == directory or candidate.startswith(directory.rstrip(os.sep) + os.sep)


def test_detectors_never_touch_a_path_outside_the_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors path_boundaries: verifies DS101/DS103/DS116 never access outside the root.

    Scenario:
        Given the full adversarial corpus (parent escapes, encoded escapes, Windows/UNC/backslash,
            schemes, tilde/env literals, absolute POSIX, query/fragment, control bytes, confusables,
            oscillation, and a runtime in-root symlink pointing outside) in one document
        When DS101, DS103, and DS116 each scan it under a recorder over every reachable filesystem call
        Then no recorded path argument lives under the out-of-root tree, every recorded path inside the
            temporary area stays within the canonical root (bar the root's own ancestor walk), and the
            real out-of-root secret file is never touched -- while the detectors still did run.

    Boundaries:
        - Focus: the HIGH existence-oracle fix; Python-level path arguments only
        - Fixtures/params: tmp_path, monkeypatch

    On failure, first check:
        - Whether a detector resolved/stat-ed an escaping or unsafe target instead of skipping it
        - Whether the in-root symlink was followed to its outside target
    """
    root, outside, secret = _build_corpus(tmp_path)
    document = models.Document("docs/README.md", 0)
    error_policy = Config(root_escape_policy="error")

    # Warm up lazy imports before the recorder is installed so that the recorded
    # window contains only the detectors' own filesystem calls, letting the
    # assertion be strict (every path is the root, under it, or an ancestor of it
    # from the one allowed realpath -- anything else, e.g. /etc/passwd, fails).
    links.detect(root, (document,))
    paths.detect(root, (document,))
    path_boundaries.detect(root, (document,), error_policy)

    recorder = _Recorder()
    _install_recorder(monkeypatch, recorder)

    links.detect(root, (document,))
    paths.detect(root, (document,))
    path_boundaries.detect(root, (document,), error_policy)

    assert recorder.paths, "recorder captured no filesystem access; the detectors did not run"
    root_str, outside_str, secret_str = (str(root), str(outside), str(secret))
    for recorded in recorder.paths:
        assert recorded != secret_str, f"touched the out-of-root secret file: {recorded}"
        assert not _is_under(recorded, outside_str), f"touched a path under the out-of-root tree: {recorded}"
        # The scan root, each of its descendants, and each of its ancestors (the
        # single permitted realpath walk of the trusted root) are allowed; any
        # other path is an out-of-root access and fails.
        allowed = _is_under(recorded, root_str) or _is_under(root_str, recorded)
        assert allowed, f"touched a path outside the scan root: {recorded}"


def test_ds116_reports_in_root_symlink_escape(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies the safe non-following symlink containment check.

    Scenario:
        Given an in-root symlink whose target is above the root and a sibling in-root symlink to an
            in-root file, each referenced by a document
        When DS116 runs with the default error policy
        Then the escaping symlink yields exactly one DS116 finding and the in-root symlink yields none.

    Boundaries:
        - Focus: ruling G4 (lexical-first, os.lstat/os.readlink only on in-root objects)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether escapes_via_symlink reads the link target lexically and compares against the root
        - Whether the in-root symlink is wrongly flagged
    """
    root = tmp_path / "scanroot"
    (root / "docs").mkdir(parents=True)
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.md").write_text("secret\n", encoding="utf-8")
    (root / "docs" / "real.md").write_text("# real\n", encoding="utf-8")
    _symlink_or_skip(root / "docs" / "escape.md", "../../outside/secret.md")
    _symlink_or_skip(root / "docs" / "inside.md", "real.md")
    (root / "docs" / "README.md").write_text("[a](escape.md)\n[b](inside.md)\n", encoding="utf-8")

    findings = path_boundaries.detect(root, (models.Document("docs/README.md", 0),))

    assert len(findings) == 1
    assert "symlink that escapes the documentation root" in findings[0].message
    assert findings[0].line == 1
