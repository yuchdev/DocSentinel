"""Verify corpus provisioning without network access in the individual tests."""

import runpy
from unittest import mock

import pytest

from tests import conftest


def test_existing_cmudict_does_not_download():
    """[Unit] Reuse an installed corpus without contacting the downloader.

    Scenario:
        Given cmudict is already installed
        When test setup checks the corpus
        Then only the local lookup runs.

    Boundaries:
        - Focus: cached corpus requires no network
        - Scope: mocked NLTK lookup and downloader

    On failure, first check:
        - _ensure_cmudict in tests/conftest.py
    """
    with (
        mock.patch.object(conftest.nltk.data, "find") as find,
        mock.patch.object(conftest.nltk, "download") as download,
    ):
        conftest._ensure_cmudict()

    find.assert_called_once_with("corpora/cmudict")
    download.assert_not_called()


def test_missing_cmudict_is_downloaded_and_verified():
    """[Unit] Regression: a fresh uv environment provisions the missing corpus.

    Scenario:
        Given cmudict is missing
        When test setup provisions the corpus
        Then it downloads cmudict and verifies the installed data.

    Boundaries:
        - Focus: missing-corpus regression without changing DS201
        - Scope: mocked NLTK lookup and downloader

    On failure, first check:
        - _ensure_cmudict in tests/conftest.py
    """
    with (
        mock.patch.object(
            conftest.nltk.data, "find", side_effect=[LookupError("missing corpus"), mock.sentinel.corpus]
        ) as find,
        mock.patch.object(conftest.nltk, "download", return_value=True) as download,
    ):
        conftest._ensure_cmudict()

    assert find.call_args_list == [mock.call("corpora/cmudict"), mock.call("corpora/cmudict")]
    download.assert_called_once_with("cmudict", quiet=True, raise_on_error=True)


def test_cmudict_download_failure_is_not_suppressed():
    """[Unit] Unavailable network fails setup instead of bypassing DS201 tests.

    Scenario:
        Given a missing corpus and a failed download
        When test setup provisions cmudict
        Then the download error propagates.

    Boundaries:
        - Focus: fail closed on network errors
        - Scope: mocked NLTK lookup and downloader

    On failure, first check:
        - _ensure_cmudict in tests/conftest.py
    """
    with (
        mock.patch.object(conftest.nltk.data, "find", side_effect=LookupError("missing corpus")) as find,
        mock.patch.object(conftest.nltk, "download", side_effect=ValueError("download failed")) as download,
        pytest.raises(ValueError, match="download failed"),
    ):
        conftest._ensure_cmudict()

    find.assert_called_once_with("corpora/cmudict")
    download.assert_called_once_with("cmudict", quiet=True, raise_on_error=True)


def test_cmudict_still_missing_after_download_fails_setup():
    """[Unit] Verify the corpus exists even if the downloader reports success.

    Scenario:
        Given a downloader reporting success without installing the corpus
        When test setup verifies the downloaded data
        Then the lookup error propagates.

    Boundaries:
        - Focus: invalid downloaded state fails setup
        - Scope: mocked NLTK lookup and downloader

    On failure, first check:
        - _ensure_cmudict in tests/conftest.py
    """
    with (
        mock.patch.object(conftest.nltk.data, "find", side_effect=LookupError("missing corpus")) as find,
        mock.patch.object(conftest.nltk, "download", return_value=True),
        pytest.raises(LookupError, match="missing corpus"),
    ):
        conftest._ensure_cmudict()

    assert find.call_count == 2


def test_conftest_import_does_not_provision_corpus():
    """[Unit] Importing test configuration never looks up or downloads NLTK data.

    Scenario:
        Given the test configuration module
        When its module body executes outside a pytest session
        Then no NLTK lookup or download runs.

    Boundaries:
        - Focus: no import-time corpus provisioning
        - Scope: isolated module namespace with mocked NLTK APIs

    On failure, first check:
        - The session fixture and module body in tests/conftest.py
    """
    with (
        mock.patch.object(conftest.nltk.data, "find") as find,
        mock.patch.object(conftest.nltk, "download") as download,
    ):
        runpy.run_path(conftest.__file__)

    find.assert_not_called()
    download.assert_not_called()
