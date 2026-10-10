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
    assert rules.RULES["DS103"] is paths.DS103
    assert paths.DS103.code == "DS103"
    assert paths.DS103.profile == "fast"
    assert paths.DS103.title == "Unresolvable path-like code span"
    assert paths.DS103.description == "An inline code span looks like a file path but does not resolve."
    assert paths.DS103.severity == "warning"


def test_detector_regex_shapes_are_exact() -> None:
    links = importlib.import_module("docsentinel.detectors.links")

    assert paths._CODE_SPAN_RE.pattern == r"`([^`\n]+)`"
    assert paths._LINK_RE.pattern == links._LINK_RE.pattern == r"!?\[[^\]]*\]\(([^)]+)\)"


def test_unresolvable_relative_path_is_flagged(tmp_path: Path) -> None:
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


def test_existing_path_produces_no_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parents[1]
    document = models.Document(path="README.md", bytes=0)

    def read_fixture(path: Path) -> str:
        assert path == root / "README.md"
        return "See `src/docsentinel/cli.py`.\n"

    monkeypatch.setattr(paths, "_read_text", read_fixture)

    assert paths.detect(root, (document,)) == ()


def test_leading_slash_resolves_from_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "scan-root"
    document = _write_document(root, "README.md", "See `/docs/x.md`.\n")
    _write_document(root, "docs/x.md", "exists\n")
    other_directory = tmp_path / "other"
    other_directory.mkdir()
    monkeypatch.chdir(other_directory)

    assert paths.detect(root, (document,)) == ()


def test_cli_flag_like_span_is_excluded(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "Use `--format`.\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_version_number_like_span_is_excluded(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "Versions `1.2.3` and `v2.0`.\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_bare_extension_span_is_excluded(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "Markdown uses `.md`.\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_span_with_whitespace_is_excluded(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "This is `not a path`.\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_shell_prompt_and_variable_like_spans_are_excluded(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "Use `$HOME/.env` or `>output.txt`.\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_code_span_inside_link_label_is_not_double_reported(tmp_path: Path) -> None:
    links = importlib.import_module("docsentinel.detectors.links")
    document = _write_document(tmp_path, "README.md", "[`missing.py`](missing.py)\n")

    assert len(links.detect(tmp_path, (document,))) == 1
    assert paths.detect(tmp_path, (document,)) == ()


def test_code_span_inside_fenced_block_is_ignored(tmp_path: Path) -> None:
    document = _write_document(
        tmp_path,
        "README.md",
        "```markdown\n`src/missing.py`\n```\n~~~\n`docs/missing.md`\n~~~\n",
    )

    assert paths.detect(tmp_path, (document,)) == ()


def test_opposite_fence_marker_does_not_close_active_fence(tmp_path: Path) -> None:
    document = _write_document(
        tmp_path,
        "README.md",
        "```markdown\n~~~\n`src/missing.py`\n```\n",
    )

    assert paths.detect(tmp_path, (document,)) == ()


def test_non_markdown_documents_are_not_scanned(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "notes.txt", "`src/missing.py`\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_finding_reports_one_based_source_line(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "first\nsecond\n`src/missing.py`\n")

    findings = paths.detect(tmp_path, (document,))

    assert len(findings) == 1
    assert findings[0].line == 3


def test_ds101_and_ds103_report_only_their_own_shared_fixture_spans(tmp_path: Path) -> None:
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


def test_findings_preserve_supplied_document_and_regex_match_order(tmp_path: Path) -> None:
    second_document = _write_document(tmp_path, "z.md", "`z-one.md` then `z-two.md`\n")
    first_document = _write_document(tmp_path, "a.md", "`a-one.md` then `a-two.md`\n")

    assert paths.detect(tmp_path, (second_document, first_document)) == (
        models.Finding("DS103", "z.md", "unresolvable path -> z-one.md", "warning", 1),
        models.Finding("DS103", "z.md", "unresolvable path -> z-two.md", "warning", 1),
        models.Finding("DS103", "a.md", "unresolvable path -> a-one.md", "warning", 1),
        models.Finding("DS103", "a.md", "unresolvable path -> a-two.md", "warning", 1),
    )


def test_source_lines_are_preserved_after_fence_stripping(tmp_path: Path) -> None:
    document = _write_document(
        tmp_path,
        "README.md",
        "intro\n```text\n`ignored.py`\n```\ntext\n`src/missing.py`\n",
    )

    assert paths.detect(tmp_path, (document,)) == (
        models.Finding("DS103", "README.md", "unresolvable path -> src/missing.py", "warning", 6),
    )


def test_relative_path_resolves_from_document_directory(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "docs/guides/intro.md", "See `../shared.md`.\n")
    _write_document(tmp_path, "docs/shared.md", "exists\n")

    assert paths.detect(tmp_path, (document,)) == ()


def test_parent_traversal_outside_root_matches_ds101_resolution(tmp_path: Path) -> None:
    root = tmp_path / "scan-root"
    document = _write_document(root, "docs/README.md", "See `../../outside.md`.\n")
    _write_document(tmp_path, "outside.md", "exists\n")

    assert paths.detect(root, (document,)) == ()


def test_missing_parent_traversal_is_flagged_without_creating_files(tmp_path: Path) -> None:
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
) -> None:
    document = _write_document(tmp_path, "README.md", f"See `{candidate}`.\n")
    original_resolve = Path.resolve
    original_exists = Path.exists

    def fail_resolve(self: Path, *args: object, **kwargs: object) -> Path:
        if candidate in str(self):
            raise AssertionError(f"unexpected resolve call for {self}")
        return original_resolve(self, *args, **kwargs)

    def fail_exists(self: Path) -> bool:
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


def test_symlink_to_existing_target_resolves(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "See `alias.md`.\n")
    target = tmp_path / "target.md"
    target.write_text("exists\n", encoding="utf-8")
    _symlink_or_skip(tmp_path / "alias.md", target)

    assert paths.detect(tmp_path, (document,)) == ()


def test_broken_symlink_is_unresolvable(tmp_path: Path) -> None:
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
def test_hostile_incomplete_span_shapes_are_ignored(tmp_path: Path, content: str) -> None:
    document = _write_document(tmp_path, "README.md", content)

    assert paths.detect(tmp_path, (document,)) == ()


def test_invalid_utf8_read_error_is_propagated(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_bytes(b"\xff")
    document = models.Document(path="README.md", bytes=1)

    with pytest.raises(UnicodeDecodeError):
        paths.detect(tmp_path, (document,))


def test_os_read_error_is_propagated(tmp_path: Path) -> None:
    document = models.Document(path="missing.md", bytes=0)

    with pytest.raises(FileNotFoundError):
        paths.detect(tmp_path, (document,))


def test_many_unclosed_code_span_openers_are_handled(tmp_path: Path) -> None:
    document = _write_document(tmp_path, "README.md", "`\n" * 2_000)

    assert paths.detect(tmp_path, (document,)) == ()
