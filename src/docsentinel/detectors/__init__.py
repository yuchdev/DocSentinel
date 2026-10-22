"""Importing this package registers every shipped detector's Rule and Analyzer."""

from docsentinel.detectors import (
    anchors,
    assets,
    comments,
    contradictions,
    fence_languages,
    fences,
    headings,
    links,
    path_boundaries,
    paths,
    references,
    sections,
    tables,
)

__all__ = [
    "anchors",
    "assets",
    "comments",
    "contradictions",
    "fence_languages",
    "fences",
    "headings",
    "links",
    "path_boundaries",
    "paths",
    "references",
    "sections",
    "tables",
]
