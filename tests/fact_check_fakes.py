"""Shared fake fact-check backend for the DS302 tests (Milestone 0010 Story 01.0 Task 06).

The mock and integration suites import this module; ``src/`` never does. Story 04.0 Task 01
extends this module rather than forking it. No fake here touches a network, a real backend or a
real API key: the only key value a test ever sets is :data:`SENTINEL`, through ``monkeypatch``.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import ClassVar, Optional, Union

import pytest

from docsentinel.config import Config
from docsentinel.fact_check.protocol import (
    FACT_CHECK_BACKENDS,
    FactCheckError,
    FactCheckResult,
    expected_api_key_env_var,
)

#: The fake API key (threat model 0010 M12). It resembles no real provider key.
SENTINEL = "sentinel-not-a-real-key-0010"

#: The fake backend's name and its plan contract C3 key variable.
FAKE_NAME = "fake"
FAKE_KEY_ENV = "DOCSENTINEL_FACTCHECK_FAKE_API_KEY"

#: The gate-2 consent variable (plan contract C1).
USE_EXTERNAL_API_ENV = "DOCSENTINEL_USE_EXTERNAL_API"

#: The per-case verdict script next to an asset case's documents (Story 04.0 Task 01 step 3).
VERDICTS_FILE = "verdicts.json"

#: What a scripted claim yields: a verdict (confidence 0.9), a ``(verdict, confidence)`` pair, a
#: ready result, or an exception to raise from ``check_claim``.
Outcome = Union[str, tuple[str, float], FactCheckResult, BaseException]


class FakeBackendBase:
    """Behaviour shared by every class :func:`make_fake_backend` returns.

    Each made class gets its own class-level recordings, so two fakes never share state.

    :cvar name: The backend name, ``fake`` unless made with another ``name``.
    :cvar API_KEY_ENV_VAR: The plan contract C3 variable of ``name``.
    :cvar calls: Every claim passed to ``check_claim``, in call order.
    :cvar instances: Every successfully constructed client, in order.
    :cvar verdicts: Claim text to scripted outcome; tests may update it.
    :cvar fail_on: Claims that raise ``FactCheckError``.
    :cvar init_error: An exception the constructor raises, or ``None``.
    :cvar citations: The citations attached to every result built from a verdict.
    :cvar constructed: Number of constructor calls.
    :cvar closed: Number of ``close()`` calls.
    """

    name: ClassVar[str] = FAKE_NAME
    API_KEY_ENV_VAR: ClassVar[str] = FAKE_KEY_ENV
    calls: ClassVar[list[str]]
    instances: ClassVar[list[FakeBackendBase]]
    verdicts: ClassVar[dict[str, Outcome]]
    fail_on: ClassVar[frozenset[str]]
    init_error: ClassVar[Optional[BaseException]]
    citations: ClassVar[tuple[str, ...]]
    constructed: ClassVar[int]
    closed: ClassVar[int]

    def __init__(self, *, api_key: str):
        """Record construction, keep the key private, or raise the scripted ``init_error``.

        :param api_key: The key DS302 read from the environment.
        :raises BaseException: The configured ``init_error``.
        """
        type(self).constructed += 1
        if type(self).init_error is not None:
            raise type(self).init_error
        self._api_key = api_key
        type(self).instances.append(self)

    def __repr__(self) -> str:
        """Return a key-free representation.

        :returns: The class name only.
        """
        return f"{type(self).__name__}()"

    def check_claim(self, claim: str) -> FactCheckResult:
        """Record ``claim`` and return or raise its scripted outcome.

        :param claim: The text DS302 sent.
        :returns: The scripted result, else an ``unverifiable`` result.
        :raises FactCheckError: For a claim in ``fail_on``.
        :raises BaseException: A scripted exception.
        """
        cls = type(self)
        cls.calls.append(claim)
        if claim in cls.fail_on:
            raise FactCheckError("fake backend: scripted failure")
        outcome = cls.verdicts.get(claim, "unverifiable")
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, FactCheckResult):
            return outcome
        verdict, confidence = (outcome, 0.9) if isinstance(outcome, str) else outcome
        return FactCheckResult(verdict=verdict, confidence=confidence, backend=cls.name, citations=cls.citations)

    def close(self):
        """Record the close call."""
        type(self).closed += 1


def make_fake_backend(
    verdicts: Optional[Mapping[str, Outcome]] = None,
    *,
    fail_on: Collection[str] = frozenset(),
    init_error: Optional[BaseException] = None,
    citations: tuple[str, ...] = (),
    name: str = FAKE_NAME,
) -> type[FakeBackendBase]:
    """Return a new fake backend class with its own recordings.

    :param verdicts: Claim text to scripted outcome (see :data:`Outcome`); other claims are
        ``unverifiable``.
    :param fail_on: Claims for which ``check_claim`` raises ``FactCheckError``.
    :param init_error: An exception the constructor raises.
    :param citations: Citations attached to every result built from a verdict.
    :param name: The backend name; ``fake`` by default. Another name (``lenz``) lets a fake stand in
        for a configured backend, for example through the CLI, whose configuration accepts only the
        shipped backend names.
    :returns: The class, conforming to ``FactCheckClient``.
    """
    return type(
        "FakeBackend",
        (FakeBackendBase,),
        {
            "name": name,
            "API_KEY_ENV_VAR": expected_api_key_env_var(name),
            "calls": [],
            "instances": [],
            "verdicts": dict(verdicts or {}),
            "fail_on": frozenset(fail_on),
            "init_error": init_error,
            "citations": tuple(citations),
            "constructed": 0,
            "closed": 0,
        },
    )


def register_fake_backend(monkeypatch: pytest.MonkeyPatch, cls: type) -> type:
    """Register ``cls`` in ``FACT_CHECK_BACKENDS`` under its ``name`` for one test only.

    :param monkeypatch: The test's monkeypatch; it restores the registry afterwards.
    :param cls: The fake backend class.
    :returns: ``cls``.
    """
    monkeypatch.setitem(FACT_CHECK_BACKENDS, cls.name, cls)
    return cls


def fake_deep_config(**overrides: object) -> Config:
    """Return a confirmed deep configuration that names the ``fake`` backend.

    :param overrides: Further ``Config`` fields, applied last.
    :returns: ``Config()`` with ``profile="deep"``, ``deep_confirm=True``,
        ``fact_check_backend="fake"`` and ``overrides``.
    """
    fields: dict[str, object] = {"profile": "deep", "deep_confirm": True, "fact_check_backend": FAKE_NAME}
    fields.update(overrides)
    return dataclasses.replace(Config(), **fields)


def fact_check_env(monkeypatch: pytest.MonkeyPatch, *, flag: bool, key: bool, key_env: str = FAKE_KEY_ENV):
    """Set or clear the two gate-2 environment prerequisites for one test.

    :param monkeypatch: The test's monkeypatch; it restores the environment afterwards.
    :param flag: Set ``DOCSENTINEL_USE_EXTERNAL_API=1`` when true, else remove it.
    :param key: Set ``key_env`` to :data:`SENTINEL` when true, else remove it.
    :param key_env: The backend key variable; the fake's by default.
    """
    if flag:
        monkeypatch.setenv(USE_EXTERNAL_API_ENV, "1")
    else:
        monkeypatch.delenv(USE_EXTERNAL_API_ENV, raising=False)
    if key:
        monkeypatch.setenv(key_env, SENTINEL)
    else:
        monkeypatch.delenv(key_env, raising=False)


def load_case_verdicts(case_root: Path) -> tuple[dict[str, Outcome], frozenset[str]]:
    """Read the ``verdicts.json`` script of an asset case.

    The file maps the exact candidate text to ``{"verdict": ..., "confidence": ...}`` under
    ``verdicts`` and lists the texts that raise ``FactCheckError`` under ``fail_on``. A case
    without the file scripts nothing: every claim is ``unverifiable``.

    :param case_root: The materialized case directory.
    :returns: The scripted outcomes and the failing texts.
    """
    path = case_root / VERDICTS_FILE
    if not path.is_file():
        return {}, frozenset()
    data = json.loads(path.read_text(encoding="utf-8"))
    verdicts: dict[str, Outcome] = {
        text: (entry["verdict"], float(entry["confidence"])) for text, entry in data.get("verdicts", {}).items()
    }
    return verdicts, frozenset(data.get("fail_on", ()))


def make_case_backend(case_root: Path, *, name: str = FAKE_NAME) -> type[FakeBackendBase]:
    """Return a fresh fake backend scripted by the case's ``verdicts.json``.

    :param case_root: The materialized case directory.
    :param name: The backend name.
    :returns: The fake class; not registered.
    """
    verdicts, fail_on = load_case_verdicts(case_root)
    return make_fake_backend(verdicts, fail_on=fail_on, name=name)
