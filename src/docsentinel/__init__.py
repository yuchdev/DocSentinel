"""Public interface for the M0 documentation inventory.

:func:`scan` takes the keyword-only arguments ``config``, ``link_root``, ``include``
and ``exclude``. ``include`` replaces the effective include patterns and ``exclude``
is appended to the effective exclude patterns; both are relative to the scan root.
"""

# Imported first for its side effect: the ``docsentinel`` logger gets a NullHandler,
# so the library stays quiet unless the application (or the CLI) configures logging.
from docsentinel import log as _log
from docsentinel.baseline import filter_baselined, fingerprint, load_baseline, save_baseline
from docsentinel.config import Config, ConfigError, ConfigSources, load_config, load_config_with_sources
from docsentinel.engine import scan
from docsentinel.models import Document, Finding, ScanResult

del _log

__all__ = [
    "Config",
    "ConfigError",
    "ConfigSources",
    "Document",
    "Finding",
    "ScanResult",
    "filter_baselined",
    "fingerprint",
    "load_baseline",
    "load_config",
    "load_config_with_sources",
    "save_baseline",
    "scan",
]
