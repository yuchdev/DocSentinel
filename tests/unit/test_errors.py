from docsentinel.errors import ExtraNotInstalledError


def test_extra_not_installed_is_a_value_error() :
    """
    [Unit] errors: verifies extra not installed is a value error.

    Scenario:
        Given test inputs and fixtures for extra not installed is a value error
        When test_extra_not_installed_is_a_value_error executes the target flow
        Then the expected outcome for extra not installed is a value error is confirmed.

    Boundaries:
        - Focus: extra not installed is a value error
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to extra not installed is a value error
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by errors
    """
    assert issubclass(ExtraNotInstalledError, ValueError)


def test_extra_not_installed_message_names_extra_and_install_command() :
    """
    [Unit] errors: verifies extra not installed message names extra and install command.

    Scenario:
        Given test inputs and fixtures for extra not installed message names extra and install command
        When test_extra_not_installed_message_names_extra_and_install_command executes the target flow
        Then the expected outcome for extra not installed message names extra and install command is confirmed.

    Boundaries:
        - Focus: extra not installed message names extra and install command
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to extra not installed message names extra and install command
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by errors
    """
    cause = ImportError("No module named 'sklearn'")
    err = ExtraNotInstalledError("standard", cause)
    message = str(err)

    assert "docsentinel[standard]" in message
    assert "uv sync --extra standard" in message
    assert "No module named 'sklearn'" in message
    expected_message = (
        "The 'standard' optional dependency group is required for this profile but is not installed.\n"
        "Install it with:  pip install docsentinel[standard]   (or: uv sync --extra standard)\n"
        "Underlying import error: No module named 'sklearn'"
    )
    assert message == expected_message


def test_extra_not_installed_preserves_cause_attribute() :
    """
    [Unit] errors: verifies extra not installed preserves cause attribute.

    Scenario:
        Given test inputs and fixtures for extra not installed preserves cause attribute
        When test_extra_not_installed_preserves_cause_attribute executes the target flow
        Then the expected outcome for extra not installed preserves cause attribute is confirmed.

    Boundaries:
        - Focus: extra not installed preserves cause attribute
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to extra not installed preserves cause attribute
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by errors
    """
    cause = ImportError("No module named 'sklearn'")
    err = ExtraNotInstalledError("standard", cause)

    assert err.extra == "standard"
    assert err.cause is cause
