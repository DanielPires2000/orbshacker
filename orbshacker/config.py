"""
orbshacker – central configuration.

Reads user-editable values from ``settings.json`` (or the legacy root-level
``settings.py``) and validates every one of them. A missing or invalid value
falls back to the default defined in ``DEFAULTS`` – the single source of truth
for all settings.

Internal-only constants (API URLs, headers, timeouts) live here and are NOT
exposed in settings.py.

Nothing in this module writes to disk or spawns subprocesses at import time:
``ensure_user_settings()`` is called explicitly from ``main()``, and the app
version is resolved lazily on first access.
"""

import json
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

from .bake import is_faked_game
from .path_utils import sanitize_relative_path

try:
    from . import _version as _build_version
except ImportError:
    _build_version = None

DEFAULTS: dict[str, Any] = {
    "CHOSEN_FOLDER": "Desktop",
    "FAKE_EXE_DIR": "Win64",
    "AUTO_DELETE_ON_TIMER_END": True,
    "AUTO_DELETE_ON_EXIT": False,
    "TIMER_MINUTES": 15,
    "MAX_SEARCH_RESULTS": 20,
    "STEAM_MANIFEST_PATH": None,
}

LEGACY_KEYS = {"AUTO_DELETE": "AUTO_DELETE_ON_TIMER_END"}


def _coerce_bool(value: Any, default: bool, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "yes", "on", "1"):
            return True
        if lowered in ("false", "no", "off", "0"):
            return False
    warnings.warn(f"settings: {name}={value!r} is not a boolean, using default {default}")
    return default


def _coerce_int(value: Any, default: int, name: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        warnings.warn(f"settings: {name}={value!r} is not a number, using default {default}")
        return default
    if isinstance(value, float) and not value.is_integer():
        warnings.warn(f"settings: {name}={value!r} is not a whole number, using default {default}")
        return default
    try:
        result = int(value)
    except (TypeError, ValueError):
        warnings.warn(f"settings: {name}={value!r} is not a number, using default {default}")
        return default
    if minimum is not None and result < minimum:
        warnings.warn(f"settings: {name}={result} is below {minimum}, using default {default}")
        return default
    return result


def _coerce_str(value: Any, default: str, name: str) -> str:
    if isinstance(value, str):
        return value
    warnings.warn(f"settings: {name}={value!r} is not a string, using default {default}")
    return default


def _coerce_optional_path(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    warnings.warn(f"settings: {name}={value!r} is not a path string, using default None")
    return None


def _get_default_json_content() -> str:
    content = {
        "CHOSEN_FOLDER": str(Path.home() / "Desktop").replace("\\", "/"),
        "AUTO_DELETE_ON_TIMER_END": DEFAULTS["AUTO_DELETE_ON_TIMER_END"],
        "AUTO_DELETE_ON_EXIT": DEFAULTS["AUTO_DELETE_ON_EXIT"],
        "TIMER_MINUTES": DEFAULTS["TIMER_MINUTES"],
    }
    return json.dumps(content, indent=2)


def _load_embedded_settings() -> dict | None:
    if not getattr(sys, "frozen", False):
        return None
    from .bake import load_baked_config

    return load_baked_config(Path(sys.executable))


def _load_settings():
    embedded = _load_embedded_settings()
    if embedded is not None:
        return embedded

    if getattr(sys, "frozen", False):
        json_path = Path(sys.executable).parent / "settings.json"
    else:
        json_path = Path(__file__).resolve().parents[1] / "settings.json"

    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            warnings.warn(f"settings: could not parse {json_path}, using defaults")

    try:
        import settings as _user
        return _user
    except ImportError:
        return None


_user = _load_settings()

_MINIMUMS = {"TIMER_MINUTES": 1, "MAX_SEARCH_RESULTS": 1}


def _get_validated(name: str) -> Any:
    """Return a validated user value for *name*, falling back to DEFAULTS."""
    default = DEFAULTS[name]
    if _user is None:
        return default
    if isinstance(_user, dict):
        raw = _user.get(name)
        if raw is None:
            legacy = next((k for k, v in LEGACY_KEYS.items() if v == name), None)
            if legacy is not None:
                raw = _user.get(legacy)
    else:
        raw = getattr(_user, name, None)
    if raw is None:
        return default
    if name == "CHOSEN_FOLDER":
        return raw if isinstance(raw, (str, Path)) else default
    if isinstance(default, bool):
        return _coerce_bool(raw, default, name)
    if isinstance(default, int):
        return _coerce_int(raw, default, name, minimum=_MINIMUMS.get(name))
    if isinstance(default, str):
        return _coerce_str(raw, default, name)
    return _coerce_optional_path(raw, name)


def ensure_user_settings() -> None:
    """Create a default settings.json next to the executable (frozen app only)."""
    if not getattr(sys, "frozen", False) or is_faked_game():
        return
    json_path = Path(sys.executable).parent / "settings.json"
    if json_path.exists():
        return
    try:
        json_path.write_text(_get_default_json_content(), encoding="utf-8")
    except Exception:
        pass


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
    built_version = getattr(_build_version, "VERSION", None)
    if built_version:
        return str(built_version)
    git_version = _git_version()
    if git_version:
        return git_version
    return "0.0.0"


# ── App identity ──────────────────────────────────────────────────────────────
DEVELOPER = "Strykey / Daniel Pires / Pannenkoekisus"

_version_cache: str | None = None


def __getattr__(name: str) -> Any:
    global _version_cache
    if name == "VERSION":
        if _version_cache is None:
            _version_cache = _resolve_version()
        return _version_cache
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── GitHub repo ───────────────────────────────────────────────────────────────
GITHUB_REPO_OWNER = "DanielPires2000"
GITHUB_REPO_NAME = "orbshacker"
REPO_URL = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"

# ── Network endpoints (internal – not in settings.py) ─────────────────────────
DISCORD_API_URL = "https://discord.com/api/v9/applications/detectable"
GITHUB_BACKUP_URL = (
    "https://gist.githubusercontent.com/Cynosphere/"
    "c1e77f77f0e565ddaac2822977961e76/raw/gameslist.json"
)
STEAMCMD_API_URL = "https://api.steamcmd.net/v1/info"
STEAM_STORE_SEARCH_URL = "https://store.steampowered.com/api/storesearch"

# ── HTTP settings (internal) ─────────────────────────────────────────────────
REQUEST_TIMEOUT = 10
REQUEST_TIMEOUT_LONG = 20

DISCORD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://discord.com/",
    "Origin": "https://discord.com",
}

# ── UI / UX (user-editable via settings.json or settings.py) ──────────────────
SLEEP_SHORT = 1.0
SLEEP_LONG = 2.0
FAKE_EXE_DIR = sanitize_relative_path(_get_validated("FAKE_EXE_DIR"))
MAX_SEARCH_RESULTS = _get_validated("MAX_SEARCH_RESULTS")
AUTO_DELETE_ON_TIMER_END = _get_validated("AUTO_DELETE_ON_TIMER_END")
AUTO_DELETE_ON_EXIT = _get_validated("AUTO_DELETE_ON_EXIT")
TIMER_MINUTES = _get_validated("TIMER_MINUTES")
STEAM_MANIFEST_PATH = _get_validated("STEAM_MANIFEST_PATH")


def _resolve_chosen_folder() -> Path:
    raw = _get_validated("CHOSEN_FOLDER")
    if isinstance(raw, Path):
        return raw
    value = raw if isinstance(raw, str) else DEFAULTS["CHOSEN_FOLDER"]
    if value.strip() in ("Desktop", ""):
        return Path.home() / "Desktop"
    return Path(value)


CHOSEN_FOLDER = _resolve_chosen_folder()
