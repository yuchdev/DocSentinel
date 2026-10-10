import importlib
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

from docsentinel import models, rules

comments: types.ModuleType


@pytest.fixture(scope="module", autouse=True)
def isolate_rule_registration() -> Iterator[None]:
    saved_rules = rules.RULES.copy()
    global comments
    comments = importlib.import_module("docsentinel.detectors.comments")
    yield
    rules.RULES.clear()
    rules.RULES.update(saved_rules)


def _write_document(root: Path, relative_path: str, content: str) -> models.Document:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return models.Document(path=relative_path, bytes=path.stat().st_size)


def test_rule_metadata_is_exact() -> None:
    assert rules.RULES["DS102"] is comments.DS102
    assert comments.DS102.code == "DS102"
    assert comments.DS102.profile == "fast"
    assert comments.DS102.title == "Stray HTML comment"
    assert comments.DS102.description == "An HTML comment was left in rendered Markdown."
    assert comments.DS102.severity == "warning"


def test_single_line_comment_is_flagged(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "intro\n<!-- TODO -->\n")

    assert comments.detect(tmp_path, (document,)) == (
        models.Finding(
            rule="DS102",
            path="README.md",
            message="stray HTML comment: '<!-- TODO -->'",
            severity="warning",
            line=2,
        ),
    )


def test_multiline_comment_is_flagged_once(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "intro\n<!-- TODO\nrewrite\nsoon -->\noutro\n")

    assert comments.detect(tmp_path, (document,)) == (
        models.Finding(
            rule="DS102",
            path="README.md",
            message="stray HTML comment: '<!-- TODO\\nrewrite\\nsoon -->'",
            severity="warning",
            line=2,
        ),
    )


def test_line_numbers_advance_across_multiline_comments(tmp_path: Path) -> None:
    document = _write_document(
        tmp_path,
        "README.md",
        "<!-- first\ncontinued -->\ntext\n<!-- second -->\n",
    )

    assert comments.detect(tmp_path, (document,)) == (
        models.Finding(
            "DS102",
            "README.md",
            "stray HTML comment: '<!-- first\\ncontinued -->'",
            "warning",
            1,
        ),
        models.Finding("DS102", "README.md", "stray HTML comment: '<!-- second -->'", "warning", 4),
    )


def test_many_unclosed_comment_openers_are_ignored(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "<!--\n" * 2_000)

    assert comments.detect(tmp_path, (document,)) == ()


def test_valid_comment_before_many_unclosed_openers_is_flagged(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "<!-- valid -->\n" + "<!--\n" * 2_000)

    assert comments.detect(tmp_path, (document,)) == (
        models.Finding("DS102", "README.md", "stray HTML comment: '<!-- valid -->'", "warning", 1),
    )


@pytest.mark.parametrize(
    "content",
    (
        "```html\n<!-- example -->\n```\nafter\n",
        "before\n```html\n<!-- example -->\n```\nafter\n",
        "before\n```html\n<!-- example -->\n```\n",
    ),
    ids=("start", "middle", "end"),
)
def test_comment_inside_fenced_code_block_is_ignored(
    tmp_path: Path,
    content: str,
) -> None:
    document = _write_document(tmp_path, "README.md", content)

    assert comments.detect(tmp_path, (document,)) == ()


def test_multiple_comments_in_one_document_each_flagged(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "<!-- first --> text <!-- second -->\n")

    assert comments.detect(tmp_path, (document,)) == (
        models.Finding("DS102", "README.md", "stray HTML comment: '<!-- first -->'", "warning", 1),
        models.Finding("DS102", "README.md", "stray HTML comment: '<!-- second -->'", "warning", 1),
    )


def test_long_comment_message_is_truncated(tmp_path: Path) -> None:
    comment_text = f"<!-- {'x' * 100} -->"
    document = _write_document(tmp_path, "README.md", f"{comment_text}\n")

    findings = comments.detect(tmp_path, (document,))

    assert findings[0].message == f"stray HTML comment: {comment_text[:80]!r}..."
    assert findings[0].message.endswith("...")
    assert len(findings[0].message) == 105


def test_non_markdown_documents_are_not_scanned(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "notes.txt", "<!-- TODO -->\n")

    assert comments.detect(tmp_path, (document,)) == ()


def test_line_numbers_are_preserved_after_fence_stripping(tmp_path: Path) -> None:
    document = _write_document(
        tmp_path,
        "README.md",
        "intro\n```html\n<!-- example -->\n```\ntext\n<!-- real -->\n",
    )

    assert comments.detect(tmp_path, (document,)) == (
        models.Finding("DS102", "README.md", "stray HTML comment: '<!-- real -->'", "warning", 6),
    )


def test_invalid_utf8_read_error_is_propagated(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_bytes(b"\xff")
    document = models.Document(path="README.md", bytes=1)

    with pytest.raises(UnicodeDecodeError):
        comments.detect(tmp_path, (document,))


def test_os_read_error_is_propagated(tmp_path: Path) -> None:
    document = models.Document(path="missing.md", bytes=0)

    with pytest.raises(FileNotFoundError):
        comments.detect(tmp_path, (document,))


def test_findings_preserve_supplied_document_and_regex_match_order(tmp_path: Path) -> None:
    second_document = _write_document(tmp_path, "z.md", "<!-- z-one --> <!-- z-two -->\n")
    first_document = _write_document(tmp_path, "a.md", "<!-- a-one --> <!-- a-two -->\n")

    assert comments.detect(tmp_path, (second_document, first_document)) == (
        models.Finding("DS102", "z.md", "stray HTML comment: '<!-- z-one -->'", "warning", 1),
        models.Finding("DS102", "z.md", "stray HTML comment: '<!-- z-two -->'", "warning", 1),
        models.Finding("DS102", "a.md", "stray HTML comment: '<!-- a-one -->'", "warning", 1),
        models.Finding("DS102", "a.md", "stray HTML comment: '<!-- a-two -->'", "warning", 1),
    )
