from docsentinel.errors import ExtraNotInstalledError


def test_extra_not_installed_is_a_value_error() -> None:
    assert issubclass(ExtraNotInstalledError, ValueError)


def test_extra_not_installed_message_names_extra_and_install_command() -> None:
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


def test_extra_not_installed_preserves_cause_attribute() -> None:
    cause = ImportError("No module named 'sklearn'")
    err = ExtraNotInstalledError("standard", cause)

    assert err.extra == "standard"
    assert err.cause is cause
