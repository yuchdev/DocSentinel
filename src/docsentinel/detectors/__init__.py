"""Importing this package registers every shipped detector's Rule and Analyzer."""

from docsentinel.detectors import comments, links, paths

__all__ = ["comments", "links", "paths"]
