"""Pytest root configuration and collection organization for DocSentinel."""

from __future__ import annotations

import importlib
import inspect
import os
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import NoReturn

import httpx
import nltk
import pytest

import docsentinel.fact_check
from docsentinel.config import USER_SETTINGS_ENV, USER_SETTINGS_OFF
from docsentinel.fact_check.protocol import FACT_CHECK_BACKENDS
from docsentinel.log import LOG_DIR_ENV, LOG_LEVEL_ENV, shutdown_cli_logging
from tests.asset_helpers import AssetCase, load_asset_case

#: The XDG data directory variable, pointed at an empty directory in every test.
_XDG_DATA_HOME = "XDG_DATA_HOME"

_DOCSTRING_TAG_RE = re.compile(r"^\s*\[(Unit|Mock|Integration|E2E)\]", re.IGNORECASE)

_E2E_BODY_MARKERS = ("clirunner", "testclient(", "playwright", "async_playwright")
_MOCK_BODY_MARKERS = ("mock.patch", "@patch", "magicmock", "mock(", "monkeypatch", "mocker.")
_MOCK_FIXTURE_NAMES = {"monkeypatch", "mocker"}

_ORDER = {
    "unit": 0,
    "mock": 1,
    "integration": 2,
    "e2e": 3,
}


def _ensure_cmudict():
    """Provision textstat's English syllable corpus, reusing NLTK's existing data cache.

    :raises ValueError: If NLTK cannot download the missing corpus.
    :raises LookupError: If the corpus is still unavailable after downloading.
    """
    try:
        nltk.data.find("corpora/cmudict")
    except LookupError:
        nltk.download("cmudict", quiet=True, raise_on_error=True)
        nltk.data.find("corpora/cmudict")


@pytest.fixture(scope="session", autouse=True)
def _nltk_cmudict():
    """Provision cmudict once for direct pytest, Stop-hook, and CI test runs.

    Download only during test setup, never at module import; failures abort setup
    rather than skipping tests or changing DS201's scoring.
    """
    _ensure_cmudict()


def _classify_item(item: pytest.Item) -> str:
    """Classify a test item into unit, mock, integration, or e2e."""
    # 1. Explicit markers already applied
    for marker_name in ("unit", "mock", "integration", "e2e"):
        if item.get_closest_marker(marker_name):
            return marker_name

    # 2. Directory structure precedence
    file_path = Path(str(item.fspath))
    rel_parts = {p.lower() for p in file_path.parts}
    if "integration" in rel_parts:
        return "integration"
    if "mock" in rel_parts:
        return "mock"
    if "e2e" in rel_parts:
        return "e2e"
    if "unit" in rel_parts:
        return "unit"

    # 3. Check docstring tag
    obj = getattr(item, "obj", None)
    doc = inspect.getdoc(obj) if obj else None
    if doc:
        match = _DOCSTRING_TAG_RE.match(doc)
        if match:
            return match.group(1).lower()

    # 4. Fallback heuristics
    stem = file_path.stem.lower()
    body_text = ""
    if obj:
        try:
            body_text = inspect.getsource(obj).lower()
        except (OSError, TypeError):
            body_text = ""

    fixturenames = getattr(item, "fixturenames", [])
    has_mock_fixture = any(name in _MOCK_FIXTURE_NAMES for name in fixturenames)

    if "end_to_end" in stem:
        return "integration"
    if has_mock_fixture or any(marker in body_text for marker in _MOCK_BODY_MARKERS):
        return "mock"
    return "unit"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]):
    """Sort and mark collected test items into unit, mock, integration, and e2e tiers."""
    for item in items:
        category = _classify_item(item)
        if not item.get_closest_marker(category):
            item.add_marker(getattr(pytest.mark, category))

    items.sort(key=lambda item: _ORDER.get(_classify_item(item), 99))


@pytest.fixture
def asset_case(tmp_path: Path) -> Callable[[str, str], AssetCase]:
    """Return a loader that copies ``tests/assets/<rule>/<case>`` into this test's ``tmp_path``."""

    def load(rule: str, case: str) -> AssetCase:
        """Materialize one asset case under ``tmp_path`` and return it."""
        return load_asset_case(rule, case, tmp_path)

    return load


@pytest.fixture(autouse=True)
def _isolated_cli_logging(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Point the CLI's per-run log files at a fresh temporary directory for every test.

    The directory is separate from ``tmp_path`` so a scan of ``tmp_path`` never sees
    log files. ``DOCSENTINEL_LOG_LEVEL`` is cleared so the default stderr level
    applies, and every handler ``cli.main`` attached is closed after the test. The
    environment is restored by hand rather than with ``monkeypatch``, which would
    add a mock fixture to every test and change :func:`_classify_item`.
    """
    log_dir = tmp_path_factory.mktemp("docsentinel-logs")
    saved = {name: os.environ.get(name) for name in (LOG_DIR_ENV, LOG_LEVEL_ENV)}
    os.environ[LOG_DIR_ENV] = str(log_dir)
    os.environ.pop(LOG_LEVEL_ENV, None)
    try:
        yield log_dir
    finally:
        shutdown_cli_logging()
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@pytest.fixture(autouse=True)
def _isolated_user_settings(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Keep every test away from the developer's real user settings file.

    ``DOCSENTINEL_SETTINGS`` is set to ``off`` and, as a second layer, ``XDG_DATA_HOME``
    points at an empty per-test directory, so a test that removes the variable
    resolves the default location there rather than under the real home (threat
    model 0009-user-settings U12, A7). Tests that exercise the layer set the variable
    to a file in ``tmp_path``; default-location tests also patch ``Path.home()``. The
    environment is restored by hand, like the log isolation above, so no mock fixture
    is added to every test.
    """
    data_home = tmp_path_factory.mktemp("docsentinel-data-home")
    saved = {name: os.environ.get(name) for name in (USER_SETTINGS_ENV, _XDG_DATA_HOME)}
    os.environ[USER_SETTINGS_ENV] = USER_SETTINGS_OFF
    os.environ[_XDG_DATA_HOME] = str(data_home)
    try:
        yield data_home
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@pytest.fixture(autouse=True)
def _isolated_fact_check_env() -> Iterator[None]:
    """Remove every fact-check consent and API-key variable for every test (threat model 0010 M12).

    ``DOCSENTINEL_USE_EXTERNAL_API``, every ``DOCSENTINEL_FACTCHECK_*`` variable and
    ``LENZ_API_KEY`` are removed, so a developer's shell can never open the ``DS302`` gate
    inside the suite. Tests set a fake key through ``monkeypatch`` only. The environment is
    restored by hand, like the isolation fixtures above.
    """
    names = [
        name
        for name in os.environ
        if name in {"DOCSENTINEL_USE_EXTERNAL_API", "LENZ_API_KEY"} or name.startswith("DOCSENTINEL_FACTCHECK_")
    ]
    saved = {name: os.environ.pop(name) for name in names}
    try:
        yield
    finally:
        os.environ.update(saved)


#: The message of the session-wide network guard (Story 03.0 Task 04 step 1).
NETWORK_GUARD_MESSAGE = "real network transport reached"

#: The Lenz client module, imported per test only through :func:`lenz_module`.
_LENZ_MODULE = "docsentinel.fact_check.lenz"


def _refuse_sync_transport(self: httpx.HTTPTransport, request: httpx.Request) -> NoReturn:
    """Stand in for ``httpx.HTTPTransport.handle_request`` and refuse every real request.

    :param self: The transport.
    :param request: The request that would have been sent.
    :raises AssertionError: Always.
    """
    raise AssertionError(NETWORK_GUARD_MESSAGE)


async def _refuse_async_transport(self: httpx.AsyncHTTPTransport, request: httpx.Request) -> NoReturn:
    """Stand in for ``httpx.AsyncHTTPTransport.handle_async_request`` and refuse every real request.

    :param self: The transport.
    :param request: The request that would have been sent.
    :raises AssertionError: Always.
    """
    raise AssertionError(NETWORK_GUARD_MESSAGE)


@pytest.fixture(scope="session", autouse=True)
def _no_real_network_transport() -> Iterator[None]:
    """Fail any test that reaches a real ``httpx`` transport (Milestone 0010 Story 03.0 Task 04).

    Both real transport entry points raise ``AssertionError("real network transport reached")``
    for the whole session; ``httpx.MockTransport`` is a different class and is unaffected.
    Importing ``httpx`` here cannot hide a lazy-import regression: every lazy-import assertion
    runs in a fresh ``python -I`` subprocess. The originals are restored by hand at session end.
    """
    saved_sync = httpx.HTTPTransport.handle_request
    saved_async = httpx.AsyncHTTPTransport.handle_async_request
    httpx.HTTPTransport.handle_request = _refuse_sync_transport  # type: ignore[method-assign]
    httpx.AsyncHTTPTransport.handle_async_request = _refuse_async_transport  # type: ignore[method-assign]
    try:
        yield
    finally:
        httpx.HTTPTransport.handle_request = saved_sync  # type: ignore[method-assign]
        httpx.AsyncHTTPTransport.handle_async_request = saved_async  # type: ignore[method-assign]


@pytest.fixture
def lenz_module() -> Iterator[ModuleType]:
    """Import ``docsentinel.fact_check.lenz`` for one test and undo every trace of it afterwards.

    The module, its attribute on the package and its ``FACT_CHECK_BACKENDS`` entry are removed
    again when they were absent before the test, so later in-process tests still see a process in
    which the client was never imported or registered.

    :return: An iterator yielding the imported module.
    """
    preloaded = _LENZ_MODULE in sys.modules
    registered = FACT_CHECK_BACKENDS.get("lenz")
    module = importlib.import_module(_LENZ_MODULE)
    try:
        yield module
    finally:
        if not preloaded:
            sys.modules.pop(_LENZ_MODULE, None)
            if getattr(docsentinel.fact_check, "lenz", None) is module:
                delattr(docsentinel.fact_check, "lenz")
        if registered is None:
            FACT_CHECK_BACKENDS.pop("lenz", None)
        else:
            FACT_CHECK_BACKENDS["lenz"] = registered
