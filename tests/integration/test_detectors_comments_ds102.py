"""Integration tests for DS102 (stray HTML comment) over text assets in ``tests/assets/ds102``."""

import importlib
import types
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from docsentinel import models, rules
from docsentinel.cli import main
from tests.asset_helpers import AssetCase

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


def _write_document(root: Path, relative_path: str, content: str) -> models.Document:
    """Write generated text to disk and return its Document model."""
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return models.Document(path=relative_path, bytes=path.stat().st_size)


def test_single_line_comment_is_flagged(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors comments ds102: verifies single line comment is flagged.

    Scenario:
        Given test inputs and fixtures for single line comment is flagged
        When test_single_line_comment_is_flagged executes the target flow
        Then the expected outcome for single line comment is flagged is confirmed.

    Boundaries:
        - Focus: single line comment is flagged
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to single line comment is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    case = asset_case("ds102", "single_line_comment")

    assert comments.detect(case.root, case.documents("README.md")) == (
        models.Finding(
            rule="DS102",
            path="README.md",
            message="stray HTML comment: '<!-- TODO -->'",
            severity="warning",
            line=2,
        ),
    )


def test_multiline_comment_is_flagged_once(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors comments ds102: verifies multiline comment is flagged once.

    Scenario:
        Given test inputs and fixtures for multiline comment is flagged once
        When test_multiline_comment_is_flagged_once executes the target flow
        Then the expected outcome for multiline comment is flagged once is confirmed.

    Boundaries:
        - Focus: multiline comment is flagged once
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to multiline comment is flagged once
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    case = asset_case("ds102", "multiline_comment")

    assert comments.detect(case.root, case.documents("README.md")) == (
        models.Finding(
            rule="DS102",
            path="README.md",
            message="stray HTML comment: '<!-- TODO\\nrewrite\\nsoon -->'",
            severity="warning",
            line=2,
        ),
    )


def test_line_numbers_advance_across_multiline_comments(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors comments ds102: verifies line numbers advance across multiline comments.

    Scenario:
        Given test inputs and fixtures for line numbers advance across multiline comments
        When test_line_numbers_advance_across_multiline_comments executes the target flow
        Then the expected outcome for line numbers advance across multiline comments is confirmed.

    Boundaries:
        - Focus: line numbers advance across multiline comments
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to line numbers advance across multiline comments
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    case = asset_case("ds102", "line_numbers_across_multiline_comments")

    assert comments.detect(case.root, case.documents("README.md")) == (
        models.Finding(
            "DS102",
            "README.md",
            "stray HTML comment: '<!-- first\\ncontinued -->'",
            "warning",
            1,
        ),
        models.Finding("DS102", "README.md", "stray HTML comment: '<!-- second -->'", "warning", 4),
    )


def test_many_unclosed_comment_openers_are_ignored(tmp_path: Path):
    """
    [Integration] detectors comments ds102: verifies many unclosed comment openers are ignored.

    Scenario:
        Given test inputs and fixtures for many unclosed comment openers are ignored
        When test_many_unclosed_comment_openers_are_ignored executes the target flow
        Then the expected outcome for many unclosed comment openers are ignored is confirmed.

    Boundaries:
        - Focus: many unclosed comment openers are ignored
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to many unclosed comment openers are ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    document = _write_document(tmp_path, "README.md", "<!--\n" * 2_000)

    assert comments.detect(tmp_path, (document,)) == ()


def test_valid_comment_before_many_unclosed_openers_is_flagged(tmp_path: Path):
    """
    [Integration] detectors comments ds102: verifies valid comment before many unclosed openers is flagged.

    Scenario:
        Given test inputs and fixtures for valid comment before many unclosed openers is flagged
        When test_valid_comment_before_many_unclosed_openers_is_flagged executes the target flow
        Then the expected outcome for valid comment before many unclosed openers is flagged is confirmed.

    Boundaries:
        - Focus: valid comment before many unclosed openers is flagged
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to valid comment before many unclosed openers is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    document = _write_document(tmp_path, "README.md", "<!-- valid -->\n" + "<!--\n" * 2_000)

    assert comments.detect(tmp_path, (document,)) == (
        models.Finding("DS102", "README.md", "stray HTML comment: '<!-- valid -->'", "warning", 1),
    )


@pytest.mark.parametrize(
    "case_name",
    ("comment_in_fence_at_start", "comment_in_fence_in_middle", "comment_in_fence_at_end"),
    ids=("start", "middle", "end"),
)
def test_comment_inside_fenced_code_block_is_ignored(
    asset_case: Callable[[str, str], AssetCase],
    case_name: str,
):
    """
    [Integration] detectors comments ds102: verifies comment inside fenced code block is ignored.

    Scenario:
        Given test inputs and fixtures for comment inside fenced code block is ignored
        When test_comment_inside_fenced_code_block_is_ignored executes the target flow
        Then the expected outcome for comment inside fenced code block is ignored is confirmed.

    Boundaries:
        - Focus: comment inside fenced code block is ignored
        - Fixtures/params: asset_case, case_name (parametrized, 3 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to comment inside fenced code block is ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    case = asset_case("ds102", case_name)

    assert comments.detect(case.root, case.documents("README.md")) == ()


def test_multiple_comments_in_one_document_each_flagged(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors comments ds102: verifies multiple comments in one document each flagged.

    Scenario:
        Given test inputs and fixtures for multiple comments in one document each flagged
        When test_multiple_comments_in_one_document_each_flagged executes the target flow
        Then the expected outcome for multiple comments in one document each flagged is confirmed.

    Boundaries:
        - Focus: multiple comments in one document each flagged
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to multiple comments in one document each flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    case = asset_case("ds102", "multiple_comments_one_line")

    assert comments.detect(case.root, case.documents("README.md")) == (
        models.Finding("DS102", "README.md", "stray HTML comment: '<!-- first -->'", "warning", 1),
        models.Finding("DS102", "README.md", "stray HTML comment: '<!-- second -->'", "warning", 1),
    )


def test_long_comment_message_is_truncated(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors comments ds102: verifies long comment message is truncated.

    Scenario:
        Given test inputs and fixtures for long comment message is truncated
        When test_long_comment_message_is_truncated executes the target flow
        Then the expected outcome for long comment message is truncated is confirmed.

    Boundaries:
        - Focus: long comment message is truncated
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to long comment message is truncated
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    case = asset_case("ds102", "long_comment")
    comment_text = case.read_text("README.md").strip()

    findings = comments.detect(case.root, case.documents("README.md"))

    assert findings[0].message == f"stray HTML comment: {comment_text[:80]!r}..."
    assert findings[0].message.endswith("...")
    assert len(findings[0].message) == 105


def test_non_markdown_documents_are_not_scanned(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors comments ds102: verifies non markdown documents are not scanned.

    Scenario:
        Given test inputs and fixtures for non markdown documents are not scanned
        When test_non_markdown_documents_are_not_scanned executes the target flow
        Then the expected outcome for non markdown documents are not scanned is confirmed.

    Boundaries:
        - Focus: non markdown documents are not scanned
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to non markdown documents are not scanned
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    case = asset_case("ds102", "non_markdown_document")

    assert comments.detect(case.root, case.documents("notes.txt")) == ()


def test_line_numbers_are_preserved_after_fence_stripping(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors comments ds102: verifies line numbers are preserved after fence stripping.

    Scenario:
        Given test inputs and fixtures for line numbers are preserved after fence stripping
        When test_line_numbers_are_preserved_after_fence_stripping executes the target flow
        Then the expected outcome for line numbers are preserved after fence stripping is confirmed.

    Boundaries:
        - Focus: line numbers are preserved after fence stripping
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to line numbers are preserved after fence stripping
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    case = asset_case("ds102", "line_numbers_after_fence_stripping")

    assert comments.detect(case.root, case.documents("README.md")) == (
        models.Finding("DS102", "README.md", "stray HTML comment: '<!-- real -->'", "warning", 6),
    )


def test_invalid_utf8_read_error_is_propagated(tmp_path: Path):
    """
    [Integration] detectors comments ds102: verifies invalid utf8 read error is propagated.

    Scenario:
        Given test inputs and fixtures for invalid utf8 read error is propagated
        When test_invalid_utf8_read_error_is_propagated executes the target flow
        Then the expected outcome for invalid utf8 read error is propagated is confirmed.

    Boundaries:
        - Focus: invalid utf8 read error is propagated
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to invalid utf8 read error is propagated
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    source = tmp_path / "README.md"
    source.write_bytes(b"\xff")
    document = models.Document(path="README.md", bytes=1)

    with pytest.raises(UnicodeDecodeError):
        comments.detect(tmp_path, (document,))


def test_os_read_error_is_propagated(tmp_path: Path):
    """
    [Integration] detectors comments ds102: verifies os read error is propagated.

    Scenario:
        Given test inputs and fixtures for os read error is propagated
        When test_os_read_error_is_propagated executes the target flow
        Then the expected outcome for os read error is propagated is confirmed.

    Boundaries:
        - Focus: os read error is propagated
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to os read error is propagated
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    document = models.Document(path="missing.md", bytes=0)

    with pytest.raises(FileNotFoundError):
        comments.detect(tmp_path, (document,))


def test_findings_preserve_supplied_document_and_regex_match_order(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors comments ds102: verifies findings preserve supplied document and regex match order.

    Scenario:
        Given test inputs and fixtures for findings preserve supplied document and regex match order
        When test_findings_preserve_supplied_document_and_regex_match_order executes the target flow
        Then the expected outcome for findings preserve supplied document and regex match order is confirmed.

    Boundaries:
        - Focus: findings preserve supplied document and regex match order
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to findings preserve supplied document and regex match order
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    case = asset_case("ds102", "findings_preserve_document_order")

    assert comments.detect(case.root, case.documents("z.md", "a.md")) == (
        models.Finding("DS102", "z.md", "stray HTML comment: '<!-- z-one -->'", "warning", 1),
        models.Finding("DS102", "z.md", "stray HTML comment: '<!-- z-two -->'", "warning", 1),
        models.Finding("DS102", "a.md", "stray HTML comment: '<!-- a-one -->'", "warning", 1),
        models.Finding("DS102", "a.md", "stray HTML comment: '<!-- a-two -->'", "warning", 1),
    )


def test_cli_strict_flag_wired_end_to_end(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors comments ds102: verifies cli strict flag wired end to end.

    Scenario:
        Given test inputs and fixtures for cli strict flag wired end to end
        When test_cli_strict_flag_wired_end_to_end executes the target flow
        Then the expected outcome for cli strict flag wired end to end is confirmed.

    Boundaries:
        - Focus: cli strict flag wired end to end
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli strict flag wired end to end
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors comments ds102
    """
    case = asset_case("ds102", "stray_comment_file")

    assert main(["scan", str(case.root)]) == 0
    assert main(["scan", str(case.root), "--strict"]) == 1
