"""
orbshacker – central configuration.

Reads user-editable values from the root-level ``settings.py``.
If a value is missing there, the default defined below is used.
Internal-only constants (API URLs, headers, timeouts) live here
and are NOT exposed in settings.py.
"""

import os
import subprocess
from pathlib import Path
from typing import TypeVar, cast

from . import _version as _build_version

T = TypeVar("T")

# ── Load user settings (root-level settings.py) ──────────────────────────────
# This lets the user edit a single, visible file at the project root.
try:
    import settings as _user  # root-level settings.py
except ImportError:
    _user = None  # no user settings file – use all defaults


def _get(name: str, default: T) -> T:
    """Return a value from the user settings module, falling back to *default*."""
    return cast(T, getattr(_user, name, default))


def _git_version() -> str | None:
    """Return the current git tag as a version string when available."""
    commands = [
        ["git", "describe", "--tags", "--exact-match", "HEAD"],
        ["git", "describe", "--tags", "--abbrev=0", "--match", "v*"],
    ]
    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                cwd=Path(__file__).resolve().parents[1],
            )
            tag = result.stdout.strip()
            if tag:
                return tag.lstrip("v")
        except Exception:
            continue
    return None


def _resolve_version() -> str:
    """Resolve the app version from the build file or git tags."""
    built_version = getattr(_build_version, "VERSION", None)
    if built_version:
        return str(built_version)

    env_version = os.getenv("ORBSHACKER_VERSION")
    if env_version:
        return env_version

    git_version = _git_version()
    if git_version:
        return git_version

    return "0.0.0"


# ── App identity ──────────────────────────────────────────────────────────────
VERSION   = _resolve_version()
DEVELOPER = _get("DEVELOPER", "Strykey")

# ── GitHub repo ───────────────────────────────────────────────────────────────
GITHUB_REPO_OWNER = _get("GITHUB_REPO_OWNER", "DanielPires2000")
GITHUB_REPO_NAME  = _get("GITHUB_REPO_NAME",  "orbshacker")
REPO_URL          = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"

# ── Network endpoints (internal – not in settings.py) ─────────────────────────
DISCORD_API_URL        = "https://discord.com/api/v9/applications/detectable"
GITHUB_BACKUP_URL      = (
    "https://gist.githubusercontent.com/Cynosphere/"
    "c1e77f77f0e565ddaac2822977961e76/raw/gameslist.json"
)
STEAMCMD_API_URL       = "https://api.steamcmd.net/v1/info"
STEAM_STORE_SEARCH_URL = "https://store.steampowered.com/api/storesearch"

# ── HTTP settings (internal) ─────────────────────────────────────────────────
REQUEST_TIMEOUT      = 10
REQUEST_TIMEOUT_LONG = 20

DISCORD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://discord.com/",
    "Origin":          "https://discord.com",
}

# ── UI / UX (user-editable via settings.py) ───────────────────────────────────
SLEEP_SHORT        = _get("SLEEP_SHORT",        1.0)
SLEEP_LONG         = _get("SLEEP_LONG",         2.0)
FAKE_EXE_DIR       = _get("FAKE_EXE_DIR",       "Win64")
MAX_SEARCH_RESULTS = _get("MAX_SEARCH_RESULTS", 20)
