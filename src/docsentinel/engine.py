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
    directory = Path(root).resolve()
    settings = config if config is not None else load_config(directory)
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
