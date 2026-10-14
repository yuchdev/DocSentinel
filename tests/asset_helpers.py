"""Helpers for materializing text assets from ``tests/assets/dsNNN/<case>/`` into a scratch directory.

Assets are grouped by the rule code a case exercises (``ds101``, ``ds202``, ...) so that the
input text for a detector can be found by error type. Each case is a miniature documentation
tree; loading a case copies it byte-for-byte under the destination directory.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from docsentinel import models

ASSETS_ROOT = Path(__file__).resolve().parent / "assets"


@dataclass(frozen=True)
class AssetCase:
    """A materialized copy of one asset case inside a scratch directory."""

    rule: str
    name: str
    root: Path

    def path(self, relative_path: str) -> Path:
        """Return the absolute path of a case file under the scratch root."""
        return self.root / relative_path

    def child(self, relative_dir: str) -> AssetCase:
        """Return a view of a subdirectory of the case, used when a case nests its own scan root."""
        return AssetCase(rule=self.rule, name=f"{self.name}/{relative_dir}", root=self.root / relative_dir)

    def document(self, relative_path: str) -> models.Document:
        """Return the Document model for one file of the case."""
        return models.Document(path=relative_path, bytes=self.path(relative_path).stat().st_size)

    def documents(self, *relative_paths: str) -> tuple[models.Document, ...]:
        """Return Documents for the named files, or for every file in the case sorted by path."""
        if relative_paths:
            return tuple(self.document(relative_path) for relative_path in relative_paths)
        files = sorted(path for path in self.root.rglob("*") if path.is_file())
        return tuple(self.document(path.relative_to(self.root).as_posix()) for path in files)

    def read_text(self, relative_path: str) -> str:
        """Return the UTF-8 text of one file of the case."""
        return self.path(relative_path).read_text(encoding="utf-8")


def load_asset_case(rule: str, case: str, destination: Path, assets_root: Path = ASSETS_ROOT) -> AssetCase:
    """Copy ``<assets_root>/<rule>/<case>`` into destination and return the materialized case.

    Several cases may be loaded into the same destination to compose a larger tree; files
    with the same relative path are overwritten by the later case.
    """
    source = assets_root / rule / case
    if not source.is_dir():
        raise FileNotFoundError(f"unknown asset case: {rule}/{case} (expected directory {source})")
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return AssetCase(rule=rule, name=case, root=destination)
