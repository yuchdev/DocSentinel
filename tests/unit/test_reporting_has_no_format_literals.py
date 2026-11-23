"""Hardcode-ban tripwire for the template-only reporting path (Milestone 0007 Story 03.0 Task 02).

``reporting.py``, ``telemetry/engine.py`` and ``telemetry/facts_model.py`` (Milestone 0010
Story 05.0 Task 02) must hold no output format of their own: every report byte comes from a
template. The tripwire parses the modules with :mod:`ast` and fails
on a string constant equal to a format name, a string carrying a fragment of a legacy layout
(the GitHub ``::`` command marker, ``Schema version``, ``Profile:``, ``bytes)``), a
``json.dumps`` call in ``reporting.py``, or a comparison against a format name. A second case
re-adds such a literal to a temp copy and asserts the tripwire fires, so it cannot rot into a
no-op.
"""

import ast
from pathlib import Path

import pytest

from docsentinel import reporting
from docsentinel.telemetry import engine, facts_model
from docsentinel.telemetry.loader import CONTEXTS, packaged_template_names

#: Format names a module may not spell: the legacy three plus every packaged template name of
#: both contexts (``report`` and ``facts``).
_FORMAT_NAMES: frozenset[str] = frozenset({"text", "json", "github"}).union(
    *(packaged_template_names(context) for context in sorted(CONTEXTS))
)

#: Context field names ``telemetry/facts_model.py`` may spell, and only as a dict-literal key: the
#: fact's ``text`` field (``ExtractedFact.text``, story 05.0 facts context table) is data, never a
#: format selection.
_FACTS_MODEL_KEY_NAMES: frozenset[str] = frozenset({"text"})

#: Substrings of the legacy hand-built layouts.
_LAYOUT_FRAGMENTS: tuple[str, ...] = ("::", "Schema version", "Profile:", "bytes)")


def _is_format_name(node: ast.AST) -> bool:
    """Return whether ``node`` is a string constant equal to a format name.

    :param node: Any AST node.
    :returns: ``True`` for a ``str`` constant in :data:`_FORMAT_NAMES`.
    """
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in _FORMAT_NAMES


def _is_json_dumps(node: ast.AST) -> bool:
    """Return whether ``node`` calls ``json.dumps`` (or a bare ``dumps``).

    :param node: Any AST node.
    :returns: ``True`` for a ``json.dumps(...)`` or ``dumps(...)`` call.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "dumps" and isinstance(func.value, ast.Name) and func.value.id == "json"
    return isinstance(func, ast.Name) and func.id == "dumps"


def violations(source: str, *, ban_json_dumps: bool, key_names: frozenset[str] = frozenset()) -> list[str]:
    """Return every hardcode-ban violation in a module's source.

    :param source: Python source text.
    :param ban_json_dumps: Also flag ``json.dumps`` calls (``reporting.py``, ``facts_model.py``).
    :param key_names: Format names allowed only as a key of a dict literal (a context field name).
    :returns: One ``line N: reason`` entry per violation, in walk order.
    """
    tree = ast.parse(source)
    allowed = {
        id(key)
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for key in node.keys
        if isinstance(key, ast.Constant) and key.value in key_names
    }
    found: list[str] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if id(node) in allowed:
            continue
        if _is_format_name(node):
            found.append(f"line {line}: format-name literal {node.value!r}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.extend(
                f"line {line}: layout fragment {fragment!r}" for fragment in _LAYOUT_FRAGMENTS if fragment in node.value
            )
        if isinstance(node, ast.Compare) and any(
            _is_format_name(operand) for operand in (node.left, *node.comparators)
        ):
            found.append(f"line {line}: comparison against a format name")
        if ban_json_dumps and _is_json_dumps(node):
            found.append(f"line {line}: json.dumps call")
    return found


@pytest.mark.parametrize(
    ("module_file", "ban_json_dumps", "key_names"),
    [
        (reporting.__file__, True, frozenset()),
        (engine.__file__, False, frozenset()),
        (facts_model.__file__, True, _FACTS_MODEL_KEY_NAMES),
    ],
    ids=["reporting", "telemetry_engine", "telemetry_facts_model"],
)
def test_module_holds_no_format_literals(module_file: str, ban_json_dumps: bool, key_names: frozenset[str]):
    """
    [Unit] reporting tripwire: verifies the render path spells no format name, layout fragment or serializer.

    Scenario:
        Given the source of ``reporting.py``, ``telemetry/engine.py`` or ``telemetry/facts_model.py``
        When it is parsed with ``ast`` and every node is inspected
        Then no format-name constant, legacy layout fragment, format-name comparison or (reporting, facts model)
            ``json.dumps`` call is found.

    Boundaries:
        - Focus: the template-only output contract (Story 03.0 Task 02, ADR 0003)
        - Fixtures/params: parametrized over the three modules; ``facts_model.py`` may use the fact field
          name ``text`` only as a dict-literal key
        - Scope: static source analysis; nothing is imported beyond locating the files

    On failure, first check:
        - Whether an output format or line layout was re-added in Python instead of a template
        - Whether a new constant should come from ``telemetry.loader`` (e.g. ``DEFAULT_TEMPLATE``, ``TYPE_TEXT``)
    """
    source = Path(module_file).read_text(encoding="utf-8")

    assert violations(source, ban_json_dumps=ban_json_dumps, key_names=key_names) == []


@pytest.mark.parametrize(
    "injected",
    [
        'LEGACY = "text"\n',
        'def _line(path):\n    return f"  {path} (1 bytes)"\n',
        'BANNER = "Schema version: 1"\n',
        'HEADER = "Profile: fast"\n',
        'def _annotate(level):\n    return f"::{level} file=x"\n',
        "import json\n\ndef _dump(data):\n    return json.dumps(data)\n",
        "def _pick(fmt):\n    return 1 if fmt == FORMATS['json-v1'] else 0\nFORMATS = {'json-v1': 1}\n",
    ],
    ids=["format-name", "bytes-suffix", "schema-header", "profile-header", "gha-marker", "json-dumps", "compare"],
)
def test_tripwire_fires_on_a_reinjected_literal(injected: str, tmp_path: Path):
    """
    [Unit] reporting tripwire: verifies the tripwire fails a copy of ``reporting.py`` with a re-added literal.

    Scenario:
        Given a temp copy of ``reporting.py`` with one banned literal or call appended
        When the tripwire inspects the copy
        Then it reports at least one violation, while the untouched copy reports none.

    Boundaries:
        - Focus: the tripwire cannot silently become a no-op
        - Fixtures/params: parametrized over one injection per banned category; ``tmp_path`` for the copy
        - Scope: static source analysis of a temp file

    On failure, first check:
        - Whether ``violations`` stopped walking a node type (``Constant``, ``Compare``, ``Call``)
        - Whether ``_FORMAT_NAMES`` or ``_LAYOUT_FRAGMENTS`` lost an entry
    """
    original = Path(reporting.__file__).read_text(encoding="utf-8")
    copy = tmp_path / "reporting.py"
    copy.write_text(original + "\n\n" + injected, encoding="utf-8")

    assert violations(original, ban_json_dumps=True) == []
    assert violations(copy.read_text(encoding="utf-8"), ban_json_dumps=True)


def test_facts_model_key_exemption_is_dict_key_only():
    """
    [Unit] reporting tripwire: verifies the facts-model ``text`` exemption covers only dict-literal keys.

    Scenario:
        Given sources spelling ``"text"`` as a dict key, as a value and as a comparison operand
        When the tripwire inspects them with the facts-model key names
        Then only the dict-key use is allowed.

    Boundaries:
        - Focus: the exemption cannot hide a format-name selection
        - Fixtures/params: inline sources
        - Scope: static source analysis

    On failure, first check:
        - The ``allowed`` id set in ``violations``
    """
    assert violations('ROW = {"text": 1}\n', ban_json_dumps=True, key_names=_FACTS_MODEL_KEY_NAMES) == []
    assert violations('NAME = "text"\n', ban_json_dumps=True, key_names=_FACTS_MODEL_KEY_NAMES)
    assert violations('ROW = {1: "text"}\n', ban_json_dumps=True, key_names=_FACTS_MODEL_KEY_NAMES)
    assert violations('OK = name == "text"\n', ban_json_dumps=True, key_names=_FACTS_MODEL_KEY_NAMES)
