"""Unit tests for the template ``context`` key and the ``facts`` context (Milestone 0010 Story 05.0 Task 02).

Covers the loader's closed ``context`` key (``report`` default, ``facts``), :func:`schema_for` at
the text root, the json root and alias scope, the refusal of extensions in ``facts`` templates,
the static packaged name-to-context table, :class:`FactsModel` (closed dispositions, the E5
``hidden_characters`` flag), the E3 ``##[`` json escape, and the context checks of both
``reporting`` shims and of ``render_template``. Task 04 extends this file.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from docsentinel.mining.salience import DISPOSITIONS as MINING_DISPOSITIONS
from docsentinel.models import Document, ExtractedFact, FactExtractionResult, FactSettings, ScanResult
from docsentinel.reporting import render, render_facts
from docsentinel.telemetry import loader
from docsentinel.telemetry.engine import render_template
from docsentinel.telemetry.facts_model import DISPOSITIONS, FactsModel, has_hidden_characters
from docsentinel.telemetry.filters import TemplateError
from docsentinel.telemetry.loader import (
    PACKAGED_TEMPLATE_CONTEXTS,
    available_templates,
    load_named_template,
    packaged_template_names,
    validate_template,
)


def _fact(rank: int, path: str, text: str, disposition: str = "selected") -> ExtractedFact:
    """Return a synthetic fact.

    :param rank: The listed rank.
    :param path: The document path.
    :param text: The claim text.
    :param disposition: The disposition.
    :returns: The fact.
    """
    return ExtractedFact(rank, path, 1, text, 0.5, 0.25, 0.5, 0.75, rank, 1, ("3",), ("ORG:Acme",), disposition)


def _result(*facts: ExtractedFact, include_rejected: bool = False) -> FactExtractionResult:
    """Return a synthetic extraction result.

    :param facts: The listed facts.
    :param include_rejected: The ``include_rejected`` flag.
    :returns: The result.
    """
    return FactExtractionResult(
        documents=(Document("a.md", 1), Document("b.md", 2)),
        documents_unreadable=0,
        claims_extracted=len(facts),
        facts=facts,
        settings=FactSettings(0.3, 3, 25, (0.4, 0.3, 0.3), 0.85),
        matches_ds302=True,
        include_rejected=include_rejected,
        notice="Synthetic notice.",
    )


def _line(text: str) -> dict[str, Any]:
    """Return a ``line`` node whose ``variables_used`` lists the variables of ``text``.

    :param text: The line text.
    :returns: The raw node.
    """
    return {"type": "line", "text": text, "variables_used": re.findall(r"\{([A-Za-z0-9_.]+)", text)}


def _text_template(text: str, *, context: Any = "facts", **extra: Any) -> dict[str, Any]:
    """Return a one-line text template mapping.

    :param text: The line text.
    :param context: The ``context`` value.
    :param extra: Extra top-level keys.
    :returns: The raw template.
    """
    return {
        "template_version": 1,
        "name": "t",
        "type": "text",
        "context": context,
        "lines": [_line(text)],
        **extra,
    }


def test_packaged_context_table_matches_loaded_templates():
    """
    [Unit] packaged templates: verifies the static name-to-context table equals the loaded templates (E2).

    Scenario:
        Given every packaged template file
        When each is loaded by name
        Then its ``context`` equals the table entry, the five report templates are ``report`` and the
            default listing is unchanged.

    Boundaries:
        - Focus: ``PACKAGED_TEMPLATE_CONTEXTS``, ``packaged_template_names(context=)``
        - Fixtures/params: none
        - Scope: packaged templates only

    On failure, first check:
        - Whether a packaged template was added without a table entry
    """
    assert set(PACKAGED_TEMPLATE_CONTEXTS) == set(packaged_template_names()) | set(packaged_template_names("facts"))
    for name, context in PACKAGED_TEMPLATE_CONTEXTS.items():
        assert load_named_template(name).context == context
    assert packaged_template_names() == ("github", "json", "json-documents", "json-v1", "text")
    assert packaged_template_names("facts") == ("facts-json", "facts-text")


@pytest.mark.parametrize("value", ["Report", "fact", "", 1, None])
def test_unknown_context_value_is_refused(value: Any):
    """
    [Unit] loader context key: verifies any value other than report/facts is a TemplateError.

    Scenario:
        Given a template whose ``context`` is not ``report`` or ``facts``
        When it is validated
        Then it fails with the documented message.

    Boundaries:
        - Focus: closed ``context`` key
        - Fixtures/params: parametrized over invalid values
        - Scope: ``validate_template``

    On failure, first check:
        - The ``context`` check in ``_Validator.template``
    """
    with pytest.raises(TemplateError, match='context must be "report" or "facts"'):
        validate_template(_text_template("x", context=value))


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (_text_template("{findings_count}"), "unknown variable"),
        (_text_template("{facts|len}", context="report"), "unknown variable"),
        (
            {
                "template_version": 1,
                "name": "t",
                "type": "json",
                "context": "facts",
                "body": {"$var": "profile"},
            },
            "unknown variable",
        ),
        (
            {
                "template_version": 1,
                "name": "t",
                "type": "text",
                "context": "facts",
                "lines": [
                    {
                        "type": "loop",
                        "over": "facts",
                        "as": "f",
                        "placement": "block",
                        "body": [_line("{documents_count}")],
                    }
                ],
            },
            "unknown variable",
        ),
        (
            {
                "template_version": 1,
                "name": "t",
                "type": "text",
                "context": "facts",
                "lines": [
                    {
                        "type": "loop",
                        "over": "facts",
                        "as": "run",
                        "placement": "block",
                        "body": [_line("x")],
                    }
                ],
            },
            "shadows",
        ),
        (_text_template("{f}", requires_extensions=["domain"]), "cannot require extensions"),
        (_text_template("{run.notice|ext.domain.x}"), "cannot use extension filters"),
        (_text_template("{facts.0.text}"), "must end its filter chain"),
        (_text_template("{documents.0.path|lower}"), "must end its filter chain"),
    ],
    ids=[
        "report-var-at-text-root",
        "facts-var-in-report",
        "report-var-at-json-root",
        "report-var-in-alias-scope",
        "alias-shadows-facts-root",
        "requires-extensions",
        "ext-filter",
        "text-without-sink",
        "path-without-sink",
    ],
)
def test_facts_context_refusals(raw: dict[str, Any], message: str):
    """
    [Unit] loader context key: verifies the cross-context, extension and sink refusals (E4, M4).

    Scenario:
        Given a template that names the other context's variable, uses an extension, or places an
            untrusted facts value without a terminal sink filter
        When it is validated
        Then it fails with the matching TemplateError.

    Boundaries:
        - Focus: ``schema_for`` at every scope entry point, no ``ext`` in ``facts``
        - Fixtures/params: parametrized over inline template mappings
        - Scope: ``validate_template``

    On failure, first check:
        - Whether a scope entry point names ``CONTEXT_SCHEMA`` directly instead of ``schema_for``
    """
    with pytest.raises(TemplateError, match=message):
        validate_template(raw)


def test_github_sink_facts_template_obeys_t2_r1():
    """
    [Unit] loader context key: verifies a github-sink facts template obeys the T2-R1 rules unchanged.

    Scenario:
        Given a ``facts`` text template with ``output.sink: github``
        When it places claim text on a plain line, or in a well-formed command with ``gha_data``
        Then the plain line is refused and the command line loads.

    Boundaries:
        - Focus: sink rules apply to both contexts
        - Fixtures/params: inline mappings
        - Scope: ``validate_template``

    On failure, first check:
        - Whether ``_check_ref`` started branching on the context
    """
    github = {"output": {"sink": "github"}}
    with pytest.raises(TemplateError, match="well-formed workflow command"):
        validate_template(_text_template("fact {facts.0.text|gha_data}", **github))
    loaded = validate_template(
        _text_template("::notice file={facts.0.path|gha_property}::{facts.0.text|gha_data}", **github)
    )
    assert loaded.context == "facts"


def test_facts_model_dispositions_and_hidden_characters():
    """
    [Unit] facts model: verifies the closed disposition set and the E5 hidden-characters flag.

    Scenario:
        Given facts holding U+E0041, U+2060, plain text, and a fact with an unknown disposition
        When the context is built
        Then the hidden ones are flagged, the plain one is not, and the unknown disposition raises.

    Boundaries:
        - Focus: ``FactsModel.build``, ``has_hidden_characters``, parity with ``mining.salience``
        - Fixtures/params: synthetic facts
        - Scope: pure function

    On failure, first check:
        - The ``_HIDDEN_CODE_POINTS`` table and the category test
    """
    assert DISPOSITIONS == frozenset(MINING_DISPOSITIONS)
    context = FactsModel.build(
        _result(_fact(1, "b.md", "tag\U000e0041"), _fact(2, "a.md", "word⁠joiner"), _fact(3, "a.md", "plain"))
    )
    assert [fact["hidden_characters"] for fact in context["facts"]] == [True, True, False]
    assert [doc["path"] for doc in context["documents"]] == ["a.md", "b.md"]
    assert [fact["rank"] for fact in context["documents"][0]["facts"]] == [2, 3]
    assert not has_hidden_characters("‮")  # neutralize escapes it: visible, so not hidden
    with pytest.raises(ValueError, match="closed set"):
        FactsModel.build(_result(_fact(1, "a.md", "x", disposition="forged\x1b[31m")))


def test_facts_json_escapes_the_legacy_marker_losslessly():
    """
    [Unit] facts-json: verifies ``##[`` never reaches the output and the parsed text is unchanged (E3).

    Scenario:
        Given a claim ``##[error]x`` holding a bidi control
        When it is rendered with ``facts-json`` and ``facts-text``
        Then the json is ASCII with exactly the documented keys and no ``##[`` and round-trips equal,
            and the text output neutralizes it.

    Boundaries:
        - Focus: the engine's facts-context marker escape, packaged templates
        - Fixtures/params: synthetic result
        - Scope: ``render_facts``

    On failure, first check:
        - ``_JsonStream._emit`` and ``escape_marker``
    """
    claim = "##[error]x ‮"
    result = _result(_fact(1, "a.md", claim))
    output = render_facts(result, "facts-json")
    assert "##[" not in output and output.isascii()
    parsed = json.loads(output)
    assert list(parsed) == [
        "schema",
        "schema_version",
        "notice",
        "matches_ds302",
        "include_rejected",
        "settings",
        "summary",
        "facts",
    ]
    assert parsed["facts"][0]["text"] == claim
    text = render_facts(result)
    assert "##[" not in text and "‮" not in text and "##\\[error]x \\u202e" in text


def test_facts_text_marker_and_disposition():
    """
    [Unit] facts-text: verifies the hidden-characters marker and the --all disposition column (E5).

    Scenario:
        Given a hidden-character claim and a plain claim, listed with and without rejected claims
        When rendered with ``facts-text``
        Then only the hidden one carries the marker and the disposition shows only with include_rejected.

    Boundaries:
        - Focus: packaged ``facts-text`` layout
        - Fixtures/params: synthetic result
        - Scope: ``render_facts``

    On failure, first check:
        - The ``when`` guards in ``facts-text.json``
    """
    facts = (_fact(1, "a.md", "tag\U000e0041"), _fact(2, "a.md", "plain"))
    lines = render_facts(_result(*facts)).splitlines()
    assert lines[0] == "a.md"
    assert lines[1].endswith("paragraph 1: [hidden characters] tag\U000e0041")
    assert lines[2].endswith("paragraph 1: plain")
    assert lines[-2:] == ["Matches the DS302 selection for this configuration: yes", "Synthetic notice."]
    listed = render_facts(_result(*facts, include_rejected=True)).splitlines()
    assert listed[2].endswith("paragraph 1 selected: plain")


def test_cross_context_rendering_is_refused():
    """
    [Unit] reporting shims and renderer: verifies a template of the other context is refused (E4).

    Scenario:
        Given a report template and a facts template
        When each is rendered through the wrong shim, or ``render_template`` gets the wrong model kind
        Then the documented errors are raised.

    Boundaries:
        - Focus: ``require_context`` in ``render``, ``render_facts`` and ``render_template``
        - Fixtures/params: packaged templates
        - Scope: rendering entry points

    On failure, first check:
        - Whether a shim dropped its ``require_context`` call or the ``model_kind`` keyword
    """
    scan = ScanResult(profile="fast", documents=(), findings=(), enabled_rules=(), pending=())
    with pytest.raises(ValueError, match="renders fact extraction output; use docsentinel extract-facts"):
        render(scan, "facts-json")
    with pytest.raises(ValueError, match="is a report template; use it with docsentinel scan"):
        render_facts(_result(), "text")
    context = FactsModel.build(_result())
    with pytest.raises(TemplateError, match="renders fact extraction output"):
        render_template(load_named_template("facts-json"), context)
    with pytest.raises(TemplateError, match="is a report template"):
        render_template(load_named_template("json"), {}, model_kind="facts")


def test_listing_opens_no_directory_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] template listing: verifies listing reads no report_templates_dir file and a malformed one fails alone (E2).

    Scenario:
        Given a ``report_templates_dir`` holding a malformed template and the loader's read gate spied
        When the templates are listed for either context
        Then no file is read, the name is listed, and only selecting that name fails.

    Boundaries:
        - Focus: ``available_templates(context=)`` stays name-only
        - Fixtures/params: ``tmp_path``, ``monkeypatch``
        - Scope: loader listing and load by name

    On failure, first check:
        - Whether listing started opening files to split them by context
    """
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "broken.json").write_text("{not json", encoding="utf-8")
    reads: list[str] = []
    real = loader._read_gated

    def spy(path: Path, label: str, *, nofollow: bool) -> str:
        """Record a read, then delegate.

        :param path: The file.
        :param label: The echoed label.
        :param nofollow: The symlink flag.
        :returns: The file text.
        """
        reads.append(label)
        return real(path, label, nofollow=nofollow)

    monkeypatch.setattr(loader, "_read_gated", spy)
    assert "broken" in available_templates(tmp_path, "templates")
    assert "broken" in available_templates(tmp_path, "templates", context="facts")
    assert reads == []
    assert load_named_template("json", root=tmp_path, templates_dir="templates").context == "report"
    with pytest.raises(TemplateError):
        load_named_template("broken", root=tmp_path, templates_dir="templates")
