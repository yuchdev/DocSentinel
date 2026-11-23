"""Static AST and signature checks of the Lenz client (Story 03.0 Task 04, egress E1, E3, E4, E7, E8, E10, E11).

These tests read source files and lock files as text and parse them with ``ast`` or ``tomllib``;
none sends a request. The signature check imports the client module through the ``lenz_module``
fixture, which removes it and its registry entry afterwards. A hygiene check also proves that no
file under ``tests/`` carries the API key embedded in ``examples/docs/lenz_fact-checking.md`` (the
key is read from that file at test time, never written here).
"""

from __future__ import annotations

import ast
import inspect
import re
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

import docsentinel
from docsentinel.detectors import fact_check as fact_check_detector

#: The repository root (``tests/unit/`` is two levels below it).
_REPO = Path(__file__).resolve().parents[2]

#: The installed package source tree.
_SRC = Path(docsentinel.__file__).resolve().parent

#: The client module source.
_LENZ_PATH = _SRC / "fact_check" / "lenz.py"

#: ``httpx`` client methods that take a URL.
_URL_METHODS = frozenset(
    {"stream", "request", "get", "post", "put", "patch", "delete", "head", "options", "build_request", "send"}
)

#: Keywords that would let data or the environment pick a route, a credential or trust anchors.
_FORBIDDEN_ROUTE_KEYWORDS = frozenset({"auth", "event_hooks", "mounts", "proxy", "proxies", "params", "base_url"})

#: Keywords that would weaken or replace TLS trust (E3).
_FORBIDDEN_TLS_KEYWORDS = frozenset({"verify", "cert", "proxy", "proxies"})


def _tree(path: Path) -> ast.Module:
    """Parse one source file.

    :param path: The file.
    :return: The parsed module.
    """
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _calls(tree: ast.AST) -> list[ast.Call]:
    """Return every call node of ``tree``.

    :param tree: The parsed source.
    :return: The calls, in walk order.
    """
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]


def _src_files() -> list[Path]:
    """Return every Python file under ``src/docsentinel/``, sorted.

    :return: The files.
    """
    return sorted(_SRC.rglob("*.py"))


def _class_constants(tree: ast.Module) -> dict[str, object]:
    """Return the literal class-level constants of ``LenzFactCheckClient`` (``A + B`` strings folded).

    :param tree: The parsed client module.
    :return: Constant name to value.
    """
    values: dict[str, object] = {}
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LenzFactCheckClient")
    for node in cls.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            value = node.value
            if isinstance(value, ast.Constant):
                values[node.target.id] = value.value
            elif (
                isinstance(value, ast.BinOp)
                and isinstance(value.left, ast.Name)
                and isinstance(value.right, ast.Constant)
            ):
                values[node.target.id] = f"{values[value.left.id]}{value.right.value}"
    return values


def _url_calls(tree: ast.AST) -> list[ast.Call]:
    """Return every ``<obj>._client.<method>(...)`` call of an ``httpx`` URL method.

    :param tree: The parsed source.
    :return: The calls.
    """
    found: list[ast.Call] = []
    for call in _calls(tree):
        func = call.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in _URL_METHODS
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "_client"
        ):
            found.append(call)
    return found


def _httpx_client_calls(tree: ast.AST) -> list[ast.Call]:
    """Return every ``httpx.Client(...)`` call.

    :param tree: The parsed source.
    :return: The calls.
    """
    return [
        call
        for call in _calls(tree)
        if isinstance(call.func, ast.Attribute)
        and call.func.attr == "Client"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "httpx"
    ]


def _keyword_names(tree: ast.AST) -> set[str]:
    """Return every keyword-argument name used in any call.

    :param tree: The parsed source.
    :return: The names.
    """
    return {keyword.arg for call in _calls(tree) for keyword in call.keywords if keyword.arg is not None}


def test_lenz_no_url_from_data():
    """
    [Unit] lenz static: verifies the only URL the client is given is the ASSESS_URL constant.

    Scenario:
        Given the AST of fact_check/lenz.py
        When every httpx URL-method call on self._client is inspected
        Then there is exactly one (stream), its URL argument is self.ASSESS_URL, ASSESS_URL folds to
        https://lenz.io/api/v1/assess, and no call anywhere uses auth/event_hooks/mounts/proxy/params/base_url.

    Boundaries:
        - Focus: E1
        - Fixtures/params: none
        - Scope: source text of lenz.py

    On failure, first check:
        - _fetch and the httpx.Client(...) call in __init__
    """
    tree = _tree(_LENZ_PATH)

    calls = _url_calls(tree)
    assert [call.func.attr for call in calls] == ["stream"]  # type: ignore[union-attr]
    method, url = calls[0].args[:2]
    assert isinstance(method, ast.Constant) and method.value == "POST"
    assert isinstance(url, ast.Attribute) and url.attr == "ASSESS_URL"
    assert isinstance(url.value, ast.Name) and url.value.id == "self"
    assert [keyword.arg for keyword in calls[0].keywords] == ["json"]
    assert _class_constants(tree)["ASSESS_URL"] == "https://lenz.io/api/v1/assess"
    assert _keyword_names(tree) & _FORBIDDEN_ROUTE_KEYWORDS == set()


def test_client_trust_env_false_and_no_verify_knob(lenz_module: ModuleType):
    """
    [Unit] lenz static: verifies trust_env=False, no redirects and no TLS or proxy knob anywhere.

    Scenario:
        Given the AST of fact_check/lenz.py and the constructor signature
        When the single httpx.Client(...) call and every keyword are inspected
        Then trust_env=False and follow_redirects=False are literal, no verify/cert/proxy keyword
        exists, and the constructor accepts only api_key and the transport test seam.

    Boundaries:
        - Focus: E2, E3
        - Fixtures/params: lenz_module for the signature
        - Scope: source text and signature of LenzFactCheckClient.__init__

    On failure, first check:
        - The httpx.Client(...) call in __init__

    :param lenz_module: The imported client module.
    """
    tree = _tree(_LENZ_PATH)

    clients = _httpx_client_calls(tree)
    assert len(clients) == 1
    keywords = {keyword.arg: keyword.value for keyword in clients[0].keywords}
    for name in ("trust_env", "follow_redirects"):
        assert isinstance(keywords[name], ast.Constant) and keywords[name].value is False  # type: ignore[attr-defined]
    assert _keyword_names(tree) & _FORBIDDEN_TLS_KEYWORDS == set()
    parameters = inspect.signature(lenz_module.LenzFactCheckClient.__init__).parameters
    assert list(parameters) == ["self", "api_key", "transport"]


def test_no_executor_used():
    """
    [Unit] lenz static: verifies the deadline uses a daemon thread, never concurrent.futures.

    Scenario:
        Given the AST of fact_check/lenz.py
        When its imports and calls are inspected
        Then concurrent.futures is never imported or named, and the one threading.Thread call
        passes daemon=True.

    Boundaries:
        - Focus: E4.2 (an executor's exit hook would hang interpreter exit on a stuck read)
        - Fixtures/params: none
        - Scope: source text of lenz.py

    On failure, first check:
        - The worker construction in check_claim
    """
    tree = _tree(_LENZ_PATH)

    imported = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    imported += [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not [name for name in imported if name.startswith("concurrent")]
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert names & {"ThreadPoolExecutor", "ProcessPoolExecutor", "futures"} == set()
    threads = [call for call in _calls(tree) if isinstance(call.func, ast.Attribute) and call.func.attr == "Thread"]
    assert len(threads) == 1
    daemon = {keyword.arg: keyword.value for keyword in threads[0].keywords}["daemon"]
    assert isinstance(daemon, ast.Constant) and daemon.value is True


def _logger_name_literals(tree: ast.AST) -> list[str]:
    """Return the literal first argument of every ``getLogger(...)`` call.

    :param tree: The parsed source.
    :return: The literal names.
    """
    names: list[str] = []
    for call in _calls(tree):
        func = call.func
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
        if name == "getLogger" and call.args and isinstance(call.args[0], ast.Constant):
            names.append(str(call.args[0].value))
    return names


def test_lenz_does_not_touch_httpx_loggers():
    """
    [Unit] lenz static: verifies no module under src/docsentinel/ fetches the httpx or httpcore logger.

    Scenario:
        Given the AST of every Python file under src/docsentinel/
        When every getLogger(...) literal and every string constant naming those loggers is inspected
        Then none names httpx or httpcore (a handler, level or propagation change could expose
        httpcore's DEBUG traces), and the client's own logger is logging.getLogger(__name__).

    Boundaries:
        - Focus: E7.5
        - Fixtures/params: none
        - Scope: source text of the package

    On failure, first check:
        - The file and literal named in the assertion
    """
    offenders: list[tuple[str, str]] = []
    for path in _src_files():
        for name in _logger_name_literals(_tree(path)):
            if name.split(".")[0] in {"httpx", "httpcore"}:
                offenders.append((str(path.relative_to(_SRC)), name))
    assert offenders == []
    lenz_logger_calls = [
        call
        for call in _calls(_tree(_LENZ_PATH))
        if isinstance(call.func, ast.Attribute) and call.func.attr == "getLogger"
    ]
    assert len(lenz_logger_calls) == 1
    assert isinstance(lenz_logger_calls[0].args[0], ast.Name) and lenz_logger_calls[0].args[0].id == "__name__"


def test_max_claim_chars_matches_detector(lenz_module: ModuleType):
    """
    [Unit] lenz static: verifies the client's claim cap equals the detector's candidate cap.

    Scenario:
        Given lenz.MAX_CLAIM_CHARS (which may not import the detector, plan contract C9)
        When it is compared with detectors.fact_check.MAX_CANDIDATE_CHARS
        Then both are 1000.

    Boundaries:
        - Focus: E8 drift
        - Fixtures/params: lenz_module
        - Scope: two constants

    On failure, first check:
        - Whichever constant was changed alone

    :param lenz_module: The imported client module.
    """
    assert lenz_module.LenzFactCheckClient.MAX_CLAIM_CHARS == fact_check_detector.MAX_CANDIDATE_CHARS == 1000
    assert _class_constants(_tree(_LENZ_PATH))["MAX_CLAIM_CHARS"] == 1000


def _version(text: str) -> tuple[int, ...]:
    """Parse a dotted release version into a tuple of integers.

    :param text: A version such as ``0.28.1``.
    :return: The integer parts.
    """
    return tuple(int(part) for part in re.findall(r"\d+", text.split("+")[0])[:3])


def test_lenz_dependency_floor():
    """
    [Unit] lenz static: verifies the declared httpx range and the locked transport stack floors.

    Scenario:
        Given pyproject.toml and uv.lock read as text
        When the httpx dependency and the locked httpx, httpcore and h11 versions are read
        Then pyproject declares "httpx>=0.28,<1", the lock pins httpx >= 0.28 (< 1), httpcore >=
        1.0.9 and h11 >= 0.16.0, and no h2, brotli, zstandard or socksio package is locked.

    Boundaries:
        - Focus: E10 (supply chain)
        - Fixtures/params: none
        - Scope: two repository files

    On failure, first check:
        - A dependency bump or an extra pulled in by another package
    """
    project = tomllib.loads((_REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert "httpx>=0.28,<1" in project["project"]["dependencies"]
    lock = tomllib.loads((_REPO / "uv.lock").read_text(encoding="utf-8"))
    locked = {package["name"]: package["version"] for package in lock["package"]}
    assert (0, 28) <= _version(locked["httpx"]) < (1,)
    assert _version(locked["httpcore"]) >= (1, 0, 9)
    assert _version(locked["h11"]) >= (0, 16, 0)
    assert {"h2", "brotli", "brotlicffi", "zstandard", "socksio"} & set(locked) == set()


def test_transport_is_keyword_only_test_seam(lenz_module: ModuleType):
    """
    [Unit] lenz static: verifies transport is a keyword-only parameter defaulting to None.

    Scenario:
        Given the constructor signature of LenzFactCheckClient
        When its parameters are inspected
        Then api_key is positional-or-keyword with no default and transport is keyword-only with
        default None, and the constructor docstring names it a test seam.

    Boundaries:
        - Focus: E11
        - Fixtures/params: lenz_module
        - Scope: LenzFactCheckClient.__init__ signature

    On failure, first check:
        - The bare * in __init__

    :param lenz_module: The imported client module.
    """
    init = lenz_module.LenzFactCheckClient.__init__
    parameters = inspect.signature(init).parameters
    assert parameters["api_key"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters["api_key"].default is inspect.Parameter.empty
    assert parameters["transport"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["transport"].default is None
    assert "Test seam only" in (init.__doc__ or "")


def test_no_production_transport_argument():
    """
    [Unit] lenz static: verifies no production module passes transport= except the client's own pass-through.

    Scenario:
        Given the AST of every Python file under src/docsentinel/
        When every call with a transport keyword is located
        Then the only one is httpx.Client(..., transport=transport) in lenz.py, and DS302 builds
        the client as client_cls(api_key=...) with no other argument.

    Boundaries:
        - Focus: E11 (no production code reaches the test seam)
        - Fixtures/params: none
        - Scope: source text of the package

    On failure, first check:
        - The file named in the assertion
    """
    found: list[tuple[str, str]] = []
    for path in _src_files():
        for call in _calls(_tree(path)):
            for keyword in call.keywords:
                if keyword.arg == "transport":
                    found.append((str(path.relative_to(_SRC)), ast.unparse(call.func)))
    assert found == [("fact_check/lenz.py", "httpx.Client")]
    lenz_client = _httpx_client_calls(_tree(_LENZ_PATH))[0]
    passed = {keyword.arg: keyword.value for keyword in lenz_client.keywords}["transport"]
    assert isinstance(passed, ast.Name) and passed.id == "transport"
    detector = _tree(_SRC / "detectors" / "fact_check.py")
    constructions = [
        call for call in _calls(detector) if isinstance(call.func, ast.Name) and call.func.id == "client_cls"
    ]
    assert len(constructions) == 1
    assert constructions[0].args == []
    assert [keyword.arg for keyword in constructions[0].keywords] == ["api_key"]


def _example_key() -> str:
    """Read the API key embedded in the example document, at test time only.

    :return: The key (the first fenced block under the ``## API key`` heading).
    """
    text = (_REPO / "examples" / "docs" / "lenz_fact-checking.md").read_text(encoding="utf-8")
    match = re.search(r"^## API key\s*\n+```[^\n]*\n([^\n`]+)\n```", text, re.MULTILINE)
    assert match is not None, "the example document no longer has an API key block"
    return match.group(1).strip()


def test_no_test_file_contains_the_example_key():
    """
    [Unit] lenz hygiene: verifies no file under tests/ contains the example document's key or a prefix of it.

    Scenario:
        Given the key embedded in examples/docs/lenz_fact-checking.md, read at test time
        When every file under tests/ is searched as bytes
        Then neither the key nor any prefix of 12 or more of its characters occurs.

    Boundaries:
        - Focus: Task 04 acceptance criterion (no copied key), threat model M12
        - Fixtures/params: none
        - Scope: the tests/ tree

    On failure, first check:
        - The file named in the assertion; replace the value with tests.fact_check_fakes.SENTINEL
    """
    key = _example_key()
    assert len(key) >= 16
    prefix = key[:12].encode("utf-8")
    offenders = [
        str(path.relative_to(_REPO))
        for path in sorted((_REPO / "tests").rglob("*"))
        if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts and prefix in path.read_bytes()
    ]
    assert offenders == []


@pytest.mark.parametrize("name", ["KEY_MESSAGE", "CLAIM_MESSAGE", "SHAPE_MESSAGE", "CLOSED_MESSAGE"])
def test_fixed_messages_are_plain_literals(name: str):
    """
    [Unit] lenz static: verifies the fixed E12 messages are plain string constants, never formatted.

    Scenario:
        Given the module-level message constants of lenz.py
        When their AST values are inspected
        Then each is a plain str literal of at most 200 characters.

    Boundaries:
        - Focus: E12
        - Fixtures/params: name
        - Scope: source text of lenz.py

    On failure, first check:
        - The named constant

    :param name: The constant name.
    """
    tree = _tree(_LENZ_PATH)
    values = [
        node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name
    ]
    assert len(values) == 1
    assert isinstance(values[0], ast.Constant) and isinstance(values[0].value, str)
    assert len(values[0].value) <= 200
