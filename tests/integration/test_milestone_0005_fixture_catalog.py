"""Manifest parity and registration-gated coverage for the Milestone 0005 fixture catalog.

This harness is Task 03 of Story 01.0. It reads the checked-in ``fixture-matrix.json`` and enforces
that every promised scenario is accounted for, correctly named and -- once its rule is registered --
committed, loadable and actually exercised. See :mod:`tests.milestone_0005_manifest` for the
registration-gated enforcement model that keeps the suite green for not-yet-implemented stories
while still failing actively on absent, extra, misnamed or unexercisable scenarios.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

import pytest

from tests.asset_helpers import AssetCase
from tests.milestone_0005_manifest import (
    EXPECTED_OUTCOME_COUNTS,
    EXPECTED_TOTAL,
    Scenario,
    committed_case_errors,
    committed_directories,
    csv_scenario_keys,
    declared_rules,
    execute_scenario,
    load_scenarios,
    markdown_scenario_keys,
    scenario_errors,
    slug_is_valid,
)

SCENARIOS = load_scenarios()
SCENARIO_IDS = [f"{scenario.rule}-{scenario.case}" for scenario in SCENARIOS]


#: Default-setup ERROR scenarios whose accepted safe handling is an explicit own finding rather than a raised
#: ConfigError or a pending state. Explicit on purpose: any other error row must still raise or be pending.
FINDING_SATISFIES_ERROR = frozenset({("DS114", "invalid_nested_metadata")})


def test_manifest_matches_expected_totals():
    """
    [Integration] milestone 0005 fixture catalog: verifies the manifest matches the agreed totals.

    Scenario:
        Given the checked-in JSON fixture matrix
        When its scenarios are counted by outcome
        Then the totals equal the 191 scenarios (96 clean / 91 finding / 4 error) the plan promises.

    Boundaries:
        - Focus: manifest totals and per-outcome counts only
        - Fixtures/params: none

    On failure, first check:
        - Whether a scenario was added to or removed from fixture-matrix.json
        - Whether EXPECTED_TOTAL / EXPECTED_OUTCOME_COUNTS still match the plan
    """
    assert len(SCENARIOS) == EXPECTED_TOTAL
    assert Counter(scenario.outcome for scenario in SCENARIOS) == EXPECTED_OUTCOME_COUNTS


def test_matrix_formats_are_synchronized():
    """
    [Integration] milestone 0005 fixture catalog: verifies the json, csv and md matrices agree.

    Scenario:
        Given the three fixture-matrix formats
        When their ``(rule, case)`` key sets are compared
        Then json, csv and md describe exactly the same scenarios with the same total count.

    Boundaries:
        - Focus: set equality across json, csv and md matrices
        - Fixtures/params: none

    On failure, first check:
        - Which format was edited without updating the other two
        - Whether a slug or rule was renamed in only one place
    """
    json_keys = {(scenario.rule, scenario.case) for scenario in SCENARIOS}
    assert len(json_keys) == EXPECTED_TOTAL
    assert csv_scenario_keys() == json_keys
    assert markdown_scenario_keys() == json_keys


def test_every_scenario_is_internally_consistent():
    """
    [Integration] milestone 0005 fixture catalog: verifies every scenario obeys the naming contract.

    Scenario:
        Given every promised scenario
        When slug shape, asset_root, outcome and declared Markdown are validated
        Then no scenario violates the 2-4 snake_case-word, dsNNN-matching, has-a-.md contract.

    Boundaries:
        - Focus: per-scenario naming and shape in the manifest, not on-disk assets
        - Fixtures/params: none

    On failure, first check:
        - The reported rule/case key and its specific problem list
        - Whether asset_root, slug or markdown_assets were edited inconsistently
    """
    problems = {
        f"{scenario.rule}/{scenario.case}": errors for scenario in SCENARIOS if (errors := scenario_errors(scenario))
    }
    assert problems == {}


def test_declared_rules_cover_every_scenario_rule():
    """
    [Integration] milestone 0005 fixture catalog: verifies the declared rule list matches scenarios.

    Scenario:
        Given the JSON matrix's declared rule list
        When it is compared with the rules referenced by scenarios
        Then the two sets are identical, so no scenario references an undeclared rule.

    Boundaries:
        - Focus: the ``rules`` header versus the rules used by ``cases``
        - Fixtures/params: none

    On failure, first check:
        - Whether a scenario references a rule missing from the declared list
        - Whether a declared rule has no scenarios
    """
    assert set(declared_rules()) == {scenario.rule for scenario in SCENARIOS}


def test_at_least_three_clean_and_three_finding_per_rule():
    """
    [Integration] milestone 0005 fixture catalog: verifies each rule has 3+ clean and 3+ finding cases.

    Scenario:
        Given every promised scenario grouped by rule
        When clean and finding outcomes are counted per rule
        Then every rule declares at least three clean and at least three finding scenarios.

    Boundaries:
        - Focus: per-rule minimum clean/finding coverage required by the plan
        - Fixtures/params: none

    On failure, first check:
        - The reported rule whose clean or finding count dropped below three
        - Whether an outcome value was mistyped in the matrix
    """
    by_rule: dict[str, Counter[str]] = {}
    for scenario in SCENARIOS:
        by_rule.setdefault(scenario.rule, Counter())[scenario.outcome] += 1
    thin = {rule: counts for rule, counts in by_rule.items() if counts["clean"] < 3 or counts["finding"] < 3}
    assert thin == {}


def test_no_unexpected_asset_directories():
    """
    [Integration] milestone 0005 fixture catalog: verifies committed asset dirs stay within the manifest.

    Scenario:
        Given the asset directories currently committed for Milestone 0005 rules
        When each committed directory is matched against the manifest
        Then there are no extra, misnamed or orphaned directories -- parity fails loudly on drift.

    Boundaries:
        - Focus: committed directories must be a subset of valid manifest slugs
        - Fixtures/params: none

    On failure, first check:
        - The reported rule and the unexpected or misnamed directory names
        - Whether a fixture was committed before being added to the manifest
    """
    manifest_cases: dict[str, set[str]] = {}
    for scenario in SCENARIOS:
        manifest_cases.setdefault(scenario.rule, set()).add(scenario.case)

    unexpected: dict[str, set[str]] = {}
    for rule, expected in manifest_cases.items():
        extra = {name for name in committed_directories(rule) if name not in expected or not slug_is_valid(name)}
        if extra:
            unexpected[rule] = extra
    assert unexpected == {}


def test_assets_are_not_committed_for_unregistered_rules():
    """
    [Integration] milestone 0005 fixture catalog: verifies pending rules have no unexercisable assets.

    Scenario:
        Given every rule that is not yet registered in the engine
        When its committed asset directories are counted
        Then there are none, because an unregistered rule cannot exercise any scenario -- a committed
        fixture for it would be an untested scenario, which this test fails actively.

    Boundaries:
        - Focus: no committed assets for rules absent from the rule registry
        - Fixtures/params: none

    On failure, first check:
        - The reported pending rule that already has committed assets
        - Whether the detector was committed without registering its rule code
    """
    orphaned = {
        scenario.rule: sorted(committed_directories(scenario.rule))
        for scenario in SCENARIOS
        if not scenario.is_registered and committed_directories(scenario.rule)
    }
    assert orphaned == {}


def test_registered_rules_have_every_promised_directory():
    """
    [Integration] milestone 0005 fixture catalog: verifies registered rules commit their full catalog.

    Scenario:
        Given every rule already registered in the engine
        When its promised scenarios are compared with committed directories
        Then every promised directory exists -- a registered rule missing a fixture fails the gate.

    Boundaries:
        - Focus: registered rules must commit the full manifest slice
        - Fixtures/params: none

    On failure, first check:
        - The reported rule and the case slugs whose directories are missing
        - Whether a detector story registered its rule but forgot some fixtures
    """
    missing: dict[str, list[str]] = {}
    for scenario in SCENARIOS:
        if scenario.is_registered and not scenario.is_committed:
            missing.setdefault(scenario.rule, []).append(scenario.case)
    assert missing == {}


@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_scenario_is_covered(scenario: Scenario, asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] milestone 0005 fixture catalog: verifies each scenario per its registration state.

    Scenario:
        Given one promised scenario
        When its rule's registration and its directory's presence are inspected
        Then: an unregistered rule must have no committed directory (pending, not red); a registered
        rule must have a valid, loadable directory whose default-setup outcome matches the manifest.

    Boundaries:
        - Focus: the single scenario named in the parameter id
        - Non-default ``setup`` outcome assertions belong to each rule's own task-03 test
        - A clean outcome requires the rule to have actually run, never a zero-findings no-op

    On failure, first check:
        - Whether the rule is registered and whether its directory is committed
        - The committed-directory problem list or the mismatched clean/finding/error outcome
    """
    if not scenario.is_registered:
        assert not scenario.is_committed, (
            f"{scenario.rule}/{scenario.case}: asset committed for an unregistered rule; "
            "register the detector before committing its fixtures so the scenario is exercisable"
        )
        return

    assert scenario.is_committed, (
        f"{scenario.rule}/{scenario.case}: rule is registered but its promised fixture directory "
        f"{scenario.source_dir} is missing"
    )
    assert slug_is_valid(scenario.case)
    directory_problems = committed_case_errors(scenario)
    assert directory_problems == (), f"{scenario.rule}/{scenario.case}: {directory_problems}"

    result = execute_scenario(scenario, asset_case)
    if not result.executed:
        # Non-default setup: existence and shape are gated here; outcome is asserted by the
        # rule-specific task-03 test that knows how to build the required config.
        assert scenario.setup != "default" or result.error is not None
        return

    if scenario.outcome == "clean":
        assert result.rule_enabled, f"{scenario.rule} did not run; zero findings is not a clean result"
        assert result.own_finding_count == 0
    elif scenario.outcome == "finding":
        assert result.own_finding_count >= 1
    else:  # error
        # An error-outcome scenario is satisfied by a raised ConfigError, a recorded readiness
        # pending, or -- for a default-setup scenario the detector handles by explicitly flagging
        # the offending document rather than aborting the whole scan -- at least one own finding
        # (DS114's invalid_nested_metadata ruling: an unsupported id value shape is reported, not
        # silently dropped and not escalated to exit 2). Non-default error scenarios exit above and
        # are pinned by their own rule's task-03 test.
        flagged_by_finding = (scenario.rule, scenario.case) in FINDING_SATISFIES_ERROR
        assert result.error is not None or result.pending or (flagged_by_finding and result.own_finding_count >= 1)
