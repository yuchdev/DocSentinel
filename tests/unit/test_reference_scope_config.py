"""Unit tests for the ``reference_scope`` and ``at_reference_extensions`` options (Milestone 0009 Story 01.0)."""

from pathlib import Path

import pytest

from docsentinel.config import (
    MAX_AT_REFERENCE_EXTENSIONS,
    Config,
    ConfigError,
    load_config,
    validate_at_reference_extensions,
)

_DEFAULT_EXTENSIONS = ("md", "markdown", "mdx", "txt", "rst", "toml", "json", "yaml", "yml", "py")


def test_reference_scope_and_extension_defaults():
    """
    [Unit] config: verifies the Story 01.0 defaults of both new options.

    Scenario:
        Given a default Config and a load_config over an empty directory
        When reference_scope and at_reference_extensions are read
        Then they are "links" and the ten default extensions, in both cases.

    Boundaries:
        - Focus: Config defaults equal the story's Config reference table
        - Fixtures/params: tmp_path
        - Scope: Config and load_config only

    On failure, first check:
        - The Config field defaults
    """
    assert Config().reference_scope == "links"
    assert Config().at_reference_extensions == _DEFAULT_EXTENSIONS


def test_loaded_defaults_match_config_defaults(tmp_path: Path):
    """
    [Unit] config: verifies load_config without the keys yields the Config defaults.

    Scenario:
        Given a docsentinel.toml without either key
        When load_config reads it
        Then both options equal the dataclass defaults.

    Boundaries:
        - Focus: default propagation through load_config
        - Fixtures/params: tmp_path
        - Scope: load_config only

    On failure, first check:
        - The default lookup for the two options in _load_extra_options
    """
    (tmp_path / "docsentinel.toml").write_text('profile = "fast"\n', encoding="utf-8")

    settings = load_config(tmp_path)

    assert settings.reference_scope == "links"
    assert settings.at_reference_extensions == _DEFAULT_EXTENSIONS


@pytest.mark.parametrize("wrapped", [False, True])
def test_options_load_from_standalone_and_pyproject(tmp_path: Path, wrapped: bool):
    """
    [Unit] config: verifies both options load from docsentinel.toml and [tool.doc_sentinel].

    Scenario:
        Given reference_scope = "strict" and mixed-case extensions in either config form
        When load_config reads it
        Then the scope is "strict" and the extensions are lowercased, in configured order.

    Boundaries:
        - Focus: both config sources behave the same; extensions stored lowercased as a tuple
        - Fixtures/params: tmp_path, wrapped (standalone or pyproject)
        - Scope: load_config only

    On failure, first check:
        - The lowercasing in validate_at_reference_extensions
    """
    body = 'reference_scope = "strict"\nat_reference_extensions = ["MD", "Txt", "py"]\n'
    if wrapped:
        (tmp_path / "pyproject.toml").write_text("[tool.doc_sentinel]\n" + body, encoding="utf-8")
    else:
        (tmp_path / "docsentinel.toml").write_text(body, encoding="utf-8")

    settings = load_config(tmp_path)

    assert settings.reference_scope == "strict"
    assert settings.at_reference_extensions == ("md", "txt", "py")


@pytest.mark.parametrize("value", ['"STRICT"', '"off"', '"Links"', '""', "1", "true", '["strict"]'])
def test_invalid_reference_scope_raises(tmp_path: Path, value: str):
    """
    [Unit] config: verifies an out-of-vocabulary reference_scope is a ConfigError.

    Scenario:
        Given a TOML file with reference_scope set to a wrong-case, unknown or non-string value
        When load_config validates it
        Then ConfigError("reference_scope must be one of: links, strict") is raised.

    Boundaries:
        - Focus: enum validation, exact case
        - Fixtures/params: tmp_path, seven invalid values
        - Scope: load_config only

    On failure, first check:
        - The reference_scope entry of _ENUM_OPTIONS
    """
    (tmp_path / "docsentinel.toml").write_text(f"reference_scope = {value}\n", encoding="utf-8")

    with pytest.raises(ConfigError) as caught:
        load_config(tmp_path)
    assert str(caught.value) == "reference_scope must be one of: links, strict"


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ([], 'use ignore = ["DS124"]'),  # empty list points to the ignore hint
        ([f"e{index}" for index in range(MAX_AT_REFERENCE_EXTENSIONS + 1)], "more than 64"),
        (["md", "MD"], "repeats an earlier entry"),  # duplicate after lowercasing
        (["a" * 17], "1 to 16 ASCII letters or digits"),
        ([".md"], "1 to 16 ASCII letters or digits"),  # no dot
        (["m d"], "1 to 16 ASCII letters or digits"),  # no whitespace
        (["md\n"], "1 to 16 ASCII letters or digits"),  # no trailing newline
        (["mд"], "1 to 16 ASCII letters or digits"),  # non-ASCII letter
        (["m*"], "1 to 16 ASCII letters or digits"),  # no glob character
        ([""], "1 to 16 ASCII letters or digits"),
        ([1], "1 to 16 ASCII letters or digits"),  # not a string
        ("md", "must be a list"),  # not a list
    ],
)
def test_extensions_bounds_duplicates_and_empty(value: object, message: str):
    """
    [Unit] config: verifies the at_reference_extensions bounds, duplicate and empty-list checks (M20).

    Scenario:
        Given an empty list, 65 entries, a case-folded duplicate, and malformed entries
        When validate_at_reference_extensions checks each
        Then ConfigError is raised with the matching message and the value is never echoed.

    Boundaries:
        - Focus: threat model M20 config bounds
        - Fixtures/params: twelve invalid values
        - Scope: the validator only

    On failure, first check:
        - MAX_AT_REFERENCE_EXTENSIONS and the entry pattern in config.py
    """
    with pytest.raises(ConfigError, match=message.replace("[", r"\[").replace("]", r"\]")) as caught:
        validate_at_reference_extensions(value)
    assert "д" not in str(caught.value)


def test_extensions_accept_bounds_and_injected_tuple():
    """
    [Unit] config: verifies the accepting edges: 64 entries, 16 characters, a tuple from an injected Config.

    Scenario:
        Given exactly 64 entries, one 16-character entry, and a tuple of mixed-case entries
        When validate_at_reference_extensions checks each
        Then they are returned lowercased as tuples in configured order.

    Boundaries:
        - Focus: the upper bounds are inclusive; injected tuples are re-validated the same way
        - Fixtures/params: none
        - Scope: the validator only

    On failure, first check:
        - An off-by-one in the entry-count or length bounds
    """
    many = [f"e{index}" for index in range(MAX_AT_REFERENCE_EXTENSIONS)]

    assert validate_at_reference_extensions(many) == tuple(many)
    assert validate_at_reference_extensions(["A" * 16]) == ("a" * 16,)
    assert validate_at_reference_extensions(("YAML", "Md")) == ("yaml", "md")


def test_empty_extension_list_in_config_file_is_refused(tmp_path: Path):
    """
    [Unit] config: verifies an empty at_reference_extensions list in a config file fails closed.

    Scenario:
        Given docsentinel.toml with at_reference_extensions = []
        When load_config reads it
        Then ConfigError names ignore = ["DS124"] as the way to turn the check off.

    Boundaries:
        - Focus: load_config wiring of the validator
        - Fixtures/params: tmp_path
        - Scope: load_config only

    On failure, first check:
        - Whether _load_extra_options calls validate_at_reference_extensions
    """
    (tmp_path / "docsentinel.toml").write_text("at_reference_extensions = []\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r'ignore = \["DS124"\]'):
        load_config(tmp_path)
