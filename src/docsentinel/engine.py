"""Single entry point for all scan consumers."""

from pathlib import Path
from typing import Callable, Optional

from docsentinel.baseline import filter_baselined, load_baseline
from docsentinel.config import Config, load_config
from docsentinel.discovery import discover
from docsentinel.models import Document, Finding, ScanResult
from docsentinel.rules import RULES, effective_rules

Analyzer = Callable[[Path, tuple[Document, ...]], tuple[Finding, ...]]

# Detection analyzers are keyed by their stable rule codes.
ANALYZERS: dict[str, Analyzer] = {}

from docsentinel import detectors as _detectors  # noqa: E402, F401


def scan(root: Path | str = ".", *, config: Optional[Config] = None) -> ScanResult:
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
    profile_codes = tuple(code for code, rule in RULES.items() if rule.profile == settings.profile)
    active_codes = effective_rules(profile_codes, settings.select, settings.ignore)
    findings = tuple(
        finding for code in active_codes if code in ANALYZERS for finding in ANALYZERS[code](directory, documents)
    )
    if settings.baseline is not None:
        baseline_path = (
            Path(settings.baseline)
            if Path(settings.baseline).is_absolute()
            else (directory / settings.baseline).resolve()
        )
        known = load_baseline(baseline_path)
        findings = filter_baselined(findings, known)
    if active_codes:
        pending = ()
        notice = f"{len(active_codes)} {settings.profile} rule(s) evaluated."
    elif not profile_codes:
        pending = (
            ("standard detectors are not implemented in M0",)
            if settings.profile == "standard"
            else ("deep detectors are not implemented in M0",)
            if settings.profile == "deep"
            else ()
        )
        notice = "Detection rules are not implemented in M0; this is an inventory only."
    else:
        pending = (f"all {settings.profile} rules were excluded by select/ignore",)
        notice = f"All {settings.profile} rules were excluded by select/ignore."
    return ScanResult(
        profile=settings.profile,
        documents=documents,
        findings=findings,
        enabled_rules=active_codes,
        pending=pending,
        notice=notice,
    )
