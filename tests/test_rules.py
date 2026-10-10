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
    saved_rules = RULES.copy()
    RULES.clear()
    yield
    RULES.clear()
    RULES.update(saved_rules)


def test_register_rule_adds_to_registry() -> None:
    assert len(RULES) == 0
    rule = Rule("DS101", "fast", "Dangling link", "Finds links with missing targets.")

    assert register_rule(rule) is rule
    assert RULES[rule.code] == rule


def test_register_rule_rejects_duplicate_code() -> None:
    rule = Rule("DS101", "fast", "Dangling link", "Finds links with missing targets.")
    register_rule(rule)

    with pytest.raises(ValueError, match="^Duplicate rule code: DS101$"):
        register_rule(rule)


def test_register_rule_rejects_unknown_profile() -> None:
    rule = Rule("DS101", "nonsense", "Invalid profile", "Targets no supported profile.")

    with pytest.raises(ValueError):
        register_rule(rule)
    assert RULES == {}


def test_rules_for_profile_filters_and_sorts() -> None:
    fast_later = register_rule(Rule("DS103", "fast", "Later", "Later fast rule."))
    standard = register_rule(Rule("DS201", "standard", "Standard", "Standard rule."))
    fast_earlier = register_rule(Rule("DS101", "fast", "Earlier", "Earlier fast rule."))
    registry_before_lookup = RULES.copy()

    assert rules_for_profile("fast") == (fast_earlier, fast_later)
    assert standard not in rules_for_profile("fast")
    assert RULES == registry_before_lookup


def test_matches_selector_exact_and_prefix() -> None:
    assert matches_selector("DS101", "DS101")
    assert matches_selector("DS101", "DS1")
    assert matches_selector("DS101", "DS")
    assert not matches_selector("DS101", "DS102")
    assert not matches_selector("DS101", "DS2")


def test_effective_rules_empty_select_means_all() -> None:
    assert effective_rules(("DS103", "DS101", "DS102"), (), ()) == (
        "DS101",
        "DS102",
        "DS103",
    )


def test_effective_rules_ignore_wins_over_select() -> None:
    assert effective_rules(
        ("DS101", "DS102", "DS201"),
        ("DS1", "DS201"),
        ("DS101", "DS2"),
    ) == ("DS102",)


def test_effective_rules_unmatched_selector_is_inert() -> None:
    assert effective_rules(("DS101",), ("DS999",), ()) == ()
