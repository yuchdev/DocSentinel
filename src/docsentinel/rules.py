"""Metadata registry for DocSentinel rules."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    """The stable metadata associated with a rule code."""

    code: str
    profile: str
    title: str
    description: str
    severity: str = "warning"


RULES: dict[str, Rule] = {}


def register_rule(rule: Rule) -> Rule:
    """Register and return a rule, rejecting duplicate codes or unknown profiles."""
    if rule.code in RULES:
        raise ValueError(f"Duplicate rule code: {rule.code}")
    if rule.profile not in ("fast", "standard", "deep"):
        raise ValueError(f"Unknown rule profile: {rule.profile}")
    RULES[rule.code] = rule
    return rule


def rules_for_profile(profile: str) -> tuple[Rule, ...]:
    """Return registered rules for a profile in rule-code order."""
    return tuple(sorted((rule for rule in RULES.values() if rule.profile == profile), key=lambda rule: rule.code))


def matches_selector(code: str, selector: str) -> bool:
    """Return whether a rule code matches an exact or prefix selector."""
    return code == selector or code.startswith(selector)


def effective_rules(
    available: Iterable[str],
    select: tuple[str, ...],
    ignore: tuple[str, ...],
) -> tuple[str, ...]:
    """Return selected rule codes in deterministic order, with ignore taking precedence."""
    return tuple(
        code
        for code in sorted(available)
        if (not select or any(matches_selector(code, selector) for selector in select))
        and not any(matches_selector(code, selector) for selector in ignore)
    )
