"""Unit tests for DS103 helper logic: rule metadata, regex shapes, span classification, and path resolution.

Detection over documents is covered by ``tests/integration/test_detectors_paths_ds103.py``.
"""

import importlib
import sys
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

from docsentinel import rules

paths: types.ModuleType


@pytest.fixture(scope="module", autouse=True)
def isolate_rule_registration() -> Iterator[None]:
    """Isolate rule registration state for paths detector unit tests."""
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


def test_rule_metadata_is_exact():
    """
    [Unit] detectors paths: verifies rule metadata is exact.

    Scenario:
        Given test inputs and fixtures for rule metadata is exact
        When test_rule_metadata_is_exact executes the target flow
        Then the expected outcome for rule metadata is exact is confirmed.

    Boundaries:
        - Focus: rule metadata is exact
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to rule metadata is exact
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    assert rules.RULES["DS103"] is paths.DS103
    assert paths.DS103.code == "DS103"
    assert paths.DS103.profile == "fast"
    assert paths.DS103.title == "Unresolvable path-like code span"
    assert paths.DS103.description == "An inline code span looks like a file path but does not resolve."
    assert paths.DS103.severity == "warning"


def test_detector_regex_shapes_are_exact():
    """
    [Unit] detectors paths: verifies detector regex shapes are exact.

    Scenario:
        Given test inputs and fixtures for detector regex shapes are exact
        When test_detector_regex_shapes_are_exact executes the target flow
        Then the expected outcome for detector regex shapes are exact is confirmed.

    Boundaries:
        - Focus: detector regex shapes are exact
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detector regex shapes are exact
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    links = importlib.import_module("docsentinel.detectors.links")

    assert paths._CODE_SPAN_RE.pattern == r"`([^`\n]+)`"
    assert paths._LINK_RE.pattern == links._LINK_RE.pattern == r"!?\[[^\]]*\]\(([^)]+)\)"


@pytest.mark.parametrize(
    "candidate",
    ("--format", "$HOME/.env", ">output.txt", "1.2.3", "v2.0", ".md", "not a path"),
)
def test_is_excluded_for_flags_variables_versions_extensions_and_whitespace(candidate: str):
    """
    [Unit] detectors paths: verifies is excluded for flags variables versions extensions and whitespace.

    Scenario:
        Given test inputs and fixtures for is excluded for flags variables versions extensions and whitespace
        When test_is_excluded_for_flags_variables_versions_extensions_and_whitespace executes the target flow
        Then the expected outcome for is excluded for flags variables versions extensions and whitespace is confirmed.

    Boundaries:
        - Focus: is excluded for flags variables versions extensions and whitespace
        - Fixtures/params: candidate (parametrized, 7 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to is excluded for flags variables versions extensions and whitespace
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    assert paths._is_excluded(candidate) is True


@pytest.mark.parametrize("candidate", ("src/missing.py", "docs/x.md", "README.md"))
def test_is_excluded_is_false_for_path_shaped_spans(candidate: str):
    """
    [Unit] detectors paths: verifies is excluded is false for path shaped spans.

    Scenario:
        Given test inputs and fixtures for is excluded is false for path shaped spans
        When test_is_excluded_is_false_for_path_shaped_spans executes the target flow
        Then the expected outcome for is excluded is false for path shaped spans is confirmed.

    Boundaries:
        - Focus: is excluded is false for path shaped spans
        - Fixtures/params: candidate (parametrized, 3 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to is excluded is false for path shaped spans
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    assert paths._is_excluded(candidate) is False


@pytest.mark.parametrize(
    ("candidate", "expected"),
    (
        ("src/missing.py", True),
        ("README.md", True),
        ("docs/guide", True),
        ("plain", False),
        ("--format", False),
        ("1.2.3", False),
    ),
)
def test_looks_path_like_requires_separator_or_extension(candidate: str, expected: bool):
    """
    [Unit] detectors paths: verifies looks path like requires separator or extension.

    Scenario:
        Given test inputs and fixtures for looks path like requires separator or extension
        When test_looks_path_like_requires_separator_or_extension executes the target flow
        Then the expected outcome for looks path like requires separator or extension is confirmed.

    Boundaries:
        - Focus: looks path like requires separator or extension
        - Fixtures/params: candidate, expected (parametrized, 6 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to looks path like requires separator or extension
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    assert paths._looks_path_like(candidate) is expected


def test_link_label_spans_returns_half_open_offsets_of_labels():
    """
    [Unit] detectors paths: verifies link label spans returns half open offsets of labels.

    Scenario:
        Given test inputs and fixtures for link label spans returns half open offsets of labels
        When test_link_label_spans_returns_half_open_offsets_of_labels executes the target flow
        Then the expected outcome for link label spans returns half open offsets of labels is confirmed.

    Boundaries:
        - Focus: link label spans returns half open offsets of labels
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to link label spans returns half open offsets of labels
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    text = "[`missing.py`](missing.py)\n"

    spans = paths._link_label_spans(text)

    assert spans == ((1, 13),)
    assert text[spans[0][0] : spans[0][1]] == "`missing.py`"


def test_link_label_spans_is_empty_without_links():
    """
    [Unit] detectors paths: verifies link label spans is empty without links.

    Scenario:
        Given test inputs and fixtures for link label spans is empty without links
        When test_link_label_spans_is_empty_without_links executes the target flow
        Then the expected outcome for link label spans is empty without links is confirmed.

    Boundaries:
        - Focus: link label spans is empty without links
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to link label spans is empty without links
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    assert paths._link_label_spans("Plain `code.py` text without links.\n") == ()


def test_resolve_leading_slash_uses_scan_root(tmp_path: Path):
    """
    [Unit] detectors paths: verifies resolve leading slash uses scan root.

    Scenario:
        Given test inputs and fixtures for resolve leading slash uses scan root
        When test_resolve_leading_slash_uses_scan_root executes the target flow
        Then the expected outcome for resolve leading slash uses scan root is confirmed.

    Boundaries:
        - Focus: resolve leading slash uses scan root
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to resolve leading slash uses scan root
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    root = tmp_path / "scan-root"
    source = root / "docs" / "README.md"

    assert paths._resolve("/guide/x.md", source, root) == (root / "guide" / "x.md").resolve()


def test_resolve_relative_candidate_uses_source_directory(tmp_path: Path):
    """
    [Unit] detectors paths: verifies resolve relative candidate uses source directory.

    Scenario:
        Given test inputs and fixtures for resolve relative candidate uses source directory
        When test_resolve_relative_candidate_uses_source_directory executes the target flow
        Then the expected outcome for resolve relative candidate uses source directory is confirmed.

    Boundaries:
        - Focus: resolve relative candidate uses source directory
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to resolve relative candidate uses source directory
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    root = tmp_path / "scan-root"
    source = root / "docs" / "guides" / "intro.md"

    assert paths._resolve("../shared.md", source, root) == (root / "docs" / "shared.md").resolve()


@pytest.mark.parametrize(
    "candidate",
    (r"C:\missing.py", r"\missing.py", r"\\server\share\missing.py"),
    ids=("drive-anchored", "rooted-backslash", "unc"),
)
def test_resolve_windows_anchored_candidate_is_unresolvable(tmp_path: Path, candidate: str):
    """
    [Unit] detectors paths: verifies resolve windows anchored candidate is unresolvable.

    Scenario:
        Given test inputs and fixtures for resolve windows anchored candidate is unresolvable
        When test_resolve_windows_anchored_candidate_is_unresolvable executes the target flow
        Then the expected outcome for resolve windows anchored candidate is unresolvable is confirmed.

    Boundaries:
        - Focus: resolve windows anchored candidate is unresolvable
        - Fixtures/params: tmp_path, candidate (parametrized, 3 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to resolve windows anchored candidate is unresolvable
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    assert paths._resolve(candidate, tmp_path / "README.md", tmp_path) is None
