"""Unit tests for DS101 helper logic: rule metadata, anchor slugging, and target classification.

Detection over documents is covered by ``tests/integration/test_detectors_links_ds101.py``.
"""

import importlib
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

from docsentinel import rules

links: types.ModuleType


@pytest.fixture(scope="module", autouse=True)
def isolate_rule_registration() -> Iterator[None]:
    """Isolate rule registrations for the links detector unit test suite."""
    saved_rules = rules.RULES.copy()
    global links
    links = importlib.import_module("docsentinel.detectors.links")
    yield
    rules.RULES.clear()
    rules.RULES.update(saved_rules)


def test_rule_metadata_is_exact():
    """
    [Unit] detectors links: verifies rule metadata is exact.

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
        - Recent changes in code paths exercised by detectors links
    """
    assert rules.RULES["DS101"] is links.DS101
    assert links.DS101.code == "DS101"
    assert links.DS101.profile == "fast"
    assert links.DS101.title == "Dangling link or anchor"
    assert links.DS101.description == "A Markdown link or #anchor target does not resolve."
    assert links.DS101.severity == "error"


def test_slugify_matches_github_style():
    """
    [Unit] detectors links: verifies slugify matches github style.

    Scenario:
        Given test inputs and fixtures for slugify matches github style
        When test_slugify_matches_github_style executes the target flow
        Then the expected outcome for slugify matches github style is confirmed.

    Boundaries:
        - Focus: slugify matches github style
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to slugify matches github style
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    assert links.slugify(" Hello,  World! ") == "hello--world"


@pytest.mark.parametrize(
    ("heading", "slug"),
    (
        ("Hello World", "hello-world"),
        ("  Trim Me  ", "trim-me"),
        ("Dots.and,Commas", "dotsandcommas"),
        ("under_score-dash", "under_score-dash"),
        ("", ""),
    ),
)
def test_slugify_strips_punctuation_and_hyphenates_whitespace(heading: str, slug: str):
    """
    [Unit] detectors links: verifies slugify strips punctuation and hyphenates whitespace.

    Scenario:
        Given test inputs and fixtures for slugify strips punctuation and hyphenates whitespace
        When test_slugify_strips_punctuation_and_hyphenates_whitespace executes the target flow
        Then the expected outcome for slugify strips punctuation and hyphenates whitespace is confirmed.

    Boundaries:
        - Focus: slugify strips punctuation and hyphenates whitespace
        - Fixtures/params: heading, slug (parametrized, 5 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to slugify strips punctuation and hyphenates whitespace
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    assert links.slugify(heading) == slug


@pytest.mark.parametrize(
    "target",
    (
        "",
        "http://example.invalid/missing.md",
        "mailto:nobody@example.invalid",
        "example:missing",
        "{NN}-{slug}.md",
        "*.md",
        "docs/?.md",
    ),
)
def test_is_skippable_for_external_template_and_glob_targets(target: str):
    """
    [Unit] detectors links: verifies is skippable for external template and glob targets.

    Scenario:
        Given test inputs and fixtures for is skippable for external template and glob targets
        When test_is_skippable_for_external_template_and_glob_targets executes the target flow
        Then the expected outcome for is skippable for external template and glob targets is confirmed.

    Boundaries:
        - Focus: is skippable for external template and glob targets
        - Fixtures/params: target (parametrized, 7 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to is skippable for external template and glob targets
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    assert links._is_skippable(target) is True


@pytest.mark.parametrize("target", ("#anchor", "other.md", "other.md#anchor", "docs/guide.md"))
def test_is_skippable_is_false_for_local_targets(target: str):
    """
    [Unit] detectors links: verifies is skippable is false for local targets.

    Scenario:
        Given test inputs and fixtures for is skippable is false for local targets
        When test_is_skippable_is_false_for_local_targets executes the target flow
        Then the expected outcome for is skippable is false for local targets is confirmed.

    Boundaries:
        - Focus: is skippable is false for local targets
        - Fixtures/params: target (parametrized, 4 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to is skippable is false for local targets
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    assert links._is_skippable(target) is False


def test_resolve_leading_slash_uses_scan_root(tmp_path: Path):
    """
    [Unit] detectors links: verifies resolve leading slash uses scan root.

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
        - Recent changes in code paths exercised by detectors links
    """
    root = tmp_path / "scan-root"
    source = root / "docs" / "README.md"

    assert links._resolve("/guide/x.md", source, root) == (root / "guide" / "x.md").resolve()


def test_resolve_relative_target_uses_source_directory(tmp_path: Path):
    """
    [Unit] detectors links: verifies resolve relative target uses source directory.

    Scenario:
        Given test inputs and fixtures for resolve relative target uses source directory
        When test_resolve_relative_target_uses_source_directory executes the target flow
        Then the expected outcome for resolve relative target uses source directory is confirmed.

    Boundaries:
        - Focus: resolve relative target uses source directory
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to resolve relative target uses source directory
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    root = tmp_path / "scan-root"
    source = root / "docs" / "guides" / "intro.md"

    assert links._resolve("../shared.md", source, root) == (root / "docs" / "shared.md").resolve()
