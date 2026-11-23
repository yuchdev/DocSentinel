"""Layering tripwire for the ``docsentinel.fact_check`` package (Milestone 0010 plan contract C9).

A ``docsentinel.fact_check.*`` module may import only the standard library, ``docsentinel.log``,
other ``docsentinel.fact_check.*`` modules and, in ``lenz.py`` only, ``httpx``. It never imports
the engine side of the package (configuration, rules, detectors, engine, CLI, reporting,
telemetry, baseline, discovery) or the ``mining`` layer, and ``fact_check/__init__.py`` has no
import statement at all. Until Story 03.0 lands the package holds ``__init__.py`` and
``protocol.py``; ``lenz.py`` is picked up automatically when it appears. Each check also runs
against a seeded violation so it cannot rot into a no-op. Modelled on
``tests/unit/test_mining_layering.py``.
"""

import ast
import sys
from pathlib import Path

import pytest

import docsentinel

#: The fact_check package source tree.
_PACKAGE_DIR = Path(docsentinel.__file__).resolve().parent / "fact_check"

#: The dotted name of the package, for resolving relative imports.
_PACKAGE = "docsentinel.fact_check"

#: ``docsentinel`` submodules a fact_check module must never import.
_FORBIDDEN = frozenset(
    {"config", "rules", "detectors", "engine", "cli", "reporting", "telemetry", "baseline", "discovery", "mining"}
)

#: The only third-party package allowed, and the only module allowed to import it.
_NETWORK_CLIENT = "httpx"
_NETWORK_MODULE = "lenz.py"


def _resolve_relative(module: str, level: int, package: str) -> str:
    """Return the absolute module name of a relative import.

    :param module: The ``from`` module text after the dots (may be empty).
    :param level: The number of leading dots.
    :param package: The package the importing module lives in.
    :return: The absolute module name.
    """
    parts = package.split(".")
    base = parts[: len(parts) - (level - 1)] if level > 1 else parts
    return ".".join(base + ([module] if module else []))


def _imported_modules(tree: ast.AST) -> list[str]:
    """Return every absolute module name an import statement names.

    ``from docsentinel import x`` also yields ``docsentinel.x``, so a submodule imported by name is
    caught.

    :param tree: The parsed module.
    :return: The imported module names, in source order.
    """
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = _resolve_relative(module, node.level, _PACKAGE)
            names.append(module)
            if module.split(".")[0] == "docsentinel":
                names.extend(f"{module}.{alias.name}" for alias in node.names)
    return names


def _is_allowed(name: str, filename: str) -> bool:
    """Return whether one imported module name is allowed in the named fact_check module.

    :param name: The absolute module name.
    :param filename: The importing file's name, e.g. ``protocol.py``.
    :return: ``True`` for the standard library, ``docsentinel``, ``docsentinel.log``,
        ``docsentinel.fact_check.*``, and ``httpx`` in ``lenz.py`` only.
    """
    parts = name.split(".")
    top = parts[0]
    if top == "docsentinel":
        if len(parts) == 1:
            return True
        return parts[1] in {"log", "fact_check"} and parts[1] not in _FORBIDDEN
    if top == _NETWORK_CLIENT:
        return filename == _NETWORK_MODULE
    return top in sys.stdlib_module_names or top == "__future__"


def layering_violations(source: str, filename: str) -> list[str]:
    """Return the imports in one fact_check module that break plan contract C9.

    :param source: The module source text.
    :param filename: The module's file name.
    :return: The offending module names, empty when the module respects the layering.
    """
    return [name for name in _imported_modules(ast.parse(source)) if not _is_allowed(name, filename)]


def _modules() -> list[Path]:
    """Return every Python module of the fact_check package, sorted."""
    return sorted(_PACKAGE_DIR.rglob("*.py"))


def test_fact_check_package_has_modules():
    """
    [Unit] fact_check layering: verifies the tripwire scans a non-empty module set.

    Scenario:
        Given the installed docsentinel package
        When the fact_check package is listed
        Then it holds at least __init__.py and protocol.py.

    Boundaries:
        - Focus: guard against the layering check silently scanning nothing
        - Fixtures/params: none
        - Scope: source tree listing only

    On failure, first check:
        - Whether the fact_check package was moved or renamed
    """
    assert {"__init__.py", "protocol.py"} <= {path.name for path in _modules()}


@pytest.mark.parametrize("path", _modules(), ids=lambda path: path.name)
def test_fact_check_module_respects_the_layering(path: Path):
    """
    [Unit] fact_check layering: verifies a fact_check module imports only allowed modules.

    Scenario:
        Given one module under src/docsentinel/fact_check/
        When its import statements are parsed
        Then every import is the standard library, docsentinel.log, docsentinel.fact_check.* or
        (lenz.py only) httpx.

    Boundaries:
        - Focus: plan contract C9
        - Fixtures/params: every module of the package
        - Scope: AST only, nothing is imported

    On failure, first check:
        - The named import; pass plain values in from detectors/fact_check.py instead
    """
    assert layering_violations(path.read_text(encoding="utf-8"), path.name) == []


def test_fact_check_init_has_no_import_statement():
    """
    [Unit] fact_check layering: verifies fact_check/__init__.py imports nothing.

    Scenario:
        Given src/docsentinel/fact_check/__init__.py
        When it is parsed
        Then it contains no Import or ImportFrom node.

    Boundaries:
        - Focus: import docsentinel.fact_check never pulls in a backend or httpx
        - Fixtures/params: none
        - Scope: AST only

    On failure, first check:
        - A convenience re-export added to the package
    """
    tree = ast.parse((_PACKAGE_DIR / "__init__.py").read_text(encoding="utf-8"))

    assert not [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]


@pytest.mark.parametrize(
    ("source", "filename", "expected"),
    [
        ("from docsentinel.config import Config\n", "protocol.py", ["docsentinel.config", "docsentinel.config.Config"]),
        ("from docsentinel import rules\n", "protocol.py", ["docsentinel.rules"]),
        ("import docsentinel.mining.claims\n", "lenz.py", ["docsentinel.mining.claims"]),
        (
            "from ..detectors import fact_check\n",
            "protocol.py",
            ["docsentinel.detectors", "docsentinel.detectors.fact_check"],
        ),
        ("import httpx\n", "protocol.py", ["httpx"]),
        ("import requests\n", "lenz.py", ["requests"]),
        ("import httpx\nimport json\nfrom docsentinel.log import safe\n", "lenz.py", []),
        ("from . import protocol\nfrom .protocol import FactCheckError\n", "lenz.py", []),
    ],
)
def test_seeded_violations_are_detected(source: str, filename: str, expected: list[str]):
    """
    [Unit] fact_check layering: verifies the checker flags seeded violations and passes allowed imports.

    Scenario:
        Given a seeded module source and file name
        When layering_violations parses it
        Then exactly the forbidden names are reported.

    Boundaries:
        - Focus: the checker itself, so the tripwire cannot become a no-op
        - Fixtures/params: inline sources
        - Scope: layering_violations only

    On failure, first check:
        - _is_allowed and relative import resolution
    """
    assert layering_violations(source, filename) == expected
