import dataclasses
import datetime
import json
import re

import pytest

from docsentinel import telemetry


@pytest.fixture
def event() -> telemetry.FaultEvent:
    """Return an event with inline, JSON-primitive context."""
    return telemetry.FaultEvent(
        ts="2026-08-30T00:00:00Z",
        domain="docs",
        fault_class="dangling_reference",
        tier="deterministic",
        rule="DS101",
        outcome="rejected",
        model="anthropic/claude-x",
        details={"severity": "error", "line": 42, "score": 0.5, "strict": True, "extra": None},
    )


def test_to_json_dict_preserves_wire_values(event: telemetry.FaultEvent):
    """[Unit] Serialization preserves the contract's wire values.

    Scenario:
        Serialize an inline event with every JSON primitive and round-trip it.
    Boundaries:
        Only fault_class is renamed; all other keys and values stay unchanged.
    On failure, first check:
        The serializer's rename and the event's primitive details.
    """
    data = telemetry.to_json_dict(event)
    assert data == {
        "ts": "2026-08-30T00:00:00Z",
        "domain": "docs",
        "class": "dangling_reference",
        "tier": "deterministic",
        "rule": "DS101",
        "outcome": "rejected",
        "model": "anthropic/claude-x",
        "schema_version": "1.0",
        "details": {
            "severity": "error",
            "line": 42,
            "score": 0.5,
            "strict": True,
            "extra": None,
        },
    }
    assert "fault_class" not in data
    assert json.loads(json.dumps(data)) == data


def test_fault_event_defaults_and_null_model(event: telemetry.FaultEvent):
    """[Unit] Minimal events default the version and preserve a null model.

    Scenario:
        Construct an event without optional context and serialize model=None.
    Boundaries:
        Schema defaults from SCHEMA_VERSION; JSON model is null, not omitted.
    On failure, first check:
        Dataclass defaults and null serialization.
    """
    minimal = telemetry.FaultEvent(
        ts=event.ts,
        domain=event.domain,
        fault_class=event.fault_class,
        tier=event.tier,
        rule=event.rule,
        outcome="pass",
        model=None,
    )
    assert minimal.schema_version == telemetry.SCHEMA_VERSION
    assert minimal.details == {}
    decoded = json.loads(json.dumps(telemetry.to_json_dict(minimal)))
    assert decoded["model"] is None
    assert decoded["details"] == {}


def test_fault_event_details_defaults_are_independent(event: telemetry.FaultEvent):
    """[Unit] Default context maps are allocated separately.

    Scenario:
        Construct two events without supplying details.
    Boundaries:
        Empty default maps compare equal but never share identity.
    On failure, first check:
        The details default_factory.
    """
    first = dataclasses.replace(event, details={})
    values = dataclasses.asdict(event)
    del values["details"]
    second = telemetry.FaultEvent(**values)
    third = telemetry.FaultEvent(**values)
    assert second.details == first.details == third.details == {}
    assert second.details is not third.details


def test_to_json_dict_does_not_mutate_event(event: telemetry.FaultEvent):
    """[Unit] Serializing an event leaves its context independent.

    Scenario:
        Change a serialized details value after converting the event.
    Boundaries:
        Neither the original details nor fault_class changes.
    On failure, first check:
        Whether serialization copies rather than aliases event details.
    """
    data = telemetry.to_json_dict(event)
    data["details"]["line"] = 99
    assert event.details["line"] == 42
    assert event.fault_class == "dangling_reference"
    assert telemetry.to_json_dict(event)["class"] == "dangling_reference"


def test_fault_event_is_frozen(event: telemetry.FaultEvent):
    """[Unit] Event attributes reject reassignment.

    Scenario:
        Attempt to overwrite the rule on an existing event.
    Boundaries:
        FrozenInstanceError protects attributes, not deep mapping contents.
    On failure, first check:
        The dataclass frozen option.
    """
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.rule = "DS102"


def test_fault_event_rejects_positional_arguments(event: telemetry.FaultEvent):
    """[Unit] Event construction requires keyword arguments.

    Scenario:
        Supply every required event value positionally.
    Boundaries:
        Construction raises TypeError before accepting positional fields.
    On failure, first check:
        The dataclass kw_only option.
    """
    with pytest.raises(TypeError):
        telemetry.FaultEvent(
            event.ts,
            event.domain,
            event.fault_class,
            event.tier,
            event.rule,
            event.outcome,
            event.model,
        )


def test_fault_event_requires_model_argument(event: telemetry.FaultEvent):
    """[Unit] Unknown provenance still requires an explicit model argument.

    Scenario:
        Construct an event with the model keyword missing.
    Boundaries:
        None is valid, but omission raises TypeError naming model.
    On failure, first check:
        Whether model accidentally acquired a default.
    """
    values = dataclasses.asdict(event)
    del values["model"]
    with pytest.raises(TypeError, match="model"):
        telemetry.FaultEvent(**values)


def test_fault_event_preserves_open_strings(event: telemetry.FaultEvent):
    """[Unit] Contract vocabularies remain open strings.

    Scenario:
        Serialize future domain, class, tier, outcome, and version strings.
    Boundaries:
        Vocabulary mirrors document values without enforcing closed enums.
    On failure, first check:
        Unexpected validation or coercion in construction or serialization.
    """
    extended = dataclasses.replace(
        event,
        domain="future-domain",
        fault_class="future-class",
        tier="future-tier",
        outcome="future-outcome",
        schema_version="1.1",
    )
    data = telemetry.to_json_dict(extended)
    assert data["domain"] == "future-domain"
    assert data["class"] == "future-class"
    assert data["tier"] == "future-tier"
    assert data["outcome"] == "future-outcome"
    assert data["schema_version"] == "1.1"


def test_fault_event_contract_conformance(event: telemetry.FaultEvent):
    """[Unit] Trip on drift from fault-event-contract.md sections 1 through 3.

    Scenario:
        Compare fields, vocabularies, and version with literals copied from the spec.
    Boundaries:
        References are independent literals, never derived from implementation.
    On failure, first check:
        Whether the spec and implementation need a coordinated schema bump.
    """
    assert {field.name for field in dataclasses.fields(telemetry.FaultEvent)} == {
        "ts",
        "domain",
        "fault_class",
        "tier",
        "rule",
        "outcome",
        "model",
        "schema_version",
        "details",
    }
    assert set(telemetry.to_json_dict(event)) == {
        "ts",
        "domain",
        "class",
        "tier",
        "rule",
        "outcome",
        "model",
        "schema_version",
        "details",
    }
    assert telemetry.TIER_VOCABULARY == {"deterministic", "heuristic"}
    assert telemetry.OUTCOME_VOCABULARY == {
        "pass",
        "rejected",
        "advisory",
        "suppressed",
        "escalated",
    }
    assert telemetry.SCHEMA_VERSION == "1.0"
    assert event.schema_version == "1.0"


def test_utc_now_iso_is_current_utc_with_z_suffix():
    """[Unit] Timestamp helpers produce current RFC-3339 UTC with a Z suffix.

    Scenario:
        Capture a timestamp between two real UTC clock readings.
    Boundaries:
        Accept optional fractional seconds but require UTC and trailing Z.
    On failure, first check:
        Clock changes, timezone selection, and numeric-offset replacement.
    """
    before = datetime.datetime.now(datetime.UTC)
    timestamp = telemetry.utc_now_iso()
    after = datetime.datetime.now(datetime.UTC)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", timestamp)
    parsed = datetime.datetime.fromisoformat(timestamp)
    assert parsed.utcoffset() == datetime.timedelta(0)
    assert before <= parsed <= after
