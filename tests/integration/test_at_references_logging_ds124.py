"""Integration test: DS124's DEBUG log records never carry mention text (threat model 0009 M14).

Runs the real CLI so the per-run DEBUG log file (pointed at a temporary directory by
``tests/conftest.py``) is written, then reads it back.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import cli
from docsentinel.log import LOG_DIR_ENV
from tests.asset_helpers import AssetCase


def test_debug_log_never_contains_mention_text(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] DS124 logging: the log file names DS124 but never the mention; a bidi path is escaped.

    Scenario:
        Given the missing-mention case plus a document whose name holds U+202E and whose mentions
            carry a unique marker (one missing, one step-2 refusal)
        When ``docsentinel -v scan`` runs and its per-run log file is read
        Then DS124's per-document DEBUG summary is present, no line holds the marker, and no line
            holds the raw U+202E code point.

    Boundaries:
        - Focus: M14 (safe() paths, fixed reasons, never document content)
        - Fixtures/params: ds124/prose_mention_missing; extra document built in the test body

    On failure, first check:
        - The logger.debug calls in detectors/mentions.py
    """
    case = asset_case("ds124", "prose_mention_missing")
    (case.root / "sub").mkdir()
    (case.root / "sub" / "re‮ad.md").write_text("@zqxmarker77.md @../zqxmarker78.md\n", encoding="utf-8")
    log_dir = Path(os.environ[LOG_DIR_ENV])

    code = cli.main(["scan", str(case.root), "-v", "--format", "json"])
    capsys.readouterr()

    assert code == 0
    logs = [path.read_text(encoding="utf-8") for path in log_dir.glob("docsentinel-*.log")]
    text = "\n".join(logs)
    assert "DS124 checked" in text
    assert "step-2 boundary refusal" in text
    assert "zqxmarker" not in text
    assert "‮" not in text
