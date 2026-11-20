"""Metadata registry for DocSentinel rules."""

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Final

logger = logging.getLogger(__name__)


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
    :ivar opt_in_values: The values of :attr:`opt_in_option` that switch the rule
        on (ADR 0004 Contract 1). Empty (the default) keeps the legacy truthiness
        test of :func:`opt_in_satisfied`; a non-empty set requires an exact string
        match, for example ``{"strict"}`` for ``DS103`` and ``reference_scope``.
        Each value is a code literal matching :data:`OPT_IN_VALUE_PATTERN`.
    """

    code: str
    profile: str
    title: str
    description: str
    severity: str = "warning"
    opt_in_option: str = ""
    opt_in_values: frozenset[str] = frozenset()


RULES: dict[str, Rule] = {}
ANALYZERS: dict[str, Any] = {}
#: Rules the engine itself emits instead of an analyzer, in every profile. They are
#: registered (so ``docsentinel rules`` lists them) but never take part in a
#: profile's analyzer plan, ``enabled_rules`` of a clean scan or the evaluated-rule
#: count of ``ScanResult.notice``. ``DS100`` reports a document no analyzer could read.
ENGINE_RULES: Final[frozenset[str]] = frozenset({"DS100"})
#: An enabling value of :attr:`Rule.opt_in_values`. The pattern guarantees the
#: double-quoted rendering of :func:`opt_in_hint` never needs escaping and never
#: carries a control or bidi character.
OPT_IN_VALUE_PATTERN: Final[re.Pattern[str]] = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")


def register_rule(rule: Rule) -> Rule:
    """Register and return a rule, rejecting duplicate codes, unknown profiles or invalid opt-in values.

    :param rule: The rule to register.
    :returns: ``rule`` itself.
    :raises ValueError: For a duplicate code, an unknown profile, ``opt_in_values``
        without an ``opt_in_option``, or an enabling value that is not a ``str``
        matching :data:`OPT_IN_VALUE_PATTERN`.
    """
    if rule.code in RULES:
        raise ValueError(f"Duplicate rule code: {rule.code}")
    if rule.profile not in ("fast", "standard", "deep"):
        raise ValueError(f"Unknown rule profile: {rule.profile}")
    if rule.opt_in_values and not rule.opt_in_option:
        raise ValueError(f"Rule {rule.code} has opt_in_values but no opt_in_option")
    for value in rule.opt_in_values:
        if not isinstance(value, str) or OPT_IN_VALUE_PATTERN.fullmatch(value) is None:
            raise ValueError(f"Rule {rule.code} has an invalid opt_in_values entry")
    RULES[rule.code] = rule
    logger.debug("registered rule %s (%s, %s)", rule.code, rule.profile, rule.severity)
    return rule


def rules_for_profile(profile: str) -> tuple[Rule, ...]:
    """Return registered rules for a profile in rule-code order."""
    return tuple(sorted((rule for rule in RULES.values() if rule.profile == profile), key=lambda rule: rule.code))


def opt_in_satisfied(rule: Rule, config: Any) -> bool:
    """Return whether an opt-in policy rule is switched on by the effective config.

    Ordinary rules (those with no :attr:`Rule.opt_in_option`) are always
    satisfied. A rule with :attr:`Rule.opt_in_values` is satisfied only when its
    option holds a ``str`` that is exactly one of those values (case-sensitive,
    no stripping); any other value, an unhashable one included, reads as off, so
    an injected :class:`~docsentinel.config.Config` with an unknown value keeps
    the rule inert. Otherwise an opt-in policy rule is satisfied only when its named
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
    if rule.opt_in_values:
        return isinstance(value, str) and value in rule.opt_in_values
    return bool(value) and value != "off"


def opt_in_hint(rule: Rule) -> str:
    """Return the text naming what switches an opt-in policy rule on.

    The single source of the hint shown by ``ScanResult.notice``, ``docsentinel
    rules`` and the engine's rule-plan log lines (ADR 0004 Contract 1).

    :param rule: A rule.
    :returns: ``""`` for an ordinary rule; the option name verbatim when
        :attr:`Rule.opt_in_values` is empty (for example
        ``require_fence_languages``); otherwise ``<option> = "<value>"``, several
        values double-quoted in sorted order and joined with ``" or "``.
    """
    if not rule.opt_in_option:
        return ""
    if not rule.opt_in_values:
        return rule.opt_in_option
    return f"{rule.opt_in_option} = " + " or ".join(f'"{value}"' for value in sorted(rule.opt_in_values))


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
