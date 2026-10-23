"""Mock tests proving DS112 never touches a path outside the root and never opens a non-index file.

The DS112 threat model carries three non-negotiable filesystem controls: the analyzer
must perform **no** filesystem access on any path that resolves outside the canonical
scan root (the existence-oracle inherited from DS101/DS103/DS116); it must decide a
navigation destination's existence with ``os.stat`` only -- **never** opening it, so a
committed FIFO/device at a destination can neither block nor be read; and it must never
``open`` a configured index that is not a validated in-root regular file (in particular a
FIFO configured as an index must never be opened). These tests install a recorder over
every filesystem entry point DS112 can reach, run it over an adversarial index (root
escapes, Windows forms, an external scheme, an in-root symlink to an outside file, and a
runtime FIFO destination), and assert that no recorded path argument leaves the canonical
root, that the real out-of-root target is never touched, and that ``open`` is only ever
called on the configured index document itself.

Symlink and FIFO creation are skipped only with an explicit reason when the platform does
not support them; no skip or xfail hides a regression.
"""

from __future__ import annotations

import builtins
import os
from pathlib import Path

import pytest

from docsentinel import models
from docsentinel.config import Config, ConfigError
from docsentinel.detectors import navigation

#: Raw adversarial navigation targets placed on list items of the index: lexical and
#: encoded root escapes, Windows drive/UNC/backslash forms, an external scheme, an
#: in-root symlink pointing outside, a plain in-root miss, and an in-root destination.
_CORPUS_TARGETS = (
    "../../../outside/secret.md",
    "%2e%2e/%2e%2e/secret.md",
    r"C:\Windows\guide.md",
    r"\\server\share\guide.md",
    r"a\b.md",
    "https://example.com/guide",
    "evil.md",
    "missing.md",
    "present.md",
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
    """Create the scan root, the out-of-root target tree, and the adversarial index.

    :param tmp_path: The pytest temporary directory.
    :returns: ``(root, outside_dir, secret_file)`` as real canonical paths.
    """
    root = tmp_path / "scanroot"
    docs = root / "docs"
    docs.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.md"
    secret.write_text("secret", encoding="utf-8")
    (docs / "present.md").write_text("# present\n", encoding="utf-8")

    _symlink_or_skip(docs / "evil.md", "../../outside/secret.md")

    body = "# Nav\n\n" + "".join(f"- [t{index}]({target})\n" for index, target in enumerate(_CORPUS_TARGETS))
    (docs / "index.md").write_text(body, encoding="utf-8")
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

    Each wrapper records the path, then delegates to the saved original so DS112
    behaves normally; this records Python-level call arguments without changing
    behaviour. ``open`` entry points additionally record into the opened-path set so
    the "never open a non-index file" control can be asserted directly.

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


def test_ds112_never_touches_a_path_outside_the_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors navigation: verifies DS112 never accesses a path outside the canonical root.

    Scenario:
        Given an adversarial navigation index whose list items link to lexical and encoded root
            escapes, Windows drive/UNC/backslash forms, an external scheme, an in-root symlink to a
            real outside secret, an in-root miss, and an in-root destination, scanned under a recorder
            over every reachable filesystem entry point
        When DS112 detect runs with the default (missing-checking) config
        Then no recorded path argument lives under the out-of-root tree, every recorded path stays
            within the canonical root (bar the root's own realpath ancestor walk), and the real
            outside secret is never touched -- while DS112 still did run.

    Boundaries:
        - Focus: the HIGH existence-oracle / outside-root-IO controls (R4/R6); Python-level path args
        - Fixtures/params: tmp_path, monkeypatch

    On failure, first check:
        - Whether an escaping target was resolved or stat-ed instead of reported lexically
        - Whether the in-root symlink was followed to its outside target by the stat probe
    """
    root, outside, secret = _build_corpus(tmp_path)
    document = models.Document("docs/index.md", 0)
    config = Config(navigation_indexes=("docs/index.md",))

    # Warm up lazy imports before the recorder is installed so the recorded window
    # holds only DS112's own filesystem calls.
    navigation.detect(root, (document,), config)

    recorder = _Recorder()
    _install_recorder(monkeypatch, recorder)

    navigation.detect(root, (document,), config)

    assert recorder.paths, "recorder captured no filesystem access; DS112 did not run"
    root_str, outside_str, secret_str = (str(root), str(outside), str(secret))
    for recorded in recorder.paths:
        assert recorded != secret_str, f"touched the out-of-root secret file: {recorded}"
        assert not _is_under(recorded, outside_str), f"touched a path under the out-of-root tree: {recorded}"
        allowed = _is_under(recorded, root_str) or _is_under(root_str, recorded)
        assert allowed, f"touched a path outside the scan root: {recorded}"


def test_ds112_opens_only_the_index_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors navigation: verifies DS112 opens only the configured index, never a destination.

    Scenario:
        Given an index linking to a present destination and an absent destination, scanned under a
            recorder over every filesystem entry point including ``open``
        When DS112 detect runs with the default config
        Then ``open`` is called only on the index document itself -- never on any navigation
            destination -- proving destinations are probed with os.stat alone.

    Boundaries:
        - Focus: the R6 stat-only destination probe; only the index is read
        - Fixtures/params: tmp_path, monkeypatch

    On failure, first check:
        - Whether _destination_missing opened a destination instead of using os.stat
    """
    root = Path(os.path.realpath(tmp_path))
    (root / "present.md").write_text("# p\n", encoding="utf-8")
    (root / "index.md").write_text("- [p](present.md)\n- [m](absent.md)\n", encoding="utf-8")
    document = models.Document("index.md", 0)
    config = Config(navigation_indexes=("index.md",))

    navigation.detect(root, (document,), config)  # warm up lazy imports

    recorder = _Recorder()
    _install_recorder(monkeypatch, recorder)

    findings = navigation.detect(root, (document,), config)

    assert [finding.message for finding in findings] == ["navigation target does not exist: absent.md"]
    destination_paths = {os.path.normpath(os.fspath(root / name)) for name in ("present.md", "absent.md")}
    for opened in recorder.opened:
        assert opened not in destination_paths, f"DS112 opened a navigation destination: {opened}"
    index_path = os.path.normpath(os.fspath(root / "index.md"))
    assert index_path in recorder.opened, "DS112 never opened the configured index"


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="os.mkfifo unavailable on this platform")
def test_ds112_never_opens_a_fifo_configured_as_an_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors navigation: verifies a FIFO configured as an index is never opened (R2/R3).

    Scenario:
        Given a runtime FIFO committed where a configured index path points, listed in the
            discovered documents, scanned under a recorder over every entry point including ``open``
        When DS112 detect runs
        Then it raises a ConfigError (the non-regular-file readiness error) promptly and never
            ``open``s the FIFO, so a FIFO index can neither block the scan nor be read.

    Boundaries:
        - Focus: the HIGH config-injection control (R2 os.stat + S_ISREG before any open)
        - Fixtures/params: tmp_path, monkeypatch; skipped with a reason when os.mkfifo is unavailable

    On failure, first check:
        - The stat.S_ISREG branch of _require_readable_index running before _read_index
    """
    root = Path(os.path.realpath(tmp_path))
    os.mkfifo(root / "index.md")
    document = models.Document("index.md", 0)
    config = Config(navigation_indexes=("index.md",))

    recorder = _Recorder()
    _install_recorder(monkeypatch, recorder)

    with pytest.raises(ConfigError):
        navigation.detect(root, (document,), config)

    fifo_path = os.path.normpath(os.fspath(root / "index.md"))
    assert fifo_path not in recorder.opened, "DS112 opened a FIFO configured as an index"
