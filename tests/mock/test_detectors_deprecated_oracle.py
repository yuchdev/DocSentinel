"""Mock tests proving DS115 reads only the mapping and the documents, never a target.

The DS115 threat model carries two non-negotiable filesystem controls (R1/R9): the
analyzer performs **no** filesystem access on any path that resolves outside the
canonical scan root, and it never ``stat``s, ``open``s, ``realpath``s, or
symlink-follows a deprecated link/path **target** -- a deprecated path is flagged
purely lexically whether or not it still exists. The only filesystem access during
a scan is the single bounded mapping read plus the already discovered documents, and
a FIFO configured as the mapping is never opened.

These tests install a recorder over every filesystem entry point DS115 can reach,
run it over an adversarial corpus (a deprecated link to an in-root symlink pointing
outside, a lexical root escape, a plain in-root miss, and an existing in-root file
that is *not* a scanned document), and assert that no recorded path leaves the
canonical root, that the only ``open`` calls are the mapping and the scanned
document, and that no deprecated target is ever ``stat``-ed or opened.

Symlink and FIFO creation are skipped only with an explicit reason when the platform
does not support them; no skip or xfail hides a regression.
"""

from __future__ import annotations

import builtins
import os
from pathlib import Path

import pytest

from docsentinel import models
from docsentinel.config import Config, ConfigError
from docsentinel.detectors import deprecated_refs as dep

#: The deprecated link targets placed in the scanned document; each is also a
#: ``kind="link"`` mapping entry (keyed on its tokenized path form) so DS115 flags it
#: lexically. None may be stat-ed or opened.
_LINK_TARGETS = (
    "../../outside/secret.md",
    "evil.md",
    "present.md",
    "missing.md",
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
    """Create the scan root, the out-of-root target tree, and the adversarial corpus.

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

    # An existing in-root file that is a deprecated link target but NOT a scanned
    # document, so any stat on it would be a prohibited target probe.
    (docs / "present.md").write_text("# present\n", encoding="utf-8")
    _symlink_or_skip(docs / "evil.md", "../../outside/secret.md")

    mapping = "version = 1\n" + "".join(
        f'[[replacement]]\nold = "{dep._TOKEN_RE.search(target).group()}"\nnew = "x"\nkind = "link"\n'
        for target in _LINK_TARGETS
    )
    (docs / "deprecated.toml").write_text(mapping, encoding="utf-8")

    body = "# Doc\n\n" + "".join(f"[t{i}]({target})\n" for i, target in enumerate(_LINK_TARGETS))
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

    Each wrapper records the path, then delegates to the saved original so DS115
    behaves normally; ``open`` entry points additionally record into the opened-path
    set so the "only the mapping and the documents are read" control can be asserted.

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


def test_ds115_never_touches_a_path_outside_the_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors deprecated_refs: verifies DS115 never accesses a path outside the root (R9).

    Scenario:
        Given a document whose deprecated links point at an in-root symlink to a real outside
            secret, a lexical root escape, an in-root miss, and an existing non-document file,
            scanned with the mapping configured and a recorder over every filesystem entry point
        When DS115 detect runs
        Then every recorded path stays within the canonical root, the real outside secret is never
            touched, and DS115 still emitted the four lexical link findings.

    Boundaries:
        - Focus: the zero-outside-root and zero-target-probe controls (R9)
        - Fixtures/params: tmp_path, monkeypatch

    On failure, first check:
        - Whether a link target was resolved or stat-ed instead of matched lexically
    """
    root, outside, secret = _build_corpus(tmp_path)
    document = models.Document("docs/README.md", 0)
    config = Config(deprecated_references_file="docs/deprecated.toml")

    dep.detect(root, (document,), config)  # warm up lazy imports before recording

    recorder = _Recorder()
    _install_recorder(monkeypatch, recorder)

    findings = dep.detect(root, (document,), config)

    assert len(findings) == len(_LINK_TARGETS), "DS115 did not emit a lexical finding per deprecated link"
    assert recorder.paths, "recorder captured no filesystem access; DS115 did not run"
    root_str, outside_str, secret_str = (str(root), str(outside), str(secret))
    for recorded in recorder.paths:
        assert recorded != secret_str, f"touched the out-of-root secret file: {recorded}"
        assert not _is_under(recorded, outside_str), f"touched a path under the out-of-root tree: {recorded}"
        allowed = _is_under(recorded, root_str) or _is_under(root_str, recorded)
        assert allowed, f"touched a path outside the scan root: {recorded}"


def test_ds115_opens_only_the_mapping_and_the_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors deprecated_refs: verifies DS115 opens only the mapping and the documents (R9).

    Scenario:
        Given the adversarial corpus scanned under a recorder over every entry point including open
        When DS115 detect runs
        Then the only paths opened are the configured mapping and the scanned document, and no
            deprecated link target (including the existing non-document present.md) is ever stat-ed
            or opened.

    Boundaries:
        - Focus: the single-mapping-read-plus-documents discipline and no target probe (R9)
        - Fixtures/params: tmp_path, monkeypatch

    On failure, first check:
        - Whether a link target was opened or stat-ed by the link matcher
    """
    root, _outside, _secret = _build_corpus(tmp_path)
    document = models.Document("docs/README.md", 0)
    config = Config(deprecated_references_file="docs/deprecated.toml")

    dep.detect(root, (document,), config)  # warm up lazy imports before recording

    recorder = _Recorder()
    _install_recorder(monkeypatch, recorder)

    dep.detect(root, (document,), config)

    mapping_path = os.path.normpath(os.fspath(root / "docs" / "deprecated.toml"))
    document_path = os.path.normpath(os.fspath(root / "docs" / "README.md"))
    assert recorder.opened == {mapping_path, document_path}, recorder.opened

    target_paths = {
        os.path.normpath(os.fspath(root / "docs" / name)) for name in ("present.md", "evil.md", "missing.md")
    }
    target_paths.add(os.path.normpath(os.fspath(root / "outside" / "secret.md")))
    for probed in recorder.paths:
        assert probed not in target_paths, f"DS115 probed a deprecated link target: {probed}"


def test_ds115_never_opens_a_fifo_configured_as_the_mapping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors deprecated_refs: verifies a FIFO mapping is never opened (R1).

    Scenario:
        Given a runtime FIFO committed where the configured mapping path points, scanned under a
            recorder over every entry point including open
        When DS115 detect runs
        Then it raises ConfigError (the non-regular-file readiness error) promptly and never opens
            the FIFO, so a FIFO mapping can neither block the scan nor be read.

    Boundaries:
        - Focus: the HIGH config-injection control (R1 stat + S_ISREG before any open)
        - Fixtures/params: tmp_path, monkeypatch; skipped with a reason when os.mkfifo is unavailable

    On failure, first check:
        - The stat.S_ISREG branch of load_mapping running before the bounded read
    """
    if not hasattr(os, "mkfifo"):
        pytest.skip("os.mkfifo unavailable on this platform")
    root = Path(os.path.realpath(tmp_path))
    os.mkfifo(root / "deprecated.toml")
    document = models.Document("README.md", 0)
    (root / "README.md").write_text("# doc\n", encoding="utf-8")
    config = Config(deprecated_references_file="deprecated.toml")

    recorder = _Recorder()
    _install_recorder(monkeypatch, recorder)

    with pytest.raises(ConfigError):
        dep.detect(root, (document,), config)

    fifo_path = os.path.normpath(os.fspath(root / "deprecated.toml"))
    assert fifo_path not in recorder.opened, "DS115 opened a FIFO configured as the mapping"
