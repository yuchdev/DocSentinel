"""Integration tests for DS302 statement extraction over the text assets ``ds302/statements_*``.

These run the real spaCy pipeline and are skipped when the deep dependencies or model are not installed.
"""

from collections.abc import Callable

import pytest

from docsentinel.mining import nlp
from docsentinel.mining.claims import extract_claims, extract_statements
from tests.asset_helpers import AssetCase

pytestmark = pytest.mark.skipif(not nlp.deep_ready(), reason="deep dependencies and model not installed")

#: The statements of ``statements_self_contained``, in document order: one sentence each, with
#: the possessive "Its" of two sentences replaced by the noun phrase it points at.
EXPECTED_SELF_CONTAINED = (
    "The Kestrel harbour authority dredged the main channel to a depth of 14 metres in 2024.",
    "The Kestrel harbour handled 320 cargo ships and 45 ferries in 2025.",
    "The new crane of the Kestrel harbour lifted 900 containers in one day.",
    "The height of the tide reached 6 metres.",
    "The harbour.export(year=...) call writes one row per ship to report.csv.",
)

#: The statements of ``statements_resolved``, in document order; see the test docstrings for the
#: rule each one exercises.
EXPECTED_RESOLVED = (
    "A team led by Mara Velt at the Kestrel harbour authority has built a new tidal crane for the east quay.",
    "The new tidal crane lifts 900 containers per day.",
    "The new tidal crane can run on tidal power alone.",
    "The findings of the team led by Mara Velt at the Kestrel harbour authority were published in Port Engineering.",
    "The team led by Mara Velt at the Kestrel harbour authority tested the new tidal crane on the east quay in 2025.",
    "The team led by Mara Velt at the Kestrel harbour authority added a second motor.",
    "The new tidal crane weighs 40 tonnes.",
    "The quay serves the ferry berth.",
    "Jon Ferris manages 12 berths.",
    "The Kestrel harbour authority publishes tide tables every spring.",
    "The tide tables list 4 daily tides.",
)


def _statements(asset_case: Callable[[str, str], AssetCase], case_name: str) -> tuple:
    """Return the statements of an asset document.

    :param asset_case: The asset loader fixture.
    :param case_name: The ``ds302`` case directory.
    :returns: The extracted statements.
    """
    case = asset_case("ds302", case_name)
    return extract_statements(nlp.load_pipeline(), case.read_text("doc.md"), "doc.md")


def test_statements_are_self_contained_and_markdown_free(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] mining statements: verifies one clean, self-contained statement per checkable sentence.

    Scenario:
        Given a document with front matter, a heading, a bold pseudo-heading, a "Summary:" label,
        hard-wrapped lines, a quotation followed by a sentence opening with "Its", a hedged
        prediction, a lead-in ending in a colon, a code fence and a sentence with inline code
        holding an ellipsis
        When extract_statements runs over it
        Then exactly the five expected statement texts come back, in document order: every
        sentence stands alone, and each "Its ..." subject is written as "The ... of <antecedent>"

    Boundaries:
        - Focus: what is dropped, what is resolved, and the cleaned text
        - Fixtures/params: asset ds302/statements_self_contained
        - Scope: extract_statements only

    On failure, first check:
        - _prose_blocks (Markdown structure) and _strip_inline_markdown (inline syntax, label)
        - _is_quotation, _is_hedged and _is_declarative (dropped sentences)
        - _Discourse.pronoun_antecedent (the "Its new crane" and "Its height" possessives)
    """
    statements = _statements(asset_case, "statements_self_contained")

    assert tuple(s.raw_sentence for s in statements) == EXPECTED_SELF_CONTAINED
    assert all("\n" not in s.raw_sentence and "*" not in s.raw_sentence for s in statements)


def test_statement_provenance_and_signals(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] mining statements: verifies paragraph indexes and statement-wide numbers and entities.

    Scenario:
        Given the self-contained asset document
        When extract_statements runs over it
        Then each statement keeps the paragraph index of extract_claims' paragraph split, and its
        numbers and entities cover the whole statement, the resolved subject included

    Boundaries:
        - Focus: paragraph_index, object_numbers, object_entities of statements
        - Fixtures/params: asset ds302/statements_self_contained
        - Scope: extract_statements only

    On failure, first check:
        - The paragraph split in _prose_blocks (must equal extract_claims')
        - _statement_numbers (the "one of" idiom is skipped, other numbers kept)
    """
    statements = _statements(asset_case, "statements_self_contained")

    assert [s.paragraph_index for s in statements] == [2, 4, 4, 5, 9]
    assert {"14", "2024"} <= set(statements[0].object_numbers)
    assert {"320", "45", "2025"} <= set(statements[1].object_numbers)
    assert "900" in statements[2].object_numbers
    assert "DATE:2025" in statements[1].object_entities
    assert all(s.path == "doc.md" for s in statements)


def test_statements_resolve_back_references(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] mining statements: verifies pronouns and bare definite phrases are replaced by their antecedents.

    Scenario:
        Given a document whose first sentence introduces a named team (the primary agent) that
        built "a new tidal crane" (the primary artifact), followed by "The innovation ...",
        "Their findings ...", "The researchers tested the design ...", "To address this
        limitation, the engineers ...", "In addition, the crane ...", "As a result, ...",
        "It also serves ...", a quotation attributed to a named person then "He manages ...",
        "The authority publishes tide tables ...", "Those tables ...", a hedged sentence, and a
        pronoun sentence after a heading
        When extract_statements runs over it
        Then the eleven expected statements come back: the shell noun and the pronouns name the
        crane or the team, the possessive becomes "The findings of the team ...", the agent nouns
        name the team, the fronted "To address this limitation," is cut, "In addition," and
        "also" are removed, the consequence sentence and the hedged sentence are dropped, "He"
        names the quoted speaker, "The authority" names the Kestrel harbour authority, "Those
        tables" names the tide tables, and the pronoun after the heading finds no antecedent

    Boundaries:
        - Focus: the resolution, trimming and dropping rules of extract_statements
        - Fixtures/params: asset ds302/statements_resolved
        - Scope: extract_statements only

    On failure, first check:
        - _find_topic (primary agent and artifact), _Discourse.pronoun_antecedent,
          _Discourse.definite_antecedent and _Discourse.agent_antecedent
        - _rewrite_sentence (fronted modifier cut, connective and "also" removal)
        - _grounding_text (the antecedent text: appositions removed, anchoring modifiers kept)
    """
    statements = _statements(asset_case, "statements_resolved")

    assert tuple(s.raw_sentence for s in statements) == EXPECTED_RESOLVED
    assert [s.paragraph_index for s in statements] == [1, 1, 1, 1, 2, 2, 2, 2, 3, 4, 4]
    assert "PERSON:mara velt" in statements[3].object_entities  # the resolved subject counts
    assert "PERSON:jon ferris" in statements[8].object_entities


def test_coordinated_predicates_split_unless_a_time_adverbial_is_shared(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] mining statements: verifies the clause split and its time-adverbial guard.

    Scenario:
        Given a sentence with three coordinated verbs whose last one carries "every week", a
        sentence with two coordinated verbs and none, and one whose first verb carries "could"
        and whose second verb has no auxiliary of its own
        When extract_statements runs over each
        Then the first stays one statement (extract_claims still yields several triples for it),
        the second becomes one statement per verb with the shared subject repeated, and the
        third yields nothing because the second clause inherits "could" and is hedged too

    Boundaries:
        - Focus: _clauses and the hedge check after the split
        - Fixtures/params: inline text (the asset loader is only used for the pipeline guard)
        - Scope: extract_claims and extract_statements over single sentences

    On failure, first check:
        - _clauses (the time adverbial guard, the separator check, inherited auxiliaries)
        - _is_hedged on the re-parsed clause
    """
    del asset_case
    pipeline = nlp.load_pipeline()
    shared_time = "The Brenna mill grinds 40 tonnes of wheat, packs 900 bags and ships 12 lorries every week.\n"
    plain = "The Brenna mill employs 40 people and sells flour in 12 countries.\n"
    inherited_modal = "The Brenna mill could grind 40 tonnes of wheat and sell flour in 12 countries.\n"

    assert len(extract_claims(pipeline, shared_time, "mill.md")) > 1
    assert [s.raw_sentence for s in extract_statements(pipeline, shared_time, "mill.md")] == [shared_time.strip()]
    assert [s.raw_sentence for s in extract_statements(pipeline, plain, "mill.md")] == [
        "The Brenna mill employs 40 people.",
        "The Brenna mill sells flour in 12 countries.",
    ]
    assert extract_statements(pipeline, inherited_modal, "mill.md") == ()
