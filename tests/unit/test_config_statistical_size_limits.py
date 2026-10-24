"""Unit tests for the standard-profile statistical size-limit config keys.

Covers ``min_document_words`` (DS201), ``min_paragraph_words`` and
``min_paragraph_chars`` (DS202/DS203): defaults, loading from a standalone
``doc_sentinel.toml`` and a ``[tool.doc_sentinel]`` table, and strict
validation of every rejected value shape. Tiny inline TOML only; no assets.
"""

from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, load_config


def test_statistical_size_limit_defaults_match_specification():
    """
    [Unit] config: verifies statistical size-limit defaults match specification.

    Scenario:
        Given a default Config instance
        When the statistical size-limit options are read
        Then each equals the historical built-in floor.

    Boundaries:
        - Focus: default values for the three new keys
        - Fixtures/params: none
        - Scope: assertions in this test only

    On failure, first check:
        - Config field defaults
        - The milestone ruling that fixed the defaults
    """
    config = Config()
    assert config.min_document_words == 50
    assert config.min_paragraph_words == 5
    assert config.min_paragraph_chars == 30


def test_standalone_toml_loads_statistical_size_limits(tmp_path: Path):
    """
    [Unit] config: verifies standalone toml loads statistical size limits.

    Scenario:
        Given a standalone doc_sentinel.toml setting the three keys
        When load_config reads the scan root
        Then the Config carries the configured integers.

    Boundaries:
        - Focus: standalone TOML loading
        - Fixtures/params: tmp_path
        - Scope: assertions in this test only

    On failure, first check:
        - _load_extra_options validation block
        - _CONFIG_OPTIONS membership of the three keys
    """
    (tmp_path / "doc_sentinel.toml").write_text(
        "min_document_words = 10\nmin_paragraph_words = 2\nmin_paragraph_chars = 0\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.min_document_words == 10
    assert config.min_paragraph_words == 2
    assert config.min_paragraph_chars == 0


def test_pyproject_table_loads_statistical_size_limits(tmp_path: Path):
    """
    [Unit] config: verifies pyproject table loads statistical size limits.

    Scenario:
        Given a pyproject [tool.doc_sentinel] table setting the three keys
        When load_config discovers it
        Then the Config carries identical semantics to the standalone file.

    Boundaries:
        - Focus: pyproject table loading
        - Fixtures/params: tmp_path
        - Scope: assertions in this test only

    On failure, first check:
        - The wrapped-table branch of _load_toml_table
        - Parity with the standalone loader
    """
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\nmin_document_words = 100\nmin_paragraph_words = 8\nmin_paragraph_chars = 12\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.min_document_words == 100
    assert config.min_paragraph_words == 8
    assert config.min_paragraph_chars == 12


@pytest.mark.parametrize(
    ("option", "message"),
    [
        ("min_document_words", "min_document_words must be an integer >= 1"),
        ("min_paragraph_words", "min_paragraph_words must be an integer >= 1"),
    ],
)
@pytest.mark.parametrize("value", ["0", "-1", "true", "1.0", "5.5", '"5"', "[5]"])
def test_min_words_keys_reject_invalid_shapes(tmp_path: Path, option: str, message: str, value: str):
    """
    [Unit] config: verifies the ``>= 1`` integer keys reject every invalid shape.

    Scenario:
        Given a TOML file setting a min-words key to a rejected value
        When load_config reads it
        Then a ConfigError with the range message is raised.

    Boundaries:
        - Focus: strict validation (0, negative, bool, float, string, list)
        - Fixtures/params: tmp_path, option/value (parametrized)
        - Scope: assertions in this test only

    On failure, first check:
        - _require_bounded_int for the ``minimum = 1`` path
        - That booleans and integral floats are both rejected
    """
    (tmp_path / "doc_sentinel.toml").write_text(f"{option} = {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_config(tmp_path)


@pytest.mark.parametrize("value", ["-1", "true", "1.0", "5.5", '"5"', "[5]"])
def test_min_paragraph_chars_rejects_invalid_shapes(tmp_path: Path, value: str):
    """
    [Unit] config: verifies ``min_paragraph_chars`` rejects every invalid shape.

    Scenario:
        Given a TOML file setting min_paragraph_chars to a rejected value
        When load_config reads it
        Then a ConfigError about a non-negative integer is raised.

    Boundaries:
        - Focus: strict validation (negative, bool, float, string, list)
        - Fixtures/params: tmp_path, value (parametrized)
        - Scope: assertions in this test only

    On failure, first check:
        - _require_bounded_int for the ``minimum = 0`` path
        - That ``0`` is accepted (covered elsewhere) but ``-1`` is not
    """
    (tmp_path / "doc_sentinel.toml").write_text(f"min_paragraph_chars = {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="min_paragraph_chars must be a non-negative integer"):
        load_config(tmp_path)


def test_min_paragraph_chars_accepts_zero(tmp_path: Path):
    """
    [Unit] config: verifies ``min_paragraph_chars`` accepts the zero floor.

    Scenario:
        Given a TOML file setting min_paragraph_chars to 0
        When load_config reads it
        Then the Config carries 0 (the only value below the ``>= 1`` keys).

    Boundaries:
        - Focus: the inclusive lower bound of the char floor
        - Fixtures/params: tmp_path
        - Scope: assertions in this test only

    On failure, first check:
        - The ``minimum = 0`` branch of _require_bounded_int
    """
    (tmp_path / "doc_sentinel.toml").write_text("min_paragraph_chars = 0\n", encoding="utf-8")
    assert load_config(tmp_path).min_paragraph_chars == 0
