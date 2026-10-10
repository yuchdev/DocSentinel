"""Detect unresolvable path-like inline code spans in Markdown documents.

Multi-backtick spans are not parsed; only the specified single-backtick pattern is supported.
"""

import re
from pathlib import Path, PureWindowsPath
from typing import Optional

from docsentinel import engine, models, rules

DS103 = rules.register_rule(
    rules.Rule(
        code="DS103",
        profile="fast",
        title="Unresolvable path-like code span",
        description="An inline code span looks like a file path but does not resolve.",
        severity="warning",
    )
)

_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_EXTENSION_RE = re.compile(r"\.[A-Za-z0-9]{1,5}$")
_VERSION_RE = re.compile(r"v?\d+(\.\d+){1,3}")
_BARE_EXTENSION_RE = re.compile(r"\.[A-Za-z0-9]{1,4}")


def _strip_fenced_blocks(text: str) -> str:
    """Return text with fenced code blocks blanked while preserving offsets."""
    stripped_lines: list[str] = []
    in_fence = False
    fence_marker: Optional[str] = None

    for line in text.splitlines(keepends=True):
        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)[0]
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence, fence_marker = False, None

        if in_fence or fence:
            blank_line = "".join(character if character in "\r\n" else " " for character in line)
            stripped_lines.append(blank_line)
        else:
            stripped_lines.append(line)

    return "".join(stripped_lines)


def _read_text(path: Path) -> str:
    """Read UTF-8 text from a path."""
    with path.open(encoding="utf-8") as stream:
        return stream.read()


def _is_excluded(candidate: str) -> bool:
    """Return whether a code span is excluded from path detection."""
    if any(character.isspace() for character in candidate):
        return True
    if candidate.startswith(("-", "$", ">")):
        return True
    if _VERSION_RE.fullmatch(candidate):
        return True
    return bool(_BARE_EXTENSION_RE.fullmatch(candidate))


def _looks_path_like(candidate: str) -> bool:
    """Return whether a code span has the specified path-like shape."""
    return not _is_excluded(candidate) and ("/" in candidate or bool(_EXTENSION_RE.search(candidate)))


def _resolve(candidate: str, source: Path, root: Path) -> Optional[Path]:
    """Resolve a candidate relative to the scan root or source document."""
    if candidate.startswith("/"):
        return (root / candidate.lstrip("/")).resolve()
    if PureWindowsPath(candidate).anchor:
        return None
    return (source.parent / candidate).resolve()


def _link_label_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Return half-open offsets for Markdown link labels in match order."""
    spans: list[tuple[int, int]] = []
    for match in _LINK_RE.finditer(text):
        matched_text = match.group(0)
        label_start = match.start() + matched_text.index("[") + 1
        label_end = match.start() + matched_text.index("]")
        spans.append((label_start, label_end))
    return tuple(spans)


def detect(root: Path, documents: tuple[models.Document, ...]) -> tuple[models.Finding, ...]:
    """Return DS103 findings for Markdown documents in their supplied order."""
    findings: list[models.Finding] = []
    for document in documents:
        if not document.path.endswith(".md"):
            continue

        source = root / document.path
        text = _strip_fenced_blocks(_read_text(source))
        label_spans = _link_label_spans(text)
        label_index = 0
        line = 1
        line_cursor = 0

        for match in _CODE_SPAN_RE.finditer(text):
            start, end = match.span()
            line += text.count("\n", line_cursor, start)
            line_cursor = start

            while label_index < len(label_spans) and label_spans[label_index][1] <= start:
                label_index += 1
            if (
                label_index < len(label_spans)
                and label_spans[label_index][0] <= start
                and end <= label_spans[label_index][1]
            ):
                continue

            candidate = match.group(1)
            if not _looks_path_like(candidate) or _is_excluded(candidate):
                continue
            resolved = _resolve(candidate, source, root)
            if resolved is not None and resolved.exists():
                continue

            findings.append(
                models.Finding(
                    rule=DS103.code,
                    path=document.path,
                    message=f"unresolvable path -> {candidate}",
                    severity=DS103.severity,
                    line=line,
                )
            )
    return tuple(findings)


engine.ANALYZERS[DS103.code] = detect
