"""Unit tests for the engine's analyzer-signature dispatch.

These guard :func:`docsentinel.engine._analyzer_accepts_config`, the helper that
decides whether the engine forwards effective config to an analyzer. They use
tiny inline callables and never load assets or touch the filesystem.
"""

from docsentinel.config import Config
from docsentinel.engine import _analyzer_accepts_config, _run_analyzer


def _two_arg(root, documents) -> tuple[()]:
    """Legacy two-argument analyzer form."""
    return ()


def _three_arg(root, documents, config=None) -> tuple[()]:
    """Preferred three-argument analyzer form."""
    return ()


def _variadic(*args, **kwargs) -> tuple[()]:
    """Variadic analyzer form that accepts any call shape."""
    return ()


def _var_positional(root, *args) -> tuple[()]:
    """Analyzer with a ``*args`` third slot but no keyword config."""
    return ()


def _kwargs_only(**kwargs) -> tuple[()]:
    """Analyzer with only ``**kwargs`` and so no third positional slot."""
    return ()


def _keyword_only_config(root, documents, *, config=None) -> tuple:
    """Analyzer whose ``config`` is keyword-only and must be passed by keyword."""
    return (("keyword-only", root, documents, config),)


def _positional_config(root, documents, config=None) -> tuple:
    """Analyzer whose ``config`` is a positional-or-keyword third parameter."""
    return (("positional", root, documents, config),)


class _UninspectableAnalyzer:
    """A callable analyzer whose signature cannot be introspected.

    Accessing ``__signature__`` raises, so :func:`inspect.signature` propagates a
    ``ValueError`` rather than returning a signature, exercising the defensive
    guard in :func:`_analyzer_accepts_config`.
    """

    @property
    def __signature__(self):
        """Raise to simulate a callable with no introspectable signature."""
        raise ValueError("signature unavailable")

    def __call__(self, root, documents) -> tuple[()]:
        """Record the two-argument call and return no findings."""
        self.received = (root, documents)
        return ()


def test_two_argument_analyzer_is_not_offered_config():
    """
    [Unit] engine: verifies a two-argument analyzer is detected as legacy.

    Scenario:
        Given an analyzer declaring only ``(root, documents)``
        When the dispatch helper inspects it
        Then it reports that config must not be forwarded.

    Boundaries:
        - Focus: the legacy two-argument branch
        - Fixtures/params: inline callable

    On failure, first check:
        - The positional-parameter count threshold in _analyzer_accepts_config
    """
    assert _analyzer_accepts_config(_two_arg) is False


def test_three_argument_and_variadic_analyzers_accept_config():
    """
    [Unit] engine: verifies three-argument and variadic analyzers accept config.

    Scenario:
        Given a three-argument ``config``-aware analyzer and a variadic analyzer
        When the dispatch helper inspects each
        Then both are reported as able to receive effective config.

    Boundaries:
        - Focus: the preferred config-aware and variadic branches
        - Fixtures/params: inline callables

    On failure, first check:
        - The config-parameter and variadic detection in _analyzer_accepts_config
    """
    assert _analyzer_accepts_config(_three_arg) is True
    assert _analyzer_accepts_config(_variadic) is True


def test_kwargs_only_analyzer_is_treated_as_legacy_two_argument():
    """
    [Unit] engine: verifies a ``**kwargs``-only analyzer is not offered config.

    Scenario:
        Given an analyzer declaring only ``**kwargs``
        When the dispatch helper inspects it
        Then config is reported as unsupported, because a ``**kwargs``-only callable
        has no third positional slot and calling it positionally with config would
        raise TypeError; the legacy two-argument call is used instead.

    Boundaries:
        - Focus: VAR_KEYWORD alone must not mark an analyzer as config-aware
        - Fixtures/params: inline callable

    On failure, first check:
        - That _analyzer_config_mode no longer returns a config mode for VAR_KEYWORD only
    """
    assert _analyzer_accepts_config(_kwargs_only) is False


def test_var_positional_analyzer_accepts_config_positionally():
    """
    [Unit] engine: verifies a ``*args`` analyzer accepts config as a third positional.

    Scenario:
        Given an analyzer declaring ``(root, *args)``
        When the dispatch helper inspects it and the engine runs it
        Then config is forwarded as the third positional argument without error.

    Boundaries:
        - Focus: the VAR_POSITIONAL positional-dispatch branch
        - Fixtures/params: inline callable

    On failure, first check:
        - That VAR_POSITIONAL still maps to a positional config call
    """
    assert _analyzer_accepts_config(_var_positional) is True
    assert _run_analyzer(_var_positional, "docs", (), Config()) == ()


def test_keyword_only_config_is_passed_by_keyword():
    """
    [Unit] engine: verifies a keyword-only ``config`` analyzer receives config by keyword.

    Scenario:
        Given an analyzer ``def f(root, documents, *, config=None)``
        When the engine runs it with effective settings
        Then it is recognized as config-aware and invoked as ``f(root, documents, config=settings)``,
        so the keyword-only parameter is filled and the settings reach the analyzer - a positional
        third argument would raise TypeError, so passing by keyword is the only correct dispatch.

    Boundaries:
        - Focus: keyword-only config must be forwarded by keyword, not position
        - Fixtures/params: inline callable

    On failure, first check:
        - That _analyzer_config_mode returns the keyword mode for a keyword-only config
        - That _run_analyzer forwards config=settings rather than a third positional
    """
    settings = Config()

    assert _analyzer_accepts_config(_keyword_only_config) is True
    result = _run_analyzer(_keyword_only_config, "root", (), settings)  # type: ignore[arg-type]

    assert result == (("keyword-only", "root", (), settings),)


def test_positional_or_keyword_config_is_passed_by_keyword():
    """
    [Unit] engine: verifies the standard ``config=None`` analyzer receives effective settings.

    Scenario:
        Given the preferred ``def f(root, documents, config=None)`` analyzer
        When the engine runs it with effective settings
        Then it is invoked with ``config=settings`` and the settings reach the analyzer.

    Boundaries:
        - Focus: the common positional-or-keyword config parameter is filled correctly
        - Fixtures/params: inline callable

    On failure, first check:
        - That _run_analyzer forwards the discovered Config for a named config parameter
    """
    settings = Config()

    result = _run_analyzer(_positional_config, "root", (), settings)  # type: ignore[arg-type]

    assert result == (("positional", "root", (), settings),)


def test_uninspectable_analyzer_falls_back_to_two_argument_call():
    """
    [Unit] engine: verifies an un-introspectable callable uses the two-argument path.

    Scenario:
        Given a callable analyzer whose ``__signature__`` raises
        When the dispatch helper inspects it and the engine runs it
        Then no crash occurs, config is treated as unsupported, and the analyzer
        is invoked with exactly ``(root, documents)``.

    Boundaries:
        - Focus: the ValueError/TypeError guard around inspect.signature
        - Fixtures/params: inline callable object

    On failure, first check:
        - The try/except in _analyzer_accepts_config
        - That _run_analyzer omits config on the legacy path
    """
    analyzer = _UninspectableAnalyzer()

    assert _analyzer_accepts_config(analyzer) is False

    result = _run_analyzer(analyzer, "docs", (), Config())  # type: ignore[arg-type]

    assert result == ()
    assert analyzer.received == ("docs", ())
