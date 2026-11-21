"""Unit tests for DS124's handling of ``at_reference_extensions`` (threat model 0009 M20)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from docsentinel import models
from docsentinel.config import Config, ConfigError
from docsentinel.detectors import mentions


def _detect(root: Path, text: str, config: Config) -> tuple[models.Finding, ...]:
    """Write one document and run DS124 on it.

    :param root: A scratch scan root.
    :param text: The document text.
    :param config: The injected configuration.
    :returns: The DS124 findings.
    """
    (root / "README.md").write_text(text, encoding="utf-8")
    document = models.Document(path="README.md", bytes=len(text.encode("utf-8")))
    return mentions.detect(root, (document,), config)


@pytest.mark.parametrize(
    "value",
    ((), ("md", "MD"), (".md",), ("m d",), ("a" * 17,), tuple(f"e{index}" for index in range(65)), ("md", 3)),
    ids=("empty", "duplicate_case", "dot", "space", "too_long", "too_many", "non_string"),
)
def test_injected_config_invalid_extensions_raise_config_error(tmp_path: Path, value: tuple[object, ...]):
    """
    [Unit] DS124 config: an injected Config with invalid extensions fails closed.

    Scenario:
        Given a Config built with dataclasses.replace and an out-of-bounds at_reference_extensions
        When DS124 runs
        Then ConfigError is raised before any document is checked.

    Boundaries:
        - Focus: re-validation of a Config that bypassed load_config
        - Fixtures/params: one per bound

    On failure, first check:
        - The validate_at_reference_extensions call at the top of mentions.detect
    """
    config = dataclasses.replace(Config(), at_reference_extensions=value)

    with pytest.raises(ConfigError, match="at_reference_extensions"):
        _detect(tmp_path, "@missing.md\n", config)


def test_extension_match_is_ascii_lowercase_membership(tmp_path: Path):
    """
    [Unit] DS124 config: extensions match case-insensitively by set membership, never as a pattern.

    Scenario:
        Given at_reference_extensions = ["MD", "txt"] and mentions ending .md, .Md, .TXT, .mdx and .m
        When DS124 runs on missing targets
        Then only the .md, .Md and .TXT mentions are reported.

    Boundaries:
        - Focus: lowercased membership; no prefix, glob or regex semantics
        - Fixtures/params: none

    On failure, first check:
        - _extension and the frozenset built in detect
    """
    config = dataclasses.replace(Config(), at_reference_extensions=("MD", "txt"))

    findings = _detect(tmp_path, "@a.md @b.Md @c.TXT @d.mdx @e.m\n", config)

    assert [finding.value for finding in findings] == ["@a.md", "@b.Md", "@c.TXT"]


def test_default_extensions_filter_unknown_suffix(tmp_path: Path):
    """
    [Unit] DS124 config: with defaults a mention with an unlisted extension is not checked.

    Scenario:
        Given the default Config and missing mentions ending .com and .md
        When DS124 runs
        Then only the .md mention is reported.

    Boundaries:
        - Focus: the default at_reference_extensions list
        - Fixtures/params: none

    On failure, first check:
        - The Config default for at_reference_extensions
    """
    findings = _detect(tmp_path, "@example.com @missing.md\n", Config())

    assert [finding.value for finding in findings] == ["@missing.md"]
