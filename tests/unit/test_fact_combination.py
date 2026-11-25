"""``fact_check_combination`` parsing and claim grouping (DS302 ``--fact-combination``)."""

from types import SimpleNamespace

import pytest

from docsentinel.config import Config, ConfigError, parse_fact_combination
from docsentinel.detectors import fact_check


def _candidates(count: int, path: str = "a.md") -> tuple[fact_check.CandidateClaim, ...]:
    """Build ``count`` candidates ``S1.`` ... without running claim extraction.

    :param count: How many candidates.
    :param path: The document path of every candidate.
    :returns: The candidates, in send order.
    """
    return tuple(
        fact_check.CandidateClaim(claim=SimpleNamespace(path=path), text=f"S{i}.", score=0.9)
        for i in range(1, count + 1)
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("each", "each"),
        ("all", "all"),
        ("3", ((3, 3),)),
        ("1-6,7-8,9-16", ((1, 6), (7, 8), (9, 16))),
        ("2-3,10-500", ((2, 3), (10, 500))),
    ],
)
def test_parse_accepts_keywords_and_ranges(value: str, expected: object):
    """
    [Unit] fact_check_combination: verifies the keywords and ascending ranges parse.

    Scenario:
        Given 'each', 'all' or a comma-separated list of ascending ranges
        When parse_fact_combination parses it
        Then the keyword or the (start, end) pairs come back.

    Boundaries:
        - Focus: the accepted grammar
        - Fixtures/params: five values
        - Scope: parse_fact_combination only

    On failure, first check:
        - _FACT_RANGE_RE and the ordering check in config.parse_fact_combination
    """
    assert parse_fact_combination(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "EACH", "none", "0", "0-2", "6-1", "1-501", "01", "1, 2", "1-6,", ",1", "1-3,2-4", "5,4", "1--2", 7, None],
)
def test_parse_refuses_malformed_values(value: object):
    """
    [Unit] fact_check_combination: verifies malformed, reversed, overlapping or out-of-range values are refused.

    Scenario:
        Given an empty, unknown, zero, reversed, over-500, padded, spaced, overlapping or non-string value
        When parse_fact_combination parses it
        Then ConfigError names the accepted forms.

    Boundaries:
        - Focus: fail closed on any other form
        - Fixtures/params: sixteen values
        - Scope: parse_fact_combination only

    On failure, first check:
        - The bounds and overlap checks in config.parse_fact_combination
    """
    with pytest.raises(ConfigError, match="fact_check_combination must be 'each', 'all' or"):
        parse_fact_combination(value)


def test_default_is_each():
    """
    [Unit] fact_check_combination: verifies the default keeps one request per claim.

    Scenario:
        Given a default Config
        When fact_check_combination is read
        Then it is 'each'.

    Boundaries:
        - Focus: byte-identical default behaviour
        - Fixtures/params: none
        - Scope: Config default only

    On failure, first check:
        - The Config field default in config.py
    """
    assert Config().fact_check_combination == "each"


@pytest.mark.parametrize(
    ("spec", "count", "labels"),
    [
        ("each", 3, ["1", "2", "3"]),
        ("all", 4, ["1-4"]),
        ("1-6,7-8,9-16", 16, ["1-6", "7-8", "9-16"]),
        ("1-6,7-8,9-16", 10, ["1-6", "7-8", "9-10"]),
        ("2-3", 5, ["1", "2-3", "4", "5"]),
        ("20-30", 2, ["1", "2"]),
        ("all", 0, []),
    ],
)
def test_combine_groups_in_send_order(spec: str, count: int, labels: list[str]):
    """
    [Unit] DS302 combination: verifies ranges group claims, clip to the candidates, and leave the rest alone.

    Scenario:
        Given count candidates and a combination value
        When combine_candidates groups them
        Then the groups carry the expected 1-based labels, in send order.

    Boundaries:
        - Focus: clipping, dropped ranges, unnamed claims sent alone
        - Fixtures/params: seven cases
        - Scope: combine_candidates only

    On failure, first check:
        - The loop over ranges in fact_check.combine_candidates
    """
    groups = fact_check.combine_candidates(_candidates(count), spec)

    assert [group.label for group in groups] == labels
    assert sum(len(group.members) for group in groups) == count


def test_combined_text_joins_member_texts_with_one_space():
    """
    [Unit] DS302 combination: verifies a combined fact is the member texts joined by one space.

    Scenario:
        Given three candidates combined with 'all'
        When the group text is read
        Then it is 'S1. S2. S3.'.

    Boundaries:
        - Focus: the exact text that leaves the machine
        - Fixtures/params: none
        - Scope: FactGroup.text

    On failure, first check:
        - FactGroup.text in detectors/fact_check.py
    """
    (group,) = fact_check.combine_candidates(_candidates(3), "all")

    assert group.text == "S1. S2. S3."
