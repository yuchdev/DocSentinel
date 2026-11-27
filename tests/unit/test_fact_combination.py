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


def _sized(*lengths: int) -> tuple[fact_check.CandidateClaim, ...]:
    """Build candidates whose texts have the given lengths.

    :param lengths: The text length of each candidate, in send order.
    :returns: The candidates.
    """
    return tuple(
        fact_check.CandidateClaim(claim=SimpleNamespace(path="a.md"), text=chr(ord("a") + i) * n, score=0.9)
        for i, n in enumerate(lengths)
    )


@pytest.mark.parametrize(
    ("lengths", "ranges"),
    [
        ((), ()),
        ((1000,), ((1, 1),)),
        ((10, 20, 30), ((1, 3),)),
        ((500, 499), ((1, 2),)),
        ((500, 500), ((1, 1), (2, 2))),
        ((600, 399, 2), ((1, 2), (3, 3))),
        ((1000, 1000, 1000), ((1, 1), (2, 2), (3, 3))),
        ((1, 1000, 1), ((1, 1), (2, 2), (3, 3))),
        ((333, 333, 332, 1), ((1, 3), (4, 4))),
    ],
    ids=["empty", "one-at-bound", "fits", "join-at-1000", "join-at-1001", "split", "each-full", "big-middle", "tail"],
)
def test_pack_all_splits_at_the_1000_character_boundary(lengths: tuple[int, ...], ranges: tuple[tuple[int, int], ...]):
    """
    [Unit] fact combination 'all': verifies _pack_all packs whole claims into facts of at most 1000 characters.

    Scenario:
        Given candidates of the listed text lengths, joined by one space
        When _pack_all packs them
        Then the ranges cover every candidate in order, a join of exactly 1000 characters stays one
        fact, 1001 characters starts a new one, and all is one fact when it fits.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (all split into consecutive whole-claim facts)
        - Fixtures/params: lengths, ranges
        - Scope: fact_check._pack_all

    On failure, first check:
        - The length + added > MAX_CANDIDATE_CHARS test in _pack_all
    """
    candidates = _sized(*lengths)

    assert fact_check._pack_all(candidates) == ranges
    for group in fact_check.combine_candidates(candidates, "all"):
        assert len(group.text) <= fact_check.MAX_CANDIDATE_CHARS


def test_combine_all_is_a_single_fact_when_it_fits():
    """
    [Unit] fact combination 'all': verifies a join within the bound is one group labelled 1-n.

    Scenario:
        Given four short candidates
        When combine_candidates groups them with 'all'
        Then there is exactly one group, labelled '1-4', holding all four members.

    Boundaries:
        - Focus: the single-fact case of 'all'
        - Fixtures/params: none
        - Scope: fact_check.combine_candidates

    On failure, first check:
        - _pack_all and the FACT_COMBINATION_ALL branch of combine_candidates
    """
    candidates = _candidates(4)

    (group,) = fact_check.combine_candidates(candidates, "all")

    assert (group.label, group.members) == ("1-4", candidates)
