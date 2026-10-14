"""Triple extraction and claim normalization for fact-contradiction candidate detection.

Extraction is deterministic only for a pinned model version (e.g., en_core_web_sm).
A model upgrade can alter Claim output.
"""

from __future__ import annotations

import importlib
import re
import string
from dataclasses import dataclass
from typing import Any

import spacy.language

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
    """Extract normalized SVO claims per paragraph from text."""
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

            obj_start = object_toks[0].i
            obj_end = object_toks[-1].i + 1
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

    return tuple(claims)
