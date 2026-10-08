"""Public interface for the M0 documentation inventory."""

from docsentinel.config import Config, ConfigError, load_config
from docsentinel.engine import scan
from docsentinel.models import Document, Finding, ScanResult

__all__ = ["Config", "ConfigError", "Document", "Finding", "ScanResult", "load_config", "scan"]
