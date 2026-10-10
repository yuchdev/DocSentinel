import json
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, cli, load_config, scan
from docsentinel.cli import _exit_code, main
from docsentinel.engine import ANALYZERS
from docsentinel.models import Document, Finding, ScanResult
from docsentinel.reporting import render
from docsentinel.rules import RULES, Rule, register_rule


@pytest.fixture
def fake_fast_analyzer() -> Iterator[list[tuple[Path, tuple[Document, ...]]]]:
    saved_rules = RULES.copy()
    saved_analyzers = ANALYZERS.copy()
    calls: list[tuple[Path, tuple[Document, ...]]] = []
    rule = register_rule(Rule("DS199", "fast", "Fake fast rule", "Exercises selection."))

    def analyzer(root: Path, documents: tuple[Document, ...]) -> tuple[Finding, ...]:
        calls.append((root, documents))
        return ()

    ANALYZERS[rule.code] = analyzer
    yield calls
    RULES.clear()
    RULES.update(saved_rules)
    ANALYZERS.clear()
    ANALYZERS.update(saved_analyzers)


@pytest.fixture
def captured_cli_configs(monkeypatch: pytest.MonkeyPatch) -> list[Config]:
    configs: list[Config] = []

    def fake_scan(root: str, *, config: Config) -> ScanResult:
        configs.append(config)
        return ScanResult(
            profile=config.profile,
            documents=(),
            findings=(),
            enabled_rules=(),
            pending=(),
        )

    monkeypatch.setattr(cli, "scan", fake_scan)
    return configs


def test_empty_scan_is_inventory_not_detection(tmp_path: Path) -> None:
    result = scan(tmp_path, config=Config(profile="standard"))
    assert result.documents == ()
    assert result.findings == ()
    assert result.enabled_rules == ()
    assert "not implemented" in result.notice
    assert json.loads(render(result, "json"))["enabled_rules"] == []


def test_scan_runs_analyzer_for_active_profile(
    tmp_path: Path,
    fake_fast_analyzer: list[tuple[Path, tuple[Document, ...]]],
) -> None:
    scan(tmp_path, config=Config(profile="fast"))
    assert len(fake_fast_analyzer) == 1

    fake_fast_analyzer.clear()
    scan(tmp_path, config=Config(profile="standard"))
    assert fake_fast_analyzer == []


def test_scan_respects_select(
    tmp_path: Path,
    fake_fast_analyzer: list[tuple[Path, tuple[Document, ...]]],
) -> None:
    scan(tmp_path, config=Config(select=("DS1",)))
    assert len(fake_fast_analyzer) == 1

    fake_fast_analyzer.clear()
    scan(tmp_path, config=Config(select=("DS9",)))
    assert fake_fast_analyzer == []


def test_scan_respects_ignore_over_select(
    tmp_path: Path,
    fake_fast_analyzer: list[tuple[Path, tuple[Document, ...]]],
) -> None:
    scan(tmp_path, config=Config(select=("DS1",), ignore=("DS1",)))
    assert fake_fast_analyzer == []


def test_scan_notice_reflects_rules_evaluated(
    tmp_path: Path,
    fake_fast_analyzer: list[tuple[Path, tuple[Document, ...]]],
) -> None:
    result = scan(tmp_path, config=Config(profile="fast", select=("DS199",)))

    assert len(fake_fast_analyzer) == 1
    assert "evaluated" in result.notice
    assert "not implemented" not in result.notice
    assert result.enabled_rules == ("DS199",)


def test_scan_notice_distinguishes_unimplemented_profile_from_filtered_out(
    tmp_path: Path,
    fake_fast_analyzer: list[tuple[Path, tuple[Document, ...]]],
) -> None:
    unimplemented = scan(tmp_path, config=Config(profile="standard"))
    filtered = scan(tmp_path, config=Config(profile="fast", ignore=("DS1",)))

    assert fake_fast_analyzer == []
    assert unimplemented.pending == ("standard detectors are not implemented in M0",)
    assert filtered.pending == ("all fast rules were excluded by select/ignore",)
    assert "not implemented" not in filtered.notice
    assert "evaluated" not in filtered.notice


def test_discovery_is_sorted_filtered_and_does_not_follow_symlinks(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "b.md").write_text("abc", encoding="utf-8")
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "docs" / "ignore.txt").write_text("not docs", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hidden.md").write_text("hidden", encoding="utf-8")
    (tmp_path / "alias.md").symlink_to(tmp_path / "a.md")
    result = scan(tmp_path)
    assert [(doc.path, doc.bytes) for doc in result.documents] == [
        ("a.md", 1),
        ("docs/b.md", 3),
    ]


def test_discovery_prunes_excluded_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    excluded = tmp_path / ".git"
    excluded.mkdir()
    (excluded / "hidden.md").write_text("hidden", encoding="utf-8")
    original_scandir = os.scandir

    def scandir(path: str | bytes | Path):
        if Path(path) == excluded:
            raise AssertionError("excluded directory was traversed")
        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", scandir)
    assert scan(tmp_path).documents == ()


def test_discovery_propagates_directory_listing_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    unreadable = tmp_path / "unreadable"
    unreadable.mkdir()
    original_scandir = os.scandir

    def scandir(path: str | bytes | Path):
        if Path(path) == unreadable:
            raise PermissionError("cannot list directory")
        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", scandir)
    with pytest.raises(PermissionError, match="cannot list directory"):
        scan(tmp_path)


def test_config_and_pending_profile(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "b.markdown").write_text("y", encoding="utf-8")
    (tmp_path / "doc_sentinel.toml").write_text(
        'profile = "deep"\ninclude = ["*.markdown"]\n',
        encoding="utf-8",
    )
    result = scan(tmp_path)
    assert [doc.path for doc in result.documents] == ["b.markdown"]
    assert result.pending == ("deep detectors are not implemented in M0",)
    assert result.enabled_rules == ()


@pytest.mark.parametrize(
    "contents",
    [
        'profile = "wrong"\n',
        'include = "not a list"\n',
        "unknown = 1\n",
        "bad toml ===",
    ],
)
def test_bad_config_fails_clearly(tmp_path: Path, contents: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(contents, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_invalid_utf8_config_raises_config_error(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_bytes(b"\xff")
    with pytest.raises(ConfigError):
        load_config(tmp_path)
    with pytest.raises(ConfigError):
        scan(tmp_path)


def test_init_creates_doc_sentinel_toml(tmp_path: Path) -> None:
    assert main(["init", str(tmp_path)]) == 0

    target = tmp_path / "doc_sentinel.toml"
    assert target.is_file()
    initial_content = target.read_text(encoding="utf-8")
    assert load_config(tmp_path) == Config()

    assert main(["init", str(tmp_path)]) == 2
    assert target.read_text(encoding="utf-8") == initial_content


def test_cli_select_flag_parses_comma_separated(
    tmp_path: Path,
    captured_cli_configs: list[Config],
) -> None:
    assert main(["scan", str(tmp_path), "--select", "DS1, DS2"]) == 0

    assert captured_cli_configs == [Config(select=("DS1", "DS2"))]


def test_cli_ignore_flag_works_without_config(
    tmp_path: Path,
    captured_cli_configs: list[Config],
) -> None:
    assert main(["scan", str(tmp_path), "--ignore", "DS3"]) == 0

    assert captured_cli_configs == [Config(ignore=("DS3",))]


def test_cli_ignore_flag_overrides_config_file(
    tmp_path: Path,
    captured_cli_configs: list[Config],
) -> None:
    (tmp_path / "doc_sentinel.toml").write_text('ignore = ["DS101"]\n', encoding="utf-8")

    assert main(["scan", str(tmp_path), "--ignore", "DS2"]) == 0

    assert captured_cli_configs == [Config(ignore=("DS2",))]


@pytest.mark.parametrize(
    ("arguments", "expected_profile", "expected_select", "expected_ignore"),
    [
        (("--profile", "standard"), "standard", ("DS10",), ("DS90",)),
        (("--select", "DS2, DS3"), "deep", ("DS2", "DS3"), ("DS90",)),
    ],
    ids=("profile", "select"),
)
def test_cli_explicit_override_preserves_other_loaded_settings(
    tmp_path: Path,
    captured_cli_configs: list[Config],
    arguments: tuple[str, ...],
    expected_profile: str,
    expected_select: tuple[str, ...],
    expected_ignore: tuple[str, ...],
) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        'profile = "deep"\ninclude = ["*.markdown"]\nexclude = ["build"]\nselect = ["DS10"]\nignore = ["DS90"]\n',
        encoding="utf-8",
    )

    assert main(["scan", str(tmp_path), *arguments]) == 0

    assert captured_cli_configs == [
        Config(
            include=("*.markdown",),
            exclude=("build",),
            profile=expected_profile,
            select=expected_select,
            ignore=expected_ignore,
        )
    ]


def test_rules_command_lists_real_registry(capsys: pytest.CaptureFixture[str]) -> None:
    expected_codes = ("DS101", "DS102", "DS103")
    assert tuple(sorted(RULES)) == expected_codes
    assert main(["rules"]) == 0

    output = capsys.readouterr().out
    profiles = ("fast", "standard", "deep")
    positions = tuple(output.index(profile) for profile in profiles)
    assert positions == tuple(sorted(positions))
    assert output.count("(none registered)") == 2
    for index, start in enumerate(positions):
        end = positions[index + 1] if index + 1 < len(positions) else len(output)
        profile_output = output[start:end]
        if profiles[index] == "fast":
            assert all(code in profile_output for code in expected_codes)
            assert "(none registered)" not in profile_output
        else:
            assert "(none registered)" in profile_output
    assert tuple(sorted(RULES)) == expected_codes


def test_doctor_command_reports_counts(capsys: pytest.CaptureFixture[str]) -> None:
    expected_codes = ("DS101", "DS102", "DS103")
    assert tuple(sorted(RULES)) == expected_codes
    assert main(["doctor"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "Inventory: available",
        "fast rules: 3 registered",
        "standard rules: 0 registered",
        "deep rules: 0 registered",
    ]
    assert tuple(sorted(RULES)) == expected_codes


def test_cli_scan_returns_one_and_renders_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_scan(root: str, *, config: Config) -> ScanResult:
        return ScanResult(
            profile=config.profile,
            documents=(),
            findings=(Finding(rule="DS101", path="README.md", message="Broken link", severity="error"),),
            enabled_rules=("DS101",),
            pending=(),
            notice="1 rule evaluated.",
        )

    monkeypatch.setattr(cli, "scan", fake_scan)

    assert main(["scan", str(tmp_path)]) == 1
    assert "error: README.md: Broken link" in capsys.readouterr().out.splitlines()


def test_invalid_root(tmp_path: Path) -> None:
    assert main(["scan", str(tmp_path / "missing")]) == 2


def test_public_config_can_select_only_nested_files(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("guide", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    assert [doc.path for doc in scan(tmp_path, config=Config(include=("docs/*.md",))).documents] == ["docs/guide.md"]


def test_scan_accepts_a_single_selected_file(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "b.md").write_text("bb", encoding="utf-8")
    result = scan(tmp_path / "b.md")
    assert [(item.path, item.bytes) for item in result.documents] == [("b.md", 2)]


def test_cli_scan_selected_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    assert main(["scan", str(tmp_path / "a.md"), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["documents"][0]["path"] == "a.md"


def test_exit_code_zero_for_warnings_only_by_default() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(
            Finding(rule="DS102", path="README.md", message="Stray comment", severity="warning"),
            Finding(rule="DS103", path="docs.md", message="Unresolvable path", severity="warning"),
        ),
        enabled_rules=("DS102", "DS103"),
        pending=(),
    )
    assert _exit_code(result, strict=False) == 0


def test_exit_code_one_for_any_error_by_default() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(
            Finding(rule="DS102", path="README.md", message="Stray comment", severity="warning"),
            Finding(rule="DS101", path="links.md", message="Dangling link", severity="error"),
            Finding(rule="DS103", path="docs.md", message="Unresolvable path", severity="warning"),
        ),
        enabled_rules=("DS101", "DS102", "DS103"),
        pending=(),
    )
    assert _exit_code(result, strict=False) == 1


def test_exit_code_strict_fails_on_warnings_too() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(Finding(rule="DS102", path="README.md", message="Stray comment", severity="warning"),),
        enabled_rules=("DS102",),
        pending=(),
    )
    assert _exit_code(result, strict=True) == 1


def test_exit_code_zero_when_no_findings_regardless_of_strict() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(),
        enabled_rules=("DS101", "DS102", "DS103"),
        pending=(),
    )
    assert _exit_code(result, strict=False) == 0
    assert _exit_code(result, strict=True) == 0


def test_cli_strict_flag_wired_end_to_end(tmp_path: Path) -> None:
    (tmp_path / "comment.md").write_text("<!-- stray -->\n", encoding="utf-8")

    assert main(["scan", str(tmp_path)]) == 0
    assert main(["scan", str(tmp_path), "--strict"]) == 1


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")


def test_scan_selected_symlink_raises_value_error(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("content\n", encoding="utf-8")
    link = tmp_path / "link.md"
    _symlink_or_skip(link, target)

    with pytest.raises(ValueError, match=f"^Symlinked files are not inventoried: {re.escape(str(link))}$"):
        scan(link)


def test_scan_exclude_exact_relative_root_file(tmp_path: Path) -> None:
    (tmp_path / "skip.md").write_text("skip\n", encoding="utf-8")
    (tmp_path / "keep.md").write_text("keep\n", encoding="utf-8")
    result = scan(tmp_path, config=Config(exclude=("skip.md",)))
    assert [doc.path for doc in result.documents] == ["keep.md"]


def test_scan_exclude_parent_path_pattern_nested_document(tmp_path: Path) -> None:
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    (sub_dir / "doc.md").write_text("nested doc\n", encoding="utf-8")
    (sub_dir / "preserve.md").write_text("nested preserve\n", encoding="utf-8")
    (tmp_path / "root.md").write_text("root\n", encoding="utf-8")

    result = scan(tmp_path, config=Config(exclude=("sub/doc.md",)))
    assert [doc.path for doc in result.documents] == ["root.md", "sub/preserve.md"]
