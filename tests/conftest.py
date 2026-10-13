"""Pytest root configuration and collection organization for DocSentinel."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

_DOCSTRING_TAG_RE = re.compile(r"^\s*\[(Unit|Mock|Integration|E2E)\]", re.IGNORECASE)

_E2E_BODY_MARKERS = ("clirunner", "testclient(", "playwright", "async_playwright")
_MOCK_BODY_MARKERS = ("mock.patch", "@patch", "magicmock", "mock(", "monkeypatch", "mocker.")
_MOCK_FIXTURE_NAMES = {"monkeypatch", "mocker"}

_ORDER = {
    "unit": 0,
    "mock": 1,
    "integration": 2,
    "e2e": 3,
}


def _classify_item(item: pytest.Item) -> str:
    """Classify a test item into unit, mock, integration, or e2e."""
    # 1. Explicit markers already applied
    for marker_name in ("unit", "mock", "integration", "e2e"):
        if item.get_closest_marker(marker_name):
            return marker_name

    # 2. Directory structure precedence
    file_path = Path(str(item.fspath))
    rel_parts = {p.lower() for p in file_path.parts}
    if "integration" in rel_parts:
        return "integration"
    if "mock" in rel_parts:
        return "mock"
    if "e2e" in rel_parts:
        return "e2e"
    if "unit" in rel_parts:
        return "unit"

    # 3. Check docstring tag
    obj = getattr(item, "obj", None)
    doc = inspect.getdoc(obj) if obj else None
    if doc:
        match = _DOCSTRING_TAG_RE.match(doc)
        if match:
            return match.group(1).lower()

    # 4. Fallback heuristics
    stem = file_path.stem.lower()
    body_text = ""
    if obj:
        try:
            body_text = inspect.getsource(obj).lower()
        except (OSError, TypeError):
            body_text = ""

    fixturenames = getattr(item, "fixturenames", [])
    has_mock_fixture = any(name in _MOCK_FIXTURE_NAMES for name in fixturenames)

    if "end_to_end" in stem:
        return "integration"
    if has_mock_fixture or any(marker in body_text for marker in _MOCK_BODY_MARKERS):
        return "mock"
    return "unit"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]):
    """Sort and mark collected test items into unit, mock, integration, and e2e tiers."""
    for item in items:
        category = _classify_item(item)
        if not item.get_closest_marker(category):
            item.add_marker(getattr(pytest.mark, category))

    items.sort(key=lambda item: _ORDER.get(_classify_item(item), 99))
