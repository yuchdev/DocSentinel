"""Facts model: the JSON-shaped context every ``facts`` template renders from.

:class:`FactsModel` is the core provider of the ``facts`` template context (Milestone
0010 Story 05.0 Task 02, decision X9). It turns a
:class:`~docsentinel.models.FactExtractionResult` into a plain tree of
``dict``/``list``/``str``/``int``/``float``/``bool`` -- never an object -- so a template
reaches data but no attribute. :data:`FACTS_CONTEXT_SCHEMA` declares every variable with
its type and trust tag in the same :class:`~docsentinel.telemetry.model.Variable` shape as
the report schema; the loader picks it for a template whose ``context`` is ``facts``.

Security contract (``docs/security/threat-model-0010-extract-facts-2026-11-24.md``):

* **E4** -- the disposition is tagged trusted, so :meth:`FactsModel.build` refuses any
  value outside :data:`DISPOSITIONS`. The notice is tagged trusted and comes from the
  engine constants; a notice the ``neutralize`` table would change is refused too.
  The schema has no ``ext`` entry.
* **0007 M1/M2** -- every untrusted list element (``numbers[]``, ``entities[]``) and
  every document-derived string (``path``, ``text``) is tagged untrusted.
* **E5** -- each fact carries the trusted ``hidden_characters`` flag: true when its text
  holds a code point ``neutralize`` keeps but a terminal renders invisibly (category
  Cf, Co or Cn, or the 0007 R4 list).

The module imports only :mod:`docsentinel.models` and telemetry siblings, and reads no
file, environment variable or clock. It is under the hardcode-ban tripwire, which allows
the fact field name ``text`` only as a dict-literal key.
"""

import unicodedata
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

from docsentinel.models import ExtractedFact, FactExtractionResult
from docsentinel.telemetry.filters import neutralize
from docsentinel.telemetry.model import TRUSTED, UNTRUSTED, Variable

#: The closed disposition vocabulary; equal to ``mining.salience.DISPOSITIONS`` (a unit
#: test pins the parity; this layer may not import the mining package).
DISPOSITIONS: Final[frozenset[str]] = frozenset({"selected", "duplicate", "below_floor", "document_cap", "total_cap"})

#: Unicode categories a terminal renders invisibly or not at all (E5).
_HIDDEN_CATEGORIES: Final[frozenset[str]] = frozenset({"Cf", "Co", "Cn"})

#: The 0007 R4 code points outside those categories that also render invisibly: the
#: Hangul fillers, the Mongolian free variation selectors and the variation selectors.
#: (U+00AD, U+180E, U+2060-U+2064, U+FFF9-U+FFFB and U+E0000-U+E007F are category Cf.)
_HIDDEN_CODE_POINTS: Final[frozenset[int]] = frozenset(
    {0x00AD, 0x115F, 0x1160, 0x180E, 0x3164, 0xFFA0}
    | set(range(0x180B, 0x1810))
    | set(range(0x2060, 0x2065))
    | set(range(0xFE00, 0xFE10))
    | set(range(0xE0000, 0xE0080))
    | set(range(0xE0100, 0xE01F0))
)


def _frozen(entries: dict[str, Variable]) -> Mapping[str, Variable]:
    """Return a read-only view of a schema mapping.

    :param entries: Variable name -> schema entry.
    :returns: An immutable mapping proxy.
    """
    return MappingProxyType(entries)


#: The three salience signals of a fact, or the three weights of the run.
_SIGNALS_SCHEMA: Final[Mapping[str, Variable]] = _frozen(
    {
        "numeric": Variable("float", TRUSTED),
        "entity": Variable("float", TRUSTED),
        "distinctiveness": Variable("float", TRUSTED),
    }
)

#: Members of one fact, in ``facts`` and in ``documents[].facts``.
FACT_SCHEMA: Final[Mapping[str, Variable]] = _frozen(
    {
        "rank": Variable("int", TRUSTED),
        "path": Variable("str", UNTRUSTED),
        "paragraph_index": Variable("int", TRUSTED),
        "text": Variable("str", UNTRUSTED),
        "score": Variable("float", TRUSTED),
        "signals": Variable("object", None, _SIGNALS_SCHEMA),
        "cluster": Variable(
            "object", None, _frozen({"id": Variable("int", TRUSTED), "size": Variable("int", TRUSTED)})
        ),
        "numbers": Variable("list[str]", UNTRUSTED),
        "entities": Variable("list[str]", UNTRUSTED),
        "disposition": Variable("str", TRUSTED),
        "hidden_characters": Variable("bool", TRUSTED),
    }
)

#: Members of ``run.settings``.
_SETTINGS_SCHEMA: Final[Mapping[str, Variable]] = _frozen(
    {
        "min_salience": Variable("float", TRUSTED),
        "max_per_document": Variable("int", TRUSTED),
        "max_total": Variable("int", TRUSTED),
        "dedup_threshold": Variable("float", TRUSTED),
        "weights": Variable("object", None, _SIGNALS_SCHEMA),
    }
)

#: Members of ``run.summary``.
_SUMMARY_SCHEMA: Final[Mapping[str, Variable]] = _frozen(
    {
        "documents": Variable("int", TRUSTED),
        "unreadable": Variable("int", TRUSTED),
        "claims_extracted": Variable("int", TRUSTED),
        "facts_selected": Variable("int", TRUSTED),
        "facts_listed": Variable("int", TRUSTED),
    }
)

#: Members of ``run``.
_RUN_SCHEMA: Final[Mapping[str, Variable]] = _frozen(
    {
        "notice": Variable("str", TRUSTED),
        "matches_ds302": Variable("bool", TRUSTED),
        "include_rejected": Variable("bool", TRUSTED),
        "settings": Variable("object", None, _SETTINGS_SCHEMA),
        "summary": Variable("object", None, _SUMMARY_SCHEMA),
    }
)

#: Members of a ``documents`` element.
_DOCUMENT_SCHEMA: Final[Mapping[str, Variable]] = _frozen(
    {"path": Variable("str", UNTRUSTED), "facts": Variable("list[fact]", None, FACT_SCHEMA)}
)

#: Top-level ``facts`` context schema (story README, "Facts template context"); no ``ext``.
FACTS_CONTEXT_SCHEMA: Final[Mapping[str, Variable]] = _frozen(
    {
        "run": Variable("object", None, _RUN_SCHEMA),
        "facts": Variable("list[fact]", None, FACT_SCHEMA),
        "documents": Variable("list[document]", None, _DOCUMENT_SCHEMA),
    }
)


def has_hidden_characters(text: str) -> bool:
    """Return whether ``text`` holds a code point ``neutralize`` keeps but hides (E5).

    :param text: The claim text.
    :returns: ``True`` when a code point of category Cf, Co or Cn, or of the 0007 R4
        list, survives :func:`~docsentinel.telemetry.filters.neutralize` unchanged.
    """
    return any(
        (ord(character) in _HIDDEN_CODE_POINTS or unicodedata.category(character) in _HIDDEN_CATEGORIES)
        and neutralize(character) == character
        for character in text
    )


def _signals(numeric: float, entity: float, distinctiveness: float) -> dict[str, float]:
    """Return a signals or weights object with float values.

    :param numeric: The numeric component.
    :param entity: The entity component.
    :param distinctiveness: The distinctiveness component.
    :returns: ``{numeric, entity, distinctiveness}`` as JSON numbers.
    """
    return {"numeric": float(numeric), "entity": float(entity), "distinctiveness": float(distinctiveness)}


def _fact(fact: ExtractedFact) -> dict[str, Any]:
    """Return the JSON-shaped mapping of one fact.

    :param fact: The extracted fact.
    :returns: The fact mapping of :data:`FACT_SCHEMA`.
    :raises ValueError: When the disposition is outside :data:`DISPOSITIONS` (E4).
    """
    if not isinstance(fact.disposition, str) or fact.disposition not in DISPOSITIONS:
        raise ValueError(f"fact {int(fact.rank)} has a disposition outside the closed set")
    return {
        "rank": int(fact.rank),
        "path": str(fact.path),
        "paragraph_index": int(fact.paragraph_index),
        "text": str(fact.text),
        "score": float(fact.score),
        "signals": _signals(fact.numeric, fact.entity, fact.distinctiveness),
        "cluster": {"id": int(fact.cluster_id), "size": int(fact.cluster_size)},
        "numbers": [str(number) for number in fact.numbers],
        "entities": [str(entity) for entity in fact.entities],
        "disposition": fact.disposition,
        "hidden_characters": has_hidden_characters(str(fact.text)),
    }


class FactsModel:
    """Builds the ``facts`` template context from a fact-extraction result."""

    @staticmethod
    def build(result: FactExtractionResult) -> dict[str, Any]:
        """Return the JSON-shaped context of :data:`FACTS_CONTEXT_SCHEMA`.

        ``facts`` keeps the listed order; ``documents`` holds each document with at
        least one listed fact, sorted by path, its facts in rank order. The fact
        mappings are shared between the two lists (the renderer checks a shared
        sub-tree once).

        :param result: The completed ``extract_facts`` run.
        :returns: The context tree (``dict``/``list``/``str``/``int``/``float``/``bool`` only).
        :raises TypeError: When ``result`` is not a ``FactExtractionResult``.
        :raises ValueError: When a disposition is outside :data:`DISPOSITIONS`, or the
            notice holds a code point the ``neutralize`` table escapes (E4).
        """
        if not isinstance(result, FactExtractionResult):
            raise TypeError("FactsModel.build needs a FactExtractionResult")
        notice = str(result.notice)
        if neutralize(notice) != notice:
            raise ValueError("the fact extraction notice must be plain text")
        facts = [_fact(fact) for fact in result.facts]
        by_path: dict[str, list[dict[str, Any]]] = {}
        for entry in facts:
            by_path.setdefault(entry["path"], []).append(entry)
        documents = [
            {"path": path, "facts": sorted(by_path[path], key=lambda entry: entry["rank"])} for path in sorted(by_path)
        ]
        settings = result.settings
        return {
            "run": {
                "notice": notice,
                "matches_ds302": bool(result.matches_ds302),
                "include_rejected": bool(result.include_rejected),
                "settings": {
                    "min_salience": float(settings.min_salience),
                    "max_per_document": int(settings.max_per_document),
                    "max_total": int(settings.max_total),
                    "dedup_threshold": float(settings.dedup_threshold),
                    "weights": _signals(*settings.weights),
                },
                "summary": {
                    "documents": len(result.documents),
                    "unreadable": int(result.documents_unreadable),
                    "claims_extracted": int(result.claims_extracted),
                    "facts_selected": len(result.selected),
                    "facts_listed": len(facts),
                },
            },
            "facts": facts,
            "documents": documents,
        }


__all__ = ["DISPOSITIONS", "FACTS_CONTEXT_SCHEMA", "FACT_SCHEMA", "FactsModel", "has_hidden_characters"]
