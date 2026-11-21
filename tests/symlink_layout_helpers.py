"""Symlink-out layouts shared by the DS101/DS113/DS116/DS124 deferral tests.

Each builder creates, under a canonical ``tmp_path``, a scan root ``root`` whose
``README.md`` reaches one target stem ``S`` in three forms, one per line:

1. a Markdown link ``[x](S.md)`` (DS101 and DS116),
2. a Markdown image ``![](S.png)`` (DS113 and DS116),
3. a prose mention ``@S.md`` (DS124 and DS116).

The three layouts are the cases the shared component walker
(``path_boundaries._walk``) must refuse (Milestone 0009 Story 01.0 story-close
review, SC-4):

* ``nested`` -- a symlink hidden inside a relative symlink target
  (``l -> a/b`` with ``a -> ../outside`` and ``outside/b`` -> an absolute host directory);
* ``deep_prefix`` -- a symlink-out reached after 70 plain directories, beyond the
  64-hop cap that counts only followed symlinks;
* ``round_trip`` -- ``rt -> ../outside/../root/d``: the kernel lands back inside the
  root on a real ``d/`` holding ``x.md`` and ``x.png``, but the walker must refuse it on
  the first ``..`` above the root (fail closed) rather than collapse the target
  lexically.

Symlinks are created at runtime; a platform without symlinks skips the test with an
explicit reason. Nothing is loaded from ``tests/assets``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from docsentinel import models

#: The DS116 message prefix for a reference that leaves the root through a symlink.
SYMLINK_ESCAPE = "reference resolves through a symlink that escapes the documentation root: "

#: DS116 echoes at most this many characters of the raw target, then ``...`` (transcribed
#: from the detector's bounded-echo contract, not imported from it).
ECHO_LIMIT = 80


def bounded_echo(raw: str) -> str:
    """Return the DS116 echo of an ASCII raw target: at most :data:`ECHO_LIMIT` characters, then ``...``.

    :param raw: The raw target as written in the document (ASCII only in these layouts).
    :returns: The expected echoed text.
    """
    return raw if len(raw) <= ECHO_LIMIT else raw[:ECHO_LIMIT] + "..."


@dataclass(frozen=True)
class SymlinkLayout:
    """A built symlink-out tree.

    :param base: The canonical scratch directory holding ``root`` and ``outside``.
    :param root: The canonical scan root.
    :param stem: The target stem ``S`` the README references as ``S.md`` / ``S.png``.
    :param documents: The single README document tuple to pass to ``detect``.
    """

    base: Path
    root: Path
    stem: str
    documents: tuple[models.Document, ...]

    def expected_ds116(self) -> list[tuple[int, str]]:
        """Return the ``(line, message)`` DS116 must report: link, image and mention.

        :returns: One symlink-escape finding per README line, in line order, with the raw
            target bounded the way DS116 echoes it.
        """
        return [
            (1, SYMLINK_ESCAPE + bounded_echo(f"{self.stem}.md")),
            (2, SYMLINK_ESCAPE + bounded_echo(f"{self.stem}.png")),
            (3, SYMLINK_ESCAPE + bounded_echo(f"@{self.stem}.md")),
        ]


def _symlink(link: Path, target: str):
    """Create a directory symlink or skip the test when the platform refuses.

    :param link: The link to create.
    :param target: Its target text, written verbatim.
    """
    try:
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")


def _finish(base: Path, root: Path, stem: str) -> SymlinkLayout:
    """Write the three-form README and return the layout.

    :param base: The canonical scratch directory.
    :param root: The scan root.
    :param stem: The target stem.
    :returns: The built layout.
    """
    text = f"[x]({stem}.md)\n![]({stem}.png)\n@{stem}.md\n"
    (root / "README.md").write_text(text, encoding="utf-8")
    document = models.Document("README.md", len(text.encode("utf-8")))
    return SymlinkLayout(base=base, root=root, stem=stem, documents=(document,))


def _base(tmp_path: Path) -> tuple[Path, Path]:
    """Return ``(base, root)``: the canonical scratch directory and an empty ``root`` below it.

    An ``outside`` sibling directory is created too, so every symlink target that passes
    through it is valid for the kernel.

    :param tmp_path: The pytest scratch directory.
    :returns: The base and the scan root.
    """
    base = Path(os.path.realpath(tmp_path))
    root = base / "root"
    root.mkdir()
    (base / "outside").mkdir()
    return base, root


def build_nested(tmp_path: Path) -> SymlinkLayout:
    """Build the nested symlink-out layout: ``l -> a/b``, ``a -> ../outside``, ``outside/b -> base``.

    The kernel path ``root/l/x.md`` is ``base/x.md``, which does not exist, so a rule that
    followed the symlink instead of deferring would report a dangling link or missing image.

    :param tmp_path: The pytest scratch directory.
    :returns: The layout with stem ``l/x``.
    """
    base, root = _base(tmp_path)
    _symlink(base / "outside" / "b", str(base))
    _symlink(root / "a", "../outside")
    _symlink(root / "l", "a/b")
    return _finish(base, root, "l/x")


def build_deep_prefix(tmp_path: Path) -> SymlinkLayout:
    """Build the deep-prefix layout: 70 plain ``d`` directories, then ``out -> base/outside``.

    ``outside/x.md`` does not exist, so a rule that followed the symlink would report it.

    :param tmp_path: The pytest scratch directory.
    :returns: The layout with stem ``d/``*70 + ``out/x``.
    """
    base, root = _base(tmp_path)
    deep = root.joinpath(*(["d"] * 70))
    deep.mkdir(parents=True)
    _symlink(deep / "out", str(base / "outside"))
    return _finish(base, root, "d/" * 70 + "out/x")


def build_round_trip(tmp_path: Path) -> SymlinkLayout:
    """Build the round-trip layout: ``rt -> ../outside/../root/d`` over a real ``d/x.md`` and ``d/x.png``.

    The kernel resolves ``root/rt/x.md`` to ``root/d/x.md`` (inside the root), so DS101 and
    DS113 would be silent even if they followed it; the DS116 assertion is what pins the
    walker's fail-closed refusal of a symlink target that climbs above the root.

    :param tmp_path: The pytest scratch directory.
    :returns: The layout with stem ``rt/x``.
    """
    base, root = _base(tmp_path)
    (root / "d").mkdir()
    (root / "d" / "x.md").write_text("# X\n\nReal content.\n", encoding="utf-8")
    (root / "d" / "x.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    _symlink(root / "rt", "../outside/../root/d")
    return _finish(base, root, "rt/x")


#: The three SC-4 layouts, keyed by test id.
LAYOUTS: dict[str, Callable[[Path], SymlinkLayout]] = {
    "nested": build_nested,
    "deep_prefix": build_deep_prefix,
    "round_trip": build_round_trip,
}
