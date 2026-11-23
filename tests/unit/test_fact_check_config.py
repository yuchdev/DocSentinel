"""Unit tests for the ``fact_check_*`` configuration keys and the ``--use-external-api`` surface.

Milestone 0010 Story 01.0 Task 03 (ADR 0007, plan contracts C4/C5/C10, threat model
docs/security/threat-model-0010-fact-check-gating-2026-11-23.md M1). Covers the six keys'
defaults, loading from every file kind, the exact validation messages, the absence of any
consent key, the CLI flag forwarding and the ``rules`` suffix helper. Every file is written
inline in ``tmp_path``; no asset is loaded and no network call is made.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Optional

import pytest

from docsentinel import cli
from docsentinel.config import (
    _CONFIG_OPTIONS,
    FACT_CHECK_BACKEND_NAMES,
    USER_SETTINGS_ENV,
    USER_SETTINGS_REFUSED_KEYS,
    Config,
    ConfigError,
    load_config,
)
from docsentinel.models import ScanResult
from docsentinel.rules import EXTERNAL_API_RULES, Rule

#: The six keys with their documented defaults (story config reference).
_DEFAULTS: dict[str, object] = {
    "fact_check_backend": "lenz",
    "fact_check_min_salience": 0.5,
    "fact_check_min_confidence": 0.6,
    "fact_check_max_claims_per_document": 3,
    "fact_check_max_claims_total": 25,
    "fact_check_time_budget_seconds": 300,
}

#: A non-default valid value for each key, spelled as JSON-compatible data.
_CUSTOM: dict[str, object] = {
    "fact_check_backend": "lenz",
    "fact_check_min_salience": 0.25,
    "fact_check_min_confidence": 1,
    "fact_check_max_claims_per_document": 50,
    "fact_check_max_claims_total": 500,
    "fact_check_time_budget_seconds": 3600,
}

#: A fake secret; never a real key.
_SENTINEL = "sentinel-not-a-real-key-0010"

#: A key-shaped option name (threat model FC-1); it is not a configuration option.
_KEY_SHAPED = "fact_check_lenz_api_key"


def _toml(options: dict[str, object]) -> str:
    """Return ``options`` as TOML ``key = value`` lines (JSON scalars are valid TOML here).

    :param options: Scalar options.
    :returns: The TOML text.
    """
    return "".join(f"{key} = {json.dumps(value)}\n" for key, value in options.items())


def _message(root: Path, toml_text: str) -> str:
    """Return the ``ConfigError`` message of a standalone ``docsentinel.toml`` holding ``toml_text``.

    :param root: An empty directory.
    :param toml_text: The file body.
    :returns: The error message.
    """
    (root / "docsentinel.toml").write_text(toml_text, encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        load_config(root, user_settings=False)
    return str(caught.value)


def _write_layer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, options: dict[str, object]
) -> tuple[Path, Optional[Path]]:
    """Write ``options`` as one configuration file kind and return ``(root, path)`` for load_config.

    :param tmp_path: The test's temporary directory.
    :param monkeypatch: Used to point ``DOCSENTINEL_SETTINGS`` at a user settings file.
    :param kind: ``docsentinel.toml``, ``doc_sentinel.toml``, ``pyproject``, ``json`` or ``user``.
    :param options: The options to write (keys are quoted in TOML).
    :returns: The scan root and the explicit config path (``None`` unless ``json``).
    """
    root = tmp_path / "repo"
    root.mkdir()
    toml_text = "".join(f"{json.dumps(key)} = {json.dumps(value)}\n" for key, value in options.items())
    if kind in ("docsentinel.toml", "doc_sentinel.toml"):
        (root / kind).write_text(toml_text, encoding="utf-8")
        return root, None
    if kind == "pyproject":
        (root / "pyproject.toml").write_text("[tool.doc_sentinel]\n" + toml_text, encoding="utf-8")
        return root, None
    if kind == "json":
        path = tmp_path / "config.json"
        path.write_text(json.dumps(options), encoding="utf-8")
        return root, path
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(options), encoding="utf-8")
    os.chmod(settings, 0o600)
    monkeypatch.setenv(USER_SETTINGS_ENV, str(settings))
    return root, None


def test_defaults_match_the_config_reference():
    """
    [Unit] fact-check config: the six keys default to the story's config reference.

    Scenario:
        Given a default Config
        When the six fact_check_* fields are read
        Then each equals its documented default, and the backend set is exactly {"lenz"}.

    Boundaries:
        - Focus: Config field defaults and FACT_CHECK_BACKEND_NAMES
        - Fixtures/params: none
        - Scope: pure attribute reads

    On failure, first check:
        - The Config dataclass defaults against the story config reference
    """
    config = Config()

    assert {name: getattr(config, name) for name in _DEFAULTS} == _DEFAULTS
    assert frozenset({"lenz"}) == FACT_CHECK_BACKEND_NAMES


@pytest.mark.parametrize("kind", ["docsentinel.toml", "doc_sentinel.toml", "pyproject", "json", "user"])
def test_every_file_kind_loads_the_six_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str):
    """
    [Unit] fact-check config: all six keys load from every configuration file kind.

    Scenario:
        Given the six keys at their upper bounds in a standalone TOML (either name), a
            [tool.doc_sentinel] table, an explicit JSON --config file or the user settings file
        When load_config runs
        Then the effective Config carries the configured values.

    Boundaries:
        - Focus: _CONFIG_OPTIONS registration and the shared builder
        - Fixtures/params: tmp_path, monkeypatch (DOCSENTINEL_SETTINGS), kind
        - Scope: load_config only

    On failure, first check:
        - _CONFIG_OPTIONS, _FACT_CHECK_INT_BOUNDS and _FACT_CHECK_UNIT_OPTIONS
    """
    root, path = _write_layer(tmp_path, monkeypatch, kind, _CUSTOM)

    config = load_config(root, path, user_settings=kind == "user")

    assert {name: getattr(config, name) for name in _CUSTOM} == _CUSTOM


def test_injected_config_carries_values_unchanged():
    """
    [Unit] fact-check config: an injected Config keeps the six values as given.

    Scenario:
        Given a Config built directly with non-default fact_check_* values
        When its fields are read
        Then they are unchanged (no load-time rewrite).

    Boundaries:
        - Focus: Config construction
        - Fixtures/params: none
        - Scope: pure dataclass

    On failure, first check:
        - A __post_init__ added to Config
    """
    config = Config(**_CUSTOM)

    assert {name: getattr(config, name) for name in _CUSTOM} == _CUSTOM


_PER_DOCUMENT = "fact_check_max_claims_per_document must be an integer from 1 to 50"
_TOTAL = "fact_check_max_claims_total must be an integer from 1 to 500"
_BUDGET = "fact_check_time_budget_seconds must be an integer from 1 to 3600"
_SALIENCE = "fact_check_min_salience must be a number between 0 and 1"
_CONFIDENCE = "fact_check_min_confidence must be a number between 0 and 1"


@pytest.mark.parametrize(
    ("key", "literal", "expected"),
    [
        ("fact_check_backend", '"openai"', "fact_check_backend must be one of: lenz"),
        ("fact_check_backend", '"Lenz"', "fact_check_backend must be one of: lenz"),
        ("fact_check_min_salience", "1.5", _SALIENCE),
        ("fact_check_min_salience", "-0.01", _SALIENCE),
        ("fact_check_min_salience", "nan", _SALIENCE),
        ("fact_check_min_confidence", "true", _CONFIDENCE),
        ("fact_check_min_confidence", "inf", _CONFIDENCE),
        ("fact_check_min_confidence", '"0.5"', _CONFIDENCE),
        ("fact_check_max_claims_per_document", "0", _PER_DOCUMENT),
        ("fact_check_max_claims_per_document", "51", _PER_DOCUMENT),
        ("fact_check_max_claims_per_document", "true", _PER_DOCUMENT),
        ("fact_check_max_claims_total", "0", _TOTAL),
        ("fact_check_max_claims_total", "501", _TOTAL),
        ("fact_check_time_budget_seconds", "0", _BUDGET),
        ("fact_check_time_budget_seconds", "3601", _BUDGET),
        ("fact_check_time_budget_seconds", "true", _BUDGET),
        ("fact_check_time_budget_seconds", "300.0", _BUDGET),
    ],
)
def test_invalid_value_gives_the_exact_message(tmp_path: Path, key: str, literal: str, expected: str):
    """
    [Unit] fact-check config: each invalid value raises ConfigError with the exact message.

    Scenario:
        Given a docsentinel.toml with one out-of-range, wrongly typed or non-finite value
        When load_config runs
        Then the ConfigError message is exactly the documented one.

    Boundaries:
        - Focus: _require_enum, _require_bounded_int(maximum=) and the unit-range check
        - Fixtures/params: tmp_path, key, literal (a TOML literal), expected
        - Scope: standalone TOML; parity with JSON is covered by test_config_message_parity

    On failure, first check:
        - The message wording in the story config reference
    """
    assert _message(tmp_path, f"{key} = {literal}\n") == expected


def test_cli_exits_two_for_an_invalid_value(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] fact-check CLI: an invalid fact_check_* value exits 2.

    Scenario:
        Given docsentinel.toml with fact_check_time_budget_seconds = 0
        When "docsentinel scan ROOT" runs
        Then the exit code is 2 and stderr carries the exact message.

    Boundaries:
        - Focus: ConfigError mapping in the CLI
        - Fixtures/params: tmp_path, capsys
        - Scope: cli.main over an empty directory

    On failure, first check:
        - The ConfigError handler of _run_scan
    """
    (tmp_path / "docsentinel.toml").write_text("fact_check_time_budget_seconds = 0\n", encoding="utf-8")

    assert cli.main(["scan", str(tmp_path)]) == 2
    assert _BUDGET in capsys.readouterr().err


def test_bounds_are_inclusive(tmp_path: Path):
    """
    [Unit] fact-check config: the lower bounds of every key are accepted.

    Scenario:
        Given every numeric key at its lower bound (0, 0, 1, 1, 1)
        When load_config runs
        Then the values load unchanged.

    Boundaries:
        - Focus: inclusive range checks
        - Fixtures/params: tmp_path
        - Scope: standalone TOML

    On failure, first check:
        - A strict < used where <= is required
    """
    lower = {
        "fact_check_min_salience": 0,
        "fact_check_min_confidence": 0.0,
        "fact_check_max_claims_per_document": 1,
        "fact_check_max_claims_total": 1,
        "fact_check_time_budget_seconds": 1,
    }
    (tmp_path / "docsentinel.toml").write_text(_toml(lower), encoding="utf-8")

    config = load_config(tmp_path, user_settings=False)

    assert {name: getattr(config, name) for name in lower} == lower


@pytest.mark.parametrize(
    "key",
    [
        "use_external_api",
        "use-external-api",
        "useExternalApi",
        "use_external_apis",
        "external_api",
        "fact_check_enabled",
    ],
)
@pytest.mark.parametrize("kind", ["docsentinel.toml", "pyproject", "json", "user"])
def test_consent_key_is_an_unknown_option(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, kind: str):
    """
    [Unit] fact-check config M1: no file kind can grant network consent.

    Scenario:
        Given use_external_api = true (or an FC-1 near-miss spelling) in a standalone TOML,
            a [tool.doc_sentinel] table, a JSON --config file or the user settings file
        When load_config runs
        Then it is the generic unknown-option ConfigError, and Config has no such field.

    Boundaries:
        - Focus: _require_known_options; plan contract C5
        - Fixtures/params: tmp_path, monkeypatch, key, kind
        - Scope: load_config only

    On failure, first check:
        - Whether a consent spelling was added to _CONFIG_OPTIONS or Config
    """
    root, path = _write_layer(tmp_path, monkeypatch, kind, {key: True})

    with pytest.raises(ConfigError) as caught:
        load_config(root, path, user_settings=kind == "user")

    assert str(caught.value).endswith(f"Unknown config options: {key}")
    assert key not in _CONFIG_OPTIONS
    assert "use_external_api" not in {field.name for field in dataclasses.fields(Config)}
    assert not hasattr(Config(), "use_external_api")


@pytest.mark.parametrize(
    ("kind", "body", "unknown"),
    [
        (
            "pyproject",
            '[tool.doc_sentinel]\nprofile = "fast"\n[tool.doc_sentinel.fact_check]\nuse_external_api = true\n',
            "fact_check",
        ),
        ("docsentinel.toml", "[fact_check]\nuse_external_api = true\n", "fact_check"),
        ("json", '{"fact_check": {"use_external_api": true}}', "fact_check"),
        ("pyproject", '[tool.doc_sentinel]\n"use_external_api " = true\n', "use_external_api "),
        ("docsentinel.toml", '"use_external_api " = true\n', "use_external_api "),
        ("json", '{"use_external_api ": true}', "use_external_api "),
    ],
)
def test_nested_or_padded_consent_key_is_unknown(tmp_path: Path, kind: str, body: str, unknown: str):
    """
    [Unit] fact-check config M1: a nested fact_check table or a padded key never grants consent.

    Scenario:
        Given use_external_api nested under a fact_check table, or spelled with a trailing space,
            in a [tool.doc_sentinel] table, a standalone TOML or a JSON --config file
        When load_config runs
        Then it is the generic unknown-option ConfigError naming the outer key exactly.

    Boundaries:
        - Focus: _require_known_options; FC-1 near misses
        - Fixtures/params: tmp_path, kind, body, unknown
        - Scope: load_config only

    On failure, first check:
        - Whether a nested table or stripped key name became a recognised option
    """
    path: Optional[Path] = None
    if kind == "json":
        path = tmp_path / "config.json"
        path.write_text(body, encoding="utf-8")
    else:
        (tmp_path / ("pyproject.toml" if kind == "pyproject" else kind)).write_text(body, encoding="utf-8")

    with pytest.raises(ConfigError) as caught:
        load_config(tmp_path, path, user_settings=False)

    assert str(caught.value) == f"Unknown config options: {unknown}"


def test_refused_user_settings_keys_are_unchanged():
    """
    [Unit] fact-check config: verifies Story 01.0 left USER_SETTINGS_REFUSED_KEYS exactly as before.

    Scenario:
        Given the refused user-settings key set
        When it is compared with the ten ADR 0005 keys
        Then it is equal, so no fact_check_* key was added or removed.

    Boundaries:
        - Focus: plan contract C5 (all six keys allowed at user level)
        - Fixtures/params: none
        - Scope: pure set comparison

    On failure, first check:
        - USER_SETTINGS_REFUSED_KEYS in config.py
    """
    assert (
        frozenset(
            {
                "baseline",
                "include",
                "exclude",
                "docsig_paths",
                "navigation_indexes",
                "navigation_required",
                "deprecated_references_file",
                "report_templates_dir",
                "link_root",
                "telemetry_domains",
            }
        )
        == USER_SETTINGS_REFUSED_KEYS
    )


def test_key_shaped_option_is_unknown_and_never_echoes_the_value(tmp_path: Path):
    """
    [Unit] fact-check config M1: an API key pasted into a config file is never echoed.

    Scenario:
        Given a key-shaped option set to a sentinel in docsentinel.toml and in a JSON config
        When load_config runs
        Then the unknown-option ConfigError names the key but not the sentinel.

    Boundaries:
        - Focus: _require_known_options echoes names only
        - Fixtures/params: tmp_path
        - Scope: load_config only

    On failure, first check:
        - Whether the unknown-option message started echoing values
    """
    message = _message(tmp_path, f"{_KEY_SHAPED} = {json.dumps(_SENTINEL)}\n")
    json_file = tmp_path / "config.json"
    json_file.write_text(json.dumps({_KEY_SHAPED: _SENTINEL}), encoding="utf-8")
    with pytest.raises(ConfigError) as from_json:
        load_config(tmp_path, json_file, user_settings=False)

    assert message == str(from_json.value) == f"Unknown config options: {_KEY_SHAPED}"
    assert _SENTINEL not in message


def test_no_fact_check_key_is_refused_in_user_settings():
    """
    [Unit] fact-check config: none of the six keys joins USER_SETTINGS_REFUSED_KEYS.

    Scenario:
        Given the refused user-settings key set
        When it is intersected with the six fact_check_* names
        Then the intersection is empty, and all six are known options.

    Boundaries:
        - Focus: USER_SETTINGS_REFUSED_KEYS unchanged
        - Fixtures/params: none
        - Scope: pure set comparison

    On failure, first check:
        - The story config reference column "Allowed in user settings"
    """
    assert not USER_SETTINGS_REFUSED_KEYS & set(_DEFAULTS)
    assert set(_DEFAULTS) <= _CONFIG_OPTIONS


@pytest.mark.parametrize("command", ["scan", "baseline"])
@pytest.mark.parametrize(("flag", "expected"), [((), False), (("--use-external-api",), True)])
def test_cli_forwards_use_external_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str, flag: tuple[str, ...], expected: bool
):
    """
    [Unit] fact-check CLI: scan and baseline forward --use-external-api to scan().

    Scenario:
        Given a recording stand-in for docsentinel.cli.scan
        When "docsentinel <command> ROOT" runs with and without --use-external-api
        Then scan() receives use_external_api=True with the flag and False without it.

    Boundaries:
        - Focus: _scan_overrides
        - Fixtures/params: tmp_path, monkeypatch, command, flag, expected
        - Scope: cli.main with scan() replaced; no document is read

    On failure, first check:
        - The --use-external-api argument on both parsers
    """
    seen: list[Any] = []

    def recording(root: Any, **kwargs: Any) -> ScanResult:
        """Record the consent keyword and return an empty result."""
        seen.append(kwargs["use_external_api"])
        return ScanResult(profile="fast", documents=(), findings=(), enabled_rules=(), pending=())

    monkeypatch.setattr(cli, "scan", recording)
    argv = [command, str(tmp_path), *flag]
    if command == "baseline":
        argv += ["--output", str(tmp_path / "baseline.json")]

    assert cli.main(argv) == 0
    assert seen == [expected]


def test_rules_suffix_marks_external_api_rules_only():
    """
    [Unit] fact-check CLI: the rules suffix of an EXTERNAL_API_RULES code is the fixed text.

    Scenario:
        Given a DS302 Rule and an ordinary deep rule (neither registered)
        When _rule_suffix renders each
        Then DS302 gets the documented suffix and the other rule none.

    Boundaries:
        - Focus: _rule_suffix; DS302 registration lands in Task 05
        - Fixtures/params: none
        - Scope: pure function

    On failure, first check:
        - EXTERNAL_API_RULES and EXTERNAL_API_SUFFIX
    """
    external = Rule(code="DS302", profile="deep", title="External fact-check disagreement", description="x")
    ordinary = Rule(code="DS301", profile="deep", title="Candidate contradiction", description="x")

    assert frozenset({"DS302"}) == EXTERNAL_API_RULES
    assert f"{external.code}: {external.title}{cli._rule_suffix(external)}" == (
        "DS302: External fact-check disagreement "
        "[requires --use-external-api and a backend API key; see docsentinel doctor]"
    )
    assert cli._rule_suffix(ordinary) == ""
