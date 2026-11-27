"""Fresh-interpreter import boundary of the fact-check surface (Milestone 0010 Story 01.0, threat model M9).

``httpx`` and every backend module load only on a gate-open ``DS302`` path. These probes run in a
fresh ``python -I`` interpreter, so no earlier in-process import can mask a leak, and print which
watched modules are in ``sys.modules`` afterwards. The deep probe replaces the deep-readiness check
(an external resource: the spaCy model) so the closed-gate ``DS302`` path really runs without the
model; it selects only ``DS302`` because ``DS301`` loads ``mining.claims`` itself. No network is
reached and no key is set.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

#: A sentinel API key; never a real one.
SENTINEL_KEY = "sentinel-not-a-real-key-0010"

#: Modules that must stay unloaded on a closed gate (threat model M9).
_CLOSED_GATE_MODULES = (
    "httpx",
    "docsentinel.fact_check.lenz",
    "docsentinel.mining.claims",
    "docsentinel.mining.salience",
    "docsentinel.mining.clustering",
)


def _run_probe(code: str) -> dict[str, object]:
    """Run a probe in a fresh isolated interpreter and return the JSON it prints last.

    :param code: Python source executed with ``-I``.
    :returns: The decoded last stdout line.
    """
    env = {
        name: value
        for name, value in os.environ.items()
        if not (name in {"DOCSENTINEL_USE_EXTERNAL_API"} or name.startswith("DOCSENTINEL_FACTCHECK_"))
    }
    completed = subprocess.run(
        [sys.executable, "-I", "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        timeout=600,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


_NO_HTTPX_PROBE = """
    import json, pathlib, sys, tempfile
    import docsentinel
    seen = {"import": "httpx" in sys.modules}
    from docsentinel.config import Config
    from docsentinel.engine import scan

    root = pathlib.Path(tempfile.mkdtemp())
    (root / "a.md").write_text("# A\\n\\n" + ("Acme ships 3 releases every year. " * 20) + "\\n", encoding="utf-8")
    (root / "b.md").write_text("# B\\n\\n" + ("Rotterdam handled 14 ships on Monday. " * 20) + "\\n", encoding="utf-8")
    scan(root)
    seen["fast scan"] = "httpx" in sys.modules
    scan(root, config=Config(profile="standard"))
    seen["standard scan"] = "httpx" in sys.modules
    print(json.dumps(seen))
"""

#: Run one CLI command in a fresh interpreter. ``{patch}`` optionally replaces the deep-readiness
#: probes, ``{command}`` is the subcommand.
_CLI_PROBE = """
    import contextlib, io, json, os, sys, tempfile
    from docsentinel import cli
    {patch}
    os.chdir(tempfile.mkdtemp())
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        code = cli.main([{command!r}])
    backends = sorted(name for name in sys.modules if name.startswith("docsentinel.fact_check.")
        and name not in {{"docsentinel.fact_check.protocol"}})
    print(json.dumps({{"code": code, "httpx": "httpx" in sys.modules, "spacy": "spacy" in sys.modules,
        "lenz": "docsentinel.fact_check.lenz" in sys.modules, "backends": backends}}))
"""

#: Replaces the doctor's spaCy/textacy import probes (an external resource) with "not installed".
_NO_DEEP_LIBRARIES = (
    "from docsentinel.mining import nlp; "
    "nlp.libraries_available = lambda: False; nlp.model_available = lambda: False; nlp.deep_ready = lambda: False"
)


def test_httpx_never_loads_on_import_fast_or_standard_scan():
    """
    [Unit] fact-check import boundary: verifies httpx stays unloaded on import and fast and standard scans.

    Scenario:
        Given a fresh isolated interpreter
        When it imports docsentinel, then runs a fast and a standard scan
        Then httpx is absent from sys.modules after each step.

    Boundaries:
        - Focus: Task 06 step 5 fresh-interpreter check (plan contract C9, story S1)
        - Fixtures/params: none; the probe writes its own temporary corpus
        - Scope: one subprocess, no network

    On failure, first check:
        - The step reported True; look for an eager backend or httpx import
    """
    assert _run_probe(_NO_HTTPX_PROBE) == {"import": False, "fast scan": False, "standard scan": False}


def test_rules_loads_no_httpx():
    """
    [Unit] fact-check import boundary: verifies docsentinel rules loads neither httpx nor a backend.

    Scenario:
        Given a fresh isolated interpreter
        When "docsentinel rules" runs
        Then it exits 0 and httpx and docsentinel.fact_check.lenz are absent.

    Boundaries:
        - Focus: Task 06 step 5 fresh-interpreter check
        - Fixtures/params: none
        - Scope: one subprocess, no network

    On failure, first check:
        - An eager import added to the rules listing
    """
    report = _run_probe(_CLI_PROBE.format(patch="", command="rules"))

    assert report == {"code": 0, "httpx": False, "spacy": False, "lenz": False, "backends": []}


def test_doctor_own_code_loads_no_httpx():
    """
    [Unit] fact-check import boundary: verifies doctor's own code, gate line included, loads no httpx or backend.

    Scenario:
        Given a fresh isolated interpreter whose deep-library probes report "not installed", so spaCy is not imported
        When "docsentinel doctor" runs
        Then httpx and docsentinel.fact_check.lenz are absent: the fact-check gate line imports nothing.

    Boundaries:
        - Focus: threat model M9 for doctor; the spaCy probe is the replaced external resource
        - Fixtures/params: nlp.libraries_available/model_available/deep_ready replaced in the probe
        - Scope: one subprocess, no network

    On failure, first check:
        - _doctor_fact_check_gate_line and _backend_loadable (must not run without consent and key)
    """
    report = _run_probe(_CLI_PROBE.format(patch=_NO_DEEP_LIBRARIES, command="doctor"))

    assert report == {"code": 0, "httpx": False, "spacy": False, "lenz": False, "backends": []}


def test_doctor_loads_no_fact_check_backend():
    """
    [Unit] fact-check import boundary: verifies the real docsentinel doctor never loads a fact-check backend.

    Scenario:
        Given a fresh isolated interpreter with the real deep-library probes
        When "docsentinel doctor" runs
        Then it exits 0 and no docsentinel.fact_check backend module is in sys.modules.

    Boundaries:
        - Focus: ratified Task 03 criterion (status.md, 2026-11-23): doctor never imports a backend
          module. httpx is deliberately not asserted here: spaCy imports it through weasel when the
          deep probe imports spaCy; test_doctor_own_code_loads_no_httpx proves our code does not
        - Fixtures/params: none
        - Scope: one subprocess, no network

    On failure, first check:
        - The "backends" list; then _doctor_fact_check_gate_line and _backend_loadable
    """
    report = _run_probe(_CLI_PROBE.format(patch="", command="doctor"))

    assert report["code"] == 0
    assert report["lenz"] is False
    assert report["backends"] == []


_CLOSED_GATE_PROBE = f"""
    import json, pathlib, sys, tempfile
    from docsentinel import engine
    from docsentinel.config import Config

    engine.deep_ready = lambda: True  # the spaCy model is an external resource
    root = pathlib.Path(tempfile.mkdtemp())
    (root / "a.md").write_text("# A\\n\\nAcme shipped 3 releases in 2024.\\n", encoding="utf-8")
    result = engine.scan(root, config=Config(profile="deep", select=("DS302",)))
    loaded = [name for name in {_CLOSED_GATE_MODULES!r} if name in sys.modules]
    print(json.dumps({{"enabled": list(result.enabled_rules), "pending": list(result.pending), "loaded": loaded}}))
"""


def test_closed_gate_deep_scan_loads_no_backend_or_mining_module():
    """
    [Unit] fact-check import boundary: verifies a closed-gate DS302 scan loads no backend, httpx or claim mining.

    Scenario:
        Given a fresh isolated interpreter with no consent and no key
        When a confirmed deep scan with select = ["DS302"] runs
        Then DS302 was the active rule and was skipped, and httpx, fact_check.lenz, mining.claims,
        mining.salience and mining.clustering are all absent from sys.modules.

    Boundaries:
        - Focus: threat model M9 (closed gate means no extraction, selection or backend load)
        - Fixtures/params: deep readiness replaced inside the probe; DS301 excluded by select
        - Scope: one subprocess, no network

    On failure, first check:
        - The "loaded" list; then the early return in detect() and _backend_loadable's guard
    """
    report = _run_probe(_CLOSED_GATE_PROBE)

    assert report["enabled"] == ["DS302"]
    assert report["pending"] == [
        "DS302 skipped: pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1); "
        "set DOCSENTINEL_FACTCHECK_LENZ_API_KEY or LENZ_API_KEY"
    ]
    assert report["loaded"] == []


#: Socket guard prepended to a probe: records and refuses every connection, name lookup and
#: datagram send, so a probe can prove that nothing left the machine (threat model 0010 egress
#: E13). Creating a socket object is not counted: urllib3, which spaCy loads through requests,
#: creates and binds a local ``::1`` socket at import time to probe IPv6 support.
_SOCKET_GUARD = """
    import socket
    opened = []
    def _refuse(kind):
        def guard(*args, **kwargs):
            opened.append(kind)
            raise OSError("socket guard: network access refused")
        return guard
    socket.socket.connect = _refuse("connect")
    socket.socket.connect_ex = _refuse("connect_ex")
    socket.socket.sendto = _refuse("sendto")
    socket.create_connection = _refuse("create_connection")
    socket.getaddrinfo = _refuse("getaddrinfo")
"""

_FULL_DEEP_CLOSED_GATE_PROBE = (
    _SOCKET_GUARD
    + """
    import json, pathlib, sys, tempfile
    from docsentinel import engine
    from docsentinel.config import Config
    from docsentinel.mining import nlp

    if not nlp.deep_ready():
        print(json.dumps({"ready": False}))
        raise SystemExit(0)
    root = pathlib.Path(tempfile.mkdtemp())
    (root / "a.md").write_text("# A\\n\\nAcme shipped 3 releases in 2024.\\n", encoding="utf-8")
    (root / "b.md").write_text("# B\\n\\nAcme shipped 5 releases in 2024.\\n", encoding="utf-8")
    result = engine.scan(root, config=Config(profile="deep"))
    print(json.dumps({"ready": True, "enabled": list(result.enabled_rules), "pending": list(result.pending),
        "lenz": "docsentinel.fact_check.lenz" in sys.modules, "opened": opened}))
"""
)


def test_full_closed_gate_deep_scan_loads_no_lenz_and_opens_no_socket():
    """
    [Unit] fact-check import boundary: verifies a confirmed deep scan with gate 2 closed never loads lenz.

    Scenario:
        Given a fresh isolated interpreter with a socket guard, no consent and no key
        When a confirmed deep scan runs DS301 and DS302 with the real spaCy model
        Then DS302 was skipped, docsentinel.fact_check.lenz is absent and no socket was opened.

    Boundaries:
        - Focus: Story 03.0 Task 03 amended criterion (egress threat model E13). httpx is not
          asserted: DS301 imports spaCy, which imports httpx
        - Fixtures/params: none; skipped when the spaCy model is not installed
        - Scope: one subprocess, no network

    On failure, first check:
        - The early return in fact_check.detect() and _backend_loadable's guard
    """
    report = _run_probe(_FULL_DEEP_CLOSED_GATE_PROBE)
    if not report["ready"]:
        pytest.skip("the spaCy model is not installed")

    assert report["enabled"] == ["DS301", "DS302"]
    assert report["pending"] == [
        "DS302 skipped: pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1); "
        "set DOCSENTINEL_FACTCHECK_LENZ_API_KEY or LENZ_API_KEY"
    ]
    assert report["lenz"] is False
    assert report["opened"] == []


_DOCTOR_OPEN_GATE_PROBE = (
    _SOCKET_GUARD
    + f"""
    import contextlib, io, json, os, sys, tempfile
    from docsentinel import cli
    os.environ["DOCSENTINEL_USE_EXTERNAL_API"] = "1"
    os.environ["DOCSENTINEL_FACTCHECK_LENZ_API_KEY"] = {SENTINEL_KEY!r}
    os.chdir(tempfile.mkdtemp())
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = cli.main(["doctor"])
    gate = [line for line in out.getvalue().splitlines() if line.startswith("fact-check gate:")]
    print(json.dumps({{"code": code, "gate": gate, "opened": opened, "key_echoed": {SENTINEL_KEY!r} in out.getvalue()}}))
"""
)


def test_doctor_with_consent_and_key_reports_lenz_on_and_opens_no_socket():
    """
    [Unit] fact-check import boundary: verifies doctor with consent and a key reports lenz on, offline.

    Scenario:
        Given a fresh isolated interpreter with a socket guard, the consent variable and a sentinel key
        When "docsentinel doctor" runs
        Then the gate line is "on (backend: lenz)", no socket was opened and the key is not printed.

    Boundaries:
        - Focus: Story 03.0 Task 03 amended criterion: doctor may import the client but opens no socket
        - Fixtures/params: a sentinel key, never a real one
        - Scope: one subprocess, no network

    On failure, first check:
        - _doctor_fact_check_gate_line and _backend_loadable (they load the class, never construct it)
    """
    report = _run_probe(_DOCTOR_OPEN_GATE_PROBE)

    assert report == {
        "code": 0,
        "gate": ["fact-check gate: on (backend: lenz)"],
        "opened": [],
        "key_echoed": False,
    }
