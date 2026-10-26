"""Mock tests for standalone config file-name discovery (docsentinel.toml and doc_sentinel.toml)."""

from pathlib import Path

import pytest

from docsentinel import ConfigError, load_config
from docsentinel import config as config_module

STANDALONE_NAMES = ("docsentinel.toml", "doc_sentinel.toml")


@pytest.fixture
def loader_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Path, bool]]:
    """Replace the TOML reader with a recorder returning an empty options table."""
    calls: list[tuple[Path, bool]] = []

    def fake_loader(source: Path, *, wrapped: bool) -> dict[str, object]:
        """Record the requested source and return no options."""
        calls.append((source, wrapped))
        return {}

    monkeypatch.setattr(config_module, "_load_toml_table", fake_loader)
    return calls


@pytest.mark.parametrize("name", STANDALONE_NAMES)
def test_each_standalone_name_is_read_unwrapped(tmp_path: Path, loader_calls, name: str):
    """
    [Unit] config: verifies each accepted standalone name is the one handed to the TOML reader.

    Scenario:
        Given a scan root holding exactly one of the two accepted standalone names
        When load_config discovers the configuration with the TOML reader mocked
        Then that file is read once, as a top-level (unwrapped) table.

    Boundaries:
        - Focus: file-name discovery for docsentinel.toml and doc_sentinel.toml
        - Fixtures/params: tmp_path, loader_calls, name
        - Scope: discovery only; TOML parsing is mocked

    On failure, first check:
        - STANDALONE_CONFIG_NAMES in docsentinel.config
    """
    (tmp_path / name).write_text("", encoding="utf-8")

    load_config(tmp_path)

    assert loader_calls == [(tmp_path / name, False)]


@pytest.mark.parametrize("name", STANDALONE_NAMES)
def test_each_standalone_name_beats_pyproject(tmp_path: Path, loader_calls, name: str):
    """
    [Unit] config: verifies either standalone name takes precedence over pyproject.toml.

    Scenario:
        Given pyproject.toml plus one standalone config file
        When load_config discovers the configuration with the TOML reader mocked
        Then only the standalone file is read and pyproject.toml is never opened.

    Boundaries:
        - Focus: precedence of standalone names over pyproject.toml
        - Fixtures/params: tmp_path, loader_calls, name
        - Scope: discovery only; TOML parsing is mocked

    On failure, first check:
        - Discovery order in load_config
    """
    (tmp_path / name).write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")

    load_config(tmp_path)

    assert [source.name for source, _ in loader_calls] == [name]


def test_both_standalone_names_fail_before_any_file_is_read(tmp_path: Path, loader_calls):
    """
    [Unit] config: verifies the ambiguous pair is rejected without reading either file.

    Scenario:
        Given both docsentinel.toml and doc_sentinel.toml at the scan root
        When load_config discovers the configuration with the TOML reader mocked
        Then ConfigError names both files and the reader is never called.

    Boundaries:
        - Focus: fail-closed ambiguity check
        - Fixtures/params: tmp_path, loader_calls
        - Scope: discovery only; TOML parsing is mocked

    On failure, first check:
        - The both-files check in load_config
    """
    for name in STANDALONE_NAMES:
        (tmp_path / name).write_text("", encoding="utf-8")

    with pytest.raises(ConfigError, match="docsentinel.toml and doc_sentinel.toml"):
        load_config(tmp_path)

    assert loader_calls == []


def test_no_config_file_never_invokes_the_reader(tmp_path: Path, loader_calls):
    """
    [Unit] config: verifies defaults are returned without touching the TOML reader.

    Scenario:
        Given a scan root with none of the config files
        When load_config discovers the configuration with the TOML reader mocked
        Then the reader is never called.

    Boundaries:
        - Focus: absent-config fallback
        - Fixtures/params: tmp_path, loader_calls
        - Scope: discovery only

    On failure, first check:
        - The fallback branch of load_config
    """
    load_config(tmp_path)

    assert loader_calls == []
