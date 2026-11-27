"""Environment-read tripwire for the fact-check surface (Milestone 0010 threat model M8).

Parses every module under ``src/docsentinel/`` and asserts that:

(a) only ``detectors/fact_check.py`` reads ``DOCSENTINEL_USE_EXTERNAL_API`` or a
    ``DOCSENTINEL_FACTCHECK_*`` variable, so ``cli.py``, ``config.py`` and ``engine.py`` read
    neither (``fact_check/protocol.py`` derives the key variable name but, by (c), reads nothing);
(b) no module contains a standalone ``LENZ_API_KEY``, matched as
    ``(?<![A-Za-z0-9_])LENZ_API_KEY`` (the plan contract C3 name
    ``DOCSENTINEL_FACTCHECK_LENZ_API_KEY`` contains it as a substring and is allowed);
(c) no module under ``src/docsentinel/fact_check/`` reads ``os.environ`` or calls ``os.getenv``.

Every checker also runs against seeded violations so it cannot rot into a no-op. The forbidden
token is assembled at run time so this file never contains it as a literal.
"""

import ast
import re
from pathlib import Path

import pytest

import docsentinel
from docsentinel.detectors.fact_check import _read_api_key

#: The installed package source tree.
_SRC = Path(docsentinel.__file__).resolve().parent

#: The only module allowed to read the consent or key variables.
_READER = "detectors/fact_check.py"

#: The other tool's key variable, assembled so this file does not contain it standalone.
_OTHER_TOOL_KEY = "LENZ" + "_API_KEY"

#: (b): a standalone occurrence of the other tool's key variable.
_STANDALONE_OTHER_KEY = re.compile(r"(?<![A-Za-z0-9_])" + _OTHER_TOOL_KEY)

#: String fragments that name a fact-check consent or key variable.
_VARIABLE_FRAGMENTS = ("DOCSENTINEL_USE_EXTERNAL_API", "DOCSENTINEL_FACTCHECK_")

#: Identifiers that hold or derive a fact-check variable name.
_VARIABLE_IDENTIFIERS = frozenset(
    {"USE_EXTERNAL_API_ENV", "API_KEY_ENV_VAR", "key_env_var", "expected_api_key_env_var"}
)

#: Names whose use means environment access.
_ENV_NAMES = frozenset({"environ", "environb", "getenv", "getenvb", "putenv", "unsetenv"})


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Return the ids of every docstring constant node in ``tree``.

    :param tree: The parsed module.
    :return: ``id()`` of each module, class and function docstring node.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                ids.add(id(first.value))
    return ids


def _mentions_variable(node: ast.AST) -> bool:
    """Return whether an expression names a fact-check variable.

    :param node: An expression (an env-access argument).
    :return: ``True`` when it holds a matching string fragment or a variable-name identifier.
    """
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and any(fragment in child.value for fragment in _VARIABLE_FRAGMENTS)
        ):
            return True
        if isinstance(child, ast.Name) and child.id in _VARIABLE_IDENTIFIERS:
            return True
        if isinstance(child, ast.Attribute) and child.attr in _VARIABLE_IDENTIFIERS:
            return True
    return False


def _uses_env(node: ast.AST) -> bool:
    """Return whether an expression refers to ``environ``/``getenv``.

    :param node: Any expression.
    :return: ``True`` when a Name or Attribute in it is an environment accessor.
    """
    return any(
        (isinstance(child, ast.Name) and child.id in _ENV_NAMES)
        or (isinstance(child, ast.Attribute) and child.attr in _ENV_NAMES)
        for child in ast.walk(node)
    )


def fact_check_env_reads(source: str) -> list[int]:
    """Return the line numbers where ``source`` reads a fact-check consent or key variable.

    A read is an environment access (``os.environ[...]``, ``os.environ.get(...)``,
    ``os.getenv(...)``, ``... in os.environ``) whose key names such a variable, by literal or by a
    variable-name identifier.

    :param source: A module's source text.
    :return: The offending line numbers, in source order.
    """
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        keys: list[ast.AST] = []
        if isinstance(node, ast.Call) and _uses_env(node.func):
            keys = [*node.args, *(keyword.value for keyword in node.keywords)]
        elif isinstance(node, ast.Subscript) and _uses_env(node.value):
            keys = [node.slice]
        elif isinstance(node, ast.Compare) and any(_uses_env(comparator) for comparator in node.comparators):
            keys = [node.left]
        if any(_mentions_variable(key) for key in keys):
            lines.append(node.lineno)
    return sorted(lines)


def consent_literals(source: str) -> list[str]:
    """Return the non-docstring string constants that name a fact-check variable.

    :param source: A module's source text.
    :return: The matching constants, in walk order.
    """
    tree = ast.parse(source)
    docstrings = _docstring_nodes(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and any(fragment in node.value for fragment in _VARIABLE_FRAGMENTS)
    ]


def env_accessors(source: str) -> list[str]:
    """Return every ``environ``/``getenv``-family name a module references.

    :param source: A module's source text.
    :return: The accessor names found, in walk order.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id in _ENV_NAMES:
            found.append(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in _ENV_NAMES:
            found.append(node.attr)
        elif isinstance(node, ast.alias) and node.name.split(".")[-1] in _ENV_NAMES:
            found.append(node.name)
    return found


def _modules() -> list[Path]:
    """Return every Python module under ``src/docsentinel/``, sorted."""
    return sorted(_SRC.rglob("*.py"))


def _relative(path: Path) -> str:
    """Return a module path relative to the package root, POSIX style.

    :param path: A module path.
    :return: The relative path, e.g. ``detectors/fact_check.py``.
    """
    return path.relative_to(_SRC).as_posix()


def test_only_the_ds302_detector_reads_consent_or_key_variables():
    """
    [Unit] fact-check env reads (a): verifies only detectors/fact_check.py reads the gate variables.

    Scenario:
        Given every module under src/docsentinel/
        When its environment accesses are parsed
        Then only detectors/fact_check.py reads DOCSENTINEL_USE_EXTERNAL_API or a DOCSENTINEL_FACTCHECK_* variable,
        and it does read them (so the checker is not vacuous).

    Boundaries:
        - Focus: threat model M8
        - Fixtures/params: none
        - Scope: AST of every module

    On failure, first check:
        - The listed module; route the read through detectors/fact_check.py
    """
    readers = {
        _relative(path): fact_check_env_reads(path.read_text(encoding="utf-8"))
        for path in _modules()
        if fact_check_env_reads(path.read_text(encoding="utf-8"))
    }

    assert set(readers) == {_READER}


@pytest.mark.parametrize("name", ["cli.py", "config.py", "engine.py"])
def test_cli_config_and_engine_name_no_gate_variable(name: str):
    """
    [Unit] fact-check env reads (a): verifies cli.py, config.py and engine.py hold no gate-variable literal.

    Scenario:
        Given one of the three modules most likely to grow a second consent reader
        When its non-docstring string constants are parsed
        Then none names DOCSENTINEL_USE_EXTERNAL_API or DOCSENTINEL_FACTCHECK_, and none reads such a variable.

    Boundaries:
        - Focus: threat model M8 (one reader only)
        - Fixtures/params: the three module names
        - Scope: AST of one module

    On failure, first check:
        - Whether the module started reading the environment form of the gate itself
    """
    source = (_SRC / name).read_text(encoding="utf-8")

    assert consent_literals(source) == []
    assert fact_check_env_reads(source) == []


@pytest.mark.parametrize("path", _modules(), ids=_relative)
def test_no_module_names_the_other_tool_key(path: Path):
    """
    [Unit] fact-check env reads (b): verifies no module contains the standalone third-party key variable.

    Scenario:
        Given one module under src/docsentinel/
        When its full text (docstrings included) is searched
        Then the other tool's key name never appears outside the C3 name DOCSENTINEL_FACTCHECK_LENZ_API_KEY.

    Boundaries:
        - Focus: threat model M8 (FC-8, FC-14)
        - Fixtures/params: every module
        - Scope: source text

    On failure, first check:
        - The module named in the test id
    """
    assert _STANDALONE_OTHER_KEY.findall(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("path", sorted((_SRC / "fact_check").rglob("*.py")), ids=_relative)
def test_fact_check_package_never_touches_the_environment(path: Path):
    """
    [Unit] fact-check env reads (c): verifies no fact_check module reads os.environ or calls os.getenv.

    Scenario:
        Given one module under src/docsentinel/fact_check/
        When its names, attributes and imports are parsed
        Then none is environ, environb, getenv, getenvb, putenv or unsetenv.

    Boundaries:
        - Focus: threat model M8 (a backend gets its key only through the constructor)
        - Fixtures/params: every module of the package, lenz.py included once it exists
        - Scope: AST of one module

    On failure, first check:
        - The module named in the test id
    """
    assert env_accessors(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('import os\nos.environ.get("DOCSENTINEL_USE_EXTERNAL_API")\n', [2]),
        ('import os\nx = os.environ["DOCSENTINEL_FACTCHECK_LENZ_API_KEY"]\n', [2]),
        ('from os import getenv\ngetenv("DOCSENTINEL_FACTCHECK_X_API_KEY")\n', [2]),
        ('import os\nflag = "DOCSENTINEL_USE_EXTERNAL_API" in os.environ\n', [2]),
        ("import os\nos.environ.get(fact_check.USE_EXTERNAL_API_ENV)\n", [2]),
        ("import os\nos.environ.get(cls.API_KEY_ENV_VAR)\n", [2]),
        ('import os\nos.environ.get(f"DOCSENTINEL_FACTCHECK_{name}_API_KEY")\n', [2]),
        ('import os\nos.environ.get("DOCSENTINEL_SETTINGS")\n', []),
        ('MESSAGE = "set DOCSENTINEL_USE_EXTERNAL_API=1"\n', []),
    ],
)
def test_env_read_checker_catches_seeded_reads(source: str, expected: list[int]):
    """
    [Unit] fact-check env reads: verifies the read checker flags seeded reads and ignores other variables.

    Scenario:
        Given a seeded module source
        When fact_check_env_reads parses it
        Then exactly the lines reading a gate variable are reported.

    Boundaries:
        - Focus: the checker itself, so the tripwire cannot become a no-op
        - Fixtures/params: inline sources
        - Scope: fact_check_env_reads only

    On failure, first check:
        - _uses_env and _mentions_variable
    """
    assert fact_check_env_reads(source) == expected


def test_other_checkers_catch_seeded_violations():
    """
    [Unit] fact-check env reads: verifies the literal, standalone-key and accessor checkers on seeded text.

    Scenario:
        Given seeded sources with a consent literal, a docstring mention, the other tool's key and an env read
        When each checker runs
        Then the literal and the accessor are reported, the docstring is not, and only the standalone key matches.

    Boundaries:
        - Focus: the checkers themselves
        - Fixtures/params: inline sources
        - Scope: consent_literals, env_accessors and the standalone-key pattern

    On failure, first check:
        - _docstring_nodes and the lookbehind of the standalone-key pattern
    """
    assert consent_literals('"""Reads DOCSENTINEL_USE_EXTERNAL_API."""\nX = "DOCSENTINEL_FACTCHECK_A"\n') == [
        "DOCSENTINEL_FACTCHECK_A"
    ]
    assert env_accessors("import os\nos.getenv('A')\n") == ["getenv"]
    assert env_accessors("from os import environ\n") == ["environ"]
    assert _STANDALONE_OTHER_KEY.findall("DOCSENTINEL_FACTCHECK_" + _OTHER_TOOL_KEY) == []
    assert _STANDALONE_OTHER_KEY.findall("x = " + _OTHER_TOOL_KEY) == [_OTHER_TOOL_KEY]
    assert _STANDALONE_OTHER_KEY.findall("$" + _OTHER_TOOL_KEY) == [_OTHER_TOOL_KEY]


#: Gate, backend and egress names the ``extract-facts`` handler must never reach (story decision X10).
_GATE_OR_BACKEND_NAMES = frozenset(
    {
        "resolve_external_api_gate",
        "ExternalApiGate",
        "external_api_requested",
        "load_backend",
        "EXTERNAL_API_RULES",
        "USE_EXTERNAL_API_ENV",
        "FACT_CHECK_BACKEND_MODULES",
        "use_external_api",
        "httpx",
        "lenz",
    }
)


def handler_names(source: str, entry: str) -> set[str]:
    """Return every Name/Attribute identifier reachable from ``entry`` through same-module calls.

    :param source: A module's source text.
    :param entry: The top-level function to start from.
    :return: The identifiers used by ``entry`` and every module-level function it calls, transitively.
    """
    functions = {
        node.name: node for node in ast.parse(source).body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    seen: set[str] = set()
    names: set[str] = set()
    pending = [entry]
    while pending:
        current = pending.pop()
        if current in seen or current not in functions:
            continue
        seen.add(current)
        for child in ast.walk(functions[current]):
            if isinstance(child, ast.Name):
                names.add(child.id)
                pending.append(child.id)
            elif isinstance(child, ast.Attribute):
                names.add(child.attr)
    return names


def test_extract_facts_handler_references_no_gate_or_backend():
    """
    [Unit] fact-check env reads: verifies the extract-facts CLI handler reaches no gate, backend or httpx name.

    Scenario:
        Given cli.py
        When the names used by _cmd_extract_facts and every cli.py function it calls are collected
        Then none is a gate, backend or egress name, and the handler does call extract_facts.

    Boundaries:
        - Focus: story decision X10 (threat model 0010-extract-facts E1), Task 03 step 4
        - Fixtures/params: none
        - Scope: AST of cli.py (same-module call graph only; the engine side is Task 04's)

    On failure, first check:
        - Whether _cmd_extract_facts or a helper it calls started resolving the external-API gate
    """
    names = handler_names((_SRC / "cli.py").read_text(encoding="utf-8"), "_cmd_extract_facts")

    assert "extract_facts" in names
    assert names & _GATE_OR_BACKEND_NAMES == set()


def test_handler_name_collector_follows_calls():
    """
    [Unit] fact-check env reads: verifies the call-graph collector follows same-module calls.

    Scenario:
        Given a seeded module whose entry calls a helper that names the gate
        When handler_names runs
        Then the gate name is reported, so the tripwire is not vacuous.

    Boundaries:
        - Focus: the checker itself
        - Fixtures/params: inline source
        - Scope: handler_names only

    On failure, first check:
        - The pending/seen walk in handler_names
    """
    source = "def entry():\n    helper()\n\n\ndef helper():\n    return gate.resolve_external_api_gate()\n"

    assert "resolve_external_api_gate" in handler_names(source, "entry")


def test_api_key_falls_back_to_the_standard_variable(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] key fallback: verifies the DocSentinel variable wins and the standard one is the fallback.

    Scenario:
        Given the standard variable set and the DocSentinel one unset or empty
        When the key is read
        Then the standard value is used; a set DocSentinel value always wins.

    Boundaries:
        - Focus: DS302 key lookup
        - Fixtures/params: monkeypatch
        - Scope: one function

    On failure, first check:
        - detectors/fact_check.py _read_api_key
    """
    primary = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"
    monkeypatch.setenv(_OTHER_TOOL_KEY, "standard-key-0123456789")
    assert _read_api_key(primary) == "standard-key-0123456789"
    monkeypatch.setenv(primary, "")
    assert _read_api_key(primary) == "standard-key-0123456789"
    monkeypatch.setenv(primary, "primary-key-0123456789")
    assert _read_api_key(primary) == "primary-key-0123456789"
    monkeypatch.delenv(primary)
    monkeypatch.delenv(_OTHER_TOOL_KEY)
    assert _read_api_key(primary) == ""
