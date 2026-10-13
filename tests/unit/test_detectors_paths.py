import importlib
import sys
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

from docsentinel import models, rules

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


def _write_document(root: Path, relative_path: str, content: str) -> models.Document:
    """Write markdown file to given path and return Document."""
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return models.Document(path=relative_path, bytes=path.stat().st_size)


def _symlink_or_skip(link: Path, target: Path):
    """Create symlink or skip if symlinks are not supported."""
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")


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


def test_unresolvable_relative_path_is_flagged(tmp_path: Path):
    """
    [Unit] detectors paths: verifies unresolvable relative path is flagged.

    Scenario:
        Given test inputs and fixtures for unresolvable relative path is flagged
        When test_unresolvable_relative_path_is_flagged executes the target flow
        Then the expected outcome for unresolvable relative path is flagged is confirmed.

    Boundaries:
        - Focus: unresolvable relative path is flagged
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to unresolvable relative path is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", "See `src/missing.py`.\n")

    assert paths.detect(tmp_path, (document,)) == (
        models.Finding(
            rule="DS103",
            path="README.md",
            message="unresolvable path -> src/missing.py",
            severity="warning",
            line=1,
        ),
    )


def test_existing_path_produces_no_finding(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors paths: verifies existing path produces no finding.

    Scenario:
        Given test inputs and fixtures for existing path produces no finding
        When test_existing_path_produces_no_finding executes the target flow
        Then the expected outcome for existing path produces no finding is confirmed.

    Boundaries:
        - Focus: existing path produces no finding
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to existing path produces no finding
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    root = Path(__file__).resolve().parents[2]
    document = models.Document(path="README.md", bytes=0)

    def read_fixture(path: Path) -> str:
        """Read mocked markdown fixture content."""
        assert path == root / "README.md"
        return "See `src/docsentinel/cli.py`.\n"

    monkeypatch.setattr(paths, "_read_text", read_fixture)

    assert paths.detect(root, (document,)) == ()


def test_leading_slash_resolves_from_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors paths: verifies leading slash resolves from root.

    Scenario:
        Given test inputs and fixtures for leading slash resolves from root
        When test_leading_slash_resolves_from_root executes the target flow
        Then the expected outcome for leading slash resolves from root is confirmed.

    Boundaries:
        - Focus: leading slash resolves from root
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to leading slash resolves from root
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    root = tmp_path / "scan-root"
    document = _write_document(root, "README.md", "See `/docs/x.md`.\n")
    _write_document(root, "docs/x.md", "exists\n")
    other_directory = tmp_path / "other"
    other_directory.mkdir()
    monkeypatch.chdir(other_directory)

    assert paths.detect(root, (document,)) == ()


def test_cli_flag_like_span_is_excluded(tmp_path: Path):
    """
    [Unit] detectors paths: verifies cli flag like span is excluded.

    Scenario:
        Given test inputs and fixtures for cli flag like span is excluded
        When test_cli_flag_like_span_is_excluded executes the target flow
        Then the expected outcome for cli flag like span is excluded is confirmed.

    Boundaries:
        - Focus: cli flag like span is excluded
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli flag like span is excluded
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", "Use `--format`.\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_version_number_like_span_is_excluded(tmp_path: Path):
    """
    [Unit] detectors paths: verifies version number like span is excluded.

    Scenario:
        Given test inputs and fixtures for version number like span is excluded
        When test_version_number_like_span_is_excluded executes the target flow
        Then the expected outcome for version number like span is excluded is confirmed.

    Boundaries:
        - Focus: version number like span is excluded
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to version number like span is excluded
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", "Versions `1.2.3` and `v2.0`.\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_bare_extension_span_is_excluded(tmp_path: Path):
    """
    [Unit] detectors paths: verifies bare extension span is excluded.

    Scenario:
        Given test inputs and fixtures for bare extension span is excluded
        When test_bare_extension_span_is_excluded executes the target flow
        Then the expected outcome for bare extension span is excluded is confirmed.

    Boundaries:
        - Focus: bare extension span is excluded
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to bare extension span is excluded
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", "Markdown uses `.md`.\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_span_with_whitespace_is_excluded(tmp_path: Path):
    """
    [Unit] detectors paths: verifies span with whitespace is excluded.

    Scenario:
        Given test inputs and fixtures for span with whitespace is excluded
        When test_span_with_whitespace_is_excluded executes the target flow
        Then the expected outcome for span with whitespace is excluded is confirmed.

    Boundaries:
        - Focus: span with whitespace is excluded
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to span with whitespace is excluded
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", "This is `not a path`.\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_shell_prompt_and_variable_like_spans_are_excluded(tmp_path: Path):
    """
    [Unit] detectors paths: verifies shell prompt and variable like spans are excluded.

    Scenario:
        Given test inputs and fixtures for shell prompt and variable like spans are excluded
        When test_shell_prompt_and_variable_like_spans_are_excluded executes the target flow
        Then the expected outcome for shell prompt and variable like spans are excluded is confirmed.

    Boundaries:
        - Focus: shell prompt and variable like spans are excluded
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to shell prompt and variable like spans are excluded
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", "Use `$HOME/.env` or `>output.txt`.\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_code_span_inside_link_label_is_not_double_reported(tmp_path: Path):
    """
    [Unit] detectors paths: verifies code span inside link label is not double reported.

    Scenario:
        Given test inputs and fixtures for code span inside link label is not double reported
        When test_code_span_inside_link_label_is_not_double_reported executes the target flow
        Then the expected outcome for code span inside link label is not double reported is confirmed.

    Boundaries:
        - Focus: code span inside link label is not double reported
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to code span inside link label is not double reported
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    links = importlib.import_module("docsentinel.detectors.links")
    document = _write_document(tmp_path, "README.md", "[`missing.py`](missing.py)\n")

    assert len(links.detect(tmp_path, (document,))) == 1
    assert paths.detect(tmp_path, (document,)) == ()


def test_code_span_inside_fenced_block_is_ignored(tmp_path: Path):
    """
    [Unit] detectors paths: verifies code span inside fenced block is ignored.

    Scenario:
        Given test inputs and fixtures for code span inside fenced block is ignored
        When test_code_span_inside_fenced_block_is_ignored executes the target flow
        Then the expected outcome for code span inside fenced block is ignored is confirmed.

    Boundaries:
        - Focus: code span inside fenced block is ignored
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to code span inside fenced block is ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(
        tmp_path,
        "README.md",
        "```markdown\n`src/missing.py`\n```\n~~~\n`docs/missing.md`\n~~~\n",
    )

    assert paths.detect(tmp_path, (document,)) == ()


def test_opposite_fence_marker_does_not_close_active_fence(tmp_path: Path):
    """
    [Unit] detectors paths: verifies opposite fence marker does not close active fence.

    Scenario:
        Given test inputs and fixtures for opposite fence marker does not close active fence
        When test_opposite_fence_marker_does_not_close_active_fence executes the target flow
        Then the expected outcome for opposite fence marker does not close active fence is confirmed.

    Boundaries:
        - Focus: opposite fence marker does not close active fence
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to opposite fence marker does not close active fence
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(
        tmp_path,
        "README.md",
        "```markdown\n~~~\n`src/missing.py`\n```\n",
    )

    assert paths.detect(tmp_path, (document,)) == ()


def test_non_markdown_documents_are_not_scanned(tmp_path: Path):
    """
    [Unit] detectors paths: verifies non markdown documents are not scanned.

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
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "notes.txt", "`src/missing.py`\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_finding_reports_one_based_source_line(tmp_path: Path):
    """
    [Unit] detectors paths: verifies finding reports one based source line.

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
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", "first\nsecond\n`src/missing.py`\n")

    findings = paths.detect(tmp_path, (document,))

    assert len(findings) == 1
    assert findings[0].line == 3


def test_ds101_and_ds103_report_only_their_own_shared_fixture_spans(tmp_path: Path):
    """
    [Unit] detectors paths: verifies ds101 and ds103 report only their own shared fixture spans.

    Scenario:
        Given test inputs and fixtures for ds101 and ds103 report only their own shared fixture spans
        When test_ds101_and_ds103_report_only_their_own_shared_fixture_spans executes the target flow
        Then the expected outcome for ds101 and ds103 report only their own shared fixture spans is confirmed.

    Boundaries:
        - Focus: ds101 and ds103 report only their own shared fixture spans
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to ds101 and ds103 report only their own shared fixture spans
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    links = importlib.import_module("docsentinel.detectors.links")
    document = _write_document(
        tmp_path,
        "README.md",
        "[dangling](missing.md)\nBare `src/missing.py`.\n",
    )

    link_findings = links.detect(tmp_path, (document,))
    path_findings = paths.detect(tmp_path, (document,))

    assert tuple(finding.rule for finding in link_findings) == ("DS101",)
    assert tuple(finding.rule for finding in path_findings) == ("DS103",)
    assert link_findings[0].line == 1
    assert path_findings[0].line == 2


def test_findings_preserve_supplied_document_and_regex_match_order(tmp_path: Path):
    """
    [Unit] detectors paths: verifies findings preserve supplied document and regex match order.

    Scenario:
        Given test inputs and fixtures for findings preserve supplied document and regex match order
        When test_findings_preserve_supplied_document_and_regex_match_order executes the target flow
        Then the expected outcome for findings preserve supplied document and regex match order is confirmed.

    Boundaries:
        - Focus: findings preserve supplied document and regex match order
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to findings preserve supplied document and regex match order
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    second_document = _write_document(tmp_path, "z.md", "`z-one.md` then `z-two.md`\n")
    first_document = _write_document(tmp_path, "a.md", "`a-one.md` then `a-two.md`\n")

    assert paths.detect(tmp_path, (second_document, first_document)) == (
        models.Finding("DS103", "z.md", "unresolvable path -> z-one.md", "warning", 1),
        models.Finding("DS103", "z.md", "unresolvable path -> z-two.md", "warning", 1),
        models.Finding("DS103", "a.md", "unresolvable path -> a-one.md", "warning", 1),
        models.Finding("DS103", "a.md", "unresolvable path -> a-two.md", "warning", 1),
    )


def test_source_lines_are_preserved_after_fence_stripping(tmp_path: Path):
    """
    [Unit] detectors paths: verifies source lines are preserved after fence stripping.

    Scenario:
        Given test inputs and fixtures for source lines are preserved after fence stripping
        When test_source_lines_are_preserved_after_fence_stripping executes the target flow
        Then the expected outcome for source lines are preserved after fence stripping is confirmed.

    Boundaries:
        - Focus: source lines are preserved after fence stripping
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to source lines are preserved after fence stripping
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(
        tmp_path,
        "README.md",
        "intro\n```text\n`ignored.py`\n```\ntext\n`src/missing.py`\n",
    )

    assert paths.detect(tmp_path, (document,)) == (
        models.Finding("DS103", "README.md", "unresolvable path -> src/missing.py", "warning", 6),
    )


def test_relative_path_resolves_from_document_directory(tmp_path: Path):
    """
    [Unit] detectors paths: verifies relative path resolves from document directory.

    Scenario:
        Given test inputs and fixtures for relative path resolves from document directory
        When test_relative_path_resolves_from_document_directory executes the target flow
        Then the expected outcome for relative path resolves from document directory is confirmed.

    Boundaries:
        - Focus: relative path resolves from document directory
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to relative path resolves from document directory
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "docs/guides/intro.md", "See `../shared.md`.\n")
    _write_document(tmp_path, "docs/shared.md", "exists\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_parent_traversal_outside_root_matches_ds101_resolution(tmp_path: Path):
    """
    [Unit] detectors paths: verifies parent traversal outside root matches ds101 resolution.

    Scenario:
        Given test inputs and fixtures for parent traversal outside root matches ds101 resolution
        When test_parent_traversal_outside_root_matches_ds101_resolution executes the target flow
        Then the expected outcome for parent traversal outside root matches ds101 resolution is confirmed.

    Boundaries:
        - Focus: parent traversal outside root matches ds101 resolution
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to parent traversal outside root matches ds101 resolution
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    root = tmp_path / "scan-root"
    document = _write_document(root, "docs/README.md", "See `../../outside.md`.\n")
    _write_document(tmp_path, "outside.md", "exists\n")

    assert paths.detect(root, (document,)) == ()


def test_missing_parent_traversal_is_flagged_without_creating_files(tmp_path: Path):
    """
    [Unit] detectors paths: verifies missing parent traversal is flagged without creating files.

    Scenario:
        Given test inputs and fixtures for missing parent traversal is flagged without creating files
        When test_missing_parent_traversal_is_flagged_without_creating_files executes the target flow
        Then the expected outcome for missing parent traversal is flagged without creating files is confirmed.

    Boundaries:
        - Focus: missing parent traversal is flagged without creating files
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to missing parent traversal is flagged without creating files
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    root = tmp_path / "scan-root"
    document = _write_document(root, "docs/README.md", "See `../../missing.py`.\n")

    assert paths.detect(root, (document,)) == (
        models.Finding("DS103", "docs/README.md", "unresolvable path -> ../../missing.py", "warning", 1),
    )


@pytest.mark.parametrize(
    "candidate",
    (r"C:\missing.py", r"\missing.py", r"\\server\share\missing.py"),
    ids=("drive-anchored", "rooted-backslash", "unc"),
)
def test_windows_anchored_path_is_flagged_without_filesystem_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    candidate: str,
):
    """
    [Unit] detectors paths: verifies windows anchored path is flagged without filesystem calls.

    Scenario:
        Given test inputs and fixtures for windows anchored path is flagged without filesystem calls
        When test_windows_anchored_path_is_flagged_without_filesystem_calls executes the target flow
        Then the expected outcome for windows anchored path is flagged without filesystem calls is confirmed.

    Boundaries:
        - Focus: windows anchored path is flagged without filesystem calls
        - Fixtures/params: tmp_path, monkeypatch, candidate (parametrized, 3 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to windows anchored path is flagged without filesystem calls
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", f"See `{candidate}`.\n")
    original_resolve = Path.resolve
    original_exists = Path.exists

    def fail_resolve(self: Path, *args: object, **kwargs: object) -> Path:
        """Fail if resolving unexpected path candidate."""
        if candidate in str(self):
            raise AssertionError(f"unexpected resolve call for {self}")
        return original_resolve(self, *args, **kwargs)

    def fail_exists(self: Path) -> bool:
        """Fail if checking existence of unexpected candidate."""
        if candidate in str(self):
            raise AssertionError(f"unexpected exists call for {self}")
        return original_exists(self)

    monkeypatch.setattr(Path, "resolve", fail_resolve)
    monkeypatch.setattr(Path, "exists", fail_exists)

    assert paths.detect(tmp_path, (document,)) == (
        models.Finding(
            "DS103",
            "README.md",
            f"unresolvable path -> {candidate}",
            "warning",
            1,
        ),
    )


def test_symlink_to_existing_target_resolves(tmp_path: Path):
    """
    [Unit] detectors paths: verifies symlink to existing target resolves.

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
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", "See `alias.md`.\n")
    target = tmp_path / "target.md"
    target.write_text("exists\n", encoding="utf-8")
    _symlink_or_skip(tmp_path / "alias.md", target)

    assert paths.detect(tmp_path, (document,)) == ()


def test_broken_symlink_is_unresolvable(tmp_path: Path):
    """
    [Unit] detectors paths: verifies broken symlink is unresolvable.

    Scenario:
        Given test inputs and fixtures for broken symlink is unresolvable
        When test_broken_symlink_is_unresolvable executes the target flow
        Then the expected outcome for broken symlink is unresolvable is confirmed.

    Boundaries:
        - Focus: broken symlink is unresolvable
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to broken symlink is unresolvable
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", "See `alias.md`.\n")
    _symlink_or_skip(tmp_path / "alias.md", tmp_path / "missing.md")

    assert paths.detect(tmp_path, (document,)) == (
        models.Finding("DS103", "README.md", "unresolvable path -> alias.md", "warning", 1),
    )


@pytest.mark.parametrize(
    "content",
    ("``\n", "`unterminated.py\n", "``\n`\n", "`line\nbreak.py`\n"),
    ids=("empty", "unterminated", "backticks-only", "newline"),
)
def test_hostile_incomplete_span_shapes_are_ignored(tmp_path: Path, content: str):
    """
    [Unit] detectors paths: verifies hostile incomplete span shapes are ignored.

    Scenario:
        Given test inputs and fixtures for hostile incomplete span shapes are ignored
        When test_hostile_incomplete_span_shapes_are_ignored executes the target flow
        Then the expected outcome for hostile incomplete span shapes are ignored is confirmed.

    Boundaries:
        - Focus: hostile incomplete span shapes are ignored
        - Fixtures/params: tmp_path, content (parametrized, 4 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to hostile incomplete span shapes are ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", content)

    assert paths.detect(tmp_path, (document,)) == ()


def test_invalid_utf8_read_error_is_propagated(tmp_path: Path):
    """
    [Unit] detectors paths: verifies invalid utf8 read error is propagated.

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
        - Recent changes in code paths exercised by detectors paths
    """
    source = tmp_path / "README.md"
    source.write_bytes(b"\xff")
    document = models.Document(path="README.md", bytes=1)

    with pytest.raises(UnicodeDecodeError):
        paths.detect(tmp_path, (document,))


def test_os_read_error_is_propagated(tmp_path: Path):
    """
    [Unit] detectors paths: verifies os read error is propagated.

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
        - Recent changes in code paths exercised by detectors paths
    """
    document = models.Document(path="missing.md", bytes=0)

    with pytest.raises(FileNotFoundError):
        paths.detect(tmp_path, (document,))


def test_many_unclosed_code_span_openers_are_handled(tmp_path: Path):
    """
    [Unit] detectors paths: verifies many unclosed code span openers are handled.

    Scenario:
        Given test inputs and fixtures for many unclosed code span openers are handled
        When test_many_unclosed_code_span_openers_are_handled executes the target flow
        Then the expected outcome for many unclosed code span openers are handled is confirmed.

    Boundaries:
        - Focus: many unclosed code span openers are handled
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to many unclosed code span openers are handled
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths
    """
    document = _write_document(tmp_path, "README.md", "`\n" * 2_000)

    assert paths.detect(tmp_path, (document,)) == ()
