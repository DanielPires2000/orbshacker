"""
orbshacker – Discord Orb Quest Faker.

EDUCATIONAL PURPOSES ONLY.
"""

from typing import Any


def __getattr__(name: str) -> Any:
    if name in ("__version__", "VERSION"):
        from .config import VERSION
        return VERSION
    if name in ("__author__", "DEVELOPER"):
        from .config import DEVELOPER
        return DEVELOPER
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["__version__", "__author__"]
