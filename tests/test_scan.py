import json
import os
from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, load_config, scan
from docsentinel.cli import main
from docsentinel.reporting import render


def test_empty_scan_is_inventory_not_detection(tmp_path: Path) -> None:
    result = scan(tmp_path)
    assert result.documents == ()
    assert result.findings == ()
    assert result.enabled_rules == ()
    assert "not implemented" in result.notice
    assert json.loads(render(result, "json"))["enabled_rules"] == []


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


def test_discovery_prunes_excluded_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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


def test_discovery_propagates_directory_listing_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    (tmp_path / "docsentinel.toml").write_text(
        '[docsentinel]\nprofile = "deep"\ninclude = ["*.markdown"]\n',
        encoding="utf-8",
    )
    result = scan(tmp_path)
    assert [doc.path for doc in result.documents] == ["b.markdown"]
    assert result.pending == ("deep detectors are not implemented in M0",)
    assert result.enabled_rules == ()


@pytest.mark.parametrize(
    "contents",
    ['[docsentinel]\nprofile = "wrong"\n', '[docsentinel]\ninclude = "not a list"\n',
     '[docsentinel]\nunknown = 1\n', "bad toml ==="],
)
def test_bad_config_fails_clearly(tmp_path: Path, contents: str) -> None:
    (tmp_path / "docsentinel.toml").write_text(contents, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_invalid_utf8_config_raises_config_error(tmp_path: Path) -> None:
    (tmp_path / "docsentinel.toml").write_bytes(b"\xff")
    with pytest.raises(ConfigError):
        load_config(tmp_path)
    with pytest.raises(ConfigError):
        scan(tmp_path)


def test_cli_init_scan_and_guard_against_overwrite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["init", str(tmp_path)]) == 0
    assert main(["init", str(tmp_path)]) == 2
    assert main(["scan", str(tmp_path), "--profile", "standard", "--format", "json"]) == 0
    output = json.loads(capsys.readouterr().out.split("Created ", 1)[1].split("\n", 1)[1])
    assert output["pending"] == ["standard detectors are not implemented in M0"]
    assert output["enabled_rules"] == []


def test_invalid_root_and_rules(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["scan", str(tmp_path / "missing")]) == 2
    assert main(["rules"]) == 0
    assert "not implemented" in capsys.readouterr().out


def test_public_config_can_select_only_nested_files(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("guide", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    assert [doc.path for doc in scan(tmp_path, config=Config(include=("docs/*.md",))).documents] == [
        "docs/guide.md"
    ]
