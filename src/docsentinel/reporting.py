"""Text and machine-readable representations of a scan."""

import json
from dataclasses import asdict

from docsentinel.models import ScanResult


def _escape_property(value: str) -> str:
    """Escape a GitHub Actions workflow command property value."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C")


def _escape_data(value: str) -> str:
    """Escape a GitHub Actions workflow command message."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _gha_level(severity: str) -> str:
    """Map finding severity to a GitHub Actions workflow command level."""
    if severity == "error":
        return "error"
    return "warning"


def _render_github(result: ScanResult) -> str:
    """Render scan findings as GitHub Actions workflow command annotations."""
    lines: list[str] = []
    for finding in result.findings:
        level = _gha_level(finding.severity)
        escaped_file = _escape_property(finding.path)
        location = f"file={escaped_file},line={finding.line}" if finding.line is not None else f"file={escaped_file}"
        escaped_message = _escape_data(finding.message)
        lines.append(f"::{level} {location}::{escaped_message}")
    return "\n".join(lines)


def render(result: ScanResult, format: str = "text") -> str:
    if format == "json":
        return json.dumps(asdict(result), indent=2)
    if format == "github":
        return _render_github(result)
    if format != "text":
        raise ValueError(f"Unsupported format: {format}")
    lines = [
        f"Schema version: {result.schema_version}",
        f"Profile: {result.profile}",
        f"Documents: {len(result.documents)}",
        "Enabled rules: " + json.dumps(result.enabled_rules),
        result.notice,
    ]
    lines.extend(f"  {document.path} ({document.bytes} bytes)" for document in result.documents)
    lines.extend(f"Pending: {reason}" for reason in result.pending)
    lines.extend(f"{finding.severity}: {finding.path}: {finding.message}" for finding in result.findings)
    return "\n".join(lines)
