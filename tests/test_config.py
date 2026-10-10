from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, load_config


def test_defaults_are_include_all_select_all_exclude_ignore_nothing() -> None:
    assert Config() == Config(
        include=("*.md", "**/*.md"),
        exclude=(".git", ".venv", "node_modules"),
        profile="fast",
        select=(),
        ignore=(),
        baseline=None,
    )


def test_standalone_doc_sentinel_toml_top_level_keys(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_text('select = ["DS1"]\n', encoding="utf-8")

    assert load_config(tmp_path).select == ("DS1",)


def test_pyproject_tool_doc_sentinel_table(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.doc_sentinel]\nignore = ["DS101"]\n',
        encoding="utf-8",
    )

    assert load_config(tmp_path).ignore == ("DS101",)


def test_standalone_file_wins_over_pyproject(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_text('profile = "deep"\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.doc_sentinel]\nprofile = "standard"\n',
        encoding="utf-8",
    )

    assert load_config(tmp_path).profile == "deep"


def test_pyproject_without_tool_doc_sentinel_table_is_defaults(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\n',
        encoding="utf-8",
    )

    assert load_config(tmp_path) == Config()


@pytest.mark.parametrize(
    "selector",
    ['"not-a-code"', '""', '"XX1"', "1"],
)
def test_malformed_select_entry_raises(tmp_path: Path, selector: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        f"select = [{selector}]\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_select_entry_for_unregistered_rule_still_loads(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_text('select = ["DS999"]\n', encoding="utf-8")

    assert load_config(tmp_path).select == ("DS999",)


def test_explicit_config_path_pyproject_vs_standalone(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.doc_sentinel]\nprofile = "standard"\n',
        encoding="utf-8",
    )
    standalone = tmp_path / "custom.toml"
    standalone.write_text('profile = "deep"\n', encoding="utf-8")

    assert load_config(tmp_path, pyproject).profile == "standard"
    assert load_config(tmp_path, standalone).profile == "deep"


def test_pyproject_doc_sentinel_value_must_be_table(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool]\ndoc_sentinel = "invalid"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_pyproject_doc_sentinel_table_rejects_unknown_options(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\nunknown = true\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Unknown config options: unknown"):
        load_config(tmp_path)


def test_standalone_doc_sentinel_toml_baseline_setting(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_text('baseline = ".docsentinel-baseline.json"\n', encoding="utf-8")
    assert load_config(tmp_path).baseline == ".docsentinel-baseline.json"


def test_pyproject_tool_doc_sentinel_baseline_setting(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.doc_sentinel]\nbaseline = "custom-baseline.json"\n',
        encoding="utf-8",
    )
    assert load_config(tmp_path).baseline == "custom-baseline.json"


@pytest.mark.parametrize(
    "invalid_baseline",
    ['""', "123", "true", '["item"]', "{}"],
)
def test_invalid_baseline_setting_raises(tmp_path: Path, invalid_baseline: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        f"baseline = {invalid_baseline}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="baseline must be a nonempty string"):
        load_config(tmp_path)
