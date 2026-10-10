import importlib
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

from docsentinel import models, rules

links: types.ModuleType


@pytest.fixture(scope="module", autouse=True)
def isolate_rule_registration() -> Iterator[None]:
    saved_rules = rules.RULES.copy()
    global links
    links = importlib.import_module("docsentinel.detectors.links")
    yield
    rules.RULES.clear()
    rules.RULES.update(saved_rules)


def _write_document(root: Path, relative_path: str, content: str) -> models.Document:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return models.Document(path=relative_path, bytes=path.stat().st_size)


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")


def test_rule_metadata_is_exact() -> None:
    assert rules.RULES["DS101"] is links.DS101
    assert links.DS101.code == "DS101"
    assert links.DS101.profile == "fast"
    assert links.DS101.title == "Dangling link or anchor"
    assert links.DS101.description == "A Markdown link or #anchor target does not resolve."
    assert links.DS101.severity == "error"


def test_slugify_matches_github_style() -> None:
    assert links.slugify(" Hello,  World! ") == "hello--world"


def test_dangling_file_link_is_flagged(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "[missing](missing.md)\n")

    assert links.detect(tmp_path, (document,)) == (
        models.Finding(
            rule="DS101",
            path="README.md",
            message="dangling link -> missing.md",
            severity="error",
            line=1,
        ),
    )


def test_missing_file_with_anchor_reports_only_dangling_link(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "[missing](missing.md#nope)\n")

    findings = links.detect(tmp_path, (document,))

    assert len(findings) == 1
    assert findings[0].message == "dangling link -> missing.md#nope"


@pytest.mark.parametrize(
    ("target", "target_content"),
    (("other.md", "plain text\n"), ("other.md#other", "# Other\n")),
)
def test_valid_link_produces_no_finding(tmp_path: Path, target: str, target_content: str) -> None:
    document = _write_document(tmp_path, "README.md", f"[valid]({target})\n")
    _write_document(tmp_path, "other.md", target_content)

    assert links.detect(tmp_path, (document,)) == ()


def test_missing_anchor_in_same_file_is_flagged(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "# Present\n\n[x](#nope)\n")

    assert links.detect(tmp_path, (document,)) == (
        models.Finding(
            rule="DS101",
            path="README.md",
            message="missing anchor '#nope' in this file",
            severity="error",
            line=3,
        ),
    )


def test_missing_anchor_in_other_file_is_flagged(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "[x](other.md#nope)\n")
    _write_document(tmp_path, "other.md", "# Present\n")

    assert links.detect(tmp_path, (document,)) == (
        models.Finding(
            rule="DS101",
            path="README.md",
            message="missing anchor '#nope' in other.md",
            severity="error",
            line=1,
        ),
    )


def test_duplicate_headings_get_suffixed_anchors(tmp_path: Path) -> None:
    document = _write_document(
        tmp_path,
        "README.md",
        "[second](#foo-1) [third](#foo-2)\n\n## Foo\n## Foo\n## Foo\n",
    )

    assert links.detect(tmp_path, (document,)) == ()


@pytest.mark.parametrize("attribute", ("id", "name"))
def test_html_anchor_tag_is_recognized(tmp_path: Path, attribute: str) -> None:
    document = _write_document(
        tmp_path,
        "README.md",
        f'<a {attribute}="custom"></a>\n\n[x](#custom)\n',
    )

    assert links.detect(tmp_path, (document,)) == ()


def test_links_inside_fenced_code_are_ignored(tmp_path: Path) -> None:
    document = _write_document(
        tmp_path,
        "README.md",
        "```markdown\n[x](missing-one.md)\n```\n~~~\n[y](missing-two.md)\n~~~\n",
    )

    assert links.detect(tmp_path, (document,)) == ()


def test_headings_inside_fenced_code_are_ignored(tmp_path: Path) -> None:
    document = _write_document(
        tmp_path,
        "README.md",
        "[x](#not-a-heading)\n\n```markdown\n# Not A Heading\n```\n",
    )

    findings = links.detect(tmp_path, (document,))

    assert len(findings) == 1
    assert findings[0].message == "missing anchor '#not-a-heading' in this file"


def test_links_inside_inline_code_span_are_ignored(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "`[x](bad.md)`\n")

    assert links.detect(tmp_path, (document,)) == ()


def test_asymmetric_backtick_stripping_exposes_one_dangling_link(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "`` `[x](bad.md)` ``\n")

    assert links.detect(tmp_path, (document,)) == (
        models.Finding(
            rule="DS101",
            path="README.md",
            message="dangling link -> bad.md",
            severity="error",
            line=1,
        ),
    )


def test_external_and_template_and_glob_targets_are_skipped(tmp_path: Path) -> None:
    document = _write_document(
        tmp_path,
        "README.md",
        "\n".join(
            (
                "[web](http://example.invalid/missing.md)",
                "[mail](mailto:nobody@example.invalid)",
                "[custom](example:missing)",
                "[template]({NN}-{slug}.md)",
                "[glob](*.md)",
                "[question](docs/?.md)",
                "[empty]()",
                "[space]( )",
            )
        ),
    )

    assert links.detect(tmp_path, (document,)) == ()


def test_leading_slash_resolves_from_scan_root_not_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "scan-root"
    document = _write_document(root, "README.md", "[root file](/docs/x.md)\n")
    _write_document(root, "docs/x.md", "exists\n")
    cwd = tmp_path / "different-cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    assert links.detect(root, (document,)) == ()


def test_nested_relative_link_resolves_from_document_directory(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "docs/guides/intro.md", "[shared](../shared.md)\n")
    _write_document(tmp_path, "docs/shared.md", "exists\n")

    assert links.detect(tmp_path, (document,)) == ()


def test_parent_traversal_outside_root_matches_source_script(tmp_path: Path) -> None:
    root = tmp_path / "scan-root"
    document = _write_document(root, "docs/README.md", "[outside](../../outside.md)\n")
    _write_document(tmp_path, "outside.md", "exists\n")

    assert links.detect(root, (document,)) == ()


def test_symlink_to_existing_target_resolves(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "[alias](alias.md)\n")
    target = tmp_path / "target.md"
    target.write_text("exists\n", encoding="utf-8")
    _symlink_or_skip(tmp_path / "alias.md", target)

    assert links.detect(tmp_path, (document,)) == ()


def test_broken_symlink_is_dangling(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "[alias](alias.md)\n")
    _symlink_or_skip(tmp_path / "alias.md", tmp_path / "missing.md")

    assert links.detect(tmp_path, (document,)) == (
        models.Finding(
            rule="DS101",
            path="README.md",
            message="dangling link -> alias.md",
            severity="error",
            line=1,
        ),
    )


def test_non_markdown_documents_are_not_scanned(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "notes.txt", "[x](missing.md)\n")

    assert links.detect(tmp_path, (document,)) == ()


def test_finding_reports_one_based_source_line(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "first\nsecond\n[x](missing.md)\n")

    findings = links.detect(tmp_path, (document,))

    assert len(findings) == 1
    assert findings[0].line == 3


def test_invalid_utf8_read_error_is_propagated(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_bytes(b"\xff")
    document = models.Document(path="README.md", bytes=1)

    with pytest.raises(UnicodeDecodeError):
        links.detect(tmp_path, (document,))


def test_invalid_utf8_target_heading_read_is_propagated(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "[target](target.md#heading)\n")
    (tmp_path / "target.md").write_bytes(b"\xff")

    with pytest.raises(UnicodeDecodeError):
        links.detect(tmp_path, (document,))


def test_os_read_error_is_propagated(tmp_path: Path) -> None:
    document = models.Document(path="missing.md", bytes=0)

    with pytest.raises(FileNotFoundError):
        links.detect(tmp_path, (document,))


@pytest.mark.parametrize(
    "error_type",
    (OSError, PermissionError),
    ids=("os-error", "permission-error"),
)
def test_target_open_error_is_propagated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[OSError],
) -> None:
    document = _write_document(tmp_path, "README.md", "[target](target.md#heading)\n")
    target = tmp_path / "target.md"
    target.write_text("# Heading\n", encoding="utf-8")
    original_read_lines = links._read_lines

    def fail_target_read(path: Path) -> list[str]:
        if path == target:
            raise error_type("target read failed")
        return original_read_lines(path)

    monkeypatch.setattr(links, "_read_lines", fail_target_read)

    with pytest.raises(error_type, match="target read failed"):
        links.detect(tmp_path, (document,))


def test_findings_preserve_supplied_document_and_link_order(tmp_path: Path) -> None:
    second_document = _write_document(
        tmp_path,
        "z.md",
        "[second-one](z-one.md) [second-two](z-two.md)\n",
    )
    first_document = _write_document(
        tmp_path,
        "a.md",
        "[first-one](a-one.md) [first-two](a-two.md)\n",
    )

    assert links.detect(tmp_path, (second_document, first_document)) == (
        models.Finding("DS101", "z.md", "dangling link -> z-one.md", "error", 1),
        models.Finding("DS101", "z.md", "dangling link -> z-two.md", "error", 1),
        models.Finding("DS101", "a.md", "dangling link -> a-one.md", "error", 1),
        models.Finding("DS101", "a.md", "dangling link -> a-two.md", "error", 1),
    )


def test_real_world_document_has_zero_findings() -> None:
    root = Path(__file__).resolve().parents[1]
    relative_path = "docs/adr/0001-config-loading-via-layered-settings.md"
    path = root / relative_path
    document = models.Document(path=relative_path, bytes=path.stat().st_size)

    findings = links.detect(root, (document,))

    assert len(findings) == 0
