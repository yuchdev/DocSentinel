"""Discover Python source files for code-vs-doc signature checks."""

import os
from fnmatch import fnmatchcase
from pathlib import Path

from docsentinel.config import Config


def discover_python(root: Path, config: Config) -> tuple[Path, ...]:
    """Return a reproducible inventory of matching Python source files."""
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    root = root.resolve()

    def raise_walk_error(error: OSError):
        """Re-raise directory walk errors encountered during os.walk."""
        raise error

    discovered: list[Path] = []

    for entry in config.docsig_paths:
        configured_target = root / entry
        if configured_target.is_symlink():
            continue
        target = configured_target.resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"docsig path must remain under scan root: {entry}")
        if not target.exists():
            continue

        if target.is_file():
            if not target.name.endswith(".py"):
                continue
            try:
                relative = target.relative_to(root).as_posix()
                rel_parts = target.relative_to(root).parts[:-1]
            except ValueError:
                relative = target.as_posix()
                rel_parts = target.parts[:-1]
            if any(fnmatchcase(relative, pattern) for pattern in config.exclude):
                continue
            if any(fnmatchcase(part, pattern) for part in rel_parts for pattern in config.exclude):
                continue
            discovered.append(target)
        elif target.is_dir():
            try:
                target_rel = target.relative_to(root).as_posix()
                target_parts = target.relative_to(root).parts
            except ValueError:
                target_rel = target.as_posix()
                target_parts = target.parts
            if any(fnmatchcase(target_rel, pattern) for pattern in config.exclude):
                continue
            if any(fnmatchcase(part, pattern) for part in target_parts for pattern in config.exclude):
                continue

            for current, directories, filenames in os.walk(target, topdown=True, onerror=raise_walk_error):
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
                    if not filename.endswith(".py"):
                        continue
                    try:
                        relative = path.relative_to(root).as_posix()
                        rel_parts = path.relative_to(root).parts[:-1]
                    except ValueError:
                        relative = path.as_posix()
                        rel_parts = path.parts[:-1]
                    if any(fnmatchcase(relative, pattern) for pattern in config.exclude):
                        continue
                    if any(fnmatchcase(part, pattern) for part in rel_parts for pattern in config.exclude):
                        continue
                    discovered.append(path)

    return tuple(sorted(set(discovered)))
