"""Importing this package registers every shipped STANDARD-profile detector.

Heavy: importing this module imports scikit-learn / textstat / docsig transitively.
Never import it eagerly - go through docsentinel.detectors.loader.ensure_standard_loaded().
Detector stories (Milestone 0002, Stories 02.0-04.0) each append one submodule import below.
"""

from docsentinel.detectors.standard import complexity, duplication, low_information, signatures

__all__ = ["complexity", "duplication", "low_information", "signatures"]
