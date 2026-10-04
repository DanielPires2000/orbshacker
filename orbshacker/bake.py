"""
bake.py – Embed and read orbshacker settings inside faked executables.

Stdlib-only on purpose: its source is inlined into generated timer scripts,
so it must never import anything from the orbshacker package.
"""

import json
import sys
from pathlib import Path

MARKER = b"__ORBSHACKER_BAKED_CONFIG__"
_TAIL_BYTES = 65536


def bake_config(path, config: dict) -> None:
    """Append *config* to *path* between marker blocks."""
    payload = MARKER + json.dumps(config, separators=(",", ":")).encode("utf-8") + MARKER
    with open(path, "ab") as fh:
        fh.write(payload)


def load_baked_config(path) -> dict | None:
    """Return the config baked at the tail of *path*, or None if absent/corrupt."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - _TAIL_BYTES))
            chunk = fh.read()
    except Exception:
        return None
    if MARKER not in chunk:
        return None
    parts = chunk.split(MARKER)
    if len(parts) < 3:
        return None
    try:
        return json.loads(parts[-2].decode("utf-8"))
    except Exception:
        return None


def has_baked_config(path) -> bool:
    return load_baked_config(path) is not None


def current_target() -> Path | None:
    """Return the executable or script the current process was started from."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    if sys.argv and sys.argv[0]:
        return Path(sys.argv[0])
    return None


def is_faked_game(path=None) -> bool:
    """A process is a faked game only if it carries an orbshacker baked config."""
    target = Path(path) if path is not None else current_target()
    return bool(target) and has_baked_config(target)
