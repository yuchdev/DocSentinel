"""AST tripwire: the DS124 module never expands a home directory or environment variable.

Threat model 0009 M7: ``home`` mentions are never resolved, so the mentions module must not
reference ``expanduser``, ``expandvars`` or ``home`` (``Path.home``) at all, nor resolve paths
with ``realpath`` or ``Path.resolve`` (M4).
"""

from __future__ import annotations

import ast
import inspect

from docsentinel.detectors import mentions

#: Names and attributes the module must never reference.
_FORBIDDEN = frozenset({"expanduser", "expandvars", "home", "realpath", "resolve", "scandir", "listdir"})


def _referenced_names(tree: ast.AST) -> set[str]:
    """Return every ``Name`` id, ``Attribute`` attr and imported name in ``tree``.

    :param tree: A parsed module.
    :returns: The referenced identifiers.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.rpartition(".")[2])
            if node.asname:
                names.add(node.asname)
    return names


def test_module_never_references_expanduser():
    """
    [Unit] DS124 module: no home or environment expansion and no symlink-following resolve.

    Scenario:
        Given the source of docsentinel.detectors.mentions
        When its AST is walked
        Then no name, attribute or import is expanduser, expandvars, home, realpath, resolve,
            scandir or listdir.

    Boundaries:
        - Focus: threat model M4, M7, M16 as a static guarantee
        - Fixtures/params: none

    On failure, first check:
        - A new helper call in mentions.py; home and absolute mentions must be skipped on kind
    """
    tree = ast.parse(inspect.getsource(mentions))

    assert _referenced_names(tree) & _FORBIDDEN == set()
