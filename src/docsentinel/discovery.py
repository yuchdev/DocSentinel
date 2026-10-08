"""Discover Markdown files without following directory symlinks."""

from fnmatch import fnmatchcase
import os
from pathlib import Path

from docsentinel.config import Config
from docsentinel.models import Document


def discover(root: Path, config: Config) -> tuple[Document, ...]:
    """Return a reproducible inventory of matching regular files."""
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    documents: list[Document] = []

    def raise_walk_error(error: OSError) -> None:
        raise error

    for current, directories, filenames in os.walk(
        root, topdown=True, onerror=raise_walk_error
    ):
        current_path = Path(current)
        directories[:] = [
            name
            for name in directories
            if not (current_path / name).is_symlink()
            and not any(fnmatchcase(name, pattern) for pattern in config.exclude)
        ]
        for filename in filenames:
            path = current_path / filename
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            if any(fnmatchcase(relative, pattern) for pattern in config.exclude):
                continue
            if any(fnmatchcase(part, pattern) for part in path.relative_to(root).parts[:-1]
                   for pattern in config.exclude):
                continue
            if not any(fnmatchcase(relative, pattern) for pattern in config.include):
                continue
            documents.append(Document(relative, path.stat().st_size))
    return tuple(sorted(documents, key=lambda item: item.path))
