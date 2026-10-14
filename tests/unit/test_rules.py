from collections.abc import Iterator

import pytest

from docsentinel.rules import (
    RULES,
    Rule,
    effective_rules,
    matches_selector,
    register_rule,
    rules_for_profile,
)


@pytest.fixture(autouse=True)
def isolate_rules_registry() -> Iterator[None]:
    """Isolate RULES registry state before and after each test."""
    saved_rules = RULES.copy()
    RULES.clear()
    yield
    RULES.clear()
    RULES.update(saved_rules)


def test_register_rule_adds_to_registry():
    """
    [Unit] rules: verifies register rule adds to registry.

    Scenario:
        Given test inputs and fixtures for register rule adds to registry
        When test_register_rule_adds_to_registry executes the target flow
        Then the expected outcome for register rule adds to registry is confirmed.

    Boundaries:
        - Focus: register rule adds to registry
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to register rule adds to registry
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by rules
    """
    assert len(RULES) == 0
    rule = Rule("DS101", "fast", "Dangling link", "Finds links with missing targets.")

    assert register_rule(rule) is rule
    assert RULES[rule.code] == rule


def test_register_rule_rejects_duplicate_code():
    """
    [Unit] rules: verifies register rule rejects duplicate code.

    Scenario:
        Given test inputs and fixtures for register rule rejects duplicate code
        When test_register_rule_rejects_duplicate_code executes the target flow
        Then the expected outcome for register rule rejects duplicate code is confirmed.

    Boundaries:
        - Focus: register rule rejects duplicate code
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to register rule rejects duplicate code
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by rules
    """
    rule = Rule("DS101", "fast", "Dangling link", "Finds links with missing targets.")
    register_rule(rule)

    with pytest.raises(ValueError, match="^Duplicate rule code: DS101$"):
        register_rule(rule)


def test_register_rule_rejects_unknown_profile():
    """
    [Unit] rules: verifies register rule rejects unknown profile.

    Scenario:
        Given test inputs and fixtures for register rule rejects unknown profile
        When test_register_rule_rejects_unknown_profile executes the target flow
        Then the expected outcome for register rule rejects unknown profile is confirmed.

    Boundaries:
        - Focus: register rule rejects unknown profile
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to register rule rejects unknown profile
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by rules
    """
    rule = Rule("DS101", "nonsense", "Invalid profile", "Targets no supported profile.")

    with pytest.raises(ValueError):
        register_rule(rule)
    assert RULES == {}


def test_rules_for_profile_filters_and_sorts():
    """
    [Unit] rules: verifies rules for profile filters and sorts.

    Scenario:
        Given test inputs and fixtures for rules for profile filters and sorts
        When test_rules_for_profile_filters_and_sorts executes the target flow
        Then the expected outcome for rules for profile filters and sorts is confirmed.

    Boundaries:
        - Focus: rules for profile filters and sorts
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to rules for profile filters and sorts
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by rules
    """
    fast_later = register_rule(Rule("DS103", "fast", "Later", "Later fast rule."))
    standard = register_rule(Rule("DS201", "standard", "Standard", "Standard rule."))
    fast_earlier = register_rule(Rule("DS101", "fast", "Earlier", "Earlier fast rule."))
    registry_before_lookup = RULES.copy()

    assert rules_for_profile("fast") == (fast_earlier, fast_later)
    assert standard not in rules_for_profile("fast")
    assert RULES == registry_before_lookup


def test_matches_selector_exact_and_prefix():
    """
    [Unit] rules: verifies matches selector exact and prefix.

    Scenario:
        Given test inputs and fixtures for matches selector exact and prefix
        When test_matches_selector_exact_and_prefix executes the target flow
        Then the expected outcome for matches selector exact and prefix is confirmed.

    Boundaries:
        - Focus: matches selector exact and prefix
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to matches selector exact and prefix
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by rules
    """
    assert matches_selector("DS101", "DS101")
    assert matches_selector("DS101", "DS1")
    assert matches_selector("DS101", "DS")
    assert not matches_selector("DS101", "DS102")
    assert not matches_selector("DS101", "DS2")


def test_effective_rules_empty_select_means_all():
    """
    [Unit] rules: verifies effective rules empty select means all.

    Scenario:
        Given test inputs and fixtures for effective rules empty select means all
        When test_effective_rules_empty_select_means_all executes the target flow
        Then the expected outcome for effective rules empty select means all is confirmed.

    Boundaries:
        - Focus: effective rules empty select means all
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to effective rules empty select means all
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by rules
    """
    assert effective_rules(("DS103", "DS101", "DS102"), (), ()) == (
        "DS101",
        "DS102",
        "DS103",
    )


def test_effective_rules_ignore_wins_over_select():
    """
    [Unit] rules: verifies effective rules ignore wins over select.

    Scenario:
        Given test inputs and fixtures for effective rules ignore wins over select
        When test_effective_rules_ignore_wins_over_select executes the target flow
        Then the expected outcome for effective rules ignore wins over select is confirmed.

    Boundaries:
        - Focus: effective rules ignore wins over select
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to effective rules ignore wins over select
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by rules
    """
    assert effective_rules(
        ("DS101", "DS102", "DS201"),
        ("DS1", "DS201"),
        ("DS101", "DS2"),
    ) == ("DS102",)


def test_effective_rules_unmatched_selector_is_inert():
    """
    [Unit] rules: verifies effective rules unmatched selector is inert.

    Scenario:
        Given test inputs and fixtures for effective rules unmatched selector is inert
        When test_effective_rules_unmatched_selector_is_inert executes the target flow
        Then the expected outcome for effective rules unmatched selector is inert is confirmed.

    Boundaries:
        - Focus: effective rules unmatched selector is inert
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to effective rules unmatched selector is inert
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by rules
    """
    assert effective_rules(("DS101",), ("DS999",), ()) == ()
