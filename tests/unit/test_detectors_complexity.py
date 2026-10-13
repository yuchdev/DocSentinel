"""Tests for DS201 text complexity detector."""

from pathlib import Path

import pytest

pytest.importorskip("textstat")

from docsentinel import models
from docsentinel.detectors.standard import complexity

_SIMPLE_TEXT = (
    "The cat sat on the mat. The sun was hot and bright today. "
    "We had fun playing outside in the yard with our friends all day long. "
    "The dog ran after the red ball across the green grass. "
    "We ate lunch and drank cool water under the shade. "
    "It was a good day for everyone in the park. "
    "Tomorrow we will go to the park again."
)

_DENSE_TEXT = (
    "The epistemological ramifications of post-structuralist hermeneutics "
    "necessitate a comprehensive re-evaluation of ontologically indeterminate "
    "socio-historical contextualizations within modern institutional paradigms. "
    "Consequently, idiosyncratic methodological approaches deliberately obfuscate "
    "the phenomenological dialectic inherent in multidisciplinary theoretical syntaxes. "
    "Furthermore, the institutionalized hegemony of predetermined conceptual frameworks "
    "systematically perpetuates epistemological disenfranchisement across heterogeneous "
    "linguistic subcultures, thereby precluding equitable academic discourse and "
    "collaborative interdisciplinary synthesis."
)


def test_rule_metadata() :
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


def test_compute_grade_level_simple_text_below_threshold() :
    """
    [Unit] detectors complexity: verifies compute grade level simple text below threshold.

    Scenario:
        Given test inputs and fixtures for compute grade level simple text below threshold
        When test_compute_grade_level_simple_text_below_threshold executes the target flow
        Then the expected outcome for compute grade level simple text below threshold is confirmed.

    Boundaries:
        - Focus: compute grade level simple text below threshold
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to compute grade level simple text below threshold
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    grade = complexity.compute_grade_level(_SIMPLE_TEXT)
    assert grade < 14.0


def test_compute_grade_level_dense_academic_text_above_threshold() :
    """
    [Unit] detectors complexity: verifies compute grade level dense academic text above threshold.

    Scenario:
        Given test inputs and fixtures for compute grade level dense academic text above threshold
        When test_compute_grade_level_dense_academic_text_above_threshold executes the target flow
        Then the expected outcome for compute grade level dense academic text above threshold is confirmed.

    Boundaries:
        - Focus: compute grade level dense academic text above threshold
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to compute grade level dense academic text above threshold
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    grade = complexity.compute_grade_level(_DENSE_TEXT)
    assert grade > 14.0


def test_strip_markdown_removes_code_blocks_and_links() :
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


def test_short_document_skipped(tmp_path: Path) :
    """
    [Unit] detectors complexity: verifies short document skipped.

    Scenario:
        Given test inputs and fixtures for short document skipped
        When test_short_document_skipped executes the target flow
        Then the expected outcome for short document skipped is confirmed.

    Boundaries:
        - Focus: short document skipped
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to short document skipped
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    short_dense = (
        "The epistemological ramifications of post-structuralist hermeneutics "
        "necessitate a comprehensive re-evaluation of ontologically indeterminate "
        "socio-historical contextualizations."
    )
    doc_path = tmp_path / "short.md"
    doc_path.write_text(short_dense, encoding="utf-8")
    doc = models.Document(path="short.md", bytes=len(short_dense.encode("utf-8")))

    findings = complexity.check_document(tmp_path, doc, max_grade=14.0)
    assert findings == ()


def test_check_document_emits_warning_finding_on_breach(tmp_path: Path) :
    """
    [Unit] detectors complexity: verifies check document emits warning finding on breach.

    Scenario:
        Given test inputs and fixtures for check document emits warning finding on breach
        When test_check_document_emits_warning_finding_on_breach executes the target flow
        Then the expected outcome for check document emits warning finding on breach is confirmed.

    Boundaries:
        - Focus: check document emits warning finding on breach
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to check document emits warning finding on breach
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    doc_path = tmp_path / "dense.md"
    doc_path.write_text(_DENSE_TEXT, encoding="utf-8")
    doc = models.Document(path="dense.md", bytes=len(_DENSE_TEXT.encode("utf-8")))

    findings = complexity.check_document(tmp_path, doc, max_grade=14.0)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS201"
    assert finding.path == "dense.md"
    assert finding.severity == "warning"
    assert "Readability grade level" in finding.message
    assert "exceeds threshold 14.0" in finding.message


def test_check_document_clean_below_threshold(tmp_path: Path) :
    """
    [Unit] detectors complexity: verifies check document clean below threshold.

    Scenario:
        Given test inputs and fixtures for check document clean below threshold
        When test_check_document_clean_below_threshold executes the target flow
        Then the expected outcome for check document clean below threshold is confirmed.

    Boundaries:
        - Focus: check document clean below threshold
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to check document clean below threshold
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    doc_path = tmp_path / "simple.md"
    doc_path.write_text(_SIMPLE_TEXT, encoding="utf-8")
    doc = models.Document(path="simple.md", bytes=len(_SIMPLE_TEXT.encode("utf-8")))

    findings = complexity.check_document(tmp_path, doc, max_grade=14.0)
    assert findings == ()


def test_detect_runs_over_all_documents(tmp_path: Path) :
    """
    [Unit] detectors complexity: verifies detect runs over all documents.

    Scenario:
        Given test inputs and fixtures for detect runs over all documents
        When test_detect_runs_over_all_documents executes the target flow
        Then the expected outcome for detect runs over all documents is confirmed.

    Boundaries:
        - Focus: detect runs over all documents
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect runs over all documents
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    dense_path = tmp_path / "dense.md"
    dense_path.write_text(_DENSE_TEXT, encoding="utf-8")
    simple_path = tmp_path / "simple.md"
    simple_path.write_text(_SIMPLE_TEXT, encoding="utf-8")
    txt_path = tmp_path / "dense.txt"
    txt_path.write_text(_DENSE_TEXT, encoding="utf-8")

    docs = (
        models.Document(path="dense.md", bytes=len(_DENSE_TEXT.encode("utf-8"))),
        models.Document(path="simple.md", bytes=len(_SIMPLE_TEXT.encode("utf-8"))),
        models.Document(path="dense.txt", bytes=len(_DENSE_TEXT.encode("utf-8"))),
    )

    findings = complexity.detect(tmp_path, docs)
    assert len(findings) == 1
    assert findings[0].path == "dense.md"
    assert findings[0].rule == "DS201"


def test_detect_respects_custom_threshold_from_config(tmp_path: Path) :
    """
    [Unit] detectors complexity: verifies detect respects custom threshold from config.

    Scenario:
        Given test inputs and fixtures for detect respects custom threshold from config
        When test_detect_respects_custom_threshold_from_config executes the target flow
        Then the expected outcome for detect respects custom threshold from config is confirmed.

    Boundaries:
        - Focus: detect respects custom threshold from config
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect respects custom threshold from config
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity
    """
    dense_path = tmp_path / "dense.md"
    dense_path.write_text(_DENSE_TEXT, encoding="utf-8")
    docs = (models.Document(path="dense.md", bytes=len(_DENSE_TEXT.encode("utf-8"))),)

    (tmp_path / "doc_sentinel.toml").write_text("max_grade_level = 50.0\n", encoding="utf-8")
    findings = complexity.detect(tmp_path, docs)
    assert findings == ()

    (tmp_path / "doc_sentinel.toml").write_text("max_grade_level = 10.0\n", encoding="utf-8")
    findings = complexity.detect(tmp_path, docs)
    assert len(findings) == 1
    assert "exceeds threshold 10.0" in findings[0].message
