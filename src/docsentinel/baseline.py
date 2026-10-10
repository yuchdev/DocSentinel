"""Finding fingerprints and baseline suppression mechanism."""

import hashlib
import json
from pathlib import Path

from docsentinel.config import ConfigError
from docsentinel.models import Finding

__all__ = ["filter_baselined", "fingerprint", "load_baseline", "save_baseline"]


def fingerprint(finding: Finding) -> str:
    """Compute a stable fingerprint string for a finding."""
    message_hash = hashlib.sha256(finding.message.encode("utf-8")).hexdigest()[:12]
    return f"{finding.rule}:{finding.path}:{message_hash}"


def load_baseline(path: Path) -> frozenset[str]:
    """Load suppressed finding fingerprints from a JSON baseline file.

    Returns an empty frozenset if the file does not exist.
    Raises ConfigError if the file cannot be read, contains invalid JSON,
    or does not adhere strictly to the `{"fingerprints": [...]}` schema
    with string list items.
    """
    if not path.exists():
        return frozenset()
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Cannot read {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"Invalid baseline shape in {path}: expected a JSON object")
    if set(data.keys()) != {"fingerprints"}:
        raise ConfigError(f"Invalid baseline in {path}: expected exactly 'fingerprints' key")
    fingerprints = data["fingerprints"]
    if not isinstance(fingerprints, list) or not all(isinstance(item, str) for item in fingerprints):
        raise ConfigError(f"Invalid baseline in {path}: 'fingerprints' must be a list of strings")
    return frozenset(fingerprints)


def save_baseline(path: Path, findings: tuple[Finding, ...]) -> None:
    """Save finding fingerprints to a JSON baseline file in deterministic sorted order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fingerprints": sorted({fingerprint(f) for f in findings})}
    content = json.dumps(payload, indent=2) + "\n"
    with path.open("w", encoding="utf-8") as stream:
        stream.write(content)


def filter_baselined(findings: tuple[Finding, ...], known: frozenset[str]) -> tuple[Finding, ...]:
    """Filter out findings whose fingerprints are present in the known baseline set."""
    return tuple(finding for finding in findings if fingerprint(finding) not in known)
