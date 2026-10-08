"""Text and machine-readable representations of a scan."""

from dataclasses import asdict
import json

from docsentinel.models import ScanResult


def render(result: ScanResult, format: str = "text") -> str:
    if format == "json":
        return json.dumps(asdict(result), indent=2)
    if format != "text":
        raise ValueError(f"Unsupported format: {format}")
    lines = [
        f"Profile: {result.profile}",
        f"Documents: {len(result.documents)}",
        "Enabled rules: " + json.dumps(result.enabled_rules),
        result.notice,
    ]
    lines.extend(f"  {document.path} ({document.bytes} bytes)" for document in result.documents)
    lines.extend(f"Pending: {reason}" for reason in result.pending)
    lines.extend(f"{finding.severity}: {finding.path}: {finding.message}" for finding in result.findings)
    return "\n".join(lines)
