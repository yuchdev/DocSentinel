"""Lazy loader for standard profile detectors and dependencies."""

from docsentinel.errors import ExtraNotInstalledError

_STANDARD_PACKAGES: frozenset[str] = frozenset({"sklearn", "textstat", "docsig"})
_standard_loaded: bool = False


def ensure_standard_loaded() -> None:
    """Import the standard detectors package if not already loaded."""
    global _standard_loaded
    if _standard_loaded:
        return
    try:
        import docsentinel.detectors.standard  # noqa: F401
    except ImportError as exc:
        if exc.name in _STANDARD_PACKAGES:
            raise ExtraNotInstalledError("standard", exc) from exc
        raise
    _standard_loaded = True
