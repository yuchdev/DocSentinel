"""Unit tests for ``Rule.opt_in_values``, ``opt_in_satisfied`` and ``opt_in_hint`` (ADR 0004 Contract 1)."""

import logging
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from docsentinel import cli
from docsentinel.config import Config
from docsentinel.engine import _log_rule_plan, evaluated_notice, scan
from docsentinel.rules import RULES, Rule, opt_in_hint, opt_in_satisfied, register_rule

#: The legacy opt-in fragments that must stay byte-identical (plan C2, ADR 0004 Contract 1).
_LEGACY_NOTICE = (
    "12 fast rule(s) evaluated; opt-in rule(s) not enabled: DS110 (set require_fence_languages), "
    "DS112 (set navigation_indexes), DS115 (set deprecated_references_file), "
    "DS118 (set documentation_naming)."
)


@pytest.fixture
def restore_registry() -> Iterator[None]:
    """Restore the global rule registry after a test registers throwaway rules."""
    saved = RULES.copy()
    yield
    RULES.clear()
    RULES.update(saved)


def _scope_rule(values: frozenset[str] = frozenset({"strict"})) -> Rule:
    """Return an unregistered opt-in rule keyed on ``reference_scope``."""
    return Rule(
        "DS990", "fast", "Scope rule", "A scope test rule.", opt_in_option="reference_scope", opt_in_values=values
    )


def test_opt_in_values_defaults_empty():
    """
    [Unit] rules: verifies ``Rule.opt_in_values`` defaults to an empty frozenset.

    Scenario:
        Given a rule built positionally without opt_in_values
        When its field is read
        Then it is an empty frozenset, so legacy rules keep truthiness semantics.

    Boundaries:
        - Focus: the defaulted dataclass field
        - Fixtures/params: none
        - Scope: Rule construction only

    On failure, first check:
        - The default of Rule.opt_in_values
    """
    rule = Rule("DS990", "fast", "Title", "Description.", "warning", "require_fence_languages")

    assert rule.opt_in_values == frozenset()


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (SimpleNamespace(reference_scope="strict"), True),  # the enabling value
        (SimpleNamespace(reference_scope="links"), False),  # the default scope
        (SimpleNamespace(reference_scope="STRICT"), False),  # exact, case-sensitive match
        (SimpleNamespace(reference_scope=" strict"), False),  # no stripping
        (SimpleNamespace(reference_scope=["strict"]), False),  # unhashable: isinstance guard, no TypeError
        (SimpleNamespace(reference_scope=True), False),  # truthy non-str is not an enabling value
        (SimpleNamespace(reference_scope=None), False),
        (SimpleNamespace(), False),  # missing attribute reads as None
    ],
)
def test_opt_in_satisfied_matches_enabling_values_exactly(config: object, expected: bool):
    """
    [Unit] rules: verifies ``opt_in_satisfied`` uses exact str membership when values are set.

    Scenario:
        Given a rule with opt_in_values {"strict"} and configs holding various values
        When opt_in_satisfied inspects each pair
        Then only the exact string "strict" satisfies it; a list returns False without raising.

    Boundaries:
        - Focus: step 3 of Contract 1 including the isinstance(value, str) guard
        - Fixtures/params: eight config shapes
        - Scope: the predicate only

    On failure, first check:
        - The isinstance guard and the membership test in opt_in_satisfied
    """
    assert opt_in_satisfied(_scope_rule(), config) is expected


def test_unknown_injected_scope_keeps_ds103_inert(tmp_path: Path):
    """
    [Unit] engine: verifies an injected Config with an unknown scope leaves DS103 inert (M20).

    Scenario:
        Given a document with an unresolvable path-like code span
        And an injected Config whose reference_scope is "STRICT" (bypassing load_config)
        When scan runs with that config
        Then DS103 reports nothing and the notice still names DS103 with its hint.

    Boundaries:
        - Focus: fail-safe handling of an unvalidated injected scope
        - Fixtures/params: tmp_path
        - Scope: one scan over one inline document

    On failure, first check:
        - opt_in_satisfied's exact membership test, and the engine's opt_in_off computation
    """
    (tmp_path / "a.md").write_text("See `docs/missing/file.md` here.\n", encoding="utf-8")

    result = scan(tmp_path, config=Config(select=("DS103",), reference_scope="STRICT"))

    assert opt_in_satisfied(RULES["DS103"], Config(reference_scope="STRICT")) is False
    assert [finding for finding in result.findings if finding.rule == "DS103"] == []
    assert result.opt_in_off == (("DS103", "reference_scope"),)
    assert 'DS103 (set reference_scope = "strict")' in result.notice


def test_strict_scope_enables_ds103_and_default_scope_names_it(tmp_path: Path):
    """
    [Unit] engine: verifies the default scope names DS103 in the notice and strict scope evaluates it.

    Scenario:
        Given a document with an unresolvable path-like code span
        When scan runs with the default Config and again with reference_scope="strict"
        Then the default run has no DS103 finding and names DS103 as opt-in off,
        And the strict run reports DS103 and counts it as evaluated.

    Boundaries:
        - Focus: Story 01.0 acceptance "Default scope is links; DS103 is inert and named"
        - Fixtures/params: tmp_path
        - Scope: two scans over one inline document

    On failure, first check:
        - DS103's opt_in_option/opt_in_values registration in detectors/paths.py
    """
    (tmp_path / "a.md").write_text("See `docs/missing/file.md` here.\n", encoding="utf-8")

    default = scan(tmp_path, config=Config(select=("DS103",)))
    strict = scan(tmp_path, config=Config(select=("DS103",), reference_scope="strict"))

    assert default.findings == ()
    assert default.notice == (
        '0 fast rule(s) evaluated; opt-in rule(s) not enabled: DS103 (set reference_scope = "strict").'
    )
    assert [finding.rule for finding in strict.findings] == ["DS103"]
    assert strict.opt_in_off == ()
    assert strict.notice == "1 fast rule(s) evaluated."


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        (Rule("DS990", "fast", "T", "D."), ""),
        (Rule("DS990", "fast", "T", "D.", opt_in_option="require_fence_languages"), "require_fence_languages"),
        (
            Rule("DS990", "fast", "T", "D.", opt_in_option="reference_scope", opt_in_values=frozenset({"strict"})),
            'reference_scope = "strict"',
        ),
        (
            Rule("DS990", "fast", "T", "D.", opt_in_option="x", opt_in_values=frozenset({"b", "a", "c-1"})),
            'x = "a" or "b" or "c-1"',
        ),
    ],
)
def test_opt_in_hint_renders_each_rule_shape(rule: Rule, expected: str):
    """
    [Unit] rules: verifies ``opt_in_hint`` for every rule shape, sorting several values.

    Scenario:
        Given an ordinary rule, a legacy opt-in rule, a one-value rule and a three-value rule
        When opt_in_hint renders each
        Then the text is "", the option, option = "value", and the sorted " or " join.

    Boundaries:
        - Focus: the single source of hint text (Contract 1 table)
        - Fixtures/params: four rule shapes
        - Scope: the helper only

    On failure, first check:
        - The sorted() order and the double-quote rendering in opt_in_hint
    """
    assert opt_in_hint(rule) == expected


@pytest.mark.parametrize(
    ("option", "values"),
    [
        ("", frozenset({"strict"})),  # values without an option
        ("x", frozenset({"Strict"})),  # uppercase
        ("x", frozenset({""})),  # empty
        ("x", frozenset({"-a"})),  # must start with a letter or digit
        ("x", frozenset({'a"b'})),  # a quote would need escaping
        ("x", frozenset({"a" * 33})),  # longer than 32 characters
        ("x", frozenset({"a‮b"})),  # bidi control
        ("x", frozenset({1})),  # not a str
    ],
)
def test_register_rule_rejects_invalid_opt_in_values(restore_registry: None, option: str, values: frozenset):
    """
    [Unit] rules: verifies ``register_rule`` enforces the Contract 1 opt-in value invariants.

    Scenario:
        Given a rule whose opt_in_values lack an option or hold a value outside ^[a-z0-9][a-z0-9_-]{0,31}$
        When register_rule is called
        Then ValueError is raised and the rule is not registered.

    Boundaries:
        - Focus: registration invariants
        - Fixtures/params: eight invalid shapes; restore_registry
        - Scope: register_rule only

    On failure, first check:
        - The opt-in value pattern and the option-required check in register_rule
    """
    rule = Rule("DS990", "fast", "T", "D.", opt_in_option=option, opt_in_values=values)

    with pytest.raises(ValueError, match="opt_in_values"):
        register_rule(rule)
    assert "DS990" not in RULES


def test_register_rule_accepts_valid_opt_in_values(restore_registry: None):
    """
    [Unit] rules: verifies a rule with valid opt-in values registers unchanged.

    Scenario:
        Given a rule with opt_in_option "x" and values {"a", "b_2", "0-9"} (32-character edge too)
        When register_rule is called
        Then the same rule object is returned and stored.

    Boundaries:
        - Focus: the accepting side of the invariants, including the 32-character bound
        - Fixtures/params: restore_registry
        - Scope: register_rule only

    On failure, first check:
        - An over-strict value pattern in register_rule
    """
    rule = Rule("DS990", "fast", "T", "D.", opt_in_option="x", opt_in_values=frozenset({"a", "b_2", "0-9", "a" * 32}))

    assert register_rule(rule) is rule
    assert RULES["DS990"] is rule


def test_legacy_opt_in_text_is_byte_identical(caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine/cli: golden test pinning the DS110, DS112, DS115 and DS118 opt-in texts.

    Scenario:
        Given the four legacy opt-in rules as registered
        When the notice, the rules suffix, the plan line and the selection warning are rendered
        Then each text equals its pre-Milestone-0009 form byte for byte.

    Boundaries:
        - Focus: plan C2 byte-identity requirement
        - Fixtures/params: caplog
        - Scope: evaluated_notice, cli._opt_in_suffix and engine._log_rule_plan

    On failure, first check:
        - opt_in_hint for a rule with empty opt_in_values, and its use in engine/cli
    """
    legacy = (
        ("DS110", "require_fence_languages"),
        ("DS112", "navigation_indexes"),
        ("DS115", "deprecated_references_file"),
        ("DS118", "documentation_naming"),
    )
    codes = tuple(code for code, _ in legacy)

    assert evaluated_notice("fast", 12, legacy) == _LEGACY_NOTICE
    assert [cli._opt_in_suffix(RULES[code]) for code in codes] == [
        " [opt-in: set require_fence_languages]",
        " [opt-in: set navigation_indexes]",
        " [opt-in: set deprecated_references_file]",
        " [opt-in: set documentation_naming]",
    ]
    with caplog.at_level(logging.DEBUG, logger="docsentinel.engine"):
        _log_rule_plan(replace(Config(), select=codes), codes, legacy)
    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "profile=fast: 4 rules selected, 0 evaluated; opt-in off: DS110 (require_fence_languages), "
        "DS112 (navigation_indexes), DS115 (deprecated_references_file), DS118 (documentation_naming)",
        "DS110 is selected but evaluates nothing until require_fence_languages is set",
        "DS112 is selected but evaluates nothing until navigation_indexes is set",
        "DS115 is selected but evaluates nothing until deprecated_references_file is set",
        "DS118 is selected but evaluates nothing until documentation_naming is set",
    ]


def test_ds103_hint_is_rendered_on_every_surface(caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine/cli: verifies DS103's ``reference_scope = "strict"`` hint on every surface.

    Scenario:
        Given DS103 registered with opt_in_values {"strict"}
        When the notice, rules suffix, plan line and selection warning are rendered for it
        Then each carries reference_scope = "strict", while opt_in_off keeps the bare option.

    Boundaries:
        - Focus: Contract 1 "Where the hint is rendered" table
        - Fixtures/params: caplog
        - Scope: evaluated_notice, cli._opt_in_suffix and engine._log_rule_plan

    On failure, first check:
        - DS103's registration and the engine's hint lookup
    """
    off = (("DS103", "reference_scope"),)

    assert evaluated_notice("fast", 0, off) == (
        '0 fast rule(s) evaluated; opt-in rule(s) not enabled: DS103 (set reference_scope = "strict").'
    )
    assert cli._opt_in_suffix(RULES["DS103"]) == ' [opt-in: set reference_scope = "strict"]'
    with caplog.at_level(logging.DEBUG, logger="docsentinel.engine"):
        _log_rule_plan(replace(Config(), select=("DS103",)), ("DS103",), off)
    assert [record.getMessage() for record in caplog.records] == [
        'profile=fast: 1 rules selected, 0 evaluated; opt-in off: DS103 (reference_scope = "strict")',
        'DS103 is selected but evaluates nothing until reference_scope = "strict" is set',
    ]


def test_evaluated_notice_falls_back_to_option_for_unknown_code():
    """
    [Unit] engine: verifies ``evaluated_notice`` never raises for a caller-built, unregistered code.

    Scenario:
        Given an opt_in_off tuple naming an unregistered code
        When evaluated_notice renders it
        Then the option string is used verbatim.

    Boundaries:
        - Focus: the RULES.get fallback of Contract 1
        - Fixtures/params: none
        - Scope: evaluated_notice only

    On failure, first check:
        - The hint lookup helper in engine.py
    """
    assert evaluated_notice("fast", 1, (("DS999", "some_option"),)) == (
        "1 fast rule(s) evaluated; opt-in rule(s) not enabled: DS999 (set some_option)."
    )
