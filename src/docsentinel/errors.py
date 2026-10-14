"""Exception types for DocSentinel runtime and environment failures."""


class ExtraNotInstalledError(ValueError):
    """Raised when a profile requires an optional dependency group that is not installed."""

    def __init__(self, extra: str, cause: ImportError):
        """Initialise ExtraNotInstalledError with missing extra name and root cause."""
        self.extra: str = extra
        self.cause: ImportError = cause
        message = (
            f"The '{extra}' optional dependency group is required for this profile but is not installed.\n"
            f"Install it with:  pip install docsentinel[{extra}]   (or: uv sync --extra {extra})\n"
            f"Underlying import error: {cause}"
        )
        super().__init__(message)
