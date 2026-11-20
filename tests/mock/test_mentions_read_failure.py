"""Mock tests: DS124 skips a document whose read fails after the engine's readability check.

``Path.open`` is wrapped so the read of one scanned document raises, which simulates a file
that changed between the engine's ``_partition_readable`` check and the DS124 read. Trees are
built in the test body under ``tmp_path``; no asset is loaded.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from docsentinel import models
from docsentinel.config import Config
from docsentinel.detectors import mentions

_BROKEN_MENTION = "@secret-missing.md"


def _doc(root: Path, relative: str, text: str) -> models.Document:
    """Write ``relative`` under ``root`` and return its Document.

    :param root: The scan root.
    :param relative: POSIX relative path of the document.
    :param text: The document text.
    :returns: The Document.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return models.Document(path=relative, bytes=len(text.encode("utf-8")))


@pytest.mark.parametrize(
    "error",
    [
        OSError("simulated vanish"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "simulated invalid byte"),
    ],
    ids=["oserror", "unicodedecodeerror"],
)
def test_read_failure_skips_document_and_scan_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, error: Exception
):
    """
    [Unit] DS124 read guard: a document that fails to read is skipped, not fatal.

    Scenario:
        Given two documents with a dangling mention each, the first of which fails to read
        When DS124 runs
        Then the scan continues, only the readable document yields a finding, only the
            scanned documents are opened, and one DEBUG record names only the skipped path.

    Boundaries:
        - Focus: the OSError/UnicodeDecodeError guard around mentions._read_text in detect
        - Fixtures/params: monkeypatch, caplog, error (OSError, UnicodeDecodeError)

    On failure, first check:
        - The try/except around _read_text in mentions.detect
        - That the DEBUG record passes only safe(document.path), never content or mention text
    """
    broken = _doc(tmp_path, "broken.md", f"{_BROKEN_MENTION}\n")
    healthy = _doc(tmp_path, "healthy.md", "@also-missing.md\n")
    broken_path = (tmp_path / broken.path).resolve()
    opened: list[Path] = []
    original_open = Path.open

    def fake_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        """Record the opened path, fail for the broken document, else delegate."""
        opened.append(self.resolve())
        if self.resolve() == broken_path:
            raise error
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open)
    caplog.set_level(logging.DEBUG, logger=mentions.logger.name)

    findings = mentions.detect(tmp_path, (broken, healthy), Config(), link_root=tmp_path)

    assert [(finding.path, finding.value) for finding in findings] == [("healthy.md", "@also-missing.md")]
    assert opened == [broken_path, (tmp_path / healthy.path).resolve()]
    skipped = [record for record in caplog.records if "no longer readable" in record.getMessage()]
    assert len(skipped) == 1
    assert "broken.md" in skipped[0].getMessage()
    assert all(_BROKEN_MENTION not in record.getMessage() for record in caplog.records)
    assert all("simulated" not in record.getMessage() for record in caplog.records)
