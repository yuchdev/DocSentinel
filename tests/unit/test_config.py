from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, load_config


def test_defaults_are_include_all_select_all_exclude_ignore_nothing() :
    """
    [Unit] config: verifies defaults are include all select all exclude ignore nothing.

    Scenario:
        Given test inputs and fixtures for defaults are include all select all exclude ignore nothing
        When test_defaults_are_include_all_select_all_exclude_ignore_nothing executes the target flow
        Then the expected outcome for defaults are include all select all exclude ignore nothing is confirmed.

    Boundaries:
        - Focus: defaults are include all select all exclude ignore nothing
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to defaults are include all select all exclude ignore nothing
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
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


def test_standalone_doc_sentinel_toml_top_level_keys(tmp_path: Path) :
    """
    [Unit] config: verifies standalone doc sentinel toml top level keys.

    Scenario:
        Given test inputs and fixtures for standalone doc sentinel toml top level keys
        When test_standalone_doc_sentinel_toml_top_level_keys executes the target flow
        Then the expected outcome for standalone doc sentinel toml top level keys is confirmed.

    Boundaries:
        - Focus: standalone doc sentinel toml top level keys
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to standalone doc sentinel toml top level keys
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text('select = ["DS1"]\n', encoding="utf-8")

    assert load_config(tmp_path).select == ("DS1",)


def test_pyproject_tool_doc_sentinel_table(tmp_path: Path) :
    """
    [Unit] config: verifies pyproject tool doc sentinel table.

    Scenario:
        Given test inputs and fixtures for pyproject tool doc sentinel table
        When test_pyproject_tool_doc_sentinel_table executes the target flow
        Then the expected outcome for pyproject tool doc sentinel table is confirmed.

    Boundaries:
        - Focus: pyproject tool doc sentinel table
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to pyproject tool doc sentinel table
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "pyproject.toml").write_text(
        '[tool.doc_sentinel]\nignore = ["DS101"]\n',
        encoding="utf-8",
    )

    assert load_config(tmp_path).ignore == ("DS101",)


def test_standalone_file_wins_over_pyproject(tmp_path: Path) :
    """
    [Unit] config: verifies standalone file wins over pyproject.

    Scenario:
        Given test inputs and fixtures for standalone file wins over pyproject
        When test_standalone_file_wins_over_pyproject executes the target flow
        Then the expected outcome for standalone file wins over pyproject is confirmed.

    Boundaries:
        - Focus: standalone file wins over pyproject
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to standalone file wins over pyproject
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text('profile = "deep"\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.doc_sentinel]\nprofile = "standard"\n',
        encoding="utf-8",
    )

    assert load_config(tmp_path).profile == "deep"


def test_pyproject_without_tool_doc_sentinel_table_is_defaults(tmp_path: Path) :
    """
    [Unit] config: verifies pyproject without tool doc sentinel table is defaults.

    Scenario:
        Given test inputs and fixtures for pyproject without tool doc sentinel table is defaults
        When test_pyproject_without_tool_doc_sentinel_table_is_defaults executes the target flow
        Then the expected outcome for pyproject without tool doc sentinel table is defaults is confirmed.

    Boundaries:
        - Focus: pyproject without tool doc sentinel table is defaults
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to pyproject without tool doc sentinel table is defaults
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\n',
        encoding="utf-8",
    )

    assert load_config(tmp_path) == Config()


@pytest.mark.parametrize(
    "selector",
    ['"not-a-code"', '""', '"XX1"', "1"],
)
def test_malformed_select_entry_raises(tmp_path: Path, selector: str) :
    """
    [Unit] config: verifies malformed select entry raises.

    Scenario:
        Given test inputs and fixtures for malformed select entry raises
        When test_malformed_select_entry_raises executes the target flow
        Then the expected outcome for malformed select entry raises is confirmed.

    Boundaries:
        - Focus: malformed select entry raises
        - Fixtures/params: tmp_path, selector (parametrized, 4 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to malformed select entry raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text(
        f"select = [{selector}]\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_select_entry_for_unregistered_rule_still_loads(tmp_path: Path) :
    """
    [Unit] config: verifies select entry for unregistered rule still loads.

    Scenario:
        Given test inputs and fixtures for select entry for unregistered rule still loads
        When test_select_entry_for_unregistered_rule_still_loads executes the target flow
        Then the expected outcome for select entry for unregistered rule still loads is confirmed.

    Boundaries:
        - Focus: select entry for unregistered rule still loads
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to select entry for unregistered rule still loads
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text('select = ["DS999"]\n', encoding="utf-8")

    assert load_config(tmp_path).select == ("DS999",)


def test_explicit_config_path_pyproject_vs_standalone(tmp_path: Path) :
    """
    [Unit] config: verifies explicit config path pyproject vs standalone.

    Scenario:
        Given test inputs and fixtures for explicit config path pyproject vs standalone
        When test_explicit_config_path_pyproject_vs_standalone executes the target flow
        Then the expected outcome for explicit config path pyproject vs standalone is confirmed.

    Boundaries:
        - Focus: explicit config path pyproject vs standalone
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to explicit config path pyproject vs standalone
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.doc_sentinel]\nprofile = "standard"\n',
        encoding="utf-8",
    )
    standalone = tmp_path / "custom.toml"
    standalone.write_text('profile = "deep"\n', encoding="utf-8")

    assert load_config(tmp_path, pyproject).profile == "standard"
    assert load_config(tmp_path, standalone).profile == "deep"


def test_pyproject_doc_sentinel_value_must_be_table(tmp_path: Path) :
    """
    [Unit] config: verifies pyproject doc sentinel value must be table.

    Scenario:
        Given test inputs and fixtures for pyproject doc sentinel value must be table
        When test_pyproject_doc_sentinel_value_must_be_table executes the target flow
        Then the expected outcome for pyproject doc sentinel value must be table is confirmed.

    Boundaries:
        - Focus: pyproject doc sentinel value must be table
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to pyproject doc sentinel value must be table
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "pyproject.toml").write_text(
        '[tool]\ndoc_sentinel = "invalid"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_pyproject_doc_sentinel_table_rejects_unknown_options(tmp_path: Path) :
    """
    [Unit] config: verifies pyproject doc sentinel table rejects unknown options.

    Scenario:
        Given test inputs and fixtures for pyproject doc sentinel table rejects unknown options
        When test_pyproject_doc_sentinel_table_rejects_unknown_options executes the target flow
        Then the expected outcome for pyproject doc sentinel table rejects unknown options is confirmed.

    Boundaries:
        - Focus: pyproject doc sentinel table rejects unknown options
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to pyproject doc sentinel table rejects unknown options
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\nunknown = true\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Unknown config options: unknown"):
        load_config(tmp_path)


def test_standalone_doc_sentinel_toml_baseline_setting(tmp_path: Path) :
    """
    [Unit] config: verifies standalone doc sentinel toml baseline setting.

    Scenario:
        Given test inputs and fixtures for standalone doc sentinel toml baseline setting
        When test_standalone_doc_sentinel_toml_baseline_setting executes the target flow
        Then the expected outcome for standalone doc sentinel toml baseline setting is confirmed.

    Boundaries:
        - Focus: standalone doc sentinel toml baseline setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to standalone doc sentinel toml baseline setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text('baseline = ".docsentinel-baseline.json"\n', encoding="utf-8")
    assert load_config(tmp_path).baseline == ".docsentinel-baseline.json"


def test_pyproject_tool_doc_sentinel_baseline_setting(tmp_path: Path) :
    """
    [Unit] config: verifies pyproject tool doc sentinel baseline setting.

    Scenario:
        Given test inputs and fixtures for pyproject tool doc sentinel baseline setting
        When test_pyproject_tool_doc_sentinel_baseline_setting executes the target flow
        Then the expected outcome for pyproject tool doc sentinel baseline setting is confirmed.

    Boundaries:
        - Focus: pyproject tool doc sentinel baseline setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to pyproject tool doc sentinel baseline setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "pyproject.toml").write_text(
        '[tool.doc_sentinel]\nbaseline = "custom-baseline.json"\n',
        encoding="utf-8",
    )
    assert load_config(tmp_path).baseline == "custom-baseline.json"


@pytest.mark.parametrize(
    "invalid_baseline",
    ['""', "123", "true", '["item"]', "{}"],
)
def test_invalid_baseline_setting_raises(tmp_path: Path, invalid_baseline: str) :
    """
    [Unit] config: verifies invalid baseline setting raises.

    Scenario:
        Given test inputs and fixtures for invalid baseline setting raises
        When test_invalid_baseline_setting_raises executes the target flow
        Then the expected outcome for invalid baseline setting raises is confirmed.

    Boundaries:
        - Focus: invalid baseline setting raises
        - Fixtures/params: tmp_path, invalid_baseline (parametrized, 5 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to invalid baseline setting raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text(
        f"baseline = {invalid_baseline}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="baseline must be a nonempty string"):
        load_config(tmp_path)


def test_max_grade_level_default_is_14() :
    """
    [Unit] config: verifies max grade level default is 14.

    Scenario:
        Given test inputs and fixtures for max grade level default is 14
        When test_max_grade_level_default_is_14 executes the target flow
        Then the expected outcome for max grade level default is 14 is confirmed.

    Boundaries:
        - Focus: max grade level default is 14
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to max grade level default is 14
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    assert Config().max_grade_level == 14.0


def test_standalone_doc_sentinel_toml_max_grade_level_setting(tmp_path: Path) :
    """
    [Unit] config: verifies standalone doc sentinel toml max grade level setting.

    Scenario:
        Given test inputs and fixtures for standalone doc sentinel toml max grade level setting
        When test_standalone_doc_sentinel_toml_max_grade_level_setting executes the target flow
        Then the expected outcome for standalone doc sentinel toml max grade level setting is confirmed.

    Boundaries:
        - Focus: standalone doc sentinel toml max grade level setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to standalone doc sentinel toml max grade level setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text("max_grade_level = 10.5\n", encoding="utf-8")
    assert load_config(tmp_path).max_grade_level == 10.5


def test_pyproject_tool_doc_sentinel_max_grade_level_setting(tmp_path: Path) :
    """
    [Unit] config: verifies pyproject tool doc sentinel max grade level setting.

    Scenario:
        Given test inputs and fixtures for pyproject tool doc sentinel max grade level setting
        When test_pyproject_tool_doc_sentinel_max_grade_level_setting executes the target flow
        Then the expected outcome for pyproject tool doc sentinel max grade level setting is confirmed.

    Boundaries:
        - Focus: pyproject tool doc sentinel max grade level setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to pyproject tool doc sentinel max grade level setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\nmax_grade_level = 12\n",
        encoding="utf-8",
    )
    assert load_config(tmp_path).max_grade_level == 12.0


@pytest.mark.parametrize(
    "invalid_grade",
    ['"high"', "true", "false", "0", "-1", "-3.5", '["14.0"]', "{}"],
)
def test_invalid_max_grade_level_setting_raises(tmp_path: Path, invalid_grade: str) :
    """
    [Unit] config: verifies invalid max grade level setting raises.

    Scenario:
        Given test inputs and fixtures for invalid max grade level setting raises
        When test_invalid_max_grade_level_setting_raises executes the target flow
        Then the expected outcome for invalid max grade level setting raises is confirmed.

    Boundaries:
        - Focus: invalid max grade level setting raises
        - Fixtures/params: tmp_path, invalid_grade (parametrized, 8 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to invalid max grade level setting raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text(
        f"max_grade_level = {invalid_grade}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="max_grade_level must be a positive number"):
        load_config(tmp_path)


def test_duplicate_similarity_default_is_0_85() :
    """
    [Unit] config: verifies duplicate similarity default is 0 85.

    Scenario:
        Given test inputs and fixtures for duplicate similarity default is 0 85
        When test_duplicate_similarity_default_is_0_85 executes the target flow
        Then the expected outcome for duplicate similarity default is 0 85 is confirmed.

    Boundaries:
        - Focus: duplicate similarity default is 0 85
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to duplicate similarity default is 0 85
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    assert Config().duplicate_similarity == 0.85


def test_standalone_doc_sentinel_toml_duplicate_similarity_setting(tmp_path: Path) :
    """
    [Unit] config: verifies standalone doc sentinel toml duplicate similarity setting.

    Scenario:
        Given test inputs and fixtures for standalone doc sentinel toml duplicate similarity setting
        When test_standalone_doc_sentinel_toml_duplicate_similarity_setting executes the target flow
        Then the expected outcome for standalone doc sentinel toml duplicate similarity setting is confirmed.

    Boundaries:
        - Focus: standalone doc sentinel toml duplicate similarity setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to standalone doc sentinel toml duplicate similarity setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text("duplicate_similarity = 0.9\n", encoding="utf-8")
    assert load_config(tmp_path).duplicate_similarity == 0.9


def test_pyproject_tool_doc_sentinel_duplicate_similarity_setting(tmp_path: Path) :
    """
    [Unit] config: verifies pyproject tool doc sentinel duplicate similarity setting.

    Scenario:
        Given test inputs and fixtures for pyproject tool doc sentinel duplicate similarity setting
        When test_pyproject_tool_doc_sentinel_duplicate_similarity_setting executes the target flow
        Then the expected outcome for pyproject tool doc sentinel duplicate similarity setting is confirmed.

    Boundaries:
        - Focus: pyproject tool doc sentinel duplicate similarity setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to pyproject tool doc sentinel duplicate similarity setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\nduplicate_similarity = 1\n",
        encoding="utf-8",
    )
    assert load_config(tmp_path).duplicate_similarity == 1.0


@pytest.mark.parametrize("invalid_similarity", ["1.5", "-0.1", "2.0", "-1"])
def test_duplicate_similarity_out_of_range_raises(tmp_path: Path, invalid_similarity: str) :
    """
    [Unit] config: verifies duplicate similarity out of range raises.

    Scenario:
        Given test inputs and fixtures for duplicate similarity out of range raises
        When test_duplicate_similarity_out_of_range_raises executes the target flow
        Then the expected outcome for duplicate similarity out of range raises is confirmed.

    Boundaries:
        - Focus: duplicate similarity out of range raises
        - Fixtures/params: tmp_path, invalid_similarity (parametrized, 4 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to duplicate similarity out of range raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
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
def test_duplicate_similarity_non_number_raises(tmp_path: Path, invalid_similarity: str) :
    """
    [Unit] config: verifies duplicate similarity non number raises.

    Scenario:
        Given test inputs and fixtures for duplicate similarity non number raises
        When test_duplicate_similarity_non_number_raises executes the target flow
        Then the expected outcome for duplicate similarity non number raises is confirmed.

    Boundaries:
        - Focus: duplicate similarity non number raises
        - Fixtures/params: tmp_path, invalid_similarity (parametrized, 5 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to duplicate similarity non number raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text(
        f"duplicate_similarity = {invalid_similarity}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="duplicate_similarity must be a number between 0 and 1"):
        load_config(tmp_path)


def test_min_information_score_default_is_0_15() :
    """
    [Unit] config: verifies min information score default is 0 15.

    Scenario:
        Given test inputs and fixtures for min information score default is 0 15
        When test_min_information_score_default_is_0_15 executes the target flow
        Then the expected outcome for min information score default is 0 15 is confirmed.

    Boundaries:
        - Focus: min information score default is 0 15
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to min information score default is 0 15
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    assert Config().min_information_score == 0.15


def test_standalone_doc_sentinel_toml_min_information_score_setting(tmp_path: Path) :
    """
    [Unit] config: verifies standalone doc sentinel toml min information score setting.

    Scenario:
        Given test inputs and fixtures for standalone doc sentinel toml min information score setting
        When test_standalone_doc_sentinel_toml_min_information_score_setting executes the target flow
        Then the expected outcome for standalone doc sentinel toml min information score setting is confirmed.

    Boundaries:
        - Focus: standalone doc sentinel toml min information score setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to standalone doc sentinel toml min information score setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text("min_information_score = 0.25\n", encoding="utf-8")
    assert load_config(tmp_path).min_information_score == 0.25


def test_pyproject_tool_doc_sentinel_min_information_score_setting(tmp_path: Path) :
    """
    [Unit] config: verifies pyproject tool doc sentinel min information score setting.

    Scenario:
        Given test inputs and fixtures for pyproject tool doc sentinel min information score setting
        When test_pyproject_tool_doc_sentinel_min_information_score_setting executes the target flow
        Then the expected outcome for pyproject tool doc sentinel min information score setting is confirmed.

    Boundaries:
        - Focus: pyproject tool doc sentinel min information score setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to pyproject tool doc sentinel min information score setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\nmin_information_score = 0.5\n",
        encoding="utf-8",
    )
    assert load_config(tmp_path).min_information_score == 0.5


@pytest.mark.parametrize("invalid_score", ["1.5", "-0.1", "2.0", "-1"])
def test_min_information_score_out_of_range_raises(tmp_path: Path, invalid_score: str) :
    """
    [Unit] config: verifies min information score out of range raises.

    Scenario:
        Given test inputs and fixtures for min information score out of range raises
        When test_min_information_score_out_of_range_raises executes the target flow
        Then the expected outcome for min information score out of range raises is confirmed.

    Boundaries:
        - Focus: min information score out of range raises
        - Fixtures/params: tmp_path, invalid_score (parametrized, 4 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to min information score out of range raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
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
def test_min_information_score_non_number_raises(tmp_path: Path, invalid_score: str) :
    """
    [Unit] config: verifies min information score non number raises.

    Scenario:
        Given test inputs and fixtures for min information score non number raises
        When test_min_information_score_non_number_raises executes the target flow
        Then the expected outcome for min information score non number raises is confirmed.

    Boundaries:
        - Focus: min information score non number raises
        - Fixtures/params: tmp_path, invalid_score (parametrized, 5 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to min information score non number raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text(
        f"min_information_score = {invalid_score}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="min_information_score must be a number between 0 and 1"):
        load_config(tmp_path)


def test_docsig_paths_default_is_src() :
    """
    [Unit] config: verifies docsig paths default is src.

    Scenario:
        Given test inputs and fixtures for docsig paths default is src
        When test_docsig_paths_default_is_src executes the target flow
        Then the expected outcome for docsig paths default is src is confirmed.

    Boundaries:
        - Focus: docsig paths default is src
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to docsig paths default is src
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    assert Config().docsig_paths == ("src",)


def test_standalone_doc_sentinel_toml_docsig_paths_setting(tmp_path: Path) :
    """
    [Unit] config: verifies standalone doc sentinel toml docsig paths setting.

    Scenario:
        Given test inputs and fixtures for standalone doc sentinel toml docsig paths setting
        When test_standalone_doc_sentinel_toml_docsig_paths_setting executes the target flow
        Then the expected outcome for standalone doc sentinel toml docsig paths setting is confirmed.

    Boundaries:
        - Focus: standalone doc sentinel toml docsig paths setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to standalone doc sentinel toml docsig paths setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text('docsig_paths = ["lib", "scripts"]\n', encoding="utf-8")
    assert load_config(tmp_path).docsig_paths == ("lib", "scripts")


def test_pyproject_tool_doc_sentinel_docsig_paths_setting(tmp_path: Path) :
    """
    [Unit] config: verifies pyproject tool doc sentinel docsig paths setting.

    Scenario:
        Given test inputs and fixtures for pyproject tool doc sentinel docsig paths setting
        When test_pyproject_tool_doc_sentinel_docsig_paths_setting executes the target flow
        Then the expected outcome for pyproject tool doc sentinel docsig paths setting is confirmed.

    Boundaries:
        - Focus: pyproject tool doc sentinel docsig paths setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to pyproject tool doc sentinel docsig paths setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "pyproject.toml").write_text(
        '[tool.doc_sentinel]\ndocsig_paths = ["src/module.py"]\n',
        encoding="utf-8",
    )
    assert load_config(tmp_path).docsig_paths == ("src/module.py",)


@pytest.mark.parametrize(
    "invalid_paths",
    ['"src"', "123", "true", "false", "{}"],
)
def test_docsig_paths_non_list_raises(tmp_path: Path, invalid_paths: str) :
    """
    [Unit] config: verifies docsig paths non list raises.

    Scenario:
        Given test inputs and fixtures for docsig paths non list raises
        When test_docsig_paths_non_list_raises executes the target flow
        Then the expected outcome for docsig paths non list raises is confirmed.

    Boundaries:
        - Focus: docsig paths non list raises
        - Fixtures/params: tmp_path, invalid_paths (parametrized, 5 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to docsig paths non list raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
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
def test_docsig_paths_empty_string_entry_raises(tmp_path: Path, empty_entry: str) :
    """
    [Unit] config: verifies docsig paths empty string entry raises.

    Scenario:
        Given test inputs and fixtures for docsig paths empty string entry raises
        When test_docsig_paths_empty_string_entry_raises executes the target flow
        Then the expected outcome for docsig paths empty string entry raises is confirmed.

    Boundaries:
        - Focus: docsig paths empty string entry raises
        - Fixtures/params: tmp_path, empty_entry (parametrized, 3 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to docsig paths empty string entry raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
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
def test_docsig_paths_non_string_entry_raises(tmp_path: Path, non_string_entry: str) :
    """
    [Unit] config: verifies docsig paths non string entry raises.

    Scenario:
        Given test inputs and fixtures for docsig paths non string entry raises
        When test_docsig_paths_non_string_entry_raises executes the target flow
        Then the expected outcome for docsig paths non string entry raises is confirmed.

    Boundaries:
        - Focus: docsig paths non string entry raises
        - Fixtures/params: tmp_path, non_string_entry (parametrized, 5 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to docsig paths non string entry raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text(
        f"docsig_paths = {non_string_entry}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="docsig_paths must be a list of nonempty paths"):
        load_config(tmp_path)


def test_deep_confirm_default_is_false() :
    """
    [Unit] config: verifies deep confirm default is false.

    Scenario:
        Given test inputs and fixtures for deep confirm default is false
        When test_deep_confirm_default_is_false executes the target flow
        Then the expected outcome for deep confirm default is false is confirmed.

    Boundaries:
        - Focus: deep confirm default is false
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to deep confirm default is false
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    assert Config().deep_confirm is False


def test_standalone_doc_sentinel_toml_deep_confirm_setting(tmp_path: Path) :
    """
    [Unit] config: verifies standalone doc sentinel toml deep confirm setting.

    Scenario:
        Given test inputs and fixtures for standalone doc sentinel toml deep confirm setting
        When test_standalone_doc_sentinel_toml_deep_confirm_setting executes the target flow
        Then the expected outcome for standalone doc sentinel toml deep confirm setting is confirmed.

    Boundaries:
        - Focus: standalone doc sentinel toml deep confirm setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to standalone doc sentinel toml deep confirm setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text("deep_confirm = true\n", encoding="utf-8")
    assert load_config(tmp_path).deep_confirm is True


def test_pyproject_tool_doc_sentinel_deep_confirm_setting(tmp_path: Path) :
    """
    [Unit] config: verifies pyproject tool doc sentinel deep confirm setting.

    Scenario:
        Given test inputs and fixtures for pyproject tool doc sentinel deep confirm setting
        When test_pyproject_tool_doc_sentinel_deep_confirm_setting executes the target flow
        Then the expected outcome for pyproject tool doc sentinel deep confirm setting is confirmed.

    Boundaries:
        - Focus: pyproject tool doc sentinel deep confirm setting
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to pyproject tool doc sentinel deep confirm setting
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\ndeep_confirm = true\n",
        encoding="utf-8",
    )
    assert load_config(tmp_path).deep_confirm is True


@pytest.mark.parametrize(
    "invalid_confirm",
    ['"true"', '"yes"', "1", "0", "1.0", '["true"]', "{}"],
)
def test_deep_confirm_non_bool_raises(tmp_path: Path, invalid_confirm: str) :
    """
    [Unit] config: verifies deep confirm non bool raises.

    Scenario:
        Given test inputs and fixtures for deep confirm non bool raises
        When test_deep_confirm_non_bool_raises executes the target flow
        Then the expected outcome for deep confirm non bool raises is confirmed.

    Boundaries:
        - Focus: deep confirm non bool raises
        - Fixtures/params: tmp_path, invalid_confirm (parametrized, 7 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to deep confirm non bool raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by config
    """
    (tmp_path / "doc_sentinel.toml").write_text(
        f"deep_confirm = {invalid_confirm}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="deep_confirm must be true or false"):
        load_config(tmp_path)
