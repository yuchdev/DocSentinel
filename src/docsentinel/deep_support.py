"""Lazy loaders and readiness probes for deep profile dependencies and models.

TODO(milestone-0002-dedup): consider unifying optional-dependency probes across profiles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import spacy.language

DEEP_EXTRA_HINT: str = (
    "install the deep extra (pip install docsentinel[deep]) and the model (python -m spacy download en_core_web_sm)"
)
MODEL_NAME: str = "en_core_web_sm"


def libraries_available() -> bool:
    """Return True if both spacy and textacy can be imported without error."""
    try:
        import spacy  # noqa: F401
        import textacy  # noqa: F401
    except ImportError:
        return False
    return True


def model_available() -> bool:
    """Return True if the pinned spaCy model package is installed, without fully loading it."""
    try:
        import spacy.util
    except ImportError:
        return False
    return bool(spacy.util.is_package(MODEL_NAME))


def deep_ready() -> bool:
    """Return True if both libraries and the pinned model are available."""
    return libraries_available() and model_available()


def load_pipeline() -> spacy.language.Language:
    """Load and return the pinned spaCy model pipeline.

    Raises RuntimeError with install guidance if libraries or model are missing.
    """
    try:
        import spacy
    except ImportError as exc:
        raise RuntimeError(f"deep profile needs the model '{MODEL_NAME}': {DEEP_EXTRA_HINT}") from exc

    try:
        return spacy.load(MODEL_NAME)
    except (OSError, ImportError) as exc:
        raise RuntimeError(f"deep profile needs the model '{MODEL_NAME}': {DEEP_EXTRA_HINT}") from exc
