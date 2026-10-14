"""Unit tests for DS102 helper logic: rule metadata and fenced-block blanking.

Detection over documents is covered by ``tests/integration/test_detectors_comments_ds102.py``.
"""

import importlib
import types
from collections.abc import Iterator

import pytest

from docsentinel import rules

comments: types.ModuleType


@pytest.fixture(scope="module", autouse=True)
def isolate_rule_registration() -> Iterator[None]:
    """Isolate rule registrations before and after running tests in this module."""
    saved_rules = rules.RULES.copy()
    global comments
    comments = importlib.import_module("docsentinel.detectors.comments")
    yield
    rules.RULES.clear()
    rules.RULES.update(saved_rules)


def test_rule_metadata_is_exact():
    """
    [Unit] detectors comments: verifies rule metadata is exact.

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
        - Recent changes in code paths exercised by detectors comments
    """
    assert rules.RULES["DS102"] is comments.DS102
    assert comments.DS102.code == "DS102"
    assert comments.DS102.profile == "fast"
    assert comments.DS102.title == "Stray HTML comment"
    assert comments.DS102.description == "An HTML comment was left in rendered Markdown."
    assert comments.DS102.severity == "warning"


def test_strip_fenced_blocks_blanks_fence_lines_and_body_preserving_offsets():
    """
    [Unit] detectors comments: verifies strip fenced blocks blanks fence lines and body preserving offsets.

    Scenario:
        Given test inputs and fixtures for strip fenced blocks blanks fence lines and body preserving offsets
        When test_strip_fenced_blocks_blanks_fence_lines_and_body_preserving_offsets executes the target flow
        Then the expected outcome for strip fenced blocks blanks fence lines and body preserving offsets is confirmed.

    Boundaries:
        - Focus: strip fenced blocks blanks fence lines and body preserving offsets
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to strip fenced blocks blanks fence lines and body preserving offsets
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments
    """
    text = "intro\n```html\n<!-- example -->\n```\ntext\n"

    stripped = comments._strip_fenced_blocks(text)

    assert len(stripped) == len(text)
    assert stripped.count("\n") == text.count("\n")
    assert stripped.splitlines()[0] == "intro"
    assert stripped.splitlines()[4] == "text"
    assert "<!--" not in stripped
    assert "```" not in stripped


def test_strip_fenced_blocks_leaves_unfenced_text_untouched():
    """
    [Unit] detectors comments: verifies strip fenced blocks leaves unfenced text untouched.

    Scenario:
        Given test inputs and fixtures for strip fenced blocks leaves unfenced text untouched
        When test_strip_fenced_blocks_leaves_unfenced_text_untouched executes the target flow
        Then the expected outcome for strip fenced blocks leaves unfenced text untouched is confirmed.

    Boundaries:
        - Focus: strip fenced blocks leaves unfenced text untouched
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to strip fenced blocks leaves unfenced text untouched
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments
    """
    text = "before\n<!-- visible -->\nafter\n"

    assert comments._strip_fenced_blocks(text) == text


def test_strip_fenced_blocks_requires_matching_marker_to_close_fence():
    """
    [Unit] detectors comments: verifies strip fenced blocks requires matching marker to close fence.

    Scenario:
        Given test inputs and fixtures for strip fenced blocks requires matching marker to close fence
        When test_strip_fenced_blocks_requires_matching_marker_to_close_fence executes the target flow
        Then the expected outcome for strip fenced blocks requires matching marker to close fence is confirmed.

    Boundaries:
        - Focus: strip fenced blocks requires matching marker to close fence
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to strip fenced blocks requires matching marker to close fence
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments
    """
    text = "```html\n~~~\n<!-- still fenced -->\n```\n<!-- visible -->\n"

    stripped = comments._strip_fenced_blocks(text)

    assert "still fenced" not in stripped
    assert "<!-- visible -->" in stripped
