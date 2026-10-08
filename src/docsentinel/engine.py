"""Single entry point for all scan consumers."""

from pathlib import Path
from typing import Callable

from docsentinel.config import Config, load_config
from docsentinel.discovery import discover
from docsentinel.models import Document, Finding, ScanResult

Analyzer = Callable[[Path, tuple[Document, ...]], tuple[Finding, ...]]

# Detection analyzers will be registered here in later milestones.
ANALYZERS: dict[str, Analyzer] = {}


def scan(root: Path | str = ".", *, config: Config | None = None) -> ScanResult:
    """Inventory documents and run registered analyzers, without implicit deep checks."""
    target = Path(root).resolve()
    selected_file = target.is_file()
    directory = target.parent if selected_file else target
    settings = config if config is not None else load_config(directory)
    if selected_file:
        # An explicitly selected file bypasses include/exclude patterns.
        if Path(root).is_symlink():
            raise ValueError(f"Symlinked files are not inventoried: {root}")
        documents = (Document(target.name, target.stat().st_size),)
    else:
        documents = discover(directory, settings)
    findings = tuple(
        finding
        for analyzer in ANALYZERS.values()
        for finding in analyzer(directory, documents)
    )
    pending = (
        ("standard detectors are not implemented in M0",)
        if settings.profile == "standard"
        else ("deep detectors are not implemented in M0",)
        if settings.profile == "deep"
        else ()
    )
    return ScanResult(settings.profile, documents, findings, tuple(ANALYZERS), pending)
