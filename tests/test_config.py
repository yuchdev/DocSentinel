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
        max_grade_level=14.0,
        duplicate_similarity=0.85,
        min_information_score=0.15,
        docsig_paths=("src",),
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


def test_max_grade_level_default_is_14() -> None:
    assert Config().max_grade_level == 14.0


def test_standalone_doc_sentinel_toml_max_grade_level_setting(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_text("max_grade_level = 10.5\n", encoding="utf-8")
    assert load_config(tmp_path).max_grade_level == 10.5


def test_pyproject_tool_doc_sentinel_max_grade_level_setting(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\nmax_grade_level = 12\n",
        encoding="utf-8",
    )
    assert load_config(tmp_path).max_grade_level == 12.0


@pytest.mark.parametrize(
    "invalid_grade",
    ['"high"', "true", "false", "0", "-1", "-3.5", '["14.0"]', "{}"],
)
def test_invalid_max_grade_level_setting_raises(tmp_path: Path, invalid_grade: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        f"max_grade_level = {invalid_grade}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="max_grade_level must be a positive number"):
        load_config(tmp_path)


def test_duplicate_similarity_default_is_0_85() -> None:
    assert Config().duplicate_similarity == 0.85


def test_standalone_doc_sentinel_toml_duplicate_similarity_setting(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_text("duplicate_similarity = 0.9\n", encoding="utf-8")
    assert load_config(tmp_path).duplicate_similarity == 0.9


def test_pyproject_tool_doc_sentinel_duplicate_similarity_setting(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\nduplicate_similarity = 1\n",
        encoding="utf-8",
    )
    assert load_config(tmp_path).duplicate_similarity == 1.0


@pytest.mark.parametrize("invalid_similarity", ["1.5", "-0.1", "2.0", "-1"])
def test_duplicate_similarity_out_of_range_raises(tmp_path: Path, invalid_similarity: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        f"duplicate_similarity = {invalid_similarity}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="duplicate_similarity must be a number between 0 and 1"):
        load_config(tmp_path)


@pytest.mark.parametrize(
    "invalid_similarity",
    ['"high"', "true", "false", '["0.85"]', "{}"],
)
def test_duplicate_similarity_non_number_raises(tmp_path: Path, invalid_similarity: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        f"duplicate_similarity = {invalid_similarity}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="duplicate_similarity must be a number between 0 and 1"):
        load_config(tmp_path)


def test_min_information_score_default_is_0_15() -> None:
    assert Config().min_information_score == 0.15


def test_standalone_doc_sentinel_toml_min_information_score_setting(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_text("min_information_score = 0.25\n", encoding="utf-8")
    assert load_config(tmp_path).min_information_score == 0.25


def test_pyproject_tool_doc_sentinel_min_information_score_setting(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\nmin_information_score = 0.5\n",
        encoding="utf-8",
    )
    assert load_config(tmp_path).min_information_score == 0.5


@pytest.mark.parametrize("invalid_score", ["1.5", "-0.1", "2.0", "-1"])
def test_min_information_score_out_of_range_raises(tmp_path: Path, invalid_score: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        f"min_information_score = {invalid_score}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="min_information_score must be a number between 0 and 1"):
        load_config(tmp_path)


@pytest.mark.parametrize(
    "invalid_score",
    ['"low"', "true", "false", '["0.15"]', "{}"],
)
def test_min_information_score_non_number_raises(tmp_path: Path, invalid_score: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        f"min_information_score = {invalid_score}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="min_information_score must be a number between 0 and 1"):
        load_config(tmp_path)


def test_docsig_paths_default_is_src() -> None:
    assert Config().docsig_paths == ("src",)


def test_standalone_doc_sentinel_toml_docsig_paths_setting(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_text('docsig_paths = ["lib", "scripts"]\n', encoding="utf-8")
    assert load_config(tmp_path).docsig_paths == ("lib", "scripts")


def test_pyproject_tool_doc_sentinel_docsig_paths_setting(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.doc_sentinel]\ndocsig_paths = ["src/module.py"]\n',
        encoding="utf-8",
    )
    assert load_config(tmp_path).docsig_paths == ("src/module.py",)


@pytest.mark.parametrize(
    "invalid_paths",
    ['"src"', "123", "true", "false", "{}"],
)
def test_docsig_paths_non_list_raises(tmp_path: Path, invalid_paths: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        f"docsig_paths = {invalid_paths}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="docsig_paths must be a list of nonempty paths"):
        load_config(tmp_path)


@pytest.mark.parametrize(
    "empty_entry",
    ['[""]', '["src", ""]', '["", "src"]'],
)
def test_docsig_paths_empty_string_entry_raises(tmp_path: Path, empty_entry: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        f"docsig_paths = {empty_entry}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="docsig_paths must be a list of nonempty paths"):
        load_config(tmp_path)


@pytest.mark.parametrize(
    "non_string_entry",
    ["[123]", "[true]", "[false]", "[[]]", "[{}]"],
)
def test_docsig_paths_non_string_entry_raises(tmp_path: Path, non_string_entry: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        f"docsig_paths = {non_string_entry}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="docsig_paths must be a list of nonempty paths"):
        load_config(tmp_path)


def test_deep_confirm_default_is_false() -> None:
    assert Config().deep_confirm is False


def test_standalone_doc_sentinel_toml_deep_confirm_setting(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_text("deep_confirm = true\n", encoding="utf-8")
    assert load_config(tmp_path).deep_confirm is True


def test_pyproject_tool_doc_sentinel_deep_confirm_setting(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\ndeep_confirm = true\n",
        encoding="utf-8",
    )
    assert load_config(tmp_path).deep_confirm is True


@pytest.mark.parametrize(
    "invalid_confirm",
    ['"true"', '"yes"', "1", "0", "1.0", '["true"]', "{}"],
)
def test_deep_confirm_non_bool_raises(tmp_path: Path, invalid_confirm: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        f"deep_confirm = {invalid_confirm}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="deep_confirm must be true or false"):
        load_config(tmp_path)
