"""Tests for errors.py – exception hierarchy."""

import pytest
from orbshacker.errors import (
    OrbshackerError,
    NetworkError,
    SteamNotFoundError,
    DatabaseLoadError,
)


def test_network_error_is_orbshacker_error():
    assert issubclass(NetworkError, OrbshackerError)


def test_steam_not_found_is_orbshacker_error():
    assert issubclass(SteamNotFoundError, OrbshackerError)


def test_database_load_error_is_orbshacker_error():
    assert issubclass(DatabaseLoadError, OrbshackerError)


def test_can_catch_all_with_base():
    with pytest.raises(OrbshackerError):
        raise NetworkError("test")
