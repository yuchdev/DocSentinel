"""Unit tests for DS201 function logic: rule metadata, grade-level scoring, and markdown stripping.

Detection over documents is covered by ``tests/integration/test_detectors_complexity_ds201.py``.
"""

import pytest

pytest.importorskip("textstat")

from docsentinel.detectors.standard import complexity


def test_rule_metadata():
    """
    [Unit] detectors complexity: verifies rule metadata.

    Scenario:
        Given test inputs and fixtures for rule metadata
        When test_rule_metadata executes the target flow
        Then the expected outcome for rule metadata is confirmed.

    Boundaries:
        - Focus: rule metadata
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to rule metadata
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    assert complexity.DS201.code == "DS201"
    assert complexity.DS201.profile == "standard"
    assert complexity.DS201.title == "High text complexity"
    assert complexity.DS201.severity == "warning"


def test_compute_grade_level_simple_sentence_is_low():
    """
    [Unit] detectors complexity: verifies compute grade level simple sentence is low.

    Scenario:
        Given test inputs and fixtures for compute grade level simple sentence is low
        When test_compute_grade_level_simple_sentence_is_low executes the target flow
        Then the expected outcome for compute grade level simple sentence is low is confirmed.

    Boundaries:
        - Focus: compute grade level simple sentence is low
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to compute grade level simple sentence is low
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    assert complexity.compute_grade_level("The cat sat on the mat.") < 14.0


def test_compute_grade_level_dense_sentence_is_high():
    """
    [Unit] detectors complexity: verifies compute grade level dense sentence is high.

    Scenario:
        Given test inputs and fixtures for compute grade level dense sentence is high
        When test_compute_grade_level_dense_sentence_is_high executes the target flow
        Then the expected outcome for compute grade level dense sentence is high is confirmed.

    Boundaries:
        - Focus: compute grade level dense sentence is high
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to compute grade level dense sentence is high
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    sentence = (
        "The epistemological ramifications of post-structuralist hermeneutics "
        "necessitate a comprehensive re-evaluation of ontologically indeterminate "
        "socio-historical contextualizations within modern institutional paradigms."
    )

    assert complexity.compute_grade_level(sentence) > 14.0


def test_strip_markdown_removes_code_blocks_and_links():
    """
    [Unit] detectors complexity: verifies strip markdown removes code blocks and links.

    Scenario:
        Given test inputs and fixtures for strip markdown removes code blocks and links
        When test_strip_markdown_removes_code_blocks_and_links executes the target flow
        Then the expected outcome for strip markdown removes code blocks and links is confirmed.

    Boundaries:
        - Focus: strip markdown removes code blocks and links
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to strip markdown removes code blocks and links
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    markdown = (
        "# Main Heading\n\n"
        "Here is [a helpful link](https://example.com) and an image ![sample logo](img.png).\n\n"
        "```python\n"
        "def ignored_in_analysis():\n"
        "    return 'code block should not be evaluated'\n"
        "```\n\n"
        'Inline `code_call()` and <span class="highlight">HTML tag</span> are present.\n\n'
        "> A wisdom quote\n\n"
        "- First bullet\n"
        "- Second bullet\n"
        "1. Ordered item\n\n"
        "~~~sh\n"
        "echo ignored\n"
        "~~~\n"
    )
    stripped = complexity._strip_markdown(markdown)
    assert "ignored_in_analysis" not in stripped
    assert "code block should not be evaluated" not in stripped
    assert "https://example.com" not in stripped
    assert "a helpful link" in stripped
    assert "img.png" not in stripped
    assert "sample logo" not in stripped
    assert "code_call" not in stripped
    assert "HTML tag" in stripped
    assert "<span" not in stripped
    assert "#" not in stripped
    assert ">" not in stripped
    assert "echo ignored" not in stripped


def test_strip_markdown_collapses_whitespace_into_single_spaces():
    """
    [Unit] detectors complexity: verifies strip markdown collapses whitespace into single spaces.

    Scenario:
        Given test inputs and fixtures for strip markdown collapses whitespace into single spaces
        When test_strip_markdown_collapses_whitespace_into_single_spaces executes the target flow
        Then the expected outcome for strip markdown collapses whitespace into single spaces is confirmed.

    Boundaries:
        - Focus: strip markdown collapses whitespace into single spaces
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to strip markdown collapses whitespace into single spaces
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    assert complexity._strip_markdown("First   line\n\nSecond\tline\n") == "First line Second line"
