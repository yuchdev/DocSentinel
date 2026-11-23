"""Unit tests for ``docsentinel.fact_check.protocol`` (Milestone 0010 Story 01.0 Task 04).

ADR 0007 Contract 4 and threat model docs/security/threat-model-0010-fact-check-gating-2026-11-23.md
M5/M7/M8. Covers the ``FactCheckClient`` structural check, ``FactCheckResult`` validation, the
backend-name grammar under ``re.fullmatch``, the registry split (static module map, lazy
``load_backend``) and the drift test against ``config.FACT_CHECK_BACKEND_NAMES``. No backend module
exists yet and no network call is made: every import of a backend module is intercepted.
"""

from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from docsentinel import config
from docsentinel.fact_check import protocol
from docsentinel.fact_check.protocol import (
    FACT_CHECK_BACKEND_MODULES,
    MAX_CITATION_CHARS,
    MAX_CITATIONS,
    REPORTABLE_VERDICTS,
    VERDICTS,
    FactCheckClient,
    FactCheckError,
    FactCheckResult,
    expected_api_key_env_var,
    load_backend,
)

#: The fact_check package source tree.
_PACKAGE = Path(protocol.__file__).resolve().parent

#: The C3 variable name of the fake backend used below.
_FAKE_ENV = "DOCSENTINEL_FACTCHECK_FAKE_API_KEY"

#: Backend names the grammar must refuse (task 04 acceptance criteria, threat model M7).
_BAD_NAMES = [
    "Lenz",
    "le-nz",
    "",
    "a" * 33,
    "lenz\n",
    "lenz ",
    "\uff4cenz",  # full-width small letter l
    "../x",
    "docsentinel.fact_check.lenz",
    "1lenz",
]


class _Fake:
    """A minimal conforming backend."""

    name = "fake"
    API_KEY_ENV_VAR = _FAKE_ENV

    def __init__(self, api_key: str = ""):
        """Keep the key private."""
        self._api_key = api_key

    def check_claim(self, claim: str) -> FactCheckResult:
        """Return a fixed result."""
        return FactCheckResult(verdict="unverifiable", confidence=0.0, backend=self.name)


@pytest.fixture
def registry() -> Iterator[dict[str, type[FactCheckClient]]]:
    """Give each test an empty backend registry and restore the real one afterwards."""
    saved = dict(protocol.FACT_CHECK_BACKENDS)
    protocol.FACT_CHECK_BACKENDS.clear()
    yield protocol.FACT_CHECK_BACKENDS
    protocol.FACT_CHECK_BACKENDS.clear()
    protocol.FACT_CHECK_BACKENDS.update(saved)


@pytest.fixture
def import_spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace ``importlib.import_module`` with a recorder that imports nothing.

    :return: The module names it was called with, in call order.
    """
    calls: list[str] = []

    def spy(name: str, package: object = None):
        """Record the module name and fail the import."""
        calls.append(name)
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(importlib, "import_module", spy)
    return calls


def test_verdict_sets():
    """
    [Unit] fact-check protocol: verifies the verdict vocabulary and the reportable subset.

    Scenario:
        Given the module constants
        When VERDICTS and REPORTABLE_VERDICTS are read
        Then they hold the four C2 verdicts and the {false, mixed} subset

    Boundaries:
        - Focus: data contract constants
        - Fixtures/params: none
        - Scope: constants only

    On failure, first check:
        - Whether the Verdict literal and VERDICTS drifted apart
    """
    assert VERDICTS == {"true", "false", "mixed", "unverifiable"}
    assert REPORTABLE_VERDICTS == {"false", "mixed"}
    assert REPORTABLE_VERDICTS < VERDICTS


def test_minimal_class_satisfies_protocol():
    """
    [Unit] fact-check protocol: verifies the runtime structural check accepts a minimal backend.

    Scenario:
        Given a class with only name, API_KEY_ENV_VAR and check_claim
        When an instance is checked with isinstance against FactCheckClient
        Then the check passes

    Boundaries:
        - Focus: PEP 544 structural typing, no base class needed
        - Fixtures/params: none
        - Scope: isinstance only

    On failure, first check:
        - Whether FactCheckClient lost @runtime_checkable
    """
    assert isinstance(_Fake(), FactCheckClient)


@pytest.mark.parametrize("missing", ["name", "API_KEY_ENV_VAR", "check_claim"])
def test_class_missing_a_member_fails_protocol(missing: str):
    """
    [Unit] fact-check protocol: verifies removing any one protocol member fails the check.

    Scenario:
        Given a minimal backend class with one of the three members left out
        When an instance is checked with isinstance against FactCheckClient
        Then the check fails

    Boundaries:
        - Focus: every protocol member is required
        - Fixtures/params: each of the three members
        - Scope: isinstance only

    On failure, first check:
        - Whether a member was moved off the Protocol body
    """
    members: dict[str, object] = {
        "name": "fake",
        "API_KEY_ENV_VAR": _FAKE_ENV,
        "check_claim": lambda self, claim: None,
    }
    del members[missing]
    cls = type("Partial", (), members)
    assert not isinstance(cls(), FactCheckClient)


def test_valid_result_is_frozen():
    """
    [Unit] fact-check protocol: verifies a valid result constructs and is immutable.

    Scenario:
        Given valid verdict, confidence (int and float bounds), backend and citations
        When FactCheckResult is constructed
        Then construction succeeds and assigning a field raises

    Boundaries:
        - Focus: the happy path and the frozen dataclass
        - Fixtures/params: none
        - Scope: value object only

    On failure, first check:
        - Whether the dataclass lost frozen=True
    """
    result = FactCheckResult("false", 0.75, "lenz", ("https://example.invalid/a",))
    assert result.citations == ("https://example.invalid/a",)
    assert FactCheckResult("true", 1, "lenz").citations == ()
    assert FactCheckResult("mixed", 0.0, "a" * 32, ("x" * MAX_CITATION_CHARS,) * MAX_CITATIONS)
    with pytest.raises(AttributeError):
        result.verdict = "true"  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"verdict": "maybe"},
        {"verdict": "TRUE"},
        {"verdict": ["true"]},
        {"verdict": None},
        {"confidence": True},
        {"confidence": False},
        {"confidence": float("nan")},
        {"confidence": float("inf")},
        {"confidence": -0.01},
        {"confidence": 1.01},
        {"confidence": "0.5"},
        {"confidence": None},
        {"backend": "Lenz"},
        {"backend": "lenz\n"},
        {"backend": "lenz "},
        {"backend": "../x"},
        {"backend": ""},
        {"backend": "a" * 33},
        {"backend": 7},
        {"citations": ["a"]},
        {"citations": ("a", 1)},
        {"citations": "abc"},
        {"citations": ("a",) * (MAX_CITATIONS + 1)},
        {"citations": ("x" * (MAX_CITATION_CHARS + 1),)},
    ],
    ids=repr,
)
def test_invalid_result_raises_fact_check_error(kwargs: dict[str, object]):
    """
    [Unit] fact-check protocol: verifies every invalid field raises FactCheckError, not ValueError.

    Scenario:
        Given a valid result's fields with one replaced by an invalid value
        When FactCheckResult is constructed
        Then FactCheckError is raised with a fixed message of at most 200 characters

    Boundaries:
        - Focus: Task 04 step 3 rules, bool and NaN confidence, newline backend (M7)
        - Fixtures/params: one invalid value per case
        - Scope: value object only

    On failure, first check:
        - Whether __post_init__ switched to re.match or lost the bool check
    """
    fields: dict[str, object] = {"verdict": "false", "confidence": 0.5, "backend": "lenz", "citations": ()}
    fields.update(kwargs)
    with pytest.raises(FactCheckError) as caught:
        FactCheckResult(**fields)  # type: ignore[arg-type]
    assert len(str(caught.value)) <= 200
    assert "lenz\n" not in str(caught.value)


def test_expected_api_key_env_var_valid():
    """
    [Unit] fact-check protocol: verifies the C3 variable name.

    Scenario:
        Given a valid backend name
        When expected_api_key_env_var is called
        Then it returns DOCSENTINEL_FACTCHECK_<NAME>_API_KEY

    Boundaries:
        - Focus: plan contract C3
        - Fixtures/params: none
        - Scope: pure function

    On failure, first check:
        - The f-string in expected_api_key_env_var
    """
    assert expected_api_key_env_var("lenz") == "DOCSENTINEL_FACTCHECK_" + "LENZ" + "_API_KEY"
    assert expected_api_key_env_var("fake") == _FAKE_ENV
    assert expected_api_key_env_var("a" * 32) == f"DOCSENTINEL_FACTCHECK_{'A' * 32}_API_KEY"


@pytest.mark.parametrize("name", [*_BAD_NAMES, None, 3, b"lenz"], ids=repr)
def test_expected_api_key_env_var_refuses_bad_names(name: object):
    """
    [Unit] fact-check protocol: verifies malformed backend names raise ValueError (M7).

    Scenario:
        Given a name with a capital, hyphen, trailing newline or space, full-width letter, path,
            dotted module name, wrong length or non-str type
        When expected_api_key_env_var is called
        Then ValueError is raised

    Boundaries:
        - Focus: re.fullmatch, never re.match ("lenz\\n")
        - Fixtures/params: every refused spelling
        - Scope: pure function

    On failure, first check:
        - Whether the pattern is applied with re.match or re.search
    """
    with pytest.raises(ValueError):
        expected_api_key_env_var(name)  # type: ignore[arg-type]


def test_backend_module_map_matches_config_names():
    """
    [Unit] fact-check protocol: verifies the static module map and the config enum do not drift.

    Scenario:
        Given FACT_CHECK_BACKEND_MODULES and config.FACT_CHECK_BACKEND_NAMES
        When their key sets are compared
        Then they are equal, the map is read-only and every module has a fixed-literal importer

    Boundaries:
        - Focus: registry split (ADR 0007 Contract 4)
        - Fixtures/params: none
        - Scope: constants only

    On failure, first check:
        - Whether a backend was added to one side only
    """
    assert set(FACT_CHECK_BACKEND_MODULES) == config.FACT_CHECK_BACKEND_NAMES
    assert set(protocol._MODULE_IMPORTERS) == set(FACT_CHECK_BACKEND_MODULES.values())
    assert all(value.startswith("docsentinel.fact_check.") for value in FACT_CHECK_BACKEND_MODULES.values())
    with pytest.raises(TypeError):
        FACT_CHECK_BACKEND_MODULES["evil"] = "os"  # type: ignore[index]


def test_load_backend_returns_registered_fake_without_import(registry, import_spy):
    """
    [Unit] fact-check protocol: verifies a pre-registered backend is returned with no import.

    Scenario:
        Given a conforming fake registered under its name
        When load_backend is called with that name
        Then the fake class is returned and importlib.import_module is never called

    Boundaries:
        - Focus: load_backend step 1
        - Fixtures/params: registry, import_spy
        - Scope: registry only

    On failure, first check:
        - Whether load_backend imports before reading FACT_CHECK_BACKENDS
    """
    registry["fake"] = _Fake
    assert load_backend("fake") is _Fake
    assert import_spy == []


@pytest.mark.parametrize("name", [*_BAD_NAMES, "fake", "os", None], ids=repr)
def test_load_backend_unknown_name_raises_key_error_and_imports_nothing(registry, import_spy, name):
    """
    [Unit] fact-check protocol: verifies an unmapped name is refused without any import (M7).

    Scenario:
        Given an empty registry and a name that is not a key of the static module map
        When load_backend is called
        Then KeyError is raised and importlib.import_module is never called

    Boundaries:
        - Focus: a configuration value never becomes an import argument
        - Fixtures/params: registry, import_spy, refused names including a module path
        - Scope: registry only

    On failure, first check:
        - Whether load_backend imports something derived from name
    """
    with pytest.raises(KeyError):
        load_backend(name)
    assert import_spy == []


def test_load_backend_imports_only_the_mapped_module(registry, monkeypatch):
    """
    [Unit] fact-check protocol: verifies a mapped name imports exactly its mapped module.

    Scenario:
        Given an empty registry and an import_module stand-in that registers a conforming backend
        When load_backend("lenz") is called
        Then import_module was called once, with the mapped module, and the backend is returned

    Boundaries:
        - Focus: load_backend step 2 with no real backend module present
        - Fixtures/params: registry, patched importlib.import_module
        - Scope: registry only

    On failure, first check:
        - FACT_CHECK_BACKEND_MODULES and _MODULE_IMPORTERS
    """
    lenz = type(
        "Lenz",
        (),
        {"name": "lenz", "API_KEY_ENV_VAR": expected_api_key_env_var("lenz"), "check_claim": _Fake.check_claim},
    )
    calls: list[str] = []

    def fake_import(name: str, package: object = None):
        """Record the module name and register the stand-in backend."""
        calls.append(name)
        registry["lenz"] = lenz  # type: ignore[assignment]

    monkeypatch.setattr(importlib, "import_module", fake_import)
    assert load_backend("lenz") is lenz
    assert calls == [FACT_CHECK_BACKEND_MODULES["lenz"]]


def test_load_backend_import_error_propagates(registry, import_spy):
    """
    [Unit] fact-check protocol: verifies an ImportError from the mapped module propagates.

    Scenario:
        Given an empty registry and an import_module that raises ModuleNotFoundError
        When load_backend("lenz") is called
        Then ImportError propagates (Task 05 turns it into a fail-soft skip)

    Boundaries:
        - Focus: missing backend module or missing httpx
        - Fixtures/params: registry, import_spy
        - Scope: registry only

    On failure, first check:
        - Whether load_backend swallows ImportError
    """
    with pytest.raises(ImportError):
        load_backend("lenz")
    assert import_spy == ["docsentinel.fact_check.lenz"]


def test_load_backend_module_that_does_not_register_raises_key_error(registry, monkeypatch):
    """
    [Unit] fact-check protocol: verifies a mapped module that registers nothing gives KeyError.

    Scenario:
        Given an import_module stand-in that succeeds but registers nothing
        When load_backend("lenz") is called
        Then KeyError is raised

    Boundaries:
        - Focus: load_backend step 2 second lookup
        - Fixtures/params: registry, patched importlib.import_module
        - Scope: registry only

    On failure, first check:
        - The second FACT_CHECK_BACKENDS lookup
    """
    monkeypatch.setattr(importlib, "import_module", lambda name, package=None: None)
    with pytest.raises(KeyError):
        load_backend("lenz")


@pytest.mark.parametrize(
    "overrides",
    [
        {"API_KEY_ENV_VAR": "LENZ_KEY"},
        {"API_KEY_ENV_VAR": "DOCSENTINEL_FACTCHECK_OTHER_API_KEY"},
        {"name": "other"},
        {"check_claim": "not callable"},
    ],
    ids=["env-var-not-c3", "env-var-other-backend", "name-mismatch", "check-claim-not-callable"],
)
def test_load_backend_rejects_non_conforming_class(registry, overrides: dict[str, object]):
    """
    [Unit] fact-check protocol: verifies a non-conforming registered class raises TypeError.

    Scenario:
        Given a registered class whose API_KEY_ENV_VAR breaks C3, whose name differs from its key,
            or whose check_claim is not callable
        When load_backend is called
        Then TypeError is raised

    Boundaries:
        - Focus: load_backend step 4 verification
        - Fixtures/params: registry, one defect per case
        - Scope: registry only

    On failure, first check:
        - _verify_backend
    """
    registry["fake"] = type("Bad", (_Fake,), overrides)  # type: ignore[assignment]
    with pytest.raises(TypeError):
        load_backend("fake")


def test_load_backend_rejects_non_class_and_bad_registry_key(registry):
    """
    [Unit] fact-check protocol: verifies a registered non-class or malformed key raises TypeError.

    Scenario:
        Given an instance registered instead of a class, and a class registered under "Fake"
        When load_backend is called for each
        Then TypeError is raised, never ValueError

    Boundaries:
        - Focus: load_backend step 4 edge cases
        - Fixtures/params: registry
        - Scope: registry only

    On failure, first check:
        - Whether _verify_backend checks the name grammar before deriving the variable name
    """
    registry["fake"] = _Fake()  # type: ignore[assignment]
    registry["Fake"] = type("Upper", (_Fake,), {"name": "Fake"})  # type: ignore[assignment]
    with pytest.raises(TypeError):
        load_backend("fake")
    with pytest.raises(TypeError):
        load_backend("Fake")


def test_fact_check_init_imports_nothing():
    """
    [Unit] fact-check protocol: verifies fact_check/__init__.py holds only a docstring.

    Scenario:
        Given src/docsentinel/fact_check/__init__.py
        When it is parsed
        Then its body is a single docstring expression

    Boundaries:
        - Focus: import docsentinel.fact_check never pulls in httpx or a backend
        - Fixtures/params: none
        - Scope: AST only

    On failure, first check:
        - Whether a convenience re-export was added
    """
    tree = ast.parse((_PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    assert ast.get_docstring(tree)
    assert len(tree.body) == 1


def test_protocol_module_imports_and_env_access_are_minimal():
    """
    [Unit] fact-check protocol: verifies protocol.py imports only the stdlib and reads no environment.

    Scenario:
        Given src/docsentinel/fact_check/protocol.py
        When its imports and names are parsed
        Then it imports only stdlib modules, never os, and never names environ, getenv or the
            third-party Lenz variable

    Boundaries:
        - Focus: C9 layering and threat model M8 for this module (Task 06 extends to the package)
        - Fixtures/params: none
        - Scope: AST and source text only

    On failure, first check:
        - A new import or an os.environ read in protocol.py
    """
    source = (_PACKAGE / "protocol.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= sys.stdlib_module_names
    assert "os" not in imported
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not names & {"environ", "environb", "getenv", "getenvb", "putenv"}
    assert "LENZ" + "_API_KEY" not in source


def test_importing_protocol_pulls_in_no_heavy_or_layered_module():
    """
    [Unit] fact-check protocol: verifies importing the protocol adds no httpx, detector or mining module.

    Scenario:
        Given a fresh interpreter that has already imported docsentinel, with the protocol and its
            package (loaded eagerly by DS302) removed from sys.modules again
        When docsentinel.fact_check.protocol is imported
        Then the only new docsentinel modules are the fact_check package and protocol, and httpx
            is not loaded at all

    Boundaries:
        - Focus: C9 layering at runtime; ``import docsentinel`` itself loads detectors and mining,
            so only the modules added by the protocol import are inspected
        - Fixtures/params: none
        - Scope: subprocess, no network

    On failure, first check:
        - A new import in protocol.py or fact_check/__init__.py
    """
    code = (
        "import sys, docsentinel\n"
        "sys.modules.pop('docsentinel.fact_check.protocol')\n"
        "sys.modules.pop('docsentinel.fact_check')\n"
        "before = set(sys.modules)\n"
        "import docsentinel.fact_check.protocol\n"
        "added = sorted(set(sys.modules) - before)\n"
        "print('\\n'.join(added))\n"
        "print('HTTPX' if 'httpx' in sys.modules else 'NO-HTTPX')\n"
    )
    output = subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True).stdout
    lines = output.split()
    assert lines[-1] == "NO-HTTPX"
    added = set(lines[:-1])
    assert {name for name in added if name.startswith("docsentinel")} == {
        "docsentinel.fact_check",
        "docsentinel.fact_check.protocol",
    }
    assert not {name for name in added if name.split(".")[0] in {"httpx", "httpcore", "h11"}}
