"""AST tripwire for the offline ``extract-facts`` path (Milestone 0010 Story 05.0 Task 04, step 4).

Parses ``engine.py``, ``detectors/fact_check.py`` and ``cli.py`` and collects, for each entry point
of the ``extract-facts`` path, every identifier and string literal reachable through same-module
calls: ``engine.extract_facts``, ``fact_check.trace_candidates``, ``collect_candidates``,
``select_candidates`` and the ``cli.py`` handler ``_cmd_extract_facts``. None of them may name the
consent gate, a backend loader, the environment, ``httpx`` or ``docsentinel.fact_check.lenz``
(threat model 0010-extract-facts E1, AST part; the socket guard is in
``tests/integration/test_extract_facts_cli_ds302.py``). It also pins that ``Config`` has no
weight or dedup field (E9) and that ``detectors/fact_check.py`` has exactly one ``extract_statements``
call site (plan contract C11). Every checker runs against a seeded violation as well.
"""

import ast
import dataclasses
import inspect
from pathlib import Path

import pytest

import docsentinel
from docsentinel.config import Config
from docsentinel.mining import salience

#: The installed package source tree.
_SRC = Path(docsentinel.__file__).resolve().parent

#: Identifiers the ``extract-facts`` path must never reference (Task 04 step 4).
_FORBIDDEN_NAMES = frozenset(
    {
        "external_api_requested",
        "resolve_external_api_gate",
        "ExternalApiGate",
        "load_backend",
        "USE_EXTERNAL_API_ENV",
        "FACT_CHECK_BACKENDS",
        "FACT_CHECK_BACKEND_MODULES",
        "environ",
        "environb",
        "getenv",
        "getenvb",
        "httpx",
        "lenz",
    }
)

#: String fragments the ``extract-facts`` path must never hold (an import name or a variable name).
_FORBIDDEN_FRAGMENTS = (
    "httpx",
    "docsentinel.fact_check",
    "DOCSENTINEL_USE_EXTERNAL_API",
    "DOCSENTINEL_FACTCHECK_",
)

#: ``(module, entry point)`` of every ``extract-facts`` path segment.
_ENTRY_POINTS = (
    ("engine.py", "extract_facts"),
    ("detectors/fact_check.py", "trace_candidates"),
    ("detectors/fact_check.py", "collect_candidates"),
    ("detectors/fact_check.py", "select_candidates"),
    ("cli.py", "_cmd_extract_facts"),
)


def _docstring_ids(tree: ast.AST) -> set[int]:
    """Return the ``id()`` of every docstring constant in ``tree``.

    :param tree: A parsed module or function.
    :return: The ids of module, class and function docstring nodes.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                ids.add(id(first.value))
    return ids


def reachable(source: str, entry: str) -> tuple[set[str], set[str], set[str]]:
    """Return what ``entry`` and every same-module function it reaches reference.

    A Name that is a module-level function is followed, transitively.

    :param source: A module's source text.
    :param entry: The module-level function to start from.
    :return: ``(identifiers, string literals except docstrings, functions visited)``.
    """
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    docstrings = _docstring_ids(tree)
    names: set[str] = set()
    strings: set[str] = set()
    seen: set[str] = set()
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
            elif isinstance(child, ast.alias):
                names.update(child.name.split("."))
            elif isinstance(child, ast.Constant) and isinstance(child.value, str) and id(child) not in docstrings:
                strings.add(child.value)
    return names, strings, seen


def violations(source: str, entry: str) -> list[str]:
    """Return the forbidden identifiers and string fragments reachable from ``entry``.

    :param source: A module's source text.
    :param entry: The entry point.
    :return: Sorted offending identifiers, then offending literals.
    """
    names, strings, _ = reachable(source, entry)
    bad_strings = sorted(text for text in strings if any(fragment in text for fragment in _FORBIDDEN_FRAGMENTS))
    return sorted(names & _FORBIDDEN_NAMES) + bad_strings


def _read(module: str) -> str:
    """Return the source of a package module.

    :param module: The path relative to the package root.
    :return: The source text.
    """
    return (_SRC / module).read_text(encoding="utf-8")


@pytest.mark.parametrize(("module", "entry"), _ENTRY_POINTS, ids=[entry for _, entry in _ENTRY_POINTS])
def test_extract_facts_path_names_no_gate_backend_environment_or_httpx(module: str, entry: str):
    """
    [Unit] extract-facts offline path: verifies no gate, backend, environment or httpx name is reachable.

    Scenario:
        Given one entry point of the extract-facts path
        When every identifier and non-docstring literal reachable through same-module calls is collected
        Then none is a gate, backend-loader, environment or httpx/lenz name, and the entry point exists

    Boundaries:
        - Focus: threat model 0010-extract-facts E1 (AST part), story decision X10
        - Fixtures/params: one entry point per case
        - Scope: AST of engine.py, detectors/fact_check.py and cli.py

    On failure, first check:
        - Whether a helper on the path started resolving the gate, loading a backend or reading os.environ
    """
    source = _read(module)
    _, _, visited = reachable(source, entry)
    assert entry in visited
    assert violations(source, entry) == []


def test_extract_facts_path_imports_only_the_mining_modules():
    """
    [Unit] extract-facts offline path: verifies the only dynamic imports on the path are two mining modules.

    Scenario:
        Given engine.extract_facts and fact_check.trace_candidates
        When every string literal starting with "docsentinel." on their paths is collected
        Then the set is exactly {"docsentinel.mining.claims", "docsentinel.mining.salience"}

    Boundaries:
        - Focus: threat model E1 (no backend module import on the path)
        - Fixtures/params: none
        - Scope: AST only

    On failure, first check:
        - A new importlib.import_module literal on the extract-facts path
    """
    modules: set[str] = set()
    for module, entry in _ENTRY_POINTS[:2]:
        _, strings, _ = reachable(_read(module), entry)
        modules |= {text for text in strings if text.startswith("docsentinel.")}
    assert modules == {"docsentinel.mining.claims", "docsentinel.mining.salience"}


def test_extract_facts_engine_path_reaches_the_shared_steps():
    """
    [Unit] extract-facts offline path: verifies the engine path is the shared one, not a copy.

    Scenario:
        Given engine.extract_facts
        When the same-module functions it reaches are collected
        Then they include _inventory, _partition_readable and _traced, and the identifiers include
            trace_candidates and deep_ready, but not scan or collect_candidates

    Boundaries:
        - Focus: plan contract C11, Task 01 step 4 (shared inventory, one candidate source)
        - Fixtures/params: none
        - Scope: AST of engine.py

    On failure, first check:
        - Whether extract_facts grew its own inventory or extraction loop
    """
    names, _, visited = reachable(_read("engine.py"), "extract_facts")
    assert {"_inventory", "_partition_readable", "_traced"} <= visited
    assert {"trace_candidates", "deep_ready"} <= names
    assert "scan" not in visited
    assert "collect_candidates" not in names


def test_config_has_no_weight_or_dedup_field():
    """
    [Unit] Config: verifies no dataclass field name contains "weight" or "dedup".

    Scenario:
        Given the Config dataclass
        When its fields are listed
        Then no name contains weight or dedup, and none is include_rejected or selection_policy

    Boundaries:
        - Focus: threat model E9, decision X5 (exploration settings are never configuration)
        - Fixtures/params: none
        - Scope: dataclasses.fields(Config)

    On failure, first check:
        - A new Config field for the salience weights or the clustering threshold
    """
    names = [field.name for field in dataclasses.fields(Config)]
    assert names
    assert [name for name in names if "weight" in name or "dedup" in name] == []
    assert {"include_rejected", "selection_policy"}.isdisjoint(names)


def test_fact_check_has_exactly_one_extract_statements_call_site():
    """
    [Unit] detectors/fact_check.py: verifies one extract_statements call in the whole module, inside trace_candidates.

    Scenario:
        Given the parsed module (every scope, nested functions and lambdas included)
        When every call whose callee is named extract_statements is located
        Then there is exactly one, and it lies within the lines of trace_candidates

    Boundaries:
        - Focus: plan contract C11 (one extraction loop)
        - Fixtures/params: none
        - Scope: AST of detectors/fact_check.py

    On failure, first check:
        - A second extraction loop, for example in detect()
    """
    tree = ast.parse(_read("detectors/fact_check.py"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "extract_statements")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "extract_statements")
        )
    ]
    (owner,) = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "trace_candidates"]
    assert len(calls) == 1
    assert owner.lineno <= calls[0].lineno <= (owner.end_lineno or owner.lineno)


def test_trace_salience_takes_no_config():
    """
    [Unit] mining.salience: verifies trace_salience takes no Config and no config-shaped parameter.

    Scenario:
        Given trace_salience
        When its signature is inspected
        Then its parameters are claims plus the five keyword-only selection numbers

    Boundaries:
        - Focus: Story 05.0 acceptance (trace_salience takes no Config; mining layering)
        - Fixtures/params: none
        - Scope: signature only

    On failure, first check:
        - A Config parameter added to the mining layer
    """
    parameters = inspect.signature(salience.trace_salience).parameters
    assert list(parameters) == [
        "claims",
        "weights",
        "dedup_threshold",
        "min_salience",
        "max_per_document",
        "max_total",
    ]
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for name, p in parameters.items() if name != "claims")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "def entry():\n    helper()\n\n\ndef helper():\n    return gate.resolve_external_api_gate()\n",
            ["resolve_external_api_gate"],
        ),
        ("import os\n\n\ndef entry():\n    return os.environ.get('X')\n", ["environ"]),
        ("def entry():\n    return importlib.import_module('httpx')\n", ["httpx"]),
        ("def entry():\n    return load('docsentinel.fact_check.lenz')\n", ["docsentinel.fact_check.lenz"]),
        ("def entry():\n    return 'DOCSENTINEL_FACTCHECK_' + name\n", ["DOCSENTINEL_FACTCHECK_"]),
        ('def entry():\n    """Never reads DOCSENTINEL_USE_EXTERNAL_API or httpx."""\n    return 1\n', []),
    ],
    ids=["transitive-gate", "environ", "httpx-import", "lenz-literal", "key-fragment", "docstring-ignored"],
)
def test_checker_catches_seeded_violations(source: str, expected: list[str]):
    """
    [Unit] extract-facts offline checker: verifies the collector reports seeded violations and ignores docstrings.

    Scenario:
        Given a seeded module with a forbidden name, literal or only a docstring mention
        When violations() runs from entry
        Then exactly the seeded violation is reported, so the tripwire is not vacuous

    Boundaries:
        - Focus: the checker itself
        - Fixtures/params: inline sources
        - Scope: reachable, violations

    On failure, first check:
        - The pending/seen walk and the docstring filter in reachable
    """
    assert violations(source, "entry") == expected
