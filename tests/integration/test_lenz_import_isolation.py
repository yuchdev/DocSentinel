"""Import isolation and offline behaviour of the Lenz client in a fresh interpreter (egress threat model E13).

One fresh ``python -I`` subprocess, with a socket guard installed before ``docsentinel`` is
imported, walks the whole closed-gate surface in order and records ``sys.modules`` after each step:
``import docsentinel``, a fast scan, a standard scan, ``docsentinel rules`` and ``docsentinel
doctor`` with the consent variable unset, then a confirmed deep scan with gate 2 closed, then
``doctor`` with consent and a sentinel key. The guard records and refuses every connection, name
lookup and datagram send, so the probe proves nothing left the machine.

Two external resources are replaced inside the probe, never the code under test: the doctor's
spaCy/textacy import probes report "not installed" (spaCy imports ``httpx`` itself, which would
mask a leak from DocSentinel's own code), and the deep-readiness check reports ready so the
closed-gate ``DS302`` path really runs without the spaCy model (``select = ["DS302"]`` keeps
``DS301`` from loading spaCy). No rule asset is loaded and no key other than the sentinel is set.
"""

import json
import os
import subprocess
import sys
import textwrap

from tests.fact_check_fakes import SENTINEL

#: The probe: socket guard first, then every step in a single interpreter.
_PROBE = """
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

    import contextlib, io, json, os, pathlib, sys, tempfile

    def state():
        return {"httpx": "httpx" in sys.modules, "lenz": "docsentinel.fact_check.lenz" in sys.modules,
                "opened": list(opened)}

    steps = {}
    import docsentinel
    steps["import"] = state()

    from docsentinel import cli, engine
    from docsentinel.config import Config
    from docsentinel.mining import nlp

    # External resources only: the deep-library probes and the spaCy model.
    nlp.libraries_available = lambda: False
    nlp.model_available = lambda: False
    nlp.deep_ready = lambda: False

    root = pathlib.Path(tempfile.mkdtemp())
    (root / "a.md").write_text("# A\\n\\n" + ("Acme ships 3 releases every year. " * 20) + "\\n", encoding="utf-8")
    (root / "b.md").write_text("# B\\n\\n" + ("Rotterdam handled 14 ships on Monday. " * 20) + "\\n", encoding="utf-8")
    fast = engine.scan(root)
    steps["fast scan"] = state()
    standard = engine.scan(root, config=Config(profile="standard"))
    steps["standard scan"] = state()

    def run_cli(command):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main([command])
        return code, out.getvalue()

    os.chdir(tempfile.mkdtemp())
    rules_code, _ = run_cli("rules")
    steps["rules"] = state()
    doctor_code, doctor_out = run_cli("doctor")
    steps["doctor"] = state()
    closed_gate = [line for line in doctor_out.splitlines() if line.startswith("fact-check gate:")]

    engine.deep_ready = lambda: True
    deep = engine.scan(root, config=Config(profile="deep", select=("DS302",)))
    steps["deep scan"] = state()

    os.environ["DOCSENTINEL_USE_EXTERNAL_API"] = "1"
    os.environ["DOCSENTINEL_FACTCHECK_LENZ_API_KEY"] = SENTINEL
    open_code, open_out = run_cli("doctor")
    steps["doctor with consent"] = state()
    open_gate = [line for line in open_out.splitlines() if line.startswith("fact-check gate:")]

    print(json.dumps({
        "steps": steps,
        "codes": [rules_code, doctor_code, open_code],
        "scans": [len(fast.documents), len(standard.documents), list(deep.enabled_rules), list(deep.pending)],
        "gates": [closed_gate, open_gate],
        "key_echoed": SENTINEL in open_out,
    }))
"""


def _run() -> dict[str, object]:
    """Run the probe in a fresh isolated interpreter with no inherited consent or key.

    :return: The decoded report (the last stdout line).
    """
    env = {
        name: value
        for name, value in os.environ.items()
        if not (name in {"DOCSENTINEL_USE_EXTERNAL_API", "LENZ_API_KEY"} or name.startswith("DOCSENTINEL_FACTCHECK_"))
    }
    code = f"SENTINEL = {SENTINEL!r}\n" + textwrap.dedent(_PROBE)
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        timeout=600,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_lenz_import_isolation():
    """
    [Integration] lenz import isolation: verifies closed-gate paths never load the client or httpx, and nothing opens a socket.

    Scenario:
        Given a fresh python -I interpreter with a socket guard, no consent and no key
        When it imports docsentinel, runs a fast and a standard scan, rules and doctor, then a
        confirmed deep scan with gate 2 closed, then doctor with consent and a sentinel key
        Then neither docsentinel.fact_check.lenz nor httpx is loaded through doctor; after the
        deep scan lenz is still absent and DS302 was skipped; doctor with consent reports
        "on (backend: lenz)" and may import the client; no step opened a socket and the key is
        never printed.

    Boundaries:
        - Focus: E13 (import isolation), Story 03.0 Task 03 amended criterion
        - Fixtures/params: deep-library probes and deep readiness replaced inside the probe
          (external resources); a sentinel key only
        - Scope: one subprocess, no network, no rule assets

    On failure, first check:
        - The first step whose state flipped; then load_backend's call sites and the
          _doctor_fact_check_gate_line / _backend_loadable helpers
    """
    report = _run()
    steps = report["steps"]
    assert isinstance(steps, dict)

    for name in ("import", "fast scan", "standard scan", "rules", "doctor"):
        assert steps[name] == {"httpx": False, "lenz": False, "opened": []}, name
    assert steps["deep scan"]["lenz"] is False
    assert steps["deep scan"]["opened"] == []
    assert steps["doctor with consent"]["opened"] == []
    assert report["codes"] == [0, 0, 0]
    assert report["scans"] == [
        2,
        2,
        ["DS302"],
        [
            "DS302 skipped: pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1); "
            "set DOCSENTINEL_FACTCHECK_LENZ_API_KEY"
        ],
    ]
    gates = report["gates"]
    assert isinstance(gates, list)
    assert gates[1] == ["fact-check gate: on (backend: lenz)"]
    assert gates[0] != gates[1] and len(gates[0]) == 1
    assert report["key_echoed"] is False
