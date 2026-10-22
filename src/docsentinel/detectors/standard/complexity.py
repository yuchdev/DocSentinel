"""Detect documents exceeding a configurable readability grade level threshold.

DS201 flags documents whose prose exceeds `max_grade_level` (default 14.0).
Readability is evaluated using textstat's Flesch-Kincaid grade level metric.
Note: textstat assumes English-language text.
Note: Configured via a single global `max_grade_level`. Per-category thresholds
are documented for future consideration.

Documents with fewer prose words than `min_document_words` (default 50) are
skipped so short notes are never scored. The Flesch-Kincaid grade level is a
fixed calibration internal of this detector and is not configurable.
"""

import re
from pathlib import Path
from typing import Optional

import textstat

from docsentinel import models, rules
from docsentinel.config import Config, load_config

DS201 = rules.register_rule(
    rules.Rule(
        code="DS201",
        profile="standard",
        title="High text complexity",
        description="Document readability grade level exceeds the configured threshold.",
        severity="warning",
    )
)

_FENCE_RE = re.compile(r"(`{3,}|~{3,}).*?\1", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`+[^`\n]+`+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_HEADER_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^\s*>+\s?", re.MULTILINE)
_LIST_MARKER_RE = re.compile(r"^\s*([-*+]|\d+\.)\s+", re.MULTILINE)


def _strip_markdown(text: str) -> str:
    """Strip code fences, inline code, HTML tags, images, links, headers, quotes, and list markers."""
    text = _FENCE_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)
    text = _IMAGE_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _HEADER_RE.sub("", text)
    text = _BLOCKQUOTE_RE.sub("", text)
    text = _LIST_MARKER_RE.sub("", text)
    return " ".join(text.split())


def _read_text(path: Path) -> str:
    """Read UTF-8 text from a path."""
    with path.open(encoding="utf-8") as stream:
        return stream.read()


def compute_grade_level(text: str) -> float:
    """Compute the Flesch-Kincaid readability grade level for the given text."""
    return float(textstat.flesch_kincaid_grade(text))


def check_document(
    root: Path,
    doc: models.Document,
    max_grade: float = 14.0,
    min_words: int = 50,
) -> tuple[models.Finding, ...]:
    """Check a single document and return DS201 findings if grade level exceeds max_grade.

    :param root: The scan root the document path is resolved against.
    :param doc: The Markdown document to score.
    :param max_grade: Grade level above which the document is flagged.
    :param min_words: Minimum prose-word count before the document is scored;
        documents with fewer words are skipped.
    :returns: A tuple holding one ``DS201`` finding, or empty when within policy.
    """
    source = root / doc.path
    text = _read_text(source)
    prose = _strip_markdown(text)
    words = prose.split()
    if len(words) < min_words:
        return ()

    grade = compute_grade_level(prose)
    if grade > max_grade:
        return (
            models.Finding(
                rule=DS201.code,
                path=doc.path,
                message=f"Readability grade level {grade:.1f} exceeds threshold {max_grade:.1f}",
                severity=DS201.severity,
            ),
        )
    return ()


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Optional[Config] = None,
) -> tuple[models.Finding, ...]:
    """Return DS201 findings for Markdown documents in their supplied order."""
    config = config or load_config(root)
    findings: list[models.Finding] = []
    for doc in documents:
        if not doc.path.endswith(".md"):
            continue
        findings.extend(check_document(root, doc, config.max_grade_level, config.min_document_words))
    return tuple(findings)


rules.ANALYZERS[DS201.code] = detect
