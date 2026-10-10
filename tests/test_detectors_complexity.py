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


def test_rule_metadata() -> None:
    assert complexity.DS201.code == "DS201"
    assert complexity.DS201.profile == "standard"
    assert complexity.DS201.title == "High text complexity"
    assert complexity.DS201.severity == "warning"


def test_compute_grade_level_simple_text_below_threshold() -> None:
    grade = complexity.compute_grade_level(_SIMPLE_TEXT)
    assert grade < 14.0


def test_compute_grade_level_dense_academic_text_above_threshold() -> None:
    grade = complexity.compute_grade_level(_DENSE_TEXT)
    assert grade > 14.0


def test_strip_markdown_removes_code_blocks_and_links() -> None:
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


def test_short_document_skipped(tmp_path: Path) -> None:
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


def test_check_document_emits_warning_finding_on_breach(tmp_path: Path) -> None:
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


def test_check_document_clean_below_threshold(tmp_path: Path) -> None:
    doc_path = tmp_path / "simple.md"
    doc_path.write_text(_SIMPLE_TEXT, encoding="utf-8")
    doc = models.Document(path="simple.md", bytes=len(_SIMPLE_TEXT.encode("utf-8")))

    findings = complexity.check_document(tmp_path, doc, max_grade=14.0)
    assert findings == ()


def test_detect_runs_over_all_documents(tmp_path: Path) -> None:
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


def test_detect_respects_custom_threshold_from_config(tmp_path: Path) -> None:
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
