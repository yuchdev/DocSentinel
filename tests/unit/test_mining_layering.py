"""Layering tripwire for the ``docsentinel.mining`` text/data-mining layer.

A ``docsentinel.mining.*`` module may import only the standard library, third-party mining
libraries, ``docsentinel.models`` and ``docsentinel.log``. It must never import the engine side
of the package (configuration, rules, detectors, engine, CLI, reporting, telemetry, baseline or
discovery), the future ``docsentinel.fact_check`` network backend or ``httpx``, so callers pass plain
values in and mining never does network I/O. Imports between mining modules are allowed. ``mining/__init__.py`` holds only a docstring, so
``import docsentinel.mining`` never pulls in a heavy dependency. Each check also runs against a
seeded violation so it cannot rot into a no-op.
"""

import ast
from pathlib import Path

import pytest

import docsentinel

#: The mining package source tree.
_MINING = Path(docsentinel.__file__).resolve().parent / "mining"

#: ``docsentinel`` submodules a mining module must never import. ``fact_check`` is the future
#: network backend package: the mining layer never does network I/O.
_FORBIDDEN = frozenset(
    {
        "config",
        "rules",
        "detectors",
        "engine",
        "cli",
        "reporting",
        "telemetry",
        "baseline",
        "discovery",
        "fact_check",
    }
)

#: Top-level third-party packages a mining module must never import (network clients).
_FORBIDDEN_THIRD_PARTY = frozenset({"httpx"})

#: The package a top-level mining module lives in, for resolving relative imports.
_MINING_PACKAGE = "docsentinel.mining"


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


def _imported_modules(tree: ast.AST, package: str = _MINING_PACKAGE) -> list[str]:
    """Return every absolute module name an ``import``/``from ... import`` statement names.

    A ``from <pkg> import x`` statement also yields ``<pkg>.x`` for each imported name, so
    importing a submodule by name is caught. Relative imports are resolved against ``package``.

    :param tree: The parsed module.
    :param package: The package the parsed module lives in.
    :return: The imported module names, in source order.
    """
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = _resolve_relative(module, node.level, package)
            names.append(module)
            if module.split(".")[0] == "docsentinel":
                names.extend(f"{module}.{alias.name}" for alias in node.names)
    return names


def _is_forbidden(name: str) -> bool:
    """Return whether one absolute module name is off-limits to the mining layer.

    :param name: The absolute module name.
    :return: ``True`` for an engine-side ``docsentinel`` module, ``fact_check`` or a network client.
    """
    parts = name.split(".")
    if parts[0] in _FORBIDDEN_THIRD_PARTY:
        return True
    return parts[0] == "docsentinel" and len(parts) > 1 and parts[1] in _FORBIDDEN


def layering_violations(source: str, package: str = _MINING_PACKAGE) -> list[str]:
    """Return the forbidden imports in one mining module's source.

    Imports between ``docsentinel.mining.*`` modules are allowed.

    :param source: The module source text.
    :param package: The package the module lives in (for relative imports).
    :return: The offending module names (empty when the module respects the layering).
    """
    return [name for name in _imported_modules(ast.parse(source), package) if _is_forbidden(name)]


def _package_of(path: Path) -> str:
    """Return the dotted package a mining source file lives in.

    :param path: A ``.py`` file under the mining package.
    :return: The package name, e.g. ``docsentinel.mining``.
    """
    relative = path.parent.relative_to(_MINING).parts
    return ".".join((_MINING_PACKAGE, *relative))


def _mining_modules() -> list[Path]:
    """Return every Python module under the mining package, sorted."""
    return sorted(_MINING.rglob("*.py"))


def test_mining_package_has_modules():
    """
    [Unit] mining layering: verifies the tripwire scans a non-empty module set.

    Scenario:
        Given the installed docsentinel package
        When the mining package is listed
        Then it holds at least __init__.py, corpus.py, claims.py and nlp.py

    Boundaries:
        - Focus: guard against the layering check silently scanning nothing
        - Fixtures/params: none
        - Scope: source tree listing only

    On failure, first check:
        - Whether a mining module was moved or renamed
    """
    names = {path.name for path in _mining_modules()}
    assert {"__init__.py", "corpus.py", "claims.py", "nlp.py"} <= names


@pytest.mark.parametrize("path", _mining_modules(), ids=lambda path: path.name)
def test_mining_module_imports_no_engine_side_module(path: Path):
    """
    [Unit] mining layering: verifies a mining module imports no forbidden docsentinel module.

    Scenario:
        Given one module under src/docsentinel/mining/
        When its import statements are parsed
        Then none names config, rules, detectors, engine, cli, reporting, telemetry, baseline, discovery,
            fact_check or httpx

    Boundaries:
        - Focus: the one-way dependency from the engine side onto the mining layer
        - Fixtures/params: every mining module
        - Scope: AST only, the module is never imported

    On failure, first check:
        - Whether a mining function should take a plain value instead of a Config or rule object
    """
    assert layering_violations(path.read_text(encoding="utf-8"), _package_of(path)) == []


def test_mining_init_has_no_imports():
    """
    [Unit] mining layering: verifies mining/__init__.py holds only a docstring.

    Scenario:
        Given src/docsentinel/mining/__init__.py
        When it is parsed
        Then its body is a single docstring expression with no import

    Boundaries:
        - Focus: ``import docsentinel.mining`` stays free of spaCy, textacy, scikit-learn and textstat
        - Fixtures/params: none
        - Scope: AST only

    On failure, first check:
        - Whether a convenience re-export was added to the package __init__
    """
    tree = ast.parse((_MINING / "__init__.py").read_text(encoding="utf-8"))
    assert not [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert ast.get_docstring(tree)
    assert len(tree.body) == 1


@pytest.mark.parametrize(
    "source",
    [
        "from docsentinel.config import Config\n",
        "from docsentinel import rules\n",
        "import docsentinel.detectors.loader\n",
        "from docsentinel.telemetry.classify import classify\n",
        "from .. import config\n",
        "from ..detectors import loader\n",
        "def f():\n    from docsentinel import engine\n",
        "import httpx\n",
        "from httpx import Client\n",
        "from docsentinel.fact_check import lenz\n",
        "from docsentinel import fact_check\n",
    ],
)
def test_layering_check_flags_seeded_violation(source: str):
    """
    [Unit] mining layering: verifies the check flags a seeded forbidden import.

    Scenario:
        Given a source string importing a forbidden module (absolute, by name, nested, relative,
            fact_check or httpx)
        When layering_violations parses it
        Then it reports at least one violation

    Boundaries:
        - Focus: the tripwire cannot rot into a no-op
        - Fixtures/params: one seeded violation per spelling
        - Scope: AST only

    On failure, first check:
        - Whether _imported_modules stopped walking nested scopes or ``from docsentinel import``
    """
    assert layering_violations(source)


def test_layering_check_allows_models_log_and_third_party():
    """
    [Unit] mining layering: verifies allowed imports pass.

    Scenario:
        Given imports of the stdlib, a mining library, docsentinel.models, docsentinel.log and sibling
            mining modules (absolute and relative)
        When layering_violations parses them
        Then it reports nothing

    Boundaries:
        - Focus: the allow side of the rule
        - Fixtures/params: none
        - Scope: AST only

    On failure, first check:
        - Whether the forbidden set grew to include models or log
    """
    source = (
        "import re\nimport numpy as np\nfrom docsentinel import models\nfrom docsentinel.log import safe\n"
        "from docsentinel.mining.corpus import create_vectorizer\nfrom docsentinel.mining import corpus\n"
        "from . import corpus\nfrom .corpus import CorpusModel\n"
    )
    assert layering_violations(source) == []
