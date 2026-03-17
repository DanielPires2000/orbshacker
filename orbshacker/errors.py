"""
Custom exceptions for orbshacker.

Keep it small — one base class + a few specific ones.
"""


class OrbshackerError(Exception):
    """Base error for all orbshacker errors."""


class NetworkError(OrbshackerError):
    """An API / HTTP call failed."""


class SteamNotFoundError(OrbshackerError):
    """Steam installation could not be located."""


class DatabaseLoadError(OrbshackerError):
    """Failed to load the games database from any source."""
