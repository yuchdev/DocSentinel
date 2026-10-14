"""Lazy loader for standard profile detectors and dependencies."""

import builtins
import importlib

from docsentinel.errors import ExtraNotInstalledError

_STANDARD_PACKAGES: frozenset[str] = frozenset({"sklearn", "textstat", "docsig"})
_standard_loaded: bool = False


def ensure_standard_loaded():
    """Import the standard detectors package if not already loaded."""
    global _standard_loaded
    if _standard_loaded:
        return
    try:
        builtins.__import__("docsentinel.detectors.standard")
    except ImportError as exc:
        if exc.name in _STANDARD_PACKAGES:
            raise ExtraNotInstalledError("standard", exc) from exc
        raise
    _standard_loaded = True


def clear_standard_caches() -> None:
    """Reset per-scan corpus caches; the corpus module imports scikit-learn, so load it lazily."""
    ensure_standard_loaded()
    importlib.import_module("docsentinel.detectors.standard.corpus").clear_corpus_cache()
