import importlib
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

from docsentinel import models, rules

links: types.ModuleType


@pytest.fixture(scope="module", autouse=True)
def isolate_rule_registration() -> Iterator[None]:
    """Isolate rule registrations for the links detector test suite."""
    saved_rules = rules.RULES.copy()
    global links
    links = importlib.import_module("docsentinel.detectors.links")
    yield
    rules.RULES.clear()
    rules.RULES.update(saved_rules)


def _write_document(root: Path, relative_path: str, content: str) -> models.Document:
    """Write markdown content to disk and return Document model."""
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return models.Document(path=relative_path, bytes=path.stat().st_size)


def _symlink_or_skip(link: Path, target: Path):
    """Create symlink or skip if symlinks are not supported on filesystem."""
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")


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


def test_dangling_file_link_is_flagged(tmp_path: Path):
    """
    [Unit] detectors links: verifies dangling file link is flagged.

    Scenario:
        Given test inputs and fixtures for dangling file link is flagged
        When test_dangling_file_link_is_flagged executes the target flow
        Then the expected outcome for dangling file link is flagged is confirmed.

    Boundaries:
        - Focus: dangling file link is flagged
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to dangling file link is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
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


def test_missing_file_with_anchor_reports_only_dangling_link(tmp_path: Path):
    """
    [Unit] detectors links: verifies missing file with anchor reports only dangling link.

    Scenario:
        Given test inputs and fixtures for missing file with anchor reports only dangling link
        When test_missing_file_with_anchor_reports_only_dangling_link executes the target flow
        Then the expected outcome for missing file with anchor reports only dangling link is confirmed.

    Boundaries:
        - Focus: missing file with anchor reports only dangling link
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to missing file with anchor reports only dangling link
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(tmp_path, "README.md", "[missing](missing.md#nope)\n")

    findings = links.detect(tmp_path, (document,))

    assert len(findings) == 1
    assert findings[0].message == "dangling link -> missing.md#nope"


@pytest.mark.parametrize(
    ("target", "target_content"),
    (("other.md", "plain text\n"), ("other.md#other", "# Other\n")),
)
def test_valid_link_produces_no_finding(tmp_path: Path, target: str, target_content: str):
    """
    [Unit] detectors links: verifies valid link produces no finding.

    Scenario:
        Given test inputs and fixtures for valid link produces no finding
        When test_valid_link_produces_no_finding executes the target flow
        Then the expected outcome for valid link produces no finding is confirmed.

    Boundaries:
        - Focus: valid link produces no finding
        - Fixtures/params: tmp_path, target, target_content (parametrized, 2 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to valid link produces no finding
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(tmp_path, "README.md", f"[valid]({target})\n")
    _write_document(tmp_path, "other.md", target_content)

    assert links.detect(tmp_path, (document,)) == ()


def test_missing_anchor_in_same_file_is_flagged(tmp_path: Path):
    """
    [Unit] detectors links: verifies missing anchor in same file is flagged.

    Scenario:
        Given test inputs and fixtures for missing anchor in same file is flagged
        When test_missing_anchor_in_same_file_is_flagged executes the target flow
        Then the expected outcome for missing anchor in same file is flagged is confirmed.

    Boundaries:
        - Focus: missing anchor in same file is flagged
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to missing anchor in same file is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
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


def test_missing_anchor_in_other_file_is_flagged(tmp_path: Path):
    """
    [Unit] detectors links: verifies missing anchor in other file is flagged.

    Scenario:
        Given test inputs and fixtures for missing anchor in other file is flagged
        When test_missing_anchor_in_other_file_is_flagged executes the target flow
        Then the expected outcome for missing anchor in other file is flagged is confirmed.

    Boundaries:
        - Focus: missing anchor in other file is flagged
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to missing anchor in other file is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
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


def test_duplicate_headings_get_suffixed_anchors(tmp_path: Path):
    """
    [Unit] detectors links: verifies duplicate headings get suffixed anchors.

    Scenario:
        Given test inputs and fixtures for duplicate headings get suffixed anchors
        When test_duplicate_headings_get_suffixed_anchors executes the target flow
        Then the expected outcome for duplicate headings get suffixed anchors is confirmed.

    Boundaries:
        - Focus: duplicate headings get suffixed anchors
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to duplicate headings get suffixed anchors
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(
        tmp_path,
        "README.md",
        "[second](#foo-1) [third](#foo-2)\n\n## Foo\n## Foo\n## Foo\n",
    )

    assert links.detect(tmp_path, (document,)) == ()


@pytest.mark.parametrize("attribute", ("id", "name"))
def test_html_anchor_tag_is_recognized(tmp_path: Path, attribute: str):
    """
    [Unit] detectors links: verifies html anchor tag is recognized.

    Scenario:
        Given test inputs and fixtures for html anchor tag is recognized
        When test_html_anchor_tag_is_recognized executes the target flow
        Then the expected outcome for html anchor tag is recognized is confirmed.

    Boundaries:
        - Focus: html anchor tag is recognized
        - Fixtures/params: tmp_path, attribute (parametrized, 2 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to html anchor tag is recognized
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(
        tmp_path,
        "README.md",
        f'<a {attribute}="custom"></a>\n\n[x](#custom)\n',
    )

    assert links.detect(tmp_path, (document,)) == ()


def test_links_inside_fenced_code_are_ignored(tmp_path: Path):
    """
    [Unit] detectors links: verifies links inside fenced code are ignored.

    Scenario:
        Given test inputs and fixtures for links inside fenced code are ignored
        When test_links_inside_fenced_code_are_ignored executes the target flow
        Then the expected outcome for links inside fenced code are ignored is confirmed.

    Boundaries:
        - Focus: links inside fenced code are ignored
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to links inside fenced code are ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(
        tmp_path,
        "README.md",
        "```markdown\n[x](missing-one.md)\n```\n~~~\n[y](missing-two.md)\n~~~\n",
    )

    assert links.detect(tmp_path, (document,)) == ()


def test_headings_inside_fenced_code_are_ignored(tmp_path: Path):
    """
    [Unit] detectors links: verifies headings inside fenced code are ignored.

    Scenario:
        Given test inputs and fixtures for headings inside fenced code are ignored
        When test_headings_inside_fenced_code_are_ignored executes the target flow
        Then the expected outcome for headings inside fenced code are ignored is confirmed.

    Boundaries:
        - Focus: headings inside fenced code are ignored
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to headings inside fenced code are ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(
        tmp_path,
        "README.md",
        "[x](#not-a-heading)\n\n```markdown\n# Not A Heading\n```\n",
    )

    findings = links.detect(tmp_path, (document,))

    assert len(findings) == 1
    assert findings[0].message == "missing anchor '#not-a-heading' in this file"


def test_links_inside_inline_code_span_are_ignored(tmp_path: Path):
    """
    [Unit] detectors links: verifies links inside inline code span are ignored.

    Scenario:
        Given test inputs and fixtures for links inside inline code span are ignored
        When test_links_inside_inline_code_span_are_ignored executes the target flow
        Then the expected outcome for links inside inline code span are ignored is confirmed.

    Boundaries:
        - Focus: links inside inline code span are ignored
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to links inside inline code span are ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(tmp_path, "README.md", "`[x](bad.md)`\n")

    assert links.detect(tmp_path, (document,)) == ()


def test_asymmetric_backtick_stripping_exposes_one_dangling_link(tmp_path: Path):
    """
    [Unit] detectors links: verifies asymmetric backtick stripping exposes one dangling link.

    Scenario:
        Given test inputs and fixtures for asymmetric backtick stripping exposes one dangling link
        When test_asymmetric_backtick_stripping_exposes_one_dangling_link executes the target flow
        Then the expected outcome for asymmetric backtick stripping exposes one dangling link is confirmed.

    Boundaries:
        - Focus: asymmetric backtick stripping exposes one dangling link
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to asymmetric backtick stripping exposes one dangling link
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
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


def test_external_and_template_and_glob_targets_are_skipped(tmp_path: Path):
    """
    [Unit] detectors links: verifies external and template and glob targets are skipped.

    Scenario:
        Given test inputs and fixtures for external and template and glob targets are skipped
        When test_external_and_template_and_glob_targets_are_skipped executes the target flow
        Then the expected outcome for external and template and glob targets are skipped is confirmed.

    Boundaries:
        - Focus: external and template and glob targets are skipped
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to external and template and glob targets are skipped
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
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
):
    """
    [Unit] detectors links: verifies leading slash resolves from scan root not cwd.

    Scenario:
        Given test inputs and fixtures for leading slash resolves from scan root not cwd
        When test_leading_slash_resolves_from_scan_root_not_cwd executes the target flow
        Then the expected outcome for leading slash resolves from scan root not cwd is confirmed.

    Boundaries:
        - Focus: leading slash resolves from scan root not cwd
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to leading slash resolves from scan root not cwd
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    root = tmp_path / "scan-root"
    document = _write_document(root, "README.md", "[root file](/docs/x.md)\n")
    _write_document(root, "docs/x.md", "exists\n")
    cwd = tmp_path / "different-cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    assert links.detect(root, (document,)) == ()


def test_nested_relative_link_resolves_from_document_directory(tmp_path: Path):
    """
    [Unit] detectors links: verifies nested relative link resolves from document directory.

    Scenario:
        Given test inputs and fixtures for nested relative link resolves from document directory
        When test_nested_relative_link_resolves_from_document_directory executes the target flow
        Then the expected outcome for nested relative link resolves from document directory is confirmed.

    Boundaries:
        - Focus: nested relative link resolves from document directory
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to nested relative link resolves from document directory
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(tmp_path, "docs/guides/intro.md", "[shared](../shared.md)\n")
    _write_document(tmp_path, "docs/shared.md", "exists\n")

    assert links.detect(tmp_path, (document,)) == ()


def test_parent_traversal_outside_root_matches_source_script(tmp_path: Path):
    """
    [Unit] detectors links: verifies parent traversal outside root matches source script.

    Scenario:
        Given test inputs and fixtures for parent traversal outside root matches source script
        When test_parent_traversal_outside_root_matches_source_script executes the target flow
        Then the expected outcome for parent traversal outside root matches source script is confirmed.

    Boundaries:
        - Focus: parent traversal outside root matches source script
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to parent traversal outside root matches source script
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    root = tmp_path / "scan-root"
    document = _write_document(root, "docs/README.md", "[outside](../../outside.md)\n")
    _write_document(tmp_path, "outside.md", "exists\n")

    assert links.detect(root, (document,)) == ()


def test_symlink_to_existing_target_resolves(tmp_path: Path):
    """
    [Unit] detectors links: verifies symlink to existing target resolves.

    Scenario:
        Given test inputs and fixtures for symlink to existing target resolves
        When test_symlink_to_existing_target_resolves executes the target flow
        Then the expected outcome for symlink to existing target resolves is confirmed.

    Boundaries:
        - Focus: symlink to existing target resolves
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to symlink to existing target resolves
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(tmp_path, "README.md", "[alias](alias.md)\n")
    target = tmp_path / "target.md"
    target.write_text("exists\n", encoding="utf-8")
    _symlink_or_skip(tmp_path / "alias.md", target)

    assert links.detect(tmp_path, (document,)) == ()


def test_broken_symlink_is_dangling(tmp_path: Path):
    """
    [Unit] detectors links: verifies broken symlink is dangling.

    Scenario:
        Given test inputs and fixtures for broken symlink is dangling
        When test_broken_symlink_is_dangling executes the target flow
        Then the expected outcome for broken symlink is dangling is confirmed.

    Boundaries:
        - Focus: broken symlink is dangling
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to broken symlink is dangling
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
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


def test_non_markdown_documents_are_not_scanned(tmp_path: Path):
    """
    [Unit] detectors links: verifies non markdown documents are not scanned.

    Scenario:
        Given test inputs and fixtures for non markdown documents are not scanned
        When test_non_markdown_documents_are_not_scanned executes the target flow
        Then the expected outcome for non markdown documents are not scanned is confirmed.

    Boundaries:
        - Focus: non markdown documents are not scanned
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to non markdown documents are not scanned
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(tmp_path, "notes.txt", "[x](missing.md)\n")

    assert links.detect(tmp_path, (document,)) == ()


def test_finding_reports_one_based_source_line(tmp_path: Path):
    """
    [Unit] detectors links: verifies finding reports one based source line.

    Scenario:
        Given test inputs and fixtures for finding reports one based source line
        When test_finding_reports_one_based_source_line executes the target flow
        Then the expected outcome for finding reports one based source line is confirmed.

    Boundaries:
        - Focus: finding reports one based source line
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to finding reports one based source line
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(tmp_path, "README.md", "first\nsecond\n[x](missing.md)\n")

    findings = links.detect(tmp_path, (document,))

    assert len(findings) == 1
    assert findings[0].line == 3


def test_invalid_utf8_read_error_is_propagated(tmp_path: Path):
    """
    [Unit] detectors links: verifies invalid utf8 read error is propagated.

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
        - Recent changes in code paths exercised by detectors links
    """
    source = tmp_path / "README.md"
    source.write_bytes(b"\xff")
    document = models.Document(path="README.md", bytes=1)

    with pytest.raises(UnicodeDecodeError):
        links.detect(tmp_path, (document,))


def test_invalid_utf8_target_heading_read_is_propagated(tmp_path: Path):
    """
    [Unit] detectors links: verifies invalid utf8 target heading read is propagated.

    Scenario:
        Given test inputs and fixtures for invalid utf8 target heading read is propagated
        When test_invalid_utf8_target_heading_read_is_propagated executes the target flow
        Then the expected outcome for invalid utf8 target heading read is propagated is confirmed.

    Boundaries:
        - Focus: invalid utf8 target heading read is propagated
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to invalid utf8 target heading read is propagated
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(tmp_path, "README.md", "[target](target.md#heading)\n")
    (tmp_path / "target.md").write_bytes(b"\xff")

    with pytest.raises(UnicodeDecodeError):
        links.detect(tmp_path, (document,))


def test_os_read_error_is_propagated(tmp_path: Path):
    """
    [Unit] detectors links: verifies os read error is propagated.

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
        - Recent changes in code paths exercised by detectors links
    """
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
):
    """
    [Unit] detectors links: verifies target open error is propagated.

    Scenario:
        Given test inputs and fixtures for target open error is propagated
        When test_target_open_error_is_propagated executes the target flow
        Then the expected outcome for target open error is propagated is confirmed.

    Boundaries:
        - Focus: target open error is propagated
        - Fixtures/params: tmp_path, monkeypatch, error_type (parametrized, 2 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to target open error is propagated
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    document = _write_document(tmp_path, "README.md", "[target](target.md#heading)\n")
    target = tmp_path / "target.md"
    target.write_text("# Heading\n", encoding="utf-8")
    original_read_lines = links._read_lines

    def fail_target_read(path: Path) -> list[str]:
        """Simulate read failure when accessing target path."""
        if path == target:
            raise error_type("target read failed")
        return original_read_lines(path)

    monkeypatch.setattr(links, "_read_lines", fail_target_read)

    with pytest.raises(error_type, match="target read failed"):
        links.detect(tmp_path, (document,))


def test_findings_preserve_supplied_document_and_link_order(tmp_path: Path):
    """
    [Unit] detectors links: verifies findings preserve supplied document and link order.

    Scenario:
        Given test inputs and fixtures for findings preserve supplied document and link order
        When test_findings_preserve_supplied_document_and_link_order executes the target flow
        Then the expected outcome for findings preserve supplied document and link order is confirmed.

    Boundaries:
        - Focus: findings preserve supplied document and link order
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to findings preserve supplied document and link order
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
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


def test_real_world_document_has_zero_findings():
    """
    [Unit] detectors links: verifies real world document has zero findings.

    Scenario:
        Given test inputs and fixtures for real world document has zero findings
        When test_real_world_document_has_zero_findings executes the target flow
        Then the expected outcome for real world document has zero findings is confirmed.

    Boundaries:
        - Focus: real world document has zero findings
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to real world document has zero findings
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links
    """
    root = Path(__file__).resolve().parents[2]
    relative_path = "docs/adr/0001-config-loading-via-layered-settings.md"
    path = root / relative_path
    document = models.Document(path=relative_path, bytes=path.stat().st_size)

    findings = links.detect(root, (document,))

    assert len(findings) == 0
