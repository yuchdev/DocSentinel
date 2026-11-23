"""Text and data-mining layer: corpus models, claim extraction and NLP pipeline support.

Modules here turn document text into plain data (TF-IDF corpus models, extracted claims, a
loaded spaCy pipeline) for the detectors to judge. They may import only the standard library,
third-party mining libraries, ``docsentinel.models`` and ``docsentinel.log``; callers pass plain
values in, so this layer never depends on configuration, rules, detectors or the engine.

This package imports nothing: ``import docsentinel.mining`` never pulls in spaCy, textacy,
scikit-learn, numpy, scipy or textstat. Import the submodule you need, lazily where the
dependency is optional.
"""
