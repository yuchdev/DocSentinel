"""Optional pytest fixture; enable with -p docsentinel.pytest_plugin."""

from pathlib import Path

import pytest

from docsentinel.engine import scan
from docsentinel.models import ScanResult


@pytest.fixture
def docsentinel_scan() -> ScanResult:
    """Scan the pytest invocation directory using the same engine as the CLI."""
    return scan(Path.cwd())
