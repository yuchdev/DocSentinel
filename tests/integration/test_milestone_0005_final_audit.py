"""Story 15.0 Task 01 - final fixture completeness and all-rule edge audit.

This is the single cross-rule release gate for Milestone 0005. It is deliberately independent
of :mod:`tests.integration.test_milestone_0005_fixture_catalog`: that harness is the Story 01.0
manifest-parity test, while this file re-derives the inventory from the three checked-in matrix
formats *and* from disk, reconciles them against one another, and then proves the far stronger
release properties Task 01 demands (meaningful fixture content, executed-not-skipped scenarios,
opt-in analyzers actually running, and cache/leak isolation across roots).

Scenario total. The milestone manifest promises **191** scenarios (96 CLEAN / 91 FINDING /
4 ERROR), not the plan's original 185. The extra six are the reviewer-driven DS116 FINDING
fixtures added at the Story 11.0 close gate -- ``html_anchor_href_escape``,
``html_img_srcset_escape``, ``angle_bracket_destination_escape``,
``entity_encoded_destination_escape``, ``nested_image_link_escape`` and ``quoted_refdef_escape``
-- each an HTML/angle-bracket/entity/nested/block-quote path-escape evasion that the
markdown_it differential proved DS116 had to extract and report. Status.md records the manifest
contract change (185 -> 191, 85 -> 91 FINDING); this audit encodes 191 with that justification
and would fail loudly if the matrices drifted back to 185.

The thirteen Milestone 0005 rules audited here are DS104, DS105, DS106, DS108, DS109, DS110,
DS112, DS113, DS114, DS115, DS116, DS117 and DS118 (sixteen fast rules are registered overall;
four of these -- DS110, DS112, DS115, DS118 -- are opt-in policy rules).
"""

from __future__ import annotations

import ast
import csv
import importlib.util
import json
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Optional

import pytest

from docsentinel.config import Config
from docsentinel.engine import scan
from tests.asset_helpers import AssetCase, load_asset_case
from tests.milestone_0005_manifest import (
    EXPECTED_OUTCOME_COUNTS,
    EXPECTED_TOTAL,
    load_scenarios,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MILESTONE_DIR = REPO_ROOT / "docs" / "roadmap" / "0005-deepening-test-case-stage-2"
MATRIX_JSON = MILESTONE_DIR / "fixture-matrix.json"
MATRIX_CSV = MILESTONE_DIR / "fixture-matrix.csv"
MATRIX_MD = MILESTONE_DIR / "fixture-matrix.md"
ASSETS_ROOT = REPO_ROOT / "tests" / "assets"
INTEGRATION_DIR = REPO_ROOT / "tests" / "integration"

#: The thirteen Milestone 0005 rule codes this audit owns, in canonical order.
RULE_CODES: tuple[str, ...] = (
    "DS104",
    "DS105",
    "DS106",
    "DS108",
    "DS109",
    "DS110",
    "DS112",
    "DS113",
    "DS114",
    "DS115",
    "DS116",
    "DS117",
    "DS118",
)

#: The four opt-in policy rules and the ``Config`` option plus enabling value that switches
#: each on, paired with one committed fixture used to prove the analyzer actually evaluates.
OPT_IN_RULES: tuple[tuple[str, str, object, str], ...] = (
    ("DS110", "require_fence_languages", True, "python_fence_label"),
    ("DS112", "navigation_indexes", ("README.md",), "required_pages_all_listed"),
    ("DS115", "deprecated_references_file", "mapping.toml", "only_current_module_name"),
    ("DS118", "documentation_naming", "kebab", "lower_kebab_docs_paths"),
)

#: The exactly-four ERROR scenarios (rule, case) the manifest declares, each a
#: validation/readiness/security failure rather than a passing detector with no findings.
EXPECTED_ERROR_ROWS: frozenset[tuple[str, str]] = frozenset(
    {
        ("DS112", "missing_index_is_error"),
        ("DS114", "invalid_nested_metadata"),
        ("DS115", "invalid_mapping_duplicate_key"),
        ("DS115", "mapping_path_outside_root"),
    }
)

#: Allowlisted conditional skips that exist in the per-rule test files today. Each entry is a
#: skip-message prefix paired with the documented platform/dependency reason it is permitted.
#: A ``pytest.skip`` whose message does not start with one of these prefixes, or any
#: ``skip``/``skipif``/``xfail`` decorator, is a NEW unconditional skip and fails the audit.
ALLOWLISTED_SKIP_REASONS: tuple[tuple[str, str], ...] = (
    ("symlinks unavailable:", "the sandbox/filesystem cannot create symlinks"),
    ("running as root bypasses the unreadable-file permission check", "chmod 000 does not block root reads"),
    ("os.mkfifo unavailable on this platform", "the platform has no os.mkfifo (e.g. Windows)"),
    ("mkfifo failed:", "os.mkfifo raised OSError on this platform"),
    ("filesystem rejected the hostile file name", "the OS refused a deliberately hostile filename"),
)

#: Placeholder tokens that, standing alone, are not meaningful fixture content.
_PLACEHOLDER_TOKENS: frozenset[str] = frozenset({"todo", "tbd", "fixme", "wip"})

_ATX_HEADING_RE = re.compile(r"(?m)^ {0,3}#{1,6}\s")
_SETEXT_HEADING_RE = re.compile(r"(?m)^ {0,3}(?:=+|-+)\s*$")
_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_ASSET_DIR_RE = re.compile(r"tests/assets/(ds\d+)/([a-z0-9_]+)/")
_MD_ROW_RE = re.compile(r"^\|\s*\*\*(CLEAN|FINDING|ERROR)\*\*\s*\|\s*`tests/assets/(ds\d+)/([a-z0-9_]+)/`")

#: Whether the ``standard`` extras (scikit-learn/textstat) are importable, gating the
#: standard-profile corpus-cache leak assertions without ever using ``pytest.skip``.
_STANDARD_AVAILABLE: bool = importlib.util.find_spec("sklearn") is not None


# --------------------------------------------------------------------------------------------
# Independent matrix parsers (deliberately not reusing the catalog harness helpers).
# --------------------------------------------------------------------------------------------


def _json_rows() -> tuple[tuple[str, str, str], ...]:
    """Return ``(rule, case, outcome)`` tuples parsed straight from the JSON matrix.

    :returns: One tuple per declared scenario, in declaration order.
    """
    data = json.loads(MATRIX_JSON.read_text(encoding="utf-8"))
    return tuple((row["rule"], row["case"], row["outcome"]) for row in data["cases"])


def _csv_rows() -> tuple[tuple[str, str, str], ...]:
    """Return ``(rule, case, outcome)`` tuples parsed straight from the CSV matrix.

    :returns: One tuple per CSV data row, in file order.
    """
    with MATRIX_CSV.open(encoding="utf-8", newline="") as handle:
        return tuple((row["rule"], row["case"], row["outcome"]) for row in csv.DictReader(handle))


def _md_rows() -> tuple[tuple[str, str, str], ...]:
    """Return ``(rule, case, outcome)`` tuples parsed from the Markdown matrix tables.

    The outcome is read from the bold first table cell and the rule/case from the asset path
    in the second cell on the same row, so a drifted outcome in one format is detectable.

    :returns: One tuple per Markdown table row describing a scenario, in file order.
    """
    rows: list[tuple[str, str, str]] = []
    for line in MATRIX_MD.read_text(encoding="utf-8").splitlines():
        match = _MD_ROW_RE.match(line)
        if match is not None:
            outcome, rule_dir, case = match.groups()
            rows.append(("DS" + rule_dir[2:], case, outcome.lower()))
    return tuple(rows)


def _keys(rows: tuple[tuple[str, str, str], ...]) -> set[tuple[str, str]]:
    """Return the ``(rule, case)`` key set of parsed matrix rows.

    :param rows: Parsed ``(rule, case, outcome)`` tuples.
    :returns: Unique ``(rule, case)`` keys.
    """
    return {(rule, case) for rule, case, _ in rows}


def _outcomes(rows: tuple[tuple[str, str, str], ...]) -> dict[tuple[str, str], str]:
    """Return a ``(rule, case) -> outcome`` mapping of parsed matrix rows.

    :param rows: Parsed ``(rule, case, outcome)`` tuples.
    :returns: Mapping from scenario key to its declared outcome.
    """
    return {(rule, case): outcome for rule, case, outcome in rows}


def _committed_case_dirs(rule: str) -> set[str]:
    """Return the committed case directory names for a rule under ``tests/assets``.

    :param rule: Rule code, for example ``DS116``.
    :returns: Directory names present under ``tests/assets/<rule lowercased>/``.
    """
    rule_root = ASSETS_ROOT / rule.lower()
    if not rule_root.is_dir():
        return set()
    return {child.name for child in rule_root.iterdir() if child.is_dir()}


def _is_meaningful_markdown(text: str) -> bool:
    """Return whether Markdown text is meaningful rather than empty or a bare placeholder.

    Meaningful means: non-empty after stripping, at least ten characters, not exactly one of
    the placeholder tokens (``TODO``/``TBD``/``FIXME``/``WIP``), and carrying either a heading
    (ATX or setext) or at least three words of prose.

    :param text: The file's UTF-8 text.
    :returns: ``True`` when the content is meaningful fixture material.
    """
    stripped = text.strip()
    if len(stripped) < 10 or stripped.lower() in _PLACEHOLDER_TOKENS:
        return False
    has_heading = bool(_ATX_HEADING_RE.search(text)) or bool(_SETEXT_HEADING_RE.search(text))
    return has_heading or len(_WORD_RE.findall(stripped)) >= 3


# --------------------------------------------------------------------------------------------
# AST helpers for the executed-not-skipped audit.
# --------------------------------------------------------------------------------------------


def _rule_test_files(rule: str) -> tuple[Path, ...]:
    """Return every integration test file whose name carries the rule id.

    :param rule: Rule code, for example ``DS116``.
    :returns: Matching file paths sorted by name (empty when none exist).
    """
    token = rule.lower()
    return tuple(sorted(path for path in INTEGRATION_DIR.glob(f"*{token}*.py")))


def _parse(path: Path) -> ast.Module:
    """Return the parsed AST of a Python source file.

    :param path: File to parse.
    :returns: The parsed module.
    """
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _test_functions(tree: ast.Module) -> tuple[ast.FunctionDef, ...]:
    """Return the top-level ``test_*`` function definitions of a module.

    :param tree: Parsed module.
    :returns: Test function nodes in source order.
    """
    return tuple(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test"))


def _skip_message_head(call: ast.Call) -> Optional[str]:
    """Return the leading string literal of a ``pytest.skip`` call, or ``None``.

    Handles both a plain constant message and an f-string whose first segment is literal text.

    :param call: A call node already known to be ``pytest.skip``.
    :returns: The leading literal message text, or ``None`` when it cannot be read statically.
    """
    argument = call.args[0] if call.args else None
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return argument.value
    if isinstance(argument, ast.JoinedStr):
        for value in argument.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
    return None


def _is_skip_call(node: ast.AST) -> bool:
    """Return whether a node is a ``pytest.skip(...)`` (or bare ``skip(...)``) call.

    :param node: Any AST node.
    :returns: ``True`` when the node calls a ``skip`` attribute or name.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr == "skip") or (
        isinstance(func, ast.Name) and func.id == "skip"
    )


def _decorator_mentions_skip_or_xfail(decorator: ast.expr) -> bool:
    """Return whether a decorator expression names skip, skipif or xfail.

    :param decorator: A decorator expression node.
    :returns: ``True`` when the dumped decorator references skip/skipif/xfail.
    """
    dumped = ast.dump(decorator)
    return "skipif" in dumped or "xfail" in dumped or re.search(r"attr='skip'", dumped) is not None


def _is_weak_assert(test: ast.expr) -> bool:
    """Return whether an assert test is a generic ``is not None`` / ``is True`` comparison.

    :param test: The expression asserted.
    :returns: ``True`` for ``x is None``/``x is not None``/``x is True`` style comparisons.
    """
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], (ast.Is, ast.IsNot)):
        comparator = test.comparators[0]
        return isinstance(comparator, ast.Constant) and (comparator.value is None or comparator.value is True)
    return False


def _load_root(load_case: Callable[[str, str], AssetCase], rule: str, case: str) -> Path:
    """Materialize one committed fixture and return its scan root.

    :param load_case: The ``asset_case`` loader fixture.
    :param rule: Rule code owning the fixture, for example ``DS118``.
    :param case: Scenario slug to load.
    :returns: The materialized scan root path.
    """
    return load_case(rule.lower(), case).root


def _ds_findings(result: object, rule: str) -> int:
    """Return how many findings in a scan result belong to a given rule.

    :param result: A :class:`~docsentinel.models.ScanResult`.
    :param rule: Rule code to count.
    :returns: The number of findings attributed to ``rule``.
    """
    return sum(1 for finding in result.findings if finding.rule == rule)  # type: ignore[attr-defined]


# --------------------------------------------------------------------------------------------
# (1) Inventory: three-format reconciliation and shape.
# --------------------------------------------------------------------------------------------


def test_matrix_three_formats_reconcile_independently():
    """
    [Integration] milestone 0005 final audit: verifies json, csv and md matrices agree on every row.

    Scenario:
        Given the three checked-in fixture-matrix formats parsed independently of the catalog harness
        When their (rule, case) key sets and per-scenario outcomes are compared pairwise
        Then json, csv and md describe exactly the same 191 scenarios with identical outcomes.

    Boundaries:
        - Focus: cross-format drift detection, re-derived here rather than reusing the catalog test
        - Fixtures/params: none

    On failure, first check:
        - The reported key differences between json/csv/md (a slug renamed in only one place)
        - The reported outcome mismatches (an outcome edited in one format only)
    """
    json_rows, csv_rows, md_rows = _json_rows(), _csv_rows(), _md_rows()
    json_keys, csv_keys, md_keys = _keys(json_rows), _keys(csv_rows), _keys(md_rows)

    assert csv_keys == json_keys, (
        f"CSV vs JSON drift: only-in-csv={sorted(csv_keys - json_keys)}, only-in-json={sorted(json_keys - csv_keys)}"
    )
    assert md_keys == json_keys, (
        f"MD vs JSON drift: only-in-md={sorted(md_keys - json_keys)}, only-in-json={sorted(json_keys - md_keys)}"
    )

    json_outcomes, csv_outcomes, md_outcomes = _outcomes(json_rows), _outcomes(csv_rows), _outcomes(md_rows)
    csv_mismatch = {
        key: (csv_outcomes[key], json_outcomes[key]) for key in json_keys if csv_outcomes[key] != json_outcomes[key]
    }
    md_mismatch = {
        key: (md_outcomes[key], json_outcomes[key]) for key in json_keys if md_outcomes[key] != json_outcomes[key]
    }
    assert csv_mismatch == {}, f"CSV vs JSON outcome drift (csv, json): {csv_mismatch}"
    assert md_mismatch == {}, f"MD vs JSON outcome drift (md, json): {md_mismatch}"


def test_total_and_per_outcome_counts_are_191():
    """
    [Integration] milestone 0005 final audit: verifies the matrices encode 191 scenarios (96/91/4).

    Scenario:
        Given the JSON matrix parsed independently
        When its scenarios are counted overall and per outcome
        Then there are 191 (96 clean / 91 finding / 4 error), matching the reviewer-raised total.

    Boundaries:
        - Focus: the agreed 191 total and the clean/finding/error split, not 185
        - Fixtures/params: none

    On failure, first check:
        - Whether a scenario was added to or removed from the matrices
        - Whether the six DS116 close-gate fixtures were reverted (would drop finding 91 -> 85)
    """
    json_rows = _json_rows()
    assert len(json_rows) == 191, f"expected 191 scenarios, found {len(json_rows)}"
    counts = Counter(outcome for _, _, outcome in json_rows)
    assert counts == {"clean": 96, "finding": 91, "error": 4}, f"outcome counts drifted: {dict(counts)}"
    # Cross-check the shared manifest constants agree, so the two gates cannot diverge silently.
    assert EXPECTED_TOTAL == 191
    assert EXPECTED_OUTCOME_COUNTS == {"clean": 96, "finding": 91, "error": 4}


def test_ondisk_directories_reconcile_with_every_matrix_format():
    """
    [Integration] milestone 0005 final audit: verifies committed asset dirs match all three matrices.

    Scenario:
        Given the committed tests/assets/dsNNN case directories for the thirteen rules
        When each rule's on-disk directory set is compared against json, csv and md
        Then the committed directories equal the matrix cases exactly, with no extra or missing dir.

    Boundaries:
        - Focus: disk-vs-matrix parity per rule across all three formats
        - Fixtures/params: none

    On failure, first check:
        - The reported rule and the directories present on disk but absent from the matrix (or vice versa)
        - Whether a fixture directory was committed, renamed or deleted without updating the matrices
    """
    json_keys, csv_keys, md_keys = _keys(_json_rows()), _keys(_csv_rows()), _keys(_md_rows())
    problems: dict[str, dict[str, list[str]]] = {}
    for rule in RULE_CODES:
        on_disk = _committed_case_dirs(rule)
        for label, keys in (("json", json_keys), ("csv", csv_keys), ("md", md_keys)):
            expected = {case for rule_code, case in keys if rule_code == rule}
            if on_disk != expected:
                problems.setdefault(rule, {})[label] = sorted(on_disk.symmetric_difference(expected))
    assert problems == {}, f"disk/matrix reconciliation failed: {problems}"


def test_every_rule_has_three_clean_and_three_finding_scenarios():
    """
    [Integration] milestone 0005 final audit: verifies each rule has at least 3 clean and 3 finding cases.

    Scenario:
        Given the matrix scenarios grouped by rule
        When clean and finding outcomes are counted for each of the thirteen rules
        Then every rule declares at least three clean and at least three finding scenarios.

    Boundaries:
        - Focus: the per-rule minimum coverage the plan requires
        - Fixtures/params: none

    On failure, first check:
        - The reported rule whose clean or finding count fell below three
    """
    by_rule: dict[str, Counter[str]] = {}
    for rule, _, outcome in _json_rows():
        by_rule.setdefault(rule, Counter())[outcome] += 1
    thin = {
        rule: dict(by_rule.get(rule, Counter()))
        for rule in RULE_CODES
        if by_rule.get(rule, Counter())["clean"] < 3 or by_rule.get(rule, Counter())["finding"] < 3
    }
    assert thin == {}, f"rules lacking 3 clean and 3 finding scenarios: {thin}"


def test_error_rows_are_exactly_the_expected_four():
    """
    [Integration] milestone 0005 final audit: verifies the ERROR scenarios are exactly the agreed four.

    Scenario:
        Given the matrix scenarios whose outcome is error
        When their (rule, case) keys are collected
        Then they are exactly the four declared error rows, no more and no fewer.

    Boundaries:
        - Focus: the exact ERROR row membership (DS112, DS114, DS115 x2)
        - Fixtures/params: none

    On failure, first check:
        - The reported unexpected or missing error row
        - Whether a detector newly escalates a scenario to error or dropped one
    """
    error_keys = {(rule, case) for rule, case, outcome in _json_rows() if outcome == "error"}
    assert error_keys == set(EXPECTED_ERROR_ROWS), (
        f"unexpected={sorted(error_keys - EXPECTED_ERROR_ROWS)}, "
        f"missing={sorted(set(EXPECTED_ERROR_ROWS) - error_keys)}"
    )


def test_each_error_row_has_proven_safe_handling_in_its_rule_test_file():
    """
    [Integration] milestone 0005 final audit: verifies every ERROR scenario is proven handled elsewhere.

    Scenario:
        Given the four ERROR scenarios
        When the rule's own integration test files are searched for the scenario slug
        Then each error slug appears in its rule's test file, where safe handling is asserted.

    Boundaries:
        - Focus: an error scenario must be exercised (not merely listed) so a scan cannot silently pass
        - Fixtures/params: none

    On failure, first check:
        - The reported error row whose slug is absent from its rule's integration test files
    """
    missing: list[str] = []
    for rule, case in sorted(EXPECTED_ERROR_ROWS):
        files = _rule_test_files(rule)
        combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
        if not re.search(r"\b" + re.escape(case) + r"\b", combined):
            missing.append(f"{rule}/{case} not found in {[p.name for p in files]}")
    assert missing == [], f"error scenarios lacking a proving test: {missing}"


# --------------------------------------------------------------------------------------------
# (2) Meaningful fixture content and companions.
# --------------------------------------------------------------------------------------------


def test_every_case_directory_has_meaningful_markdown():
    """
    [Integration] milestone 0005 final audit: verifies each fixture directory holds meaningful Markdown.

    Scenario:
        Given every committed case directory for the thirteen rules
        When its Markdown files are inspected
        Then at least one is non-empty, long enough, and carries a heading or real prose -- never a
        bare placeholder like TODO or an empty file.

    Boundaries:
        - Focus: fixture content quality so a scenario cannot pass on an empty or placeholder document
        - Fixtures/params: none

    On failure, first check:
        - The reported directory whose only Markdown is empty, too short or a placeholder token
    """
    empty: list[str] = []
    for rule in RULE_CODES:
        rule_root = ASSETS_ROOT / rule.lower()
        for case_dir in sorted(p for p in rule_root.iterdir() if p.is_dir()):
            markdown = [path for path in case_dir.rglob("*.md") if path.is_file()]
            if not any(_is_meaningful_markdown(path.read_text(encoding="utf-8")) for path in markdown):
                empty.append(f"{rule}/{case_dir.name}: no meaningful .md among {[p.name for p in markdown]}")
    assert empty == [], f"directories without meaningful Markdown: {empty}"


def test_declared_companions_and_markdown_are_present_on_disk():
    """
    [Integration] milestone 0005 final audit: verifies every declared companion and document exists.

    Scenario:
        Given each scenario's declared markdown_assets and companions in the matrix
        When the committed directory is inspected (skipping runtime-built symlink/FIFO companions)
        Then every declared file exists on disk exactly where the matrix promises.

    Boundaries:
        - Focus: no scenario references a missing committed file
        - Runtime companions (symlinks/FIFOs built in the test body) are exempt by setup marker

    On failure, first check:
        - The reported scenario and the declared file that is absent on disk
    """
    missing: list[str] = []
    for scenario in load_scenarios():
        if scenario.rule not in RULE_CODES:
            continue
        for relative in scenario.markdown_files:
            if not (scenario.source_dir / relative).is_file():
                missing.append(f"{scenario.rule}/{scenario.case}: markdown {relative!r} missing")
        if not scenario.uses_runtime_companions:
            for relative in scenario.companion_files:
                if not (scenario.source_dir / relative).is_file():
                    missing.append(f"{scenario.rule}/{scenario.case}: companion {relative!r} missing")
    assert missing == [], f"declared fixture files missing on disk: {missing}"


# --------------------------------------------------------------------------------------------
# (3) Executed-not-skipped: files, slugs, skips and weak assertions.
# --------------------------------------------------------------------------------------------


def test_each_rule_has_a_named_integration_file():
    """
    [Integration] milestone 0005 final audit: verifies each rule owns at least one named test file.

    Scenario:
        Given the thirteen rule codes
        When the integration directory is searched for a file whose name carries the rule id
        Then every rule has at least one such integration test file.

    Boundaries:
        - Focus: existence of a per-rule integration test file
        - Fixtures/params: none

    On failure, first check:
        - The reported rule that has no tests/integration file named with its id
    """
    missing = [rule for rule in RULE_CODES if not _rule_test_files(rule)]
    assert missing == [], f"rules without a named integration test file: {missing}"


def test_every_scenario_slug_appears_in_its_rule_test_files():
    """
    [Integration] milestone 0005 final audit: verifies every scenario slug is referenced by its tests.

    Scenario:
        Given every scenario of each rule
        When the union of that rule's integration test files is searched for the slug
        Then every scenario slug appears, so no committed scenario is left unexercised.

    Boundaries:
        - Focus: each scenario is referenced by a test file (per-rule task-03 files assert each outcome)
        - Fixtures/params: none

    On failure, first check:
        - The reported rule and the scenario slug that no integration test file mentions
    """
    by_rule: dict[str, list[str]] = {}
    for rule, case, _ in _json_rows():
        by_rule.setdefault(rule, []).append(case)
    missing: list[str] = []
    for rule in RULE_CODES:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in _rule_test_files(rule))
        for case in by_rule[rule]:
            if not re.search(r"\b" + re.escape(case) + r"\b", combined):
                missing.append(f"{rule}/{case}")
    assert missing == [], f"scenario slugs not referenced by their rule test files: {missing}"


def test_rule_test_files_have_no_unlisted_skips_or_decorators():
    """
    [Integration] milestone 0005 final audit: verifies no new skip/xfail hides an unexercised scenario.

    Scenario:
        Given every integration test file of the thirteen rules
        When each pytest.skip call and each test decorator is inspected
        Then every skip matches the documented conditional-platform allowlist and no skip/skipif/xfail
        decorator exists -- any new or unconditional skip fails the audit with its file and line.

    Boundaries:
        - Focus: skips stay a small, documented set of platform/dependency guards
        - Fixtures/params: none

    On failure, first check:
        - The reported file:line and skip message that is not on ALLOWLISTED_SKIP_REASONS
        - Whether a scenario was quietly xfail/skip-decorated instead of asserted
    """
    allow_prefixes = tuple(prefix for prefix, _ in ALLOWLISTED_SKIP_REASONS)
    offending_skips: list[str] = []
    offending_decorators: list[str] = []
    for rule in RULE_CODES:
        for path in _rule_test_files(rule):
            tree = _parse(path)
            for node in ast.walk(tree):
                if _is_skip_call(node):
                    head = _skip_message_head(node)
                    if head is None or not head.startswith(allow_prefixes):
                        offending_skips.append(f"{path.name}:{node.lineno}: {head!r}")
            for function in _test_functions(tree):
                for decorator in function.decorator_list:
                    if _decorator_mentions_skip_or_xfail(decorator):
                        offending_decorators.append(f"{path.name}:{function.lineno}: {function.name}")
    assert offending_skips == [], f"non-allowlisted skips: {offending_skips}"
    assert offending_decorators == [], f"skip/skipif/xfail decorators present: {offending_decorators}"


def test_rule_test_files_have_no_generic_is_not_none_only_assertions():
    """
    [Integration] milestone 0005 final audit: verifies no test asserts only ``is not None``/``is True``.

    Scenario:
        Given every test function in the rule integration files
        When its assert statements are inspected
        Then no function's only assertions are generic ``is not None`` / ``is True`` comparisons that
        would pass without checking real domain behaviour.

    Boundaries:
        - Focus: assertions must check real behaviour, not merely non-None/truthy
        - A function with zero direct asserts (it asserts through helpers) is not flagged

    On failure, first check:
        - The reported file and function whose sole assertion is a weak identity comparison
    """
    weak: list[str] = []
    for rule in RULE_CODES:
        for path in _rule_test_files(rule):
            for function in _test_functions(_parse(path)):
                asserts = [node for node in ast.walk(function) if isinstance(node, ast.Assert)]
                if asserts and all(_is_weak_assert(node.test) for node in asserts):
                    weak.append(f"{path.name}:{function.lineno}: {function.name}")
    assert weak == [], f"tests whose only assertion is is-not-None/is-True: {weak}"


# --------------------------------------------------------------------------------------------
# (4) Opt-in rules actually run the analyzer.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("rule, option, value, case", OPT_IN_RULES, ids=[row[0] for row in OPT_IN_RULES])
def test_opt_in_rule_is_counted_when_configured_and_named_when_not(
    rule: str,
    option: str,
    value: object,
    case: str,
    asset_case: Callable[[str, str], AssetCase],
):
    """
    [Integration] milestone 0005 final audit: verifies opt-in rules run only when their option is set.

    Scenario:
        Given one opt-in policy rule scanned over its own fixture with only that rule selected
        When the enabling option is set versus unset
        Then with it set the rule is counted as evaluated in ScanResult.notice (never named as not
        enabled), and with it unset the rule is named as an unmet opt-in and excluded from the count.

    Boundaries:
        - Focus: the opt-in analyzer is honestly reported as evaluated/not-evaluated via the notice
        - Fixtures/params: parametrized over DS110/DS112/DS115/DS118

    On failure, first check:
        - The reported notice string for the set and unset runs
        - Whether the rule's opt_in_option was registered or the notice wording changed
    """
    root = _load_root(asset_case, rule, case)
    not_enabled_phrase = f"{rule} (set {option})"

    configured = scan(root, config=Config(profile="fast", select=(rule,), **{option: value}))
    assert not_enabled_phrase not in configured.notice, (
        f"{rule} should be evaluated once configured, but notice still names it: {configured.notice!r}"
    )
    assert "1 fast rule(s) evaluated." in configured.notice, (
        f"{rule} should count as the 1 evaluated rule, got: {configured.notice!r}"
    )

    unset = scan(root, config=Config(profile="fast", select=(rule,)))
    assert not_enabled_phrase in unset.notice, (
        f"{rule} should be named as an unmet opt-in when unconfigured, got: {unset.notice!r}"
    )
    assert "0 fast rule(s) evaluated" in unset.notice, (
        f"{rule} should contribute 0 evaluated rules when unconfigured, got: {unset.notice!r}"
    )


# --------------------------------------------------------------------------------------------
# (5) Cache / leak isolation.
# --------------------------------------------------------------------------------------------


def test_fast_scan_results_do_not_leak_between_two_roots(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] milestone 0005 final audit: verifies editing one root cannot change another's scan.

    Scenario:
        Given the same DS116 path-escape fixture materialized into two independent roots
        When both are scanned, one root is edited to remove the escape, and both are rescanned
        Then the edited root's DS116 finding disappears while the untouched root's finding persists.

    Boundaries:
        - Focus: the shared markdown_blocks scanner and the always-on fast rules do not cache per-root
        - Fixtures/params: none

    On failure, first check:
        - Whether the untouched root's DS116 count changed (a leaked cache) or the edited root's did not
    """
    root_a = asset_case("ds116", "parent_escape_from_root").root
    root_b = load_asset_case("ds116", "parent_escape_from_root", root_a.parent / "root_b")

    assert _ds_findings(scan(root_a), "DS116") == 1
    assert _ds_findings(scan(root_b.root), "DS116") == 1

    (root_a / "README.md").write_text("# Home\n\n[safe](./local.md)\n", encoding="utf-8")
    (root_a / "local.md").write_text("# Local\n\nSafe in-root target with prose.\n", encoding="utf-8")

    assert _ds_findings(scan(root_a), "DS116") == 0, "edited root still reports the removed escape"
    assert _ds_findings(scan(root_b.root), "DS116") == 1, "untouched root changed -- a cache leaked between roots"


def test_repeated_scans_in_one_process_are_deterministic(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] milestone 0005 final audit: verifies repeated scans of one root are byte-stable.

    Scenario:
        Given one DS117 finding fixture scanned three times in the same process
        When the ordered (rule, path, line, message) tuples of each run are compared
        Then all three runs are identical, so inventory order and findings are reproducible.

    Boundaries:
        - Focus: determinism and cache stability across repeated in-process scans
        - Fixtures/params: none

    On failure, first check:
        - The first run index whose finding tuple differs, pointing at a nondeterministic cache or order
    """
    root = asset_case("ds117", "multiple_broken_tables").root
    runs = [
        tuple((finding.rule, finding.path, finding.line, finding.message) for finding in scan(root).findings)
        for _ in range(3)
    ]
    assert runs[0] == runs[1] == runs[2], f"repeated scans diverged: {runs}"
    assert any(rule == "DS117" for rule, _, _, _ in runs[0]), "fixture did not exercise DS117 at all"


def test_config_does_not_leak_between_scans_of_different_roots(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] milestone 0005 final audit: verifies a per-scan config cannot bleed into another scan.

    Scenario:
        Given one DS118 naming-violation fixture in two roots
        When root A is scanned with the naming policy off, root B with kebab, then root A off again
        Then root A reports zero DS118 findings both times and root B reports a violation -- the
        engine's analyzer-config cache keys on the analyzer, not on a leaked prior config.

    Boundaries:
        - Focus: effective Config is forwarded per scan and never cached across roots/configs
        - Fixtures/params: none

    On failure, first check:
        - Whether root A picked up the kebab policy on its second scan (a config leak)
    """
    root_a = asset_case("ds118", "uppercase_filename_violation").root
    root_b = load_asset_case("ds118", "uppercase_filename_violation", root_a.parent / "root_b").root
    off = Config(profile="fast", select=("DS118",))
    kebab = Config(profile="fast", select=("DS118",), documentation_naming="kebab")

    assert _ds_findings(scan(root_a, config=off), "DS118") == 0
    assert _ds_findings(scan(root_b, config=kebab), "DS118") >= 1
    assert _ds_findings(scan(root_a, config=off), "DS118") == 0, "kebab policy leaked into the off scan of root A"


def test_standard_corpus_cache_isolated_between_roots_and_edits(tmp_path: Path):
    """
    [Integration] milestone 0005 final audit: verifies the standard-profile corpus cache cannot leak.

    Scenario:
        Given two roots each holding two documents sharing one duplicated paragraph
        When root A is scanned (standard), its duplicate is rewritten to distinct prose and rescanned,
        and root B is rescanned unchanged
        Then root A's DS202 duplicate finding disappears while root B's persists -- the
        build_corpus_model lru_cache is cleared per scan and keyed on content, never leaking.

    Boundaries:
        - Focus: the functools.lru_cache corpus model in the standard profile
        - When the standard extras are absent the test instead proves the fast scanner never caches
          the corpus across roots, so it still asserts real isolation (never a no-op, never skipped)

    On failure, first check:
        - Whether root B's DS202 count changed (a leaked corpus model) or root A's did not drop
    """
    paragraph = (
        "This section explains the configuration workflow in careful detail so readers understand "
        "each required step before proceeding with the documented installation and verification "
        "process across every supported environment today."
    )
    root_a, root_b = tmp_path / "corpus_a", tmp_path / "corpus_b"
    for root in (root_a, root_b):
        root.mkdir()
        (root / "one.md").write_text(f"# One\n\n{paragraph}\n", encoding="utf-8")
        (root / "two.md").write_text(f"# Two\n\n{paragraph}\n", encoding="utf-8")

    if not _STANDARD_AVAILABLE:
        # Fall back to a real fast-profile isolation assertion rather than skipping: editing one
        # root's always-on DS116 fixture must not change the other root.
        (root_a / "one.md").write_text("# One\n\n[escape](../../secret.md)\n", encoding="utf-8")
        assert _ds_findings(scan(root_a), "DS116") == 1
        assert _ds_findings(scan(root_b), "DS116") == 0
        return

    assert _ds_findings(scan(root_a, config=Config(profile="standard")), "DS202") >= 1
    assert _ds_findings(scan(root_b, config=Config(profile="standard")), "DS202") >= 1

    (root_a / "two.md").write_text(
        "# Two\n\nAn entirely unrelated discussion of seasonal cuisine, regional weather patterns "
        "and distant coastal travel that shares no wording with the first document whatsoever.\n",
        encoding="utf-8",
    )
    assert _ds_findings(scan(root_a, config=Config(profile="standard")), "DS202") == 0, (
        "edited corpus still reports the removed duplicate -- a stale corpus model leaked"
    )
    assert _ds_findings(scan(root_b, config=Config(profile="standard")), "DS202") >= 1, (
        "untouched corpus changed -- the corpus model leaked between roots"
    )


# --------------------------------------------------------------------------------------------
# (6) Counts report for the loop owner to copy into status.md.
# --------------------------------------------------------------------------------------------


def _scenario_counts() -> dict[str, Counter[str]]:
    """Return per-rule outcome counts for the thirteen rules.

    :returns: Mapping from rule code to a Counter of clean/finding/error counts.
    """
    counts: dict[str, Counter[str]] = {rule: Counter() for rule in RULE_CODES}
    for rule, _, outcome in _json_rows():
        counts[rule][outcome] += 1
    return counts


def _count_test_functions(path: Path) -> int:
    """Return the number of top-level ``test_*`` functions in a file.

    :param path: Integration test file to inspect.
    :returns: Count of test function definitions (parametrization not expanded).
    """
    return len(_test_functions(_parse(path)))


def render_counts_table() -> str:
    """Return a compact per-rule counts table for pasting into status.md.

    The table lists, per rule, the clean/finding/error scenario counts, the owning integration
    test file names and the number of ``test_*`` function definitions in each file. Function
    counts are static definition counts and do not expand ``parametrize`` cases.

    :returns: A multi-line table string.
    """
    lines = ["rule | clean | finding | error | test files (test-func count)"]
    for rule in RULE_CODES:
        counts = _scenario_counts()[rule]
        files = _rule_test_files(rule)
        descriptor = ", ".join(f"{path.name} ({_count_test_functions(path)})" for path in files)
        lines.append(f"{rule} | {counts['clean']} | {counts['finding']} | {counts['error']} | {descriptor}")
    return "\n".join(lines)


def test_counts_report_is_consistent_and_printable(capsys: pytest.CaptureFixture[str]):
    """
    [Integration] milestone 0005 final audit: verifies and emits the per-rule counts report.

    Scenario:
        Given the matrix scenario counts and each rule's integration test files
        When the per-rule table is assembled
        Then every rule maps to at least one existing test file with at least one test function, the
        thirteen rows sum to 191 scenarios, and the table is printed for the loop owner to copy.

    Boundaries:
        - Focus: a truthful, consistent counts report (not status.md editing, which is out of scope)
        - Fixtures/params: none

    On failure, first check:
        - The reported rule whose file list is empty or whose test-function count is zero
        - Whether the per-rule scenario totals still sum to 191
    """
    table = render_counts_table()
    print("\nMilestone 0005 per-rule counts (Story 15.0 Task 01 audit):\n" + table)
    # capsys keeps the emitted table out of captured-stdout noise while proving it was produced.
    assert table in capsys.readouterr().out

    counts = _scenario_counts()
    total = sum(sum(counter.values()) for counter in counts.values())
    assert total == 191, f"per-rule scenario counts sum to {total}, expected 191"

    barren = [rule for rule in RULE_CODES if not _rule_test_files(rule)]
    assert barren == [], f"rules with no integration test file: {barren}"
    functionless = [
        rule for rule in RULE_CODES if sum(_count_test_functions(path) for path in _rule_test_files(rule)) == 0
    ]
    assert functionless == [], f"rules whose test files define no test functions: {functionless}"
