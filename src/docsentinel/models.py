"""Stable data contracts shared by the CLI and library."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    path: str
    bytes: int


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    message: str
    severity: str = "warning"


@dataclass(frozen=True)
class ScanResult:
    profile: str
    documents: tuple[Document, ...]
    findings: tuple[Finding, ...]
    enabled_rules: tuple[str, ...]
    pending: tuple[str, ...]
    notice: str = "Detection rules are not implemented in M0; this is an inventory only."
