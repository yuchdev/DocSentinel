"""DS302 consent gate helper (Milestone 0010 Story 01.0 Task 05, threat model 0010 M1-M3, M6, M7)."""

import ast
import inspect
import os
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import pytest

from docsentinel.config import Config, ConfigError
from docsentinel.detectors import fact_check
from docsentinel.detectors.fact_check import (
    USE_EXTERNAL_API_ENV,
    ExternalApiGate,
    external_api_requested,
    resolve_external_api_gate,
)
from docsentinel.fact_check.protocol import FACT_CHECK_BACKENDS, FactCheckResult
from tests.fact_check_fakes import FAKE_KEY_ENV, SENTINEL, make_fake_backend

#: The Lenz key variable (plan contract C3).
LENZ_KEY_ENV = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"


class LoadableLenz:
    """A conforming stand-in for the not yet shipped Lenz backend class."""

    name = "lenz"
    API_KEY_ENV_VAR: ClassVar[str] = LENZ_KEY_ENV

    def check_claim(self, claim: str) -> FactCheckResult:
        """Never called.

        :param claim: The text.
        :returns: Nothing; it raises.
        :raises AssertionError: Always.
        """
        raise AssertionError(claim)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("true", False),
        ("TRUE", False),
        ("yes", False),
        (" 1", False),
        ("1 ", False),
        ("1\n", False),
        ("1\r", False),
        ("01", False),
        ("0", False),
        ("", False),
        ("１", False),
    ],
)
def test_env_value_must_be_exactly_one(monkeypatch: pytest.MonkeyPatch, value: str, expected: bool):
    """
    [Unit] fact-check gate: verifies only the exact environment value "1" requests egress.

    Scenario:
        Given DOCSENTINEL_USE_EXTERNAL_API set to one candidate value and no flag
        When external_api_requested(False) is called
        Then only "1" gives True.

    Boundaries:
        - Focus: threat model M2
        - Fixtures/params: the FC-2 value list
        - Scope: external_api_requested only

    On failure, first check:
        - Whether the helper normalizes the value
    """
    monkeypatch.setenv(USE_EXTERNAL_API_ENV, value)

    assert external_api_requested(False) is expected


@pytest.mark.parametrize("value", ["false", "1", 1, 0, None])
def test_non_bool_consent_is_refused(value: object):
    """
    [Unit] fact-check gate: verifies a non-bool consent raises ConfigError in both helpers.

    Scenario:
        Given a use_external_api value that is not a bool
        When external_api_requested or resolve_external_api_gate is called
        Then ConfigError is raised with the fixed message.

    Boundaries:
        - Focus: threat model M3
        - Fixtures/params: five non-bool values
        - Scope: the two gate helpers

    On failure, first check:
        - The first statement of external_api_requested
    """
    with pytest.raises(ConfigError, match="^use_external_api must be True or False$"):
        external_api_requested(value)
    with pytest.raises(ConfigError, match="^use_external_api must be True or False$"):
        resolve_external_api_gate(Config(), use_external_api=value)


@pytest.mark.parametrize("backend", ["lenz\n", "Lenz", "lenz ", "../x", ""])
def test_invalid_injected_backend_is_a_config_error(backend: str):
    """
    [Unit] fact-check gate: verifies an injected invalid backend name raises ConfigError, never ValueError.

    Scenario:
        Given an injected Config whose fact_check_backend is not a known backend
        When the gate is resolved
        Then ConfigError lists the known names.

    Boundaries:
        - Focus: threat model M7
        - Fixtures/params: near-miss names
        - Scope: resolve_external_api_gate only

    On failure, first check:
        - Whether membership is checked before expected_api_key_env_var
    """
    with pytest.raises(ConfigError, match="^fact_check_backend must be one of: lenz$"):
        resolve_external_api_gate(Config(fact_check_backend=backend), use_external_api=True)


def test_reasons_name_only_what_is_missing(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] fact-check gate: verifies the reasons and skip message for neither, flag only, key only and both.

    Scenario:
        Given the four combinations of the flag and the Lenz key
        When the gate is resolved
        Then the reasons are fixed text and the key variable name, in order, and the key value never appears.

    Boundaries:
        - Focus: threat model M6
        - Fixtures/params: the key set to a sentinel
        - Scope: ExternalApiGate and resolve_external_api_gate

    On failure, first check:
        - ExternalApiGate.reasons
    """
    request = "pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1)"
    monkeypatch.setitem(FACT_CHECK_BACKENDS, "lenz", LoadableLenz)
    neither = resolve_external_api_gate(Config(), use_external_api=False)
    flag_only = resolve_external_api_gate(Config(), use_external_api=True)
    monkeypatch.setenv(LENZ_KEY_ENV, "sentinel-not-a-real-key-0010")
    key_only = resolve_external_api_gate(Config(), use_external_api=False)
    both = resolve_external_api_gate(Config(), use_external_api=True)

    assert neither.skip_message() == f"DS302 skipped: {request}; set {LENZ_KEY_ENV}"
    assert flag_only.skip_message() == f"DS302 skipped: set {LENZ_KEY_ENV}"
    assert key_only.skip_message() == f"DS302 skipped: {request}"
    assert both == ExternalApiGate(requested=True, backend="lenz", key_env_var=LENZ_KEY_ENV, key_present=True)
    assert both.open and both.reasons() == ()
    assert "sentinel" not in repr(both)


def test_config_never_grants_consent():
    """
    [Unit] fact-check gate: verifies a Config attribute named use_external_api is ignored.

    Scenario:
        Given a Config subclass exposing use_external_api = True
        When the gate is resolved without the flag
        Then requested is False.

    Boundaries:
        - Focus: threat model M1
        - Fixtures/params: none
        - Scope: resolve_external_api_gate only

    On failure, first check:
        - Whether the helper reads consent from Config
    """

    @dataclass(frozen=True)
    class Smuggling(Config):
        """A Config carrying a consent-shaped attribute."""

        use_external_api: bool = True

    assert resolve_external_api_gate(Smuggling(), use_external_api=False).requested is False


def test_requested_helper_does_not_reuse_the_deep_confirm_parser():
    """
    [Unit] fact-check gate: verifies external_api_requested never references _env_confirms.

    Scenario:
        Given the source of external_api_requested
        When it is parsed
        Then no Name or Attribute in it is _env_confirms (the lenient DOCSENTINEL_DEEP_CONFIRM parser).

    Boundaries:
        - Focus: threat model M2
        - Fixtures/params: none
        - Scope: AST of one function

    On failure, first check:
        - Whether the helper was rewritten on top of the deep_confirm env parser
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(external_api_requested)))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    assert "_env_confirms" not in names
    assert "environ" in names


@pytest.mark.parametrize(
    ("flag", "env", "expected"),
    [(False, None, False), (False, "1", True), (True, None, True), (True, "1", True), (True, "0", True)],
)
def test_flag_or_env_truth_table(monkeypatch: pytest.MonkeyPatch, flag: bool, env: object, expected: bool):
    """
    [Unit] fact-check gate: verifies requested is the keyword OR the exact environment value.

    Scenario:
        Given each combination of the flag and DOCSENTINEL_USE_EXTERNAL_API (unset, "1", "0")
        When external_api_requested and resolve_external_api_gate run
        Then both report the OR of the two, as a real bool.

    Boundaries:
        - Focus: ADR 0007 Contract 1
        - Fixtures/params: flag, env value
        - Scope: the two gate helpers

    On failure, first check:
        - The return expression of external_api_requested
    """
    if env is None:
        monkeypatch.delenv(USE_EXTERNAL_API_ENV, raising=False)
    else:
        monkeypatch.setenv(USE_EXTERNAL_API_ENV, env)

    requested = resolve_external_api_gate(Config(), use_external_api=flag).requested

    assert external_api_requested(flag) is expected
    assert requested is expected
    assert type(requested) is bool


@pytest.mark.parametrize(("value", "present"), [(None, False), ("", False), (SENTINEL, True)])
def test_key_present_needs_a_non_empty_variable(monkeypatch: pytest.MonkeyPatch, value: object, present: bool):
    """
    [Unit] fact-check gate: verifies key_present for an unset, empty and non-empty key variable.

    Scenario:
        Given the Lenz key variable unset, empty or set to the sentinel
        When the gate is resolved without the flag
        Then key_present is False, False, True and the gate holds no key value.

    Boundaries:
        - Focus: ADR 0007 Contract 3
        - Fixtures/params: three key states
        - Scope: resolve_external_api_gate

    On failure, first check:
        - The key_present expression
    """
    if value is None:
        monkeypatch.delenv(LENZ_KEY_ENV, raising=False)
    else:
        monkeypatch.setenv(LENZ_KEY_ENV, value)

    gate = resolve_external_api_gate(Config(), use_external_api=False)

    assert gate.key_present is present
    assert gate.key_env_var == LENZ_KEY_ENV
    assert SENTINEL not in repr(gate)


def test_reasons_order_with_every_item_missing():
    """
    [Unit] fact-check gate: verifies the fixed reason order request, key, backend.

    Scenario:
        Given a gate state missing the request, the key and the backend
        When reasons() and skip_message() are read
        Then the three reasons appear in that order, joined by "; ".

    Boundaries:
        - Focus: threat model M6 (fixed text only)
        - Fixtures/params: none
        - Scope: ExternalApiGate

    On failure, first check:
        - The append order in ExternalApiGate.reasons
    """
    gate = ExternalApiGate(
        requested=False, backend="lenz", key_env_var=LENZ_KEY_ENV, key_present=False, backend_available=False
    )

    assert gate.reasons() == (
        "pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1)",
        f"set {LENZ_KEY_ENV}",
        "backend lenz not available",
    )
    assert gate.skip_message() == "DS302 skipped: " + "; ".join(gate.reasons())
    assert gate.open is False


def test_setattr_smuggled_consent_is_ignored():
    """
    [Unit] fact-check gate: verifies a use_external_api attribute forced onto a frozen Config is ignored.

    Scenario:
        Given a Config instance with use_external_api=True set through object.__setattr__,
        and a Config subclass with a use_external_api property returning True
        When the gate is resolved without the flag
        Then requested is False for both.

    Boundaries:
        - Focus: threat model M1
        - Fixtures/params: none
        - Scope: resolve_external_api_gate

    On failure, first check:
        - Whether the helper reads getattr(config, "use_external_api")
    """
    smuggled = Config()
    object.__setattr__(smuggled, "use_external_api", True)

    class WithProperty(Config):
        """A Config subclass claiming consent through a property."""

        @property
        def use_external_api(self) -> bool:
            """Always claim consent."""
            return True

    assert resolve_external_api_gate(smuggled, use_external_api=False).requested is False
    assert resolve_external_api_gate(WithProperty(), use_external_api=False).requested is False


def test_direct_detect_refuses_string_consent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    [Unit] fact-check gate: verifies detect(use_external_api="false") raises before any backend call.

    Scenario:
        Given a registered fake backend with its key set
        When detect() is called directly with use_external_api="false"
        Then ConfigError is raised and the fake is never constructed or called.

    Boundaries:
        - Focus: threat model M3 (a truthy string must not open the gate)
        - Fixtures/params: shared fake, sentinel key
        - Scope: detect() called directly

    On failure, first check:
        - The isinstance check in external_api_requested
    """
    fake = make_fake_backend()
    monkeypatch.setitem(FACT_CHECK_BACKENDS, fake.name, fake)
    monkeypatch.setenv(FAKE_KEY_ENV, SENTINEL)

    with pytest.raises(ConfigError, match="^use_external_api must be True or False$"):
        fact_check.detect(tmp_path, (), Config(fact_check_backend="fake"), use_external_api="false")

    assert fake.constructed == 0
    assert fake.calls == []
    assert os.environ[FAKE_KEY_ENV] == SENTINEL
