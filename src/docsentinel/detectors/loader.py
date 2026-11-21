"""Lazy loader for standard profile detectors and dependencies."""

import builtins
import importlib
import logging

from docsentinel.errors import ExtraNotInstalledError
from docsentinel.log import safe

logger = logging.getLogger(__name__)

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
            # Not logged at WARNING/ERROR here: the caller decides (doctor/rules show
            # install guidance, a scan reports the error once at the CLI).
            logger.debug("standard extra unavailable: %s is not installed", safe(exc.name))
            raise ExtraNotInstalledError("standard", exc) from exc
        raise
    _standard_loaded = True
    logger.debug("standard detectors loaded")


def clear_standard_caches():
    """Reset per-scan corpus caches; the corpus module imports scikit-learn, so load it lazily."""
    ensure_standard_loaded()
    importlib.import_module("docsentinel.detectors.standard.corpus").clear_corpus_cache()
