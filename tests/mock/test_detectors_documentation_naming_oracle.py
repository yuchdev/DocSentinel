"""Mock tests proving DS118 performs zero filesystem access of any kind.

DS118 is a pure path-string policy over ``Document.path``: its security contract
forbids reading document content and forbids *any* filesystem access -- no
``open``/``read``, no ``stat``/``lstat``/``readlink``, no ``scandir``/``listdir``, and
not even an ``os.path.realpath`` of the scan root. These tests arm every filesystem
entry point DS118 could conceivably reach to raise on the first call, then run the
detector over a fabricated corpus rooted at a path that does not exist. If DS118
touched the filesystem at all the armed entry point would raise; instead the detector
produces its naming findings purely from the in-memory paths.

No skip or xfail hides a regression; the detector is driven end to end against
fabricated :class:`~docsentinel.models.Document` values whose names are hostile
(spaces, camelCase, control and RTL bytes) so the bounded repr-escaped echo is also
exercised under the armed recorder.
"""

from __future__ import annotations

import builtins
import io
import os
from pathlib import Path

import pytest

from docsentinel import models
from docsentinel.config import Config
from docsentinel.detectors import naming


class _FilesystemTouched(AssertionError):
    """Raised by an armed filesystem entry point to prove DS118 touched the filesystem."""


def _arm_filesystem(monkeypatch: pytest.MonkeyPatch):
    """Patch every reachable filesystem entry point to raise on first use.

    Any call to one of these entry points means DS118 violated its zero-filesystem
    contract, so each wrapper raises :class:`_FilesystemTouched` immediately.

    :param monkeypatch: The pytest monkeypatch fixture.
    """
    for module, name in (
        (os, "stat"),
        (os, "lstat"),
        (os, "readlink"),
        (os, "scandir"),
        (os, "listdir"),
        (os, "open"),
        (os.path, "exists"),
        (os.path, "realpath"),
        (os.path, "islink"),
    ):

        def raiser(*args: object, _name=name, **kwargs: object) -> object:
            """Raise to signal a forbidden filesystem call from DS118."""
            raise _FilesystemTouched(f"DS118 called os path entry point {_name!r}")

        monkeypatch.setattr(module, name, raiser)

    def open_raiser(*args: object, **kwargs: object) -> object:
        """Raise to signal a forbidden open call from DS118."""
        raise _FilesystemTouched("DS118 called an open entry point")

    monkeypatch.setattr(builtins, "open", open_raiser)
    monkeypatch.setattr(io, "open", open_raiser)
    monkeypatch.setattr(Path, "open", open_raiser)
    monkeypatch.setattr(Path, "stat", open_raiser)
    monkeypatch.setattr(Path, "is_file", open_raiser)
    monkeypatch.setattr(Path, "is_symlink", open_raiser)


def test_ds118_detect_touches_no_filesystem(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors naming: verifies DS118 detect produces findings with zero filesystem access.

    Scenario:
        Given a fabricated corpus rooted at a path that does not exist, with every filesystem entry
            point armed to raise, and hostile offending document names
        When DS118 detect runs under the kebab policy
        Then it returns the expected naming findings without any armed entry point firing, proving it
            never opened, stat-ed, or resolved anything.

    Boundaries:
        - Focus: the zero-filesystem contract and the bounded escaped echo under the armed recorder
        - Fixtures/params: monkeypatch; a non-existent root

    On failure, first check:
        - Whether detect called os.path.realpath on root or read any Document body
    """
    root = Path("/nonexistent-docsentinel-root/does/not/exist")
    documents = (
        models.Document("docs/Getting Started.md", 0),
        models.Document("BadDir/apiClient.md", 0),
        models.Document("docs/good-name.md", 0),
        models.Document("docs/wh\x1bat‮.md", 0),
    )

    _arm_filesystem(monkeypatch)

    findings = naming.detect(root, documents, Config(documentation_naming="kebab"))

    paths = [finding.path for finding in findings]
    assert "docs/Getting Started.md" in paths
    assert "docs/good-name.md" not in paths
    assert all(finding.severity == "warning" and finding.line is None for finding in findings)
    hostile = next(finding for finding in findings if finding.path == "docs/wh\x1bat‮.md")
    assert "\x1b" not in hostile.message
    assert "‮" not in hostile.message


def test_ds118_detect_is_inert_without_filesystem_when_disabled(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors naming: verifies the disabled policy returns no findings and touches no filesystem.

    Scenario:
        Given the same fabricated corpus with every filesystem entry point armed to raise
        When DS118 detect runs with documentation_naming off (the default)
        Then it returns no findings and no armed entry point fires.

    Boundaries:
        - Focus: the off opt-in gate is inert with zero filesystem access
        - Fixtures/params: monkeypatch; a non-existent root

    On failure, first check:
        - Whether check_paths short-circuits on the off style before any work
    """
    root = Path("/nonexistent-docsentinel-root")
    documents = (models.Document("docs/Getting Started.md", 0),)

    _arm_filesystem(monkeypatch)

    assert naming.detect(root, documents, Config()) == ()
