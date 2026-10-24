"""Mock tests proving DS114 touches only in-root document heads and nothing outside.

The DS114 security contract (the DS113/DS116/DS112 filesystem floor) requires that
the analyzer open only the discovered documents, each as an in-root path, and read
only the **bounded head** of each -- never a document's full body and never any
path that resolves outside the canonical scan root. These tests install a recorder
over every filesystem entry point DS114 can reach, give it a corpus whose documents
include one far larger than the head bound, and assert that every recorded path
stays within the canonical root, that ``open`` is only ever called on a discovered
document, and that the bytes read from the oversized document never exceed the head
bound (so a multi-gigabyte document can neither be read whole nor block the scan).

No skip or xfail hides a regression; the detector is driven end to end against real
files written under ``tmp_path``.
"""

from __future__ import annotations

import builtins
import os
from pathlib import Path

import pytest

from docsentinel import models
from docsentinel.config import Config
from docsentinel.detectors import document_ids


class _Recorder:
    """Records filesystem path arguments and per-file bytes read by DS114."""

    def __init__(self):
        """Initialize empty recording sets for paths, opened paths, and byte counts."""
        self.paths: set[str] = set()
        self.opened: set[str] = set()
        self.bytes_read: dict[str, int] = {}

    def note(self, candidate: object):
        """Record one path-like argument, ignoring non-path arguments such as descriptors.

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

    def note_read(self, candidate: object, count: int):
        """Accumulate the number of bytes read from one path.

        :param candidate: The path whose stream delivered the bytes.
        :param count: The number of bytes returned by this read.
        """
        if isinstance(candidate, (str, os.PathLike)):
            self.bytes_read[os.path.normpath(os.fspath(candidate))] = (
                self.bytes_read.get(os.path.normpath(os.fspath(candidate)), 0) + count
            )


class _CountingStream:
    """A thin proxy over a binary stream that records every byte read per path."""

    def __init__(self, stream: object, path: object, recorder: _Recorder):
        """Wrap ``stream`` for ``path``, accumulating reads into ``recorder``.

        :param stream: The real binary stream to delegate to.
        :param path: The path the stream was opened for.
        :param recorder: The recorder collecting byte counts.
        """
        self._stream = stream
        self._path = path
        self._recorder = recorder

    def read(self, *args: object, **kwargs: object) -> bytes:
        """Delegate to the wrapped stream and record the returned byte count.

        :param args: Positional arguments forwarded to the real read.
        :param kwargs: Keyword arguments forwarded to the real read.
        :returns: The bytes returned by the wrapped stream.
        """
        data = self._stream.read(*args, **kwargs)
        self._recorder.note_read(self._path, len(data))
        return data

    def __enter__(self) -> _CountingStream:
        """Enter the wrapped stream's context and return this proxy.

        :returns: This counting proxy.
        """
        self._stream.__enter__()
        return self

    def __exit__(self, *exc: object) -> object:
        """Exit the wrapped stream's context, forwarding any exception.

        :param exc: The exception triple from the ``with`` block.
        :returns: The wrapped stream's ``__exit__`` result.
        """
        return self._stream.__exit__(*exc)


def _install_recorder(monkeypatch: pytest.MonkeyPatch, recorder: _Recorder):
    """Patch every reachable filesystem entry point to record its path argument.

    Each wrapper records the path then delegates to the saved original so DS114
    behaves normally. ``Path.open`` additionally wraps the returned stream in a
    :class:`_CountingStream` so bytes read per document can be asserted.

    :param monkeypatch: The pytest monkeypatch fixture.
    :param recorder: The recorder collecting path and byte-count data.
    """
    for module, name in (
        (os, "stat"),
        (os, "lstat"),
        (os, "readlink"),
        (os, "scandir"),
        (os, "listdir"),
        (os.path, "exists"),
        (os.path, "realpath"),
    ):
        original = getattr(module, name)

        def wrapper(path: object, *args: object, _original=original, **kwargs: object) -> object:
            """Record the path argument then delegate to the original callable."""
            recorder.note(path)
            return _original(path, *args, **kwargs)

        monkeypatch.setattr(module, name, wrapper)

    original_builtin_open = builtins.open

    def builtin_open_wrapper(path: object, *args: object, _original=original_builtin_open, **kwargs: object) -> object:
        """Record the opened path (both sets) then delegate to the original open."""
        recorder.note(path)
        recorder.note_open(path)
        return _original(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", builtin_open_wrapper)

    original_path_open = Path.open

    def path_open_wrapper(self: Path, *args: object, _original=original_path_open, **kwargs: object) -> object:
        """Record the opened Path, then wrap the real stream in a counting proxy."""
        recorder.note(self)
        recorder.note_open(self)
        stream = _original(self, *args, **kwargs)
        return _CountingStream(stream, self, recorder)

    monkeypatch.setattr(Path, "open", path_open_wrapper)


def _is_under(candidate: str, directory: str) -> bool:
    """Return whether a normalized path equals or lives under a directory.

    :param candidate: A normalized path string.
    :param directory: A normalized directory string.
    :returns: ``True`` when ``candidate`` is ``directory`` or a descendant.
    """
    return candidate == directory or candidate.startswith(directory.rstrip(os.sep) + os.sep)


def _build_corpus(tmp_path: Path) -> tuple[Path, tuple[models.Document, ...]]:
    """Create a scan root with small docs plus one far larger than the head bound.

    :param tmp_path: The pytest temporary directory.
    :returns: ``(canonical_root, documents)`` for a detect run.
    """
    root = tmp_path / "scanroot"
    docs = root / "docs"
    docs.mkdir(parents=True)
    (root / "a.md").write_text("---\nid: alpha\n---\n# A\n", encoding="utf-8")
    (docs / "b.md").write_text("---\nid: beta\n---\n# B\n", encoding="utf-8")
    # A document whose valid frontmatter sits at the top followed by a body far
    # larger than the head bound; its id duplicates a.md so a finding is produced.
    oversized = "---\nid: alpha\n---\n\n" + ("padding line\n" * 200_000)
    (docs / "big.md").write_text(oversized, encoding="utf-8")
    documents = (
        models.Document("a.md", 0),
        models.Document("docs/b.md", 0),
        models.Document("docs/big.md", 0),
    )
    return Path(os.path.realpath(root)), documents


def test_ds114_reads_only_in_root_document_heads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors document_ids: verifies DS114 opens only in-root documents and reads only heads.

    Scenario:
        Given a scan root with two small documents and one document whose body is far larger than
            the head bound, scanned under a recorder over every reachable filesystem entry point
        When DS114 detect runs with the default config
        Then every recorded path stays within the canonical root, ``open`` is only ever called on
            the three discovered documents, and the bytes read from the oversized document never
            exceed the head bound -- while DS114 still produced its duplicate-id finding.

    Boundaries:
        - Focus: no outside-root access and the bounded head read (never the full body)
        - Fixtures/params: tmp_path, monkeypatch

    On failure, first check:
        - Whether _read_head dropped the read(_MAX_HEAD_BYTES) bound and read the whole file
        - Whether a path outside root was opened or stat-ed
    """
    root, documents = _build_corpus(tmp_path)
    config = Config()

    # Warm up any lazy imports before the recorder is installed so the recorded
    # window holds only DS114's own filesystem calls.
    document_ids.detect(root, documents, config)

    recorder = _Recorder()
    _install_recorder(monkeypatch, recorder)

    findings = document_ids.detect(root, documents, config)

    assert [finding.path for finding in findings] == ["docs/big.md"]
    assert recorder.opened, "recorder captured no open; DS114 did not read any document"

    root_str = str(root)
    for recorded in recorder.paths:
        allowed = _is_under(recorded, root_str) or _is_under(root_str, recorded)
        assert allowed, f"touched a path outside the scan root: {recorded}"

    document_paths = {os.path.normpath(os.fspath(root / document.path)) for document in documents}
    for opened in recorder.opened:
        assert opened in document_paths, f"DS114 opened a non-document path: {opened}"

    big_path = os.path.normpath(os.fspath(root / "docs/big.md"))
    assert recorder.bytes_read.get(big_path, 0) <= document_ids._MAX_HEAD_BYTES
    assert (root / "docs/big.md").stat().st_size > document_ids._MAX_HEAD_BYTES


def test_ds114_skips_a_non_utf8_head_without_touching_outside_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors document_ids: verifies a non-UTF-8 document head is skipped, not crashed on.

    Scenario:
        Given a scan root with a valid document and a second document whose head is invalid UTF-8,
            scanned under the filesystem recorder
        When DS114 detect runs
        Then the scan completes with no finding (the undecodable document contributes no identity),
            only in-root documents are opened, and no path outside the root is touched.

    Boundaries:
        - Focus: invalid-UTF-8 head handled as no-identity (documented), still in-root only
        - Fixtures/params: tmp_path, monkeypatch

    On failure, first check:
        - The _decode_head incremental-decoder branch returning None on invalid bytes
    """
    root = Path(os.path.realpath(tmp_path))
    (root / "good.md").write_text("---\nid: solo\n---\n# ok\n", encoding="utf-8")
    (root / "bad.md").write_bytes(b"---\nid: \xff\xfe bad\n---\n")
    documents = (models.Document("good.md", 0), models.Document("bad.md", 0))

    recorder = _Recorder()
    _install_recorder(monkeypatch, recorder)

    findings = document_ids.detect(root, documents, Config())

    assert findings == ()
    root_str = str(root)
    for recorded in recorder.paths:
        allowed = _is_under(recorded, root_str) or _is_under(root_str, recorded)
        assert allowed, f"touched a path outside the scan root: {recorded}"
    document_paths = {os.path.normpath(os.fspath(root / name)) for name in ("good.md", "bad.md")}
    for opened in recorder.opened:
        assert opened in document_paths, f"DS114 opened a non-document path: {opened}"
