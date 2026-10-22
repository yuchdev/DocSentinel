"""Metadata registry for DocSentinel rules."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Rule:
    """The stable metadata associated with a rule code.

    :ivar code: The stable rule code, for example ``DS110``.
    :ivar profile: The profile the rule belongs to (``fast``/``standard``/``deep``).
    :ivar title: Short human-readable rule title.
    :ivar description: One-line description of what the rule checks.
    :ivar severity: Default finding severity, ``warning`` unless overridden.
    :ivar opt_in_option: Name of the :class:`~docsentinel.config.Config` option
        that switches an opt-in policy rule on. Empty (the default) marks an
        ordinary always-active rule; a non-empty value names the setting a
        project must configure before the rule evaluates anything (for example
        ``require_fence_languages`` for ``DS110``).
    """

    code: str
    profile: str
    title: str
    description: str
    severity: str = "warning"
    opt_in_option: str = ""


RULES: dict[str, Rule] = {}
ANALYZERS: dict[str, Any] = {}


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


def opt_in_satisfied(rule: Rule, config: Any) -> bool:
    """Return whether an opt-in policy rule is switched on by the effective config.

    Ordinary rules (those with no :attr:`Rule.opt_in_option`) are always
    satisfied. An opt-in policy rule is satisfied only when its named
    configuration option is set to an enabling value: a truthy value that is not
    the string ``"off"``. This single predicate covers the several option shapes
    opt-in rules use - a boolean such as ``require_fence_languages``, a non-empty
    tuple such as ``navigation_indexes``, and a string such as
    ``deprecated_references_file`` (empty when unset) or ``documentation_naming``
    (``"off"`` when disabled). A config missing the named attribute entirely
    reads as off.

    This relies on :func:`~docsentinel.config.load_config` having already
    type-validated the option: it tests only truthiness and the ``"off"``
    sentinel, so a hand-built :class:`~docsentinel.config.Config` that bypasses
    load-time validation (for example assigning the *string* ``"false"`` to a
    boolean option) is truthy and would be read as *on*.

    :param rule: The registered rule to test.
    :param config: The effective :class:`~docsentinel.config.Config` for the scan.
    :returns: ``True`` when the rule should evaluate; ``False`` when its opt-in
        policy is off.
    """
    if not rule.opt_in_option:
        return True
    value = getattr(config, rule.opt_in_option, None)
    return bool(value) and value != "off"


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
