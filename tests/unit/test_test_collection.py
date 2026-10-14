"""Tests for Pytest test collection classification and tier sorting."""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from tests import conftest


def test_classify_pure_logic_function_as_unit():
    """
    [Unit] test collection: verifies classify pure logic function as unit.

    Scenario:
        Given test inputs and fixtures for classify pure logic function as unit
        When test_classify_pure_logic_function_as_unit executes the target flow
        Then the expected outcome for classify pure logic function as unit is confirmed.

    Boundaries:
        - Focus: classify pure logic function as unit
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to classify pure logic function as unit
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by test collection
    """
    mock_item = MagicMock(spec=pytest.Item)
    mock_item.get_closest_marker.return_value = None
    mock_item.obj = lambda: 42
    mock_item.fspath = "tests/test_example.py"
    mock_item.fixturenames = []

    assert conftest._classify_item(mock_item) == "unit"


def test_classify_item_with_docstring_tag():
    """
    [Unit] test collection: verifies classify item with docstring tag.

    Scenario:
        Given test inputs and fixtures for classify item with docstring tag
        When test_classify_item_with_docstring_tag executes the target flow
        Then the expected outcome for classify item with docstring tag is confirmed.

    Boundaries:
        - Focus: classify item with docstring tag
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to classify item with docstring tag
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by test collection
    """

    def dummy_func():
        """[Integration] example: verifies integration flow."""

    mock_item = MagicMock(spec=pytest.Item)
    mock_item.get_closest_marker.return_value = None
    mock_item.obj = dummy_func
    mock_item.fspath = "tests/test_example.py"
    mock_item.fixturenames = []

    assert conftest._classify_item(mock_item) == "integration"


def test_classify_item_with_mock_fixture():
    """
    [Unit] test collection: verifies classify item with mock fixture.

    Scenario:
        Given test inputs and fixtures for classify item with mock fixture
        When test_classify_item_with_mock_fixture executes the target flow
        Then the expected outcome for classify item with mock fixture is confirmed.

    Boundaries:
        - Focus: classify item with mock fixture
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to classify item with mock fixture
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by test collection
    """
    mock_item = MagicMock(spec=pytest.Item)
    mock_item.get_closest_marker.return_value = None
    mock_item.obj = lambda: None
    mock_item.fspath = "tests/test_example.py"
    mock_item.fixturenames = ["monkeypatch", "tmp_path"]

    assert conftest._classify_item(mock_item) == "mock"


def test_classify_item_with_end_to_end_in_path():
    """
    [Unit] test collection: verifies classify item with end to end in path.

    Scenario:
        Given test inputs and fixtures for classify item with end to end in path
        When test_classify_item_with_end_to_end_in_path executes the target flow
        Then the expected outcome for classify item with end to end in path is confirmed.

    Boundaries:
        - Focus: classify item with end to end in path
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to classify item with end to end in path
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by test collection
    """
    mock_item = MagicMock(spec=pytest.Item)
    mock_item.get_closest_marker.return_value = None
    mock_item.obj = lambda: None
    mock_item.fspath = "tests/test_fast_profile_end_to_end.py"
    mock_item.fixturenames = []

    assert conftest._classify_item(mock_item) == "integration"


def test_collection_modifyitems_sorts_and_marks():
    """
    [Unit] test collection: verifies collection modifyitems sorts and marks.

    Scenario:
        Given test inputs and fixtures for collection modifyitems sorts and marks
        When test_collection_modifyitems_sorts_and_marks executes the target flow
        Then the expected outcome for collection modifyitems sorts and marks is confirmed.

    Boundaries:
        - Focus: collection modifyitems sorts and marks
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to collection modifyitems sorts and marks
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by test collection
    """

    def make_mock_item(
        name: str, path: str, doc: Optional[str] = None, fixtures: Optional[list[str]] = None
    ) -> MagicMock:
        """Construct a mock pytest Item for collection tests."""
        item = MagicMock(spec=pytest.Item)
        markers: dict[str, Any] = {}

        def get_closest_marker(m_name: str) -> Any:
            """Get marker by name from local map."""
            return markers.get(m_name)

        def add_marker(marker: Any):
            """Add marker to local map."""
            markers[marker.name] = marker

        item.get_closest_marker.side_effect = get_closest_marker
        item.add_marker.side_effect = add_marker
        item.name = name
        item.fspath = path
        item.fixturenames = fixtures or []

        def dummy():
            """Dummy test object callable."""
            pass

        if doc:
            dummy.__doc__ = doc
        item.obj = dummy
        return item

    item_integration = make_mock_item("test_integ", "tests/integration/test_integ.py")
    item_mock = make_mock_item("test_m", "tests/mock/test_m.py")
    item_unit = make_mock_item("test_u", "tests/test_u.py")

    items = [item_integration, item_mock, item_unit]
    conftest.pytest_collection_modifyitems(MagicMock(), items)

    # Order must be unit -> mock -> integration
    assert items == [item_unit, item_mock, item_integration]
    assert item_unit.add_marker.called
    assert item_mock.add_marker.called
    assert item_integration.add_marker.called
