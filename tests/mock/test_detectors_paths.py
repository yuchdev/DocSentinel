"""Mock tests for DS103 where the document read is replaced by a stub instead of touching the filesystem."""

import importlib
import sys
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

from docsentinel import models, rules

paths: types.ModuleType


@pytest.fixture(scope="module", autouse=True)
def isolate_rule_registration() -> Iterator[None]:
    """Isolate rule registration state for paths detector mock tests."""
    saved_rules = rules.RULES.copy()
    links_module_name = "docsentinel.detectors.links"
    paths_module_name = "docsentinel.detectors.paths"
    saved_links_module = sys.modules.get(links_module_name)
    saved_paths_module = sys.modules.get(paths_module_name)
    global paths
    paths = importlib.import_module(paths_module_name)
    yield
    rules.RULES.clear()
    rules.RULES.update(saved_rules)
    if saved_links_module is None:
        sys.modules.pop(links_module_name, None)
    else:
        sys.modules[links_module_name] = saved_links_module
    if saved_paths_module is None:
        sys.modules.pop(paths_module_name, None)
    else:
        sys.modules[paths_module_name] = saved_paths_module


def test_existing_path_produces_no_finding(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors paths: verifies existing path produces no finding.

    Scenario:
        Given test inputs and fixtures for existing path produces no finding
        When test_existing_path_produces_no_finding executes the target flow
        Then the expected outcome for existing path produces no finding is confirmed.

    Boundaries:
        - Focus: existing path produces no finding
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to existing path produces no finding
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    root = Path(__file__).resolve().parents[2]
    document = models.Document(path="README.md", bytes=0)

    def read_fixture(path: Path) -> str:
        """Return stubbed markdown content instead of reading the document from disk."""
        assert path == root / "README.md"
        return "See `src/docsentinel/cli.py`.\n"

    monkeypatch.setattr(paths, "_read_text", read_fixture)

    assert paths.detect(root, (document,)) == ()
