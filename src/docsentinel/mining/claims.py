"""Triple extraction and claim normalization for fact-contradiction candidate detection.

Extraction is deterministic only for a pinned model version (e.g., en_core_web_sm).
A model upgrade can alter Claim output.
"""

from __future__ import annotations

import importlib
import logging
import re
import string
from dataclasses import dataclass, field
from typing import Any, Optional

import spacy.language

from docsentinel.log import safe

logger = logging.getLogger(__name__)

_CLOSED_ENTITY_TYPES: frozenset[str] = frozenset(
    {"ORG", "PRODUCT", "GPE", "PERSON", "CARDINAL", "QUANTITY", "PERCENT", "DATE"}
)

_WORD_NUMBERS: dict[str, str] = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "seventy": "70",
    "eighty": "80",
    "ninety": "90",
    "hundred": "100",
    "thousand": "1000",
    "million": "1000000",
}


@dataclass(frozen=True)
class Claim:
    """A normalized statement extracted from a document paragraph."""

    subject_key: str
    predicate_key: str
    raw_subject: str
    raw_object: str
    raw_sentence: str
    object_numbers: tuple[str, ...]
    object_entities: tuple[str, ...]
    path: str
    paragraph_index: int


def _normalize_key(text: str) -> str:
    """Lowercase, strip surrounding punctuation and articles, and collapse whitespace."""
    text = text.lower().strip()
    words = text.split()
    filtered = [w.strip(string.punctuation) for w in words if w.strip(string.punctuation) not in {"a", "an", "the"}]
    cleaned = " ".join(w for w in filtered if w)
    return cleaned.strip(string.punctuation)


def _object_numbers(span_or_tokens: Any) -> tuple[str, ...]:
    """Extract normalized numeric tokens from the object span or token list."""
    numbers: list[str] = []
    tokens = span_or_tokens if isinstance(span_or_tokens, (list, tuple)) else list(span_or_tokens)
    for tok in tokens:
        raw = tok.text if hasattr(tok, "text") else str(tok)
        raw_clean = raw.replace(",", "").strip(string.punctuation).lower()
        if raw_clean in _WORD_NUMBERS:
            numbers.append(_WORD_NUMBERS[raw_clean])
        elif re.fullmatch(r"-?\d+(?:\.\d+)?", raw_clean):
            numbers.append(raw_clean)
        elif getattr(tok, "like_num", False) and raw_clean:
            numbers.append(raw_clean)
    return tuple(numbers)


def _object_entities(span_or_doc: Any, tokens: list[Any]) -> tuple[str, ...]:
    """Extract named entities in the object span belonging to closed entity types."""
    entities: list[str] = []
    ents = getattr(span_or_doc, "ents", ())
    if not ents and tokens and hasattr(tokens[0], "doc"):
        doc = tokens[0].doc
        start = tokens[0].i
        end = tokens[-1].i + 1
        ents = [ent for ent in doc.ents if ent.start >= start and ent.end <= end]

    for ent in ents:
        if ent.label_ in _CLOSED_ENTITY_TYPES:
            norm_text = ent.text.strip().lower()
            entities.append(f"{ent.label_}:{norm_text}")
    return tuple(sorted(set(entities)))


def extract_claims(
    pipeline: spacy.language.Language,
    text: str,
    path: str,
) -> tuple[Claim, ...]:
    """Extract normalized SVO claims per paragraph from text.

    :param pipeline: The loaded spaCy pipeline used to parse each paragraph.
    :param text: The document text to split into paragraphs.
    :param path: The document's relative path, recorded as claim provenance.
    :returns: The extracted claims in paragraph then extraction order.
    """
    textacy_extract = importlib.import_module("textacy.extract")

    paragraphs = re.split(r"\n\s*\n", text)
    claims: list[Claim] = []

    for para_idx, para in enumerate(paragraphs):
        para_clean = para.strip()
        if not para_clean:
            continue
        doc = pipeline(para_clean)
        svo_extractor = getattr(
            textacy_extract, "subject_verb_object_triples", textacy_extract.triples.subject_verb_object_triples
        )
        for svo in svo_extractor(doc):
            subject_toks = list(svo.subject) if hasattr(svo.subject, "__iter__") else [svo.subject]
            verb_toks = list(svo.verb) if hasattr(svo.verb, "__iter__") else [svo.verb]
            object_toks = list(svo.object) if hasattr(svo.object, "__iter__") else [svo.object]

            raw_subject = " ".join(t.text for t in subject_toks)
            raw_predicate = " ".join(t.text for t in verb_toks)
            raw_object = " ".join(t.text for t in object_toks)

            raw_sentence = (
                subject_toks[0].sent.text if subject_toks and hasattr(subject_toks[0], "sent") else para_clean
            )

            subject_key = _normalize_key(raw_subject)
            predicate_key = _normalize_key(raw_predicate)

            # textacy >= 0.13 trims the object to its head noun ("entries" in "holds 100
            # entries"), so numbers and entities are read from the object's whole dependency
            # subtree; raw_object keeps textacy's own object text.
            obj_start = min(getattr(t, "left_edge", t).i for t in object_toks)
            obj_end = max(getattr(t, "right_edge", t).i for t in object_toks) + 1
            obj_span = doc[obj_start:obj_end]

            numbers = _object_numbers(obj_span)
            entities = _object_entities(obj_span, object_toks)

            claims.append(
                Claim(
                    subject_key=subject_key,
                    predicate_key=predicate_key,
                    raw_subject=raw_subject,
                    raw_object=raw_object,
                    raw_sentence=raw_sentence,
                    object_numbers=numbers,
                    object_entities=entities,
                    path=path,
                    paragraph_index=para_idx,
                )
            )

    logger.debug("extracted %d claims from %d paragraphs of %s", len(claims), len(paragraphs), safe(path))
    return tuple(claims)


# ---------------------------------------------------------------------------------------------
# Statement extraction (DS302 / extract-facts)
#
# ``extract_claims`` returns one Claim per subject-verb-object triple, which is the right unit for
# DS301 (it compares subject and predicate keys) but the wrong unit for an external fact-check: one
# sentence yields several triples, Markdown structure (headings, labels, hard wraps) leaks into the
# text, and a sentence such as "Their findings were published ..." means nothing on its own.
# ``extract_statements`` parses the same paragraphs with the same pipeline and returns one Claim per
# *statement*: one declarative, non-quoted, non-hedged sentence (or one clause of a coordinated
# sentence), rewritten so that it stands alone: every pronoun and bare definite noun phrase that
# points at an earlier sentence is replaced by the antecedent it names ("Their findings" -> "the
# findings of the team led by Nandita Saha"), discourse glue ("In addition,", "also") is removed,
# and a fronted clause built on an unresolvable "this" ("To overcome this limitation,") is cut.
# The resolution is classic rule-based anaphora resolution (number and animacy agreement, subject
# before object, nearest sentence first, a same-head noun match for definite noun phrases), not a
# learned coreference model, so it is deterministic for a pinned spaCy model.
# ---------------------------------------------------------------------------------------------

#: Modal auxiliaries that turn a sentence into a prediction or a possibility, which no fact-check can
#: confirm. ``can`` is not here: it states a capability ("can be integrated into existing systems").
_HEDGE_MODALS: frozenset[str] = frozenset({"could", "may", "might", "would", "should", "will", "shall", "'ll"})

#: Reporting verbs whose content clause carries the actual claim ("X says the design could ...").
_REPORTING_LEMMAS: frozenset[str] = frozenset(
    {"say", "add", "note", "explain", "tell", "state", "claim", "suggest", "believe", "think", "argue"}
)

_SUBJECT_DEPS: frozenset[str] = frozenset({"nsubj", "nsubjpass", "csubj", "csubjpass", "expl"})
_OBJECT_DEPS: frozenset[str] = frozenset({"dobj", "attr", "acomp", "oprd", "dative"})

#: Third-person pronouns that need an antecedent, mapped to the agreement class it must satisfy:
#: ``thing`` (singular, not a person), ``group`` (plural, or a collective noun), ``person``.
_PRONOUN_CLASS: dict[str, str] = {
    "it": "thing",
    "its": "thing",
    "they": "group",
    "them": "group",
    "their": "group",
    "he": "person",
    "him": "person",
    "his": "person",
    "she": "person",
    "her": "person",
}
_DEMONSTRATIVES: frozenset[str] = frozenset({"this", "that", "these", "those", "such"})
#: Determiners and possessives that point back to an earlier sentence (the residual check).
_ANAPHORIC_DETERMINERS: frozenset[str] = frozenset(_DEMONSTRATIVES | {"its", "their", "his", "her"})

#: Sentence-initial connectives whose sentence states a consequence of the previous one; such a
#: sentence cannot be checked on its own and is dropped. ``(text, needs_comma)``.
_RESULT_CONNECTIVES: tuple[tuple[str, bool], ...] = (
    ("as a result", False),
    ("as a consequence", False),
    ("consequently", False),
    ("therefore", False),
    ("thus", False),
    ("hence", False),
    ("for this reason", False),
    ("because of this", False),
    ("in this way", False),
    ("this way", True),
    ("so", True),
)
#: Sentence-initial connectives that only link a sentence to its neighbours; removed, the statement
#: kept. ``(text, needs_comma)``: a one-word connective that is also an ordinary word ("Still
#: images ...", "Next steps ...") counts only when a comma follows it.
_GLUE_CONNECTIVES: tuple[tuple[str, bool], ...] = (
    ("in addition", False),
    ("additionally", False),
    ("also", False),
    ("moreover", False),
    ("furthermore", False),
    ("however", False),
    ("instead", False),
    ("similarly", False),
    ("likewise", False),
    ("in contrast", False),
    ("by contrast", False),
    ("for example", False),
    ("for instance", False),
    ("on the other hand", False),
    ("at the same time", False),
    ("in other words", False),
    ("in particular", False),
    ("in short", False),
    ("in fact", False),
    ("of course", False),
    ("yet", False),
    ("but", False),
    ("meanwhile", False),
    ("nevertheless", False),
    ("nonetheless", False),
    ("indeed", False),
    ("notably", False),
    ("importantly", False),
    ("still", True),
    ("finally", True),
    ("first", True),
    ("second", True),
    ("third", True),
    ("next", True),
    ("then", True),
    ("overall", True),
    ("and", True),
    ("now", True),
    ("today", True),
)
#: Adverbs that only tie a clause to the discourse ("are *also* helping"); removed wherever they stand.
_GLUE_ADVERBS: frozenset[str] = frozenset({"also"})

#: Nouns naming the people behind a piece of work. A bare definite one ("the researchers", "the
#: team") names the document's primary agent, the first anchored agent that is a sentence subject.
_AGENT_NOUNS: frozenset[str] = frozenset(
    {
        "team",
        "researcher",
        "scientist",
        "author",
        "group",
        "investigator",
        "engineer",
        "developer",
        "maintainer",
        "lab",
        "laboratory",
        "company",
        "firm",
        "startup",
        "organization",
        "organisation",
        "institute",
        "institution",
        "consortium",
        "staff",
        "crew",
        "physicist",
        "colleague",
        "expert",
        "student",
        "professor",
        "doctor",
        "physician",
        "clinician",
        "contributor",
    }
)
#: Singular nouns that agree with "they" ("the team ... they").
_COLLECTIVE_NOUNS: frozenset[str] = frozenset(
    {
        "team",
        "group",
        "company",
        "firm",
        "startup",
        "organization",
        "organisation",
        "institute",
        "institution",
        "consortium",
        "staff",
        "crew",
        "lab",
        "laboratory",
        "center",
        "centre",
        "university",
        "department",
        "agency",
        "government",
        "board",
        "committee",
        "council",
        "family",
        "couple",
        "pair",
        "duo",
        "trio",
        "project",
        "collaboration",
        "partnership",
        "community",
        "foundation",
        "association",
        "society",
        "club",
        "party",
    }
)
#: Nouns naming a person; they agree with "he"/"she" and never with "it".
_PERSON_NOUNS: frozenset[str] = frozenset(
    {
        "researcher",
        "scientist",
        "author",
        "investigator",
        "engineer",
        "developer",
        "maintainer",
        "physicist",
        "colleague",
        "expert",
        "student",
        "professor",
        "doctor",
        "physician",
        "clinician",
        "contributor",
        "master",
        "director",
        "manager",
        "officer",
        "leader",
        "founder",
        "president",
        "chief",
        "spokesperson",
        "spokesman",
        "spokeswoman",
        "man",
        "woman",
        "person",
        "people",
        "patient",
        "user",
        "customer",
        "employee",
        "worker",
        "member",
        "child",
        "boy",
        "girl",
    }
)
#: Possessed nouns that presuppose an agent as possessor ("their findings", never "the images'
#: findings"): the possessor of such a noun must be animate or collective.
_AGENT_POSSESSIONS: frozenset[str] = frozenset(
    {
        "finding",
        "result",
        "work",
        "research",
        "study",
        "paper",
        "goal",
        "approach",
        "method",
        "colleague",
        "data",
        "experiment",
        "analysis",
        "report",
        "design",
        "team",
        "effort",
        "conclusion",
        "technique",
        "model",
        "discovery",
        "invention",
        "prototype",
        "hypothesis",
        "measurement",
        "observation",
        "publication",
        "article",
        "project",
        "lab",
        "laboratory",
        "collaboration",
        "idea",
    }
)
#: General nouns that stand for the thing a document presents ("the design", "the technology"); a
#: bare definite one names the primary artifact, the thing the primary agent introduced.
_SHELL_NOUNS: frozenset[str] = frozenset(
    {
        "design",
        "technology",
        "innovation",
        "device",
        "invention",
        "approach",
        "method",
        "hardware",
        "tool",
        "solution",
        "product",
        "prototype",
        "technique",
        "breakthrough",
        "system",
    }
)
#: Verbs whose indefinite object, under the primary agent, introduces the primary artifact.
_CREATION_VERBS: frozenset[str] = frozenset(
    {
        "develop",
        "build",
        "create",
        "design",
        "invent",
        "present",
        "introduce",
        "propose",
        "unveil",
        "publish",
        "release",
        "launch",
        "engineer",
        "construct",
        "make",
        "produce",
        "devise",
        "demonstrate",
        "describe",
        "report",
    }
)
_ANCHOR_ENTITY_TYPES: frozenset[str] = frozenset({"PERSON", "GPE", "LOC", "FAC"})
#: The most sentences back a pronoun's antecedent is looked for.
_PRONOUN_WINDOW: int = 2
#: The most tokens a grounding text may hold before it falls back to the base noun phrase.
_MAX_GROUNDING_TOKENS: int = 12
#: The most clauses one coordinated sentence is split into.
_MAX_CLAUSES: int = 4
#: Pronoun ``it`` in a verb with one of these complements is a dummy ("make it possible"), not an anaphor.
_CLAUSAL_IT_DEPS: frozenset[str] = frozenset({"ccomp", "xcomp", "oprd", "acomp"})
#: Dependency labels of a modifier that may stand in front of the subject.
_FRONTED_DEPS: frozenset[str] = frozenset({"advcl", "prep", "advmod", "npadvmod"})
#: Dependency labels of a post-modifier that may ground a noun phrase ("a team *led by* Nandita Saha").
_GROUNDING_DEPS: frozenset[str] = frozenset({"prep", "acl", "agent", "relcl"})
#: Nouns of a time adverbial ("every week", "in 2025") that, after the last conjunct, is read as shared by
#: every clause; a coordination carrying one is not split, so no clause loses it.
_TIME_NOUNS: frozenset[str] = frozenset(
    {
        "second",
        "minute",
        "hour",
        "day",
        "week",
        "month",
        "quarter",
        "year",
        "decade",
        "century",
        "time",
        "morning",
        "afternoon",
        "evening",
        "night",
        "season",
        "summer",
        "winter",
        "spring",
        "autumn",
        "fall",
        "today",
        "yesterday",
        "tomorrow",
    }
)

#: Sentence-initial fillers dropped from the start of a statement; they add no meaning on their own.
_LEADING_FILLER = re.compile(r"^(?:now|and|today)\b,?\s+", re.IGNORECASE)

_QUOTE_PAIR = re.compile(r"[\"“”][^\"“”]*[\"“”]")
_OPENING_QUOTES = ('"', "“", "‘", "'")

_HEADING = re.compile(r"^\s{0,3}#{1,6}(?:\s|$)")
_THEMATIC_BREAK = re.compile(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$")
_SETEXT_UNDERLINE = re.compile(r"^\s{0,3}=+\s*$")
_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
#: A whole line in bold or italics that does not end a sentence: a pseudo-heading ("**Next Steps**").
_PSEUDO_HEADING = re.compile(r"^\s*(\*\*|__|\*|_)(?P<body>[^*_].*?)\1\s*:?\s*$")
_TABLE_ROW = re.compile(r"^\s*\|")
_HTML_LINE = re.compile(r"^\s*<[^>]*>\s*$")
_BLOCKQUOTE = re.compile(r"^\s{0,3}>\s?")
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s+")
#: A leading "Label:" ("Summary:", "Date:", "Note:") of a paragraph or sentence.
_LABEL = re.compile(r"^(?:[A-Z][A-Za-z]*(?: [A-Za-z]+){0,2}):(?:\s+|$)")

_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_INLINE_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_REFERENCE_LINK = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
_AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")
_INLINE_CODE = re.compile(r"`+([^`]+)`+")
_STRONG = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_EMPHASIS = re.compile(r"(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?![\w*])|(?<![\w_])_(?=\S)([^_]+?)(?<=\S)_(?![\w_])")
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")

#: Private-use delimiters around the index of a parked inline code span.
_CODE_OPEN = "\ue000"
_CODE_CLOSE = "\ue001"
_CODE_PLACEHOLDER = re.compile(_CODE_OPEN + "(\\d+)" + _CODE_CLOSE)

#: A statement opening with a plain lowercase word (never an identifier such as ``scan()``).
_LOWER_FIRST_WORD = re.compile(r"^[a-z][a-z]*(?=\s|,|$)")


@dataclass(frozen=True)
class _Block:
    """One run of prose from a paragraph.

    :ivar index: The paragraph index of the paragraph split ``extract_claims`` uses.
    :ivar text: The prose with Markdown removed and lines joined; may be empty.
    :ivar boundary: Whether a section boundary (heading, thematic break, code fence) precedes the
        prose, so no sentence may refer back across it.
    :ivar code_spans: ``(start, end)`` offsets in ``text`` of former inline code spans, inside
        which no sentence may start.
    """

    index: int
    text: str
    boundary: bool
    code_spans: tuple[tuple[int, int], ...] = ()


def _strip_inline_markdown(text: str) -> tuple[str, tuple[tuple[int, int], ...]]:
    """Remove inline Markdown syntax and a leading ``Label:``, keeping the visible text.

    Inline code is set aside before the other rules run, so emphasis or link syntax inside code is
    kept verbatim, and its offsets in the result are returned.

    :param text: One run of joined lines.
    :returns: The text without images, link targets, code ticks, emphasis markers, HTML tags or a
        leading label, whitespace collapsed, and the offsets of the former code spans.
    """
    codes: list[str] = []

    def _park(match: re.Match[str]) -> str:
        """Set one inline code span aside and return its placeholder."""
        codes.append(" ".join(match.group(1).split()))
        return f"{_CODE_OPEN}{len(codes) - 1}{_CODE_CLOSE}"

    text = text.replace(_CODE_OPEN, "").replace(_CODE_CLOSE, "")
    text = _INLINE_CODE.sub(_park, text)
    text = _IMAGE.sub("", text)
    text = _INLINE_LINK.sub(r"\1", text)
    text = _REFERENCE_LINK.sub(r"\1", text)
    text = _AUTOLINK.sub(r"\1", text)
    text = _STRONG.sub(r"\2", text)
    text = _EMPHASIS.sub(lambda m: m.group(1) or m.group(2) or "", text)
    text = _HTML_TAG.sub("", text)
    text = _LABEL.sub("", " ".join(text.split()))

    out: list[str] = []
    spans: list[tuple[int, int]] = []
    length = 0
    cursor = 0
    for match in _CODE_PLACEHOLDER.finditer(text):
        out.append(text[cursor : match.start()])
        length += match.start() - cursor
        code = codes[int(match.group(1))]
        spans.append((length, length + len(code)))
        out.append(code)
        length += len(code)
        cursor = match.end()
    out.append(text[cursor:])
    return "".join(out), tuple(spans)


def _emit_block(blocks: list[_Block], index: int, lines: list[str], boundary: bool):
    """Append the prose of ``lines`` to ``blocks``, or a bare boundary when there is no prose.

    :param blocks: The blocks collected so far; extended in place.
    :param index: The paragraph index.
    :param lines: The kept lines of the current run.
    :param boundary: Whether a boundary precedes the run.
    """
    prose, spans = _strip_inline_markdown(" ".join(lines))
    if prose or boundary:
        blocks.append(_Block(index=index, text=prose, boundary=boundary, code_spans=spans))


def _prose_blocks(text: str) -> list[_Block]:
    """Split ``text`` into paragraphs exactly like ``extract_claims`` and keep only their prose.

    Headings, pseudo-headings (a whole bold line), thematic breaks, fenced code, front matter,
    table rows and HTML-only lines are dropped and mark a boundary; a boundary inside a paragraph
    splits it, so text on either side never joins. List and blockquote markers and a leading
    ``Label:`` are stripped; inline Markdown is removed and hard-wrapped lines are joined.

    :param text: The document text.
    :returns: The prose runs and boundaries, in document order.
    """
    blocks: list[_Block] = []
    in_fence = False
    in_front_matter = text.startswith("---\n")
    for index, para in enumerate(re.split(r"\n\s*\n", text)):
        boundary = False
        kept: list[str] = []
        lines = para.splitlines()
        for position, line in enumerate(lines):
            if in_front_matter:
                if (position > 0 or index > 0) and line.strip() in {"---", "..."}:
                    in_front_matter = False
                boundary = True
                continue
            if _FENCE.match(line):
                in_fence = not in_fence
                _emit_block(blocks, index, kept, boundary)
                kept, boundary = [], True
                continue
            if in_fence:
                continue
            if _SETEXT_UNDERLINE.match(line) or (_THEMATIC_BREAK.match(line) and kept and line.strip()[0] == "-"):
                kept = []  # the lines above a setext underline are a heading
                _emit_block(blocks, index, kept, boundary)
                kept, boundary = [], True
                continue
            if _HEADING.match(line) or _THEMATIC_BREAK.match(line):
                _emit_block(blocks, index, kept, boundary)
                kept, boundary = [], True
                continue
            pseudo = _PSEUDO_HEADING.match(line)
            if pseudo and not kept and not pseudo.group("body").rstrip().endswith((".", "!", "?")):
                # a whole bold line opening a paragraph ("**Next Steps**")
                _emit_block(blocks, index, kept, boundary)
                kept, boundary = [], True
                continue
            if _TABLE_ROW.match(line) or _HTML_LINE.match(line):
                continue
            line = _BLOCKQUOTE.sub("", line)
            line = _LIST_MARKER.sub("", line)
            kept.append(line.strip())
        _emit_block(blocks, index, kept, boundary)
    return blocks


def _parse(pipeline: spacy.language.Language, block: _Block) -> Any:
    """Parse a block, forbidding a sentence start inside or right after an inline code span.

    Without code spans this is ``pipeline(block.text)``. Otherwise the same pipeline's components
    run over a tokenized doc whose code-span tokens (and the token right after a span, when only
    whitespace separates them) are marked as not starting a sentence, which the parser respects,
    so ``Config(...) directly bypasses ...`` stays one sentence.

    :param pipeline: The loaded spaCy pipeline.
    :param block: The prose block.
    :returns: The parsed spaCy doc.
    """
    if not block.code_spans:
        return pipeline(block.text)
    doc = pipeline.make_doc(block.text)
    for token in doc[1:]:
        if any(
            start < token.idx < end or (end <= token.idx <= end + 1 and not block.text[end : token.idx].strip())
            for start, end in block.code_spans
        ):
            token.is_sent_start = False
    for _, component in pipeline.pipeline:
        doc = component(doc)
    return doc


def _parse_statement(pipeline: spacy.language.Language, text: str) -> Any:
    """Parse one rewritten statement as a single sentence.

    Every token after the first is marked as not starting a sentence, so a rewritten text that
    holds an identifier with dots or an ellipsis is never split in two.

    :param pipeline: The loaded spaCy pipeline.
    :param text: The statement text.
    :returns: The parsed spaCy doc, with exactly one sentence.
    """
    doc = pipeline.make_doc(text)
    for token in doc[1:]:
        token.is_sent_start = False
    for _, component in pipeline.pipeline:
        doc = component(doc)
    return doc


def _content_verb(sent: Any) -> Any:
    """Return the verb that carries the sentence's claim.

    For a reporting sentence ("X says the design could be adapted") it is the reported clause's
    verb; otherwise it is the sentence root.

    :param sent: A spaCy sentence span.
    :returns: The token of the content verb.
    """
    root = sent.root
    if root.lemma_.lower() in _REPORTING_LEMMAS:
        for child in root.children:
            if child.dep_ == "ccomp":
                return child
    return root


def _is_quotation(text: str) -> bool:
    """Return whether the sentence is (mostly) a direct quotation: an opinion, not a checkable fact.

    :param text: The sentence text.
    :returns: ``True`` when it opens with a quotation mark or quoted text makes up half of it.
    """
    if text.startswith(_OPENING_QUOTES):
        return True
    quoted = sum(len(match.group(0)) for match in _QUOTE_PAIR.finditer(text))
    return quoted * 2 >= len(text)


def _is_headline(sent: Any) -> bool:
    """Return whether every content word is capitalized, as in a title or a citation fragment.

    :param sent: A spaCy sentence span.
    :returns: ``True`` for a title-case fragment of at least four words.
    """
    words = [t for t in sent if t.is_alpha and not t.is_stop]
    return len(words) >= 4 and all(t.text[0].isupper() for t in words)


def _is_declarative(sent: Any) -> bool:
    """Return whether the sentence states something: a finite verb root with a subject.

    :param sent: A spaCy sentence span.
    :returns: ``False`` for fragments, labels, imperatives, questions, lead-ins ending in a colon,
        a bare subordinate clause and text with unbalanced brackets.
    """
    root = sent.root
    stripped = sent.text.rstrip()
    if root.pos_ not in {"VERB", "AUX"} or stripped.endswith(("?", ":")):
        return False  # a question, or a lead-in to a list or code block that follows
    if any(child.dep_ == "mark" for child in root.children):
        return False  # a subordinate clause on its own ("When you need those.")
    if any(stripped.count(o) != stripped.count(c) for o, c in ("()", "[]", "{}")):
        return False  # a fragment cut inside a bracket
    return any(child.dep_ in _SUBJECT_DEPS for child in root.children)


def _is_hedged(sent: Any) -> bool:
    """Return whether the claim's verb carries a hedging modal ("could", "may", "will", ...).

    :param sent: A spaCy sentence span.
    :returns: ``True`` for a prediction or a possibility.
    """
    verb = _content_verb(sent)
    return any(child.dep_ == "aux" and child.lower_ in _HEDGE_MODALS for child in verb.children)


def _leading_connective(text: str, table: tuple[tuple[str, bool], ...]) -> Optional[str]:
    """Return the connective from ``table`` that opens ``text``, if any.

    :param text: The sentence text.
    :param table: ``(connective, needs_comma)`` rows.
    :returns: The matched connective text, else ``None``.
    """
    lowered = text.lower()
    for connective, needs_comma in table:
        if not lowered.startswith(connective):
            continue
        rest = lowered[len(connective) : len(connective) + 1]
        if rest == "," or (not needs_comma and rest in {"", " "}):
            return connective
    return None


def _is_clausal_it(token: Any) -> bool:
    """Return whether ``it`` is a dummy pronoun ("it is clear that", "make it possible").

    :param token: A pronoun token.
    :returns: ``True`` when it refers to nothing.
    """
    if token.dep_ == "expl":
        return True
    return token.dep_ == "dobj" and any(child.dep_ in _CLAUSAL_IT_DEPS for child in token.head.children)


def _is_anaphoric_pronoun(token: Any) -> bool:
    """Return whether the token is a third-person pronoun that needs an antecedent.

    :param token: A token.
    :returns: ``True`` for ``it``/``they``/``he``/... (not relative or dummy pronouns).
    """
    if token.tag_ not in {"PRP", "PRP$"} or token.lower_ not in _PRONOUN_CLASS:
        return False
    return not (token.lower_ == "it" and _is_clausal_it(token))


def _resolved_locally(token: Any, sent: Any) -> bool:
    """Return whether a noun subject earlier in the same sentence can be the token's antecedent.

    :param token: A pronoun or demonstrative token.
    :param sent: Its sentence.
    :returns: ``True`` when a noun or proper-noun subject precedes it in the sentence.
    """
    return any(t.i < token.i and t.dep_ in {"nsubj", "nsubjpass"} and t.pos_ in {"NOUN", "PROPN"} for t in sent)


def _is_dependent(sent: Any) -> bool:
    """Return whether the (rewritten) sentence still refers to an earlier one.

    True when it opens with a connective, when a demonstrative determiner remains, or when a
    third-person pronoun or possessive remains that no noun subject earlier in the same sentence
    resolves. Relative pronouns (tag WDT/WP) and dummy ``it`` are not anaphors.

    :param sent: A spaCy sentence span.
    :returns: ``True`` when the sentence cannot stand alone.
    """
    text = _LEADING_FILLER.sub("", sent.text.strip())
    if _leading_connective(text, _RESULT_CONNECTIVES) or _leading_connective(text, _GLUE_CONNECTIVES):
        return True
    for token in sent:
        if token.lower_ in _DEMONSTRATIVES and token.dep_ == "det":
            return True
        demonstrative_subject = token.tag_ == "DT" and token.dep_ in _SUBJECT_DEPS and token.lower_ in _DEMONSTRATIVES
        if (demonstrative_subject or _is_anaphoric_pronoun(token)) and not _resolved_locally(token, sent):
            return True
    return False


def _statement_numbers(tokens: list[Any]) -> tuple[str, ...]:
    """Return the numbers of a statement, ignoring the idiom "one of".

    :param tokens: The statement's tokens.
    :returns: The normalized numbers, in text order.
    """
    kept = []
    for tok in tokens:
        following = tok.nbor(1).lower_ if tok.i + 1 < len(tok.doc) else ""
        if tok.lower_ in _WORD_NUMBERS and following == "of":
            continue
        kept.append(tok)
    return _object_numbers(kept)


def _statement_objects(sent: Any, svo_extractor: Any) -> list[str]:
    """Return the object texts of a sentence: textacy's objects, else the verb's complement heads.

    :param sent: A spaCy sentence span.
    :param svo_extractor: textacy's subject-verb-object extractor.
    :returns: The object texts, possibly empty.
    """
    objects = []
    for svo in svo_extractor(sent.as_doc()):
        object_toks = list(svo.object) if hasattr(svo.object, "__iter__") else [svo.object]
        objects.append(" ".join(t.text for t in object_toks))
    if not objects:
        verb = _content_verb(sent)
        objects = [child.text for child in verb.children if child.dep_ in _OBJECT_DEPS]
    return objects


def _statement_text(sentences: list[str]) -> str:
    """Join a statement's sentences, dropping a leading filler word from the first one.

    :param sentences: The member sentence texts, in document order.
    :returns: The statement text.
    """
    first = _LEADING_FILLER.sub("", sentences[0])
    if first != sentences[0]:
        first = first[:1].upper() + first[1:]  # only re-capitalize what the filler removal exposed
    return " ".join([first, *sentences[1:]])


# ---------------------------------------------------------------------------------------------
# The discourse model: mentions, their grounding text and the antecedent search
# ---------------------------------------------------------------------------------------------


@dataclass
class _Mention:
    """One noun phrase of a sentence, as a candidate antecedent and as a possible anaphor.

    :ivar head: The phrase's head token.
    :ivar start: Index of the phrase's first token in its doc.
    :ivar end: Index one past the phrase's last token.
    :ivar paragraph: The block ordinal of the sentence.
    :ivar subject: Whether the phrase is a clause subject.
    :ivar definite: ``indefinite`` (a/an), ``definite`` (the), ``demonstrative``, ``possessive``
        (its/their ...), ``pronoun`` or ``bare``.
    :ivar plural: Whether it agrees with "they".
    :ivar animate: Whether it names a person or an organisation.
    :ivar collective: Whether a singular noun agrees with "they" ("the team").
    :ivar person: Whether it names an individual person ("he"/"she").
    :ivar anchored: Whether the grounding text holds a proper name or a number.
    :ivar text: The grounding text: the phrase with its anchoring modifiers, article normalized,
        or the antecedent's grounding text once the phrase is resolved.
    :ivar content: Lemmas of the content words in the grounding text.
    :ivar clean: Whether the base phrase is a well-formed noun phrase (a mis-parsed chunk such as
        "the when several spellings match" never serves as an antecedent).
    :ivar resolved: Whether an anaphoric phrase found its antecedent.
    """

    head: Any
    start: int
    end: int
    paragraph: int
    subject: bool
    definite: str
    plural: bool
    animate: bool
    collective: bool
    person: bool
    anchored: bool
    text: str
    content: frozenset[str]
    clean: bool = True
    resolved: bool = False

    @property
    def lemma(self) -> str:
        """The head lemma, lowercased."""
        return self.head.lemma_.lower()

    @property
    def usable(self) -> bool:
        """Whether the mention can serve as an antecedent (a pronoun only once resolved)."""
        return self.clean and (self.definite != "pronoun" or self.resolved)

    def take(self, antecedent: _Mention, text: Optional[str] = None):
        """Adopt an antecedent's identity: grounding text, anchoring and agreement features.

        :param antecedent: The resolved antecedent.
        :param text: The grounding text to adopt; the antecedent's by default.
        """
        self.text = antecedent.text if text is None else text
        self.anchored = antecedent.anchored
        self.content = antecedent.content
        self.resolved = True
        if self.definite == "pronoun":
            self.plural, self.animate = antecedent.plural, antecedent.animate
            self.collective, self.person = antecedent.collective, antecedent.person


def _is_anchor(token: Any) -> bool:
    """Return whether a token pins a phrase to the world: a number or a proper name.

    An all-caps proper noun ("MRI") is an acronym and not an anchor by itself.

    :param token: A token.
    :returns: ``True`` for a number or a non-acronym proper noun.
    """
    if token.like_num:
        return True
    if token.tag_ in {"NNP", "NNPS"} and not token.is_upper:
        return True
    return token.ent_type_ in _ANCHOR_ENTITY_TYPES and not token.is_stop


def _is_clean_phrase(chunk: Any) -> bool:
    """Return whether a noun chunk is a well-formed noun phrase a reader would accept as a name.

    A small model sometimes roots a chunk at a verb or a subordinator ("the when several spellings
    match", "implement LenzFactCheckClient"); such a chunk must not be substituted for a pronoun.

    :param chunk: A spaCy noun chunk.
    :returns: ``True`` when the head is a noun and no finite verb, auxiliary, subordinator or
        wh-word stands in the phrase.
    """
    if chunk.root.pos_ not in {"NOUN", "PROPN", "PRON"}:
        return False
    for token in chunk:
        if token.pos_ == "SCONJ" or token.tag_ in {"WRB", "WDT", "WP", "WP$", "MD"}:
            return False
        if token.pos_ in {"VERB", "AUX"} and token.dep_ not in {"amod", "acl", "relcl", "nmod"}:
            return False
    return True


def _content_lemmas(tokens: list[Any]) -> frozenset[str]:
    """Return the lowercased lemmas of the content words among ``tokens``.

    :param tokens: Tokens.
    :returns: Lemmas of the alphabetic or numeric, non-stop, non-determiner tokens.
    """
    return frozenset(
        t.lemma_.lower()
        for t in tokens
        if (t.is_alpha or t.like_num)
        and not t.is_stop
        and t.dep_ not in {"det", "poss"}
        and t.tag_ not in {"PRP", "PRP$"}
    )


def _without_appositions(tokens: list[Any]) -> list[Any]:
    """Drop every apposition (and its subtree) from ``tokens``, with the commas around it.

    :param tokens: Tokens in index order.
    :returns: The remaining tokens, in index order.
    """
    dropped: set[int] = set()
    for tok in tokens:
        if tok.dep_ == "appos":
            dropped.update(t.i for t in tok.subtree)
    kept: list[Any] = []
    for tok in tokens:
        if tok.i in dropped:
            continue
        if tok.text == "," and (tok.i + 1 in dropped or tok.i - 1 in dropped):
            continue
        kept.append(tok)
    return kept


def _tokens_text(tokens: list[Any]) -> str:
    """Join tokens with their original spacing, trimmed of outer punctuation and whitespace.

    :param tokens: Tokens in index order.
    :returns: The text.
    """
    while tokens and tokens[0].is_punct:
        tokens = tokens[1:]
    while tokens and tokens[-1].is_punct:
        tokens = tokens[:-1]
    text = "".join(t.text_with_ws for t in tokens)
    text = re.sub(r"\s+([,.;:!?)])", r"\1", text)
    return " ".join(text.split())


def _lower_first(text: str, first: Any) -> str:
    """Lowercase the first character of ``text`` unless its first token is a proper noun or acronym.

    :param text: The phrase text.
    :param first: The phrase's first token.
    :returns: The adjusted text.
    """
    if first.tag_ in {"NNP", "NNPS"} or first.is_upper or not text[:1].isalpha():
        return text
    return text[:1].lower() + text[1:]


def _grounding_text(chunk: Any) -> tuple[str, list[Any]]:
    """Build the grounding text of a noun phrase: what a later mention is replaced with.

    The base phrase plus those post-modifiers of its head (``prep``, ``acl``, ``agent``,
    ``relcl``) that hold an anchor, appositions removed ("a team led by Nandita Saha, a doctoral
    student ..." -> "the team led by Nandita Saha"). An indefinite or demonstrative article becomes
    "the"; a bare common noun gets one.

    :param chunk: A spaCy noun chunk.
    :returns: The grounding text and the tokens it was built from.
    """
    head = chunk.root
    tokens = list(chunk)
    for child in head.children:
        if child.i < chunk.end or child.dep_ not in _GROUNDING_DEPS:
            continue
        sub = _without_appositions(list(child.subtree))
        if any(_is_anchor(t) for t in sub):
            tokens.extend(sub)
    tokens = _without_appositions(sorted(set(tokens), key=lambda t: t.i))
    if len(tokens) > _MAX_GROUNDING_TOKENS or not tokens:
        tokens = list(chunk)
    first = tokens[0]
    article = ""
    body = tokens
    if first.dep_ == "det" and first.lower_ in {"a", "an", "the", "this", "that", "these", "those"}:
        article, body = "the ", tokens[1:]
    elif first.tag_ not in {"NNP", "NNPS", "PRP", "PRP$", "CD", "DT", "PDT"} and not first.like_num:
        article = "the "
    text = _tokens_text(body) if body else ""
    if not text:
        return _tokens_text(tokens), tokens
    return article + _lower_first(text, body[0]), tokens


def _collect_mentions(sent: Any, paragraph: int) -> list[_Mention]:
    """Describe every noun phrase of a sentence.

    :param sent: A spaCy sentence span.
    :param paragraph: The block ordinal.
    :returns: The mentions in text order.
    """
    mentions: list[_Mention] = []
    for chunk in sent.noun_chunks:
        head = chunk.root
        if head.tag_ in {"WDT", "WP", "WP$", "EX"}:
            continue
        first = chunk[0]
        if head.tag_ in {"PRP", "PRP$"}:
            definite = "pronoun"
        elif first.tag_ == "PRP$" or first.dep_ == "poss":
            definite = "possessive"
        elif first.dep_ == "det" and first.lower_ in _DEMONSTRATIVES:
            definite = "demonstrative"
        elif first.dep_ == "det" and first.lower_ in {"a", "an"}:
            definite = "indefinite"
        elif first.dep_ == "det" and first.lower_ == "the":
            definite = "definite"
        else:
            definite = "bare"
        text, grounding = _grounding_text(chunk)
        lemma = head.lemma_.lower()
        coordinated = any(c.dep_ == "conj" and c.pos_ in {"NOUN", "PROPN"} for c in head.children) and any(
            c.dep_ == "cc" and c.lower_ == "and" for c in head.children
        )
        plural = head.tag_ in {"NNS", "NNPS"} or coordinated
        reporting_subject = head.dep_ == "nsubj" and head.head.lemma_.lower() in _REPORTING_LEMMAS
        person_entity = head.ent_type_ == "PERSON"
        person = (person_entity or lemma in _PERSON_NOUNS or reporting_subject) and not plural
        org_entity = head.tag_ in {"NNP", "NNPS"} and any(t.ent_type_ == "ORG" for t in chunk)
        collective = (lemma in _COLLECTIVE_NOUNS or org_entity) and not plural
        animate = person or person_entity or collective or reporting_subject or lemma in _PERSON_NOUNS | _AGENT_NOUNS
        mentions.append(
            _Mention(
                head=head,
                start=chunk.start,
                end=chunk.end,
                paragraph=paragraph,
                subject=head.dep_ in {"nsubj", "nsubjpass"},
                definite=definite,
                plural=plural,
                animate=animate,
                collective=collective,
                person=person,
                anchored=any(_is_anchor(t) for t in grounding),
                text=text,
                content=_content_lemmas(grounding),
                clean=_is_clean_phrase(chunk),
            )
        )
    return mentions


def _agrees(candidate: _Mention, pronoun_class: str, agent_possessor: bool) -> bool:
    """Return whether a candidate antecedent agrees with a pronoun's class.

    :param candidate: The candidate.
    :param pronoun_class: ``thing``, ``group`` or ``person``.
    :param agent_possessor: Whether the pronoun possesses an agent-made thing ("their findings").
    :returns: ``True`` when number and animacy agree.
    """
    if not candidate.usable:
        return False
    if pronoun_class == "person":
        return candidate.person and not candidate.plural
    if pronoun_class == "thing":
        return not candidate.plural and not candidate.person
    agrees = candidate.plural or candidate.collective
    if agent_possessor:
        agrees = agrees and candidate.animate
    return agrees


def _misfit(candidate: _Mention, pronoun_class: str) -> bool:
    """Return whether an agreeing candidate is the less likely kind for the pronoun.

    "They" names people or a collective before plain plural things; "it" names a thing before an
    organisation ("Acme released a compiler. It compiles ..." is about the compiler).

    :param candidate: An agreeing candidate.
    :param pronoun_class: ``thing``, ``group`` or ``person``.
    :returns: ``True`` when the candidate should rank after the others.
    """
    if pronoun_class == "group":
        return not (candidate.animate or candidate.collective)
    if pronoun_class == "thing":
        return candidate.animate or candidate.collective
    return False


@dataclass
class _Topic:
    """The document's primary agent and the artifact it introduced, if the document has them.

    :ivar agent: The first anchored agent-like sentence subject ("a team led by Nandita Saha").
    :ivar artifact: The indefinite object the agent introduced with a creation verb.
    """

    agent: Optional[_Mention] = None
    artifact: Optional[_Mention] = None


@dataclass
class _Discourse:
    """The antecedents available to a sentence.

    :ivar topic: The document's primary agent and artifact.
    :ivar recent: The mentions of the previous sentences of the current section, oldest first;
        a pronoun looks back at most :data:`_PRONOUN_WINDOW` of them.
    :ivar by_head: Every earlier mention of the document, keyed by ``(head lemma, plural)``, in
        text order; a definite noun phrase looks its head up here.
    """

    topic: _Topic
    recent: list[list[_Mention]] = field(default_factory=list)
    by_head: dict[tuple[str, bool], list[_Mention]] = field(default_factory=dict)

    def new_section(self):
        """Forget the pronoun window at a section boundary (definite phrases keep the document)."""
        self.recent = []

    def add(self, mentions: list[_Mention]):
        """Record a sentence's mentions once the sentence is processed.

        :param mentions: The sentence's mentions, resolved where possible.
        """
        self.recent.append(mentions)
        for mention in mentions:
            self.by_head.setdefault((mention.lemma, mention.plural), []).append(mention)

    def pronoun_antecedent(self, pronoun: Any, possessed: Optional[str]) -> Optional[_Mention]:
        """Find the antecedent of a pronoun in the previous sentences of the section.

        Nearest sentence first; within a sentence the candidates the pronoun fits best first (an
        animate or collective one for "they", an inanimate one for "it"), then a subject, then
        text order (Hobbs' search order, flattened).

        :param pronoun: The pronoun token.
        :param possessed: For a possessive, the lemma of the possessed noun.
        :returns: The antecedent, else ``None``.
        """
        pronoun_class = _PRONOUN_CLASS[pronoun.lower_]
        agent_possessor = pronoun_class == "group" and possessed in _AGENT_POSSESSIONS
        for mentions in reversed(self.recent[-_PRONOUN_WINDOW:]):
            ranked = sorted(
                (m for m in mentions if _agrees(m, pronoun_class, agent_possessor)),
                key=lambda m: (_misfit(m, pronoun_class), not m.subject, m.start),
            )
            if ranked:
                return ranked[0]
        return None

    def definite_antecedent(self, mention: _Mention, local: list[_Mention]) -> Optional[_Mention]:
        """Find what a bare definite noun phrase ("the antenna") refers to by its head noun.

        A same-head, same-number earlier mention that is more informative (anchored, or carrying
        every content word of the phrase and more). An indefinite or bare introduction ("a new MRI
        antenna") wins over a later definite one; otherwise the nearest wins.

        :param mention: The definite phrase.
        :param local: The earlier mentions of the same sentence.
        :returns: The antecedent, else ``None``.
        """
        candidates = self.by_head.get((mention.lemma, mention.plural), []) + [
            m for m in local if m.lemma == mention.lemma and m.plural == mention.plural
        ]
        fallback: Optional[_Mention] = None
        for candidate in reversed(candidates):
            if not candidate.usable:
                continue
            informative = candidate.anchored or candidate.content > mention.content
            if not informative or not mention.content <= candidate.content:
                continue
            if candidate.definite in {"indefinite", "bare"}:
                return candidate
            fallback = fallback or candidate
        return fallback

    def agent_antecedent(self, mention: _Mention) -> Optional[_Mention]:
        """Resolve a bare definite agent noun ("the researchers", "the team").

        The nearest anchored same-head mention of the same paragraph, else the primary agent when
        that is itself a people noun ("a team led by ..."); an organisation is not substituted for
        its people ("the staff" of an observatory is not the agency that funded it).

        :param mention: The definite phrase.
        :returns: The antecedent, else ``None``.
        """
        same_paragraph = [
            m
            for m in self.by_head.get((mention.lemma, mention.plural), [])
            if m.paragraph == mention.paragraph and m.anchored and m.usable
        ]
        if same_paragraph:
            return same_paragraph[-1]
        agent = self.topic.agent
        return agent if agent is not None and agent.lemma in _AGENT_NOUNS else None


def _find_topic(parsed: list[tuple[_Block, Any]]) -> _Topic:
    """Find the primary agent and artifact of a document.

    The agent is the subject of the first non-quoted, non-reporting sentence whose subject names
    people (an agent noun, or a PERSON/ORG entity) and is anchored by a name or number; the
    artifact is that sentence's indefinite direct object when its verb is a creation verb.

    :param parsed: The prose blocks with their parsed docs, in document order.
    :returns: The topic, possibly empty.
    """
    topic = _Topic()
    for block, doc in parsed:
        for sent in doc.sents:
            root = sent.root
            if _is_quotation(sent.text.strip()) or root.lemma_.lower() in _REPORTING_LEMMAS:
                continue
            mentions = _collect_mentions(sent, block.index)
            for mention in mentions:
                if mention.head.head.i != root.i or not mention.subject or not mention.anchored:
                    continue
                named = mention.head.ent_type_ in {"PERSON", "ORG"}
                if mention.lemma not in _AGENT_NOUNS and not named:
                    continue
                topic.agent = mention
                if root.lemma_.lower() in _CREATION_VERBS:
                    for other in mentions:
                        if other.head.head.i == root.i and other.head.dep_ == "dobj" and other.definite == "indefinite":
                            topic.artifact = other
                            break
                return topic
    return topic


# ---------------------------------------------------------------------------------------------
# Sentence rewriting
# ---------------------------------------------------------------------------------------------


def _render(pieces: list[Any], deleted: set[int], replaced: dict[int, tuple[int, str]]) -> str:
    """Render tokens (or inserted strings) to text, applying deletions and span replacements.

    :param pieces: Tokens in index order, or ``str`` inserts.
    :param deleted: Indices of tokens left out.
    :param replaced: ``start -> (end, text)`` spans written as ``text`` instead.
    :returns: The cleaned sentence text, capitalized and terminated.
    """
    out: list[str] = []
    skip_until = -1
    for piece in pieces:
        if isinstance(piece, str):
            out.append(piece + " ")
            continue
        if piece.i < skip_until or piece.i in deleted:
            continue
        if piece.i in replaced:
            end, text = replaced[piece.i]
            out.append(text + (piece.doc[end - 1].whitespace_ or " "))
            skip_until = end
            continue
        out.append(piece.text_with_ws)
    text = "".join(out)
    text = re.sub(r"\s+([,.;:!?%)\]])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    text = re.sub(r",(?:\s*,)+", ",", text)
    text = re.sub(r"^[\s,;:]+", "", text)
    text = re.sub(r"[\s,;:]+([.!?])$", r"\1", text)
    text = _LEADING_FILLER.sub("", " ".join(text.split()))
    if text and text[-1] not in ".!?":
        text += "."
    if _LOWER_FIRST_WORD.match(text):
        text = text[:1].upper() + text[1:]
    return text


def _fronted_modifier(token: Any, root: Any, subject_start: int) -> Optional[Any]:
    """Return the fronted modifier of the root that holds ``token``, if any.

    A fronted modifier is a child of the root (``advcl``, ``prep``, ``advmod``, ``npadvmod``)
    whose whole subtree stands before the subject ("To overcome this limitation, ...").

    :param token: A token.
    :param root: The sentence root.
    :param subject_start: Index of the subject's first token.
    :returns: The modifier's head token, else ``None``.
    """
    for child in root.children:
        fronted = child.dep_ in _FRONTED_DEPS and child.right_edge.i < subject_start
        if fronted and child.left_edge.i <= token.i <= child.right_edge.i:
            return child
    return None


def _delete_subtree(deleted: set[int], head: Any):
    """Mark a modifier's subtree, and the comma after it, as deleted.

    :param deleted: The deletion set; extended in place.
    :param head: The modifier's head token.
    """
    deleted.update(t.i for t in head.subtree)
    following = head.right_edge.i + 1
    if following < len(head.doc) and head.doc[following].text == ",":
        deleted.add(following)


def _delete_prefix(deleted: set[int], sent: Any, length: int, comma: bool):
    """Mark the tokens covering the first ``length`` characters of the sentence as deleted.

    :param deleted: The deletion set; extended in place.
    :param sent: The sentence.
    :param length: The number of characters, from the sentence's first non-blank character.
    :param comma: Whether a comma right after the prefix goes too.
    """
    limit = sent.start_char + (len(sent.text) - len(sent.text.lstrip())) + length
    for token in sent:
        if token.idx < limit:
            deleted.add(token.i)
        elif comma and token.text == "," and token.idx == limit:
            deleted.add(token.i)
            break
        else:
            break


def _is_time_adverbial(token: Any) -> bool:
    """Return whether a verb's child is a time adverbial ("every week", "in 2025", "last year").

    :param token: A child of a verb.
    :returns: ``True`` for an adverbial noun phrase or prepositional phrase about time.
    """
    if token.dep_ not in {"npadvmod", "prep", "advmod"}:
        return False
    return any(t.ent_type_ in {"DATE", "TIME"} or t.lemma_.lower() in _TIME_NOUNS for t in token.subtree)


def _clauses(sent: Any) -> list[list[Any]]:
    """Split a sentence with coordinated predicates into one token list per clause.

    Only a clean coordination is split: the root and every conjunct are verbs, the conjuncts have
    no subject of their own, every conjunction between them is "and", the root is not a reporting
    verb, and no conjunct carries a time adverbial ("every week", "in 2025"), which the reader
    takes as shared and a clause would lose. Each clause gets the sentence's fronted modifiers and the shared subject; a
    conjunct without auxiliaries inherits the root's ("could improve X, make Y" -> "could make Y",
    still hedged).

    :param sent: A spaCy sentence span.
    :returns: One token list per clause (``str`` inserts for inherited auxiliaries), or a single
        list holding the whole sentence.
    """
    root = sent.root
    whole = [list(sent)]
    subject = next((c for c in root.children if c.dep_ in {"nsubj", "nsubjpass"}), None)
    conjuncts = sorted((c for c in root.conjuncts if sent.start <= c.i < sent.end), key=lambda t: t.i)
    if (
        subject is None
        or not conjuncts
        or len(conjuncts) + 1 > _MAX_CLAUSES
        or root.lemma_.lower() in _REPORTING_LEMMAS
    ):
        return whole
    chain = [root, *conjuncts]
    chain_ids = {t.i for t in chain}
    lowest, highest = min(chain_ids), max(chain_ids)
    separators: set[int] = set()
    for verb in chain:
        if verb.pos_ not in {"VERB", "AUX"}:
            return whole
        if verb is not root and any(c.dep_ in _SUBJECT_DEPS for c in verb.children):
            return whole
        if verb is not root and any(_is_time_adverbial(c) for c in verb.children):
            return whole
        for child in verb.children:
            if child.dep_ == "cc" and lowest < child.i < highest:
                if child.lower_ != "and":
                    return whole
                separators.add(child.i)

    def _owner(token: Any) -> int:
        """Return the index of the chain verb that governs ``token``."""
        node = token
        while node.i not in chain_ids and node.head.i != node.i:
            node = node.head
        return node.i

    subject_tokens = list(subject.subtree)
    shared = {t.i for t in subject_tokens} | {t.i for t in sent if t.i < subject.left_edge.i}
    fronted = [t for t in sent if t.i < subject.left_edge.i]
    root_aux = [c.text for c in root.children if c.dep_ in {"aux", "auxpass", "neg"}]
    clauses: list[list[Any]] = []
    for verb in chain:
        own = [t for t in sent if _owner(t) == verb.i and t.i not in shared and t.i not in separators]
        if verb is not root:
            own = [t for t in own if not (t.text == "," and t.i < verb.i)]
        pieces: list[Any] = [*fronted, *subject_tokens]
        if verb is not root and root_aux and not any(c.dep_ in {"aux", "auxpass"} for c in verb.children):
            pieces.extend(root_aux)
        pieces.extend(own)
        clauses.append(pieces)
    return clauses


def _rewrite_sentence(sent: Any, paragraph: int, discourse: _Discourse) -> tuple[list[str], list[_Mention]]:
    """Resolve a sentence's back-references and render its self-contained statement texts.

    :param sent: A spaCy sentence span.
    :param paragraph: The block ordinal.
    :param discourse: The antecedents available so far.
    :returns: The statement texts (empty when the sentence is dropped) and the sentence's
        mentions, resolved where possible, for the discourse model.
    """
    mentions = _collect_mentions(sent, paragraph)
    sentence = sent.text.strip()
    label = _LABEL.match(sentence)
    body = sentence[label.end() :] if label else sentence
    if _is_quotation(body) or _is_headline(sent) or not _is_declarative(sent):
        return [], mentions
    if _leading_connective(body, _RESULT_CONNECTIVES):
        return [], mentions

    deleted: set[int] = set()
    replaced: dict[int, tuple[int, str]] = {}
    glue = _leading_connective(body, _GLUE_CONNECTIVES)
    prefix = (label.end() if label else 0) + (len(glue) if glue else 0)
    if prefix:
        _delete_prefix(deleted, sent, prefix, comma=glue is not None)
    deleted.update(t.i for t in sent if t.lower_ in _GLUE_ADVERBS and t.dep_ == "advmod")

    root = sent.root
    subject = next((c for c in root.children if c.dep_ in _SUBJECT_DEPS), None)
    subject_start = subject.left_edge.i if subject is not None else root.i
    doc = sent.doc

    def _cut_or_drop(token: Any) -> bool:
        """Cut the fronted modifier holding ``token``; report ``True`` when there is none."""
        modifier = _fronted_modifier(token, root, subject_start)
        if modifier is None:
            return True
        _delete_subtree(deleted, modifier)
        return False

    for mention in mentions:
        head = mention.head
        local = [m for m in mentions if m.end <= mention.start]
        local_subjects = [m for m in local if m.subject and m.usable and m.definite != "pronoun"]
        if mention.definite == "pronoun":
            if not _is_anaphoric_pronoun(head):
                continue
            if local_subjects:
                mention.take(local_subjects[-1])  # "Because the antenna is light, it ..." resolves inside
                continue
            antecedent = discourse.pronoun_antecedent(head, None)
            if antecedent is None:
                if _cut_or_drop(head):
                    return [], mentions
                continue
            replaced[mention.start] = (mention.end, antecedent.text)
            mention.take(antecedent)
        elif mention.definite == "possessive":
            possessive = doc[mention.start]
            if not _is_anaphoric_pronoun(possessive) or local_subjects:
                continue  # "The harbour could double its capacity" resolves inside the sentence
            antecedent = discourse.pronoun_antecedent(possessive, mention.lemma)
            if antecedent is None:
                if _cut_or_drop(possessive):
                    return [], mentions
                continue
            rest = _tokens_text(list(doc[mention.start + 1 : mention.end]))
            rest = _lower_first(rest, doc[mention.start + 1]) if rest else mention.lemma
            text = f"the {rest} of {antecedent.text}"
            replaced[mention.start] = (mention.end, text)
            mention.take(antecedent, text)
        elif mention.definite in {"definite", "demonstrative"}:
            if mention.anchored or head.tag_ in {"NNP", "NNPS"} or head.right_edge.i >= mention.end:
                continue  # already specific, or restricted by its own modifier
            antecedent = None
            if mention.definite == "definite" and mention.lemma in _AGENT_NOUNS:
                antecedent = discourse.agent_antecedent(mention)  # a topic reference, before the head match
            if antecedent is None:
                antecedent = discourse.definite_antecedent(mention, local)
            if antecedent is None and mention.definite == "definite" and mention.lemma in _SHELL_NOUNS:
                antecedent = discourse.topic.artifact
            if antecedent is None:
                if mention.definite == "demonstrative" and _cut_or_drop(doc[mention.start]):
                    return [], mentions
                continue
            if antecedent is mention or antecedent.text == mention.text:
                continue
            replaced[mention.start] = (mention.end, antecedent.text)
            mention.take(antecedent)

    texts = [_render(clause, deleted, replaced) for clause in _clauses(sent)]
    return [t for t in texts if any(ch.isalpha() for ch in t)], mentions


def extract_statements(
    pipeline: spacy.language.Language,
    text: str,
    path: str,
) -> tuple[Claim, ...]:
    """Extract self-contained, atomic, checkable statements from a Markdown document.

    The document is split into the same paragraphs as :func:`extract_claims` (so
    ``paragraph_index`` means the same thing) and each paragraph's prose -- Markdown structure and
    inline syntax removed, hard wraps joined -- is parsed once with ``pipeline``. Each sentence is
    then classified and rewritten:

    - **dropped** when it is not declarative (a fragment, a label, a question, a title-case
      citation), a direct quotation (an opinion), hedged by a modal such as "could", "may" or
      "will" on its claim verb (a prediction no fact-check can confirm), or a consequence of the
      previous sentence ("As a result, ...");
    - **resolved**: a third-person pronoun ("it", "they", "their") is replaced by its antecedent
      from the previous sentences of the section (number and animacy agreement, nearest sentence
      first, subject first), a possessive becomes "the <noun> of <antecedent>", and a bare
      definite noun phrase ("the antenna", "the researchers", "the design") is replaced by the
      earlier mention it names: the same-head introduction ("a new MRI antenna"), the document's
      primary agent (its first named agent subject) or the artifact that agent introduced. The
      replacement is the antecedent's *grounding text*: its noun phrase plus the modifiers that
      hold a proper name or a number, appositions removed;
    - **trimmed**: a leading label or connective ("Summary:", "In addition,", "Yet"), the adverb
      "also", and a fronted clause built on an unresolvable demonstrative ("To overcome this
      limitation,") are removed;
    - **split**: a sentence coordinating several predicates under one subject with "and" becomes
      one statement per predicate;
    - **dropped** after all that when a pronoun or demonstrative still has no antecedent.

    Each statement text is parsed again (as one sentence) and must still be declarative, unhedged
    and independent. Every statement becomes one :class:`Claim`: ``raw_sentence`` is the statement
    text; ``raw_subject``/``predicate_key`` come from its subject and claim verb; numbers and
    entities are those of the whole statement, so a name in the subject counts too. Resolution is
    rule-based and deterministic for a pinned spaCy model; it can be wrong, so a statement is an
    advisory candidate, never a verified fact.

    :param pipeline: The loaded spaCy pipeline (the one ``extract_claims`` uses).
    :param text: The document text.
    :param path: The document's relative path, recorded as provenance.
    :returns: The statements in document order.
    """
    textacy_extract = importlib.import_module("textacy.extract")
    svo_extractor = getattr(
        textacy_extract, "subject_verb_object_triples", textacy_extract.triples.subject_verb_object_triples
    )

    parsed = [(block, _parse(pipeline, block) if block.text else None) for block in _prose_blocks(text)]
    discourse = _Discourse(topic=_find_topic([(block, doc) for block, doc in parsed if doc is not None]))

    candidates: list[tuple[int, str]] = []
    for block, doc in parsed:
        if block.boundary:
            discourse.new_section()
        if doc is None:
            continue
        for sent in doc.sents:
            if not any(ch.isalpha() for ch in sent.text):
                continue
            texts, mentions = _rewrite_sentence(sent, block.index, discourse)
            candidates.extend((block.index, t) for t in texts)
            discourse.add(mentions)

    statements: list[Claim] = []
    dropped = 0
    for paragraph, statement_text in candidates:
        doc = _parse_statement(pipeline, statement_text)
        sent = next(doc.sents)
        # The source sentence was declarative; the rewrite is re-parsed for the hedge and dependency
        # checks and for its subject and verb. A small model can mis-parse a rewritten subject
        # ("the Falcon 9 compiler compiles ..."), so a re-parse without a verb at all is the only
        # parse failure that drops a statement.
        verb = (
            _content_verb(sent) if _is_declarative(sent) else next((t for t in sent if t.pos_ in {"VERB", "AUX"}), None)
        )
        if verb is None or _is_hedged(sent) or _is_dependent(sent):
            dropped += 1
            continue
        subject = next((c for c in verb.children if c.dep_ in _SUBJECT_DEPS), None)
        raw_subject = " ".join(t.text for t in subject.subtree) if subject is not None else ""
        aux = [c.text for c in verb.children if c.dep_ in {"aux", "auxpass", "neg"}]
        tokens = list(sent)
        statements.append(
            Claim(
                subject_key=_normalize_key(raw_subject),
                predicate_key=_normalize_key(" ".join([*aux, verb.text])),
                raw_subject=raw_subject,
                raw_object=" ".join(_statement_objects(sent, svo_extractor)),
                raw_sentence=_statement_text([sent.text.strip()]),
                object_numbers=_statement_numbers(tokens),
                object_entities=_object_entities(sent, tokens),
                path=path,
                paragraph_index=paragraph,
            )
        )
    logger.debug("extracted %d statements (%d candidates dropped) from %s", len(statements), dropped, safe(path))
    return tuple(statements)
