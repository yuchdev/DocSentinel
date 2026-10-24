"""Milestone 0005 fixture manifest and registration-gated scenario runner.

This module turns the checked-in ``fixture-matrix.{json,csv,md}`` catalog into the single
source of truth that the test harness enforces. It intentionally lives beside the tests (not a
``test_`` file) so that every per-rule story (02.0..14.0) can reuse the same manifest, slug rules
and :func:`execute_scenario` runner instead of inventing a private asset loader.

Enforcement is **registration gated** on purpose. Milestone 0005 is implemented story by story:
the shared scanner and config (Story 01.0) land first, then each rule story registers one ``DS1xx``
code and commits its own ``tests/assets/dsNNN/<slug>/`` directories. The manifest promises 191
scenarios long before any of them is committed, so a naive "every promised directory must exist"
gate would be red for the whole milestone until the very last story. Instead:

* A manifest rule that is **not yet registered** in :data:`docsentinel.rules.RULES` is *pending*.
  Its promised directories are reported as missing but do not fail the suite -- and committing an
  asset directory for such a rule *does* fail, because an unexercisable scenario is worse than a
  missing one (see contract B.4, "no silent pass for an unregistered/disabled rule").
* A manifest rule that **is registered** must have every promised directory committed, correctly
  named and loadable; a missing, extra or misnamed directory fails immediately.

The practical effect: today (no ``DS1xx`` rule registered) the suite is green while every scenario
is still accounted for; the moment a story registers its rule and commits its assets, that rule's
slice of the manifest flips from pending to actively enforced -- never the other way around, and
never via ``skip``/``xfail``.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Importing these modules also imports the ``docsentinel`` package, whose detector modules register
# their rule codes in ``RULES`` as an import side effect -- that registration is the gate this
# module reads to decide which scenarios are actively enforced versus still pending.
from docsentinel.config import Config, ConfigError
from docsentinel.engine import scan
from docsentinel.rules import RULES

REPO_ROOT = Path(__file__).resolve().parent.parent
MILESTONE_DIR = REPO_ROOT / "docs" / "roadmap" / "0005-deepening-test-case-stage-2"
MATRIX_JSON = MILESTONE_DIR / "fixture-matrix.json"
MATRIX_CSV = MILESTONE_DIR / "fixture-matrix.csv"
MATRIX_MD = MILESTONE_DIR / "fixture-matrix.md"
ASSETS_ROOT = REPO_ROOT / "tests" / "assets"

#: Allowed scenario outcomes; ``error`` means a validation/security/readiness failure, never a
#: detector that merely produced zero findings.
VALID_OUTCOMES = ("clean", "finding", "error")

#: Totals asserted against all three matrix formats, so an inconsistent edit fails loudly.
EXPECTED_TOTAL = 191
EXPECTED_OUTCOME_COUNTS = {"clean": 96, "finding": 91, "error": 4}

#: A snake_case slug of two to four lowercase/digit words.
_SLUG_RE = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+){1,3}\Z")
#: A ``tests/assets/dsNNN/<slug>/`` reference as written inside the Markdown matrix.
_ASSET_DIR_RE = re.compile(r"tests/assets/(ds\d+)/([a-z0-9_]+)/")


@dataclass(frozen=True)
class Scenario:
    """One promised fixture scenario drawn from ``fixture-matrix.json``.

    :ivar rule: Rule code the scenario exercises (for example ``DS104``).
    :ivar profile: Profile under which the scenario runs; always ``fast`` for this milestone.
    :ivar story: Owning story identifier (for example ``02.0``).
    :ivar outcome: Expected outcome, one of :data:`VALID_OUTCOMES`.
    :ivar case: snake_case scenario slug and directory name.
    :ivar asset_root: Declared repository-relative asset directory ending in a slash.
    :ivar markdown_assets: Semicolon-joined required Markdown files for the case.
    :ivar companions: Semicolon-joined non-Markdown companion files, if any.
    :ivar behavior: Human-readable required assertion.
    :ivar setup: Config/companion setup descriptor; ``default`` means no overrides.
    """

    rule: str
    profile: str
    story: str
    outcome: str
    case: str
    asset_root: str
    markdown_assets: str
    companions: str
    behavior: str
    setup: str

    @property
    def rule_dir(self) -> str:
        """Return the lowercase ``dsNNN`` directory name for the rule."""
        return self.rule.lower()

    @property
    def source_dir(self) -> Path:
        """Return the committed source asset directory for this scenario."""
        return ASSETS_ROOT / self.rule_dir / self.case

    @property
    def markdown_files(self) -> tuple[str, ...]:
        """Return the required Markdown file paths declared for the case."""
        return tuple(part for part in self.markdown_assets.split(";") if part)

    @property
    def companion_files(self) -> tuple[str, ...]:
        """Return the declared companion file paths for the case."""
        return tuple(part for part in self.companions.split(";") if part)

    @property
    def uses_runtime_companions(self) -> bool:
        """Return whether companions (symlinks, extension bytes) are built at runtime, not committed."""
        return "symlink" in self.setup or "runtime" in self.setup

    @property
    def is_committed(self) -> bool:
        """Return whether the scenario's asset directory exists in the repository."""
        return self.source_dir.is_dir()

    @property
    def is_registered(self) -> bool:
        """Return whether the scenario's rule is registered and therefore actively enforced."""
        return self.rule in RULES


def load_scenarios(path: Path = MATRIX_JSON) -> tuple[Scenario, ...]:
    """Load every promised scenario from the JSON matrix.

    :param path: Path to the JSON fixture matrix.
    :returns: Scenarios in declaration order.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        Scenario(
            rule=row["rule"],
            profile=row["profile"],
            story=row["story"],
            outcome=row["outcome"],
            case=row["case"],
            asset_root=row["asset_root"],
            markdown_assets=row["markdown_assets"],
            companions=row["companions"],
            behavior=row["behavior"],
            setup=row["setup"],
        )
        for row in data["cases"]
    )


def declared_rules(path: Path = MATRIX_JSON) -> tuple[str, ...]:
    """Return the rule codes the JSON matrix declares in scope.

    :param path: Path to the JSON fixture matrix.
    :returns: Declared rule codes in declaration order.
    """
    return tuple(json.loads(path.read_text(encoding="utf-8"))["rules"])


def csv_scenario_keys(path: Path = MATRIX_CSV) -> set[tuple[str, str]]:
    """Return ``(rule, case)`` keys recorded in the CSV matrix.

    :param path: Path to the CSV fixture matrix.
    :returns: Unique ``(rule, case)`` keys.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        return {(row["rule"], row["case"]) for row in csv.DictReader(handle)}


def markdown_scenario_keys(path: Path = MATRIX_MD) -> set[tuple[str, str]]:
    """Return ``(rule, case)`` keys referenced by the Markdown matrix.

    :param path: Path to the Markdown fixture matrix.
    :returns: Unique ``(rule, case)`` keys derived from asset directory references.
    """
    text = path.read_text(encoding="utf-8")
    return {("DS" + rule_dir[2:], slug) for rule_dir, slug in _ASSET_DIR_RE.findall(text)}


def slug_is_valid(case: str) -> bool:
    """Return whether a case slug is snake_case with two to four words.

    :param case: Candidate scenario slug.
    :returns: ``True`` when the slug matches the required shape.
    """
    return bool(_SLUG_RE.fullmatch(case))


def scenario_errors(scenario: Scenario) -> tuple[str, ...]:
    """Return internal-consistency problems for one scenario, empty when valid.

    :param scenario: Scenario to validate against the manifest contract.
    :returns: Human-readable problem descriptions.
    """
    problems: list[str] = []
    if not slug_is_valid(scenario.case):
        problems.append(f"slug {scenario.case!r} is not 2-4 snake_case words")
    expected_root = f"tests/assets/{scenario.rule_dir}/{scenario.case}/"
    if scenario.asset_root != expected_root:
        problems.append(f"asset_root {scenario.asset_root!r} does not match {expected_root!r}")
    if scenario.outcome not in VALID_OUTCOMES:
        problems.append(f"outcome {scenario.outcome!r} is not one of {VALID_OUTCOMES}")
    if not scenario.markdown_files:
        problems.append("no Markdown asset declared")
    if not any(name.endswith(".md") for name in scenario.markdown_files):
        problems.append("declares no .md document")
    return tuple(problems)


def committed_case_errors(scenario: Scenario) -> tuple[str, ...]:
    """Return problems with the committed asset directory of a scenario, empty when valid.

    Only meaningful once :attr:`Scenario.is_committed` is true.

    :param scenario: Scenario whose on-disk directory should be validated.
    :returns: Human-readable problem descriptions.
    """
    problems: list[str] = []
    markdown_present = sorted(path for path in scenario.source_dir.rglob("*.md") if path.is_file())
    if not markdown_present:
        problems.append("committed directory contains no .md document")
    for relative in scenario.markdown_files:
        if not (scenario.source_dir / relative).is_file():
            problems.append(f"declared Markdown asset {relative!r} is missing")
    if not scenario.uses_runtime_companions:
        for relative in scenario.companion_files:
            if not (scenario.source_dir / relative).is_file():
                problems.append(f"declared companion {relative!r} is missing")
    return tuple(problems)


def committed_directories(rule: str) -> frozenset[str]:
    """Return the names of committed case directories for a rule.

    :param rule: Rule code (for example ``DS104``).
    :returns: Directory names present under ``tests/assets/<rule>/``.
    """
    rule_root = ASSETS_ROOT / rule.lower()
    if not rule_root.is_dir():
        return frozenset()
    return frozenset(child.name for child in rule_root.iterdir() if child.is_dir())


@dataclass(frozen=True)
class ScenarioResult:
    """The outcome of attempting to exercise one scenario.

    :ivar executed: Whether the detector was actually run for this scenario.
    :ivar own_finding_count: Number of findings attributed to the scenario's own rule.
    :ivar rule_enabled: Whether the rule appeared in the scan's enabled-rule set.
    :ivar pending: Pending/readiness messages produced by the scan, if any.
    :ivar error: The raised error message for ``error`` scenarios, if one occurred.
    """

    executed: bool
    own_finding_count: int = 0
    rule_enabled: bool = False
    pending: tuple[str, ...] = ()
    error: Optional[str] = None


def execute_scenario(scenario: Scenario, load_case) -> ScenarioResult:
    """Run a committed, registered, default-setup scenario and summarize its outcome.

    The runner isolates the scenario's own rule via ``select`` so that a zero-findings result can
    only come from the rule actually running and finding nothing -- never from the rule being
    absent. Non-default ``setup`` scenarios need rule-specific config that each rule's own task-03
    test supplies; this generic runner reports them as not executed rather than guessing semantics.

    :param scenario: Scenario to exercise; must be committed and registered.
    :param load_case: Callable ``(rule_dir, case) -> AssetCase`` (the ``asset_case`` fixture).
    :returns: A :class:`ScenarioResult` describing what happened.
    """

    if scenario.setup != "default":
        return ScenarioResult(executed=False)

    case = load_case(scenario.rule_dir, scenario.case)
    try:
        result = scan(case.root, config=Config(profile="fast", select=(scenario.rule,)))
    except ConfigError as error:
        message = str(error)
        return ScenarioResult(executed=False, error=message)
    own = sum(1 for finding in result.findings if finding.rule == scenario.rule)
    return ScenarioResult(
        executed=True,
        own_finding_count=own,
        rule_enabled=scenario.rule in result.enabled_rules,
        pending=result.pending,
    )
