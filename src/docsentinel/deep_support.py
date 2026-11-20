"""Lazy loaders and readiness probes for deep profile dependencies and models.

TODO(milestone-0002-dedup): consider unifying optional-dependency probes across profiles.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

from docsentinel.log import safe

if TYPE_CHECKING:
    import spacy.language

logger = logging.getLogger(__name__)

DEEP_EXTRA_HINT: str = (
    "install the deep extra (pip install docsentinel[deep]) and the model (python -m spacy download en_core_web_sm)"
)
MODEL_NAME: str = "en_core_web_sm"


def libraries_available() -> bool:
    """Return True if both spacy and textacy can be imported without error."""
    try:
        importlib.import_module("spacy")
        importlib.import_module("textacy")
    except ImportError as exc:
        # A probe: a missing deep extra is a normal install state (doctor reports it).
        logger.debug("deep libraries unavailable: %s", safe(exc.name or exc))
        status = False
        return status
    return True


def model_available() -> bool:
    """Return True if the pinned spaCy model package is installed, without fully loading it."""
    try:
        spacy_util = importlib.import_module("spacy.util")
    except ImportError as exc:
        logger.debug("spacy.util unavailable, model check skipped: %s", safe(exc.name or exc))
        status = False
        return status
    return bool(spacy_util.is_package(MODEL_NAME))


def deep_ready() -> bool:
    """Return True if both libraries and the pinned model are available."""
    return libraries_available() and model_available()


def load_pipeline() -> spacy.language.Language:
    """Load and return the pinned spaCy model pipeline.

    Raises RuntimeError with install guidance if libraries or model are missing.
    """
    try:
        spacy = importlib.import_module("spacy")
    except ImportError as exc:
        logger.debug("deep profile: spacy failed to import at run time: %s", safe(exc.name or exc))
        raise RuntimeError(f"deep profile needs the model '{MODEL_NAME}': {DEEP_EXTRA_HINT}") from exc

    logger.debug("loading spaCy model %s", MODEL_NAME)
    try:
        return spacy.load(MODEL_NAME)
    except (OSError, ImportError) as exc:
        logger.debug("deep profile: spaCy model %s failed to load: %s", MODEL_NAME, type(exc).__name__)
        raise RuntimeError(f"deep profile needs the model '{MODEL_NAME}': {DEEP_EXTRA_HINT}") from exc
