"""
janitor.py – Safe, bounded self-deletion of faked artifacts.

Stdlib-only on purpose: its source is inlined into generated timer scripts,
so it must never import anything from the orbshacker package.
"""

import subprocess
import tempfile
from pathlib import Path

MAX_DELETE_ATTEMPTS = 30
RETRY_DELAY_SECONDS = 1


def cmd_quote(path) -> str:
    """Quote a filesystem path for use inside a cmd.exe batch script."""
    return '"' + str(path).replace("%", "%%") + '"'


def build_self_destruct_script(files, dirs, max_attempts: int = MAX_DELETE_ATTEMPTS) -> str:
    """Build a batch script that deletes *files* and empty *dirs* with bounded retries.

    Every command stands on its own line so a single failure never aborts the
    rest of the cleanup, and the retry loop always terminates.
    """
    quoted_files = [cmd_quote(p) for p in files]
    quoted_dirs = [cmd_quote(p) for p in sorted(dirs, key=lambda d: len(Path(d).parts), reverse=True)]
    lines = ["@echo off", "setlocal", "set /a _n=0", ":loop", "set /a _n+=1"]
    for quoted in quoted_files:
        lines.append(f"if exist {quoted} del /f /q {quoted}")
    lines.append(f"if %_n% geq {max_attempts} goto done")
    for quoted in quoted_files:
        lines.append(f"if exist {quoted} goto wait")
    lines.append("goto done")
    lines.append(":wait")
    lines.append(f"ping -n {RETRY_DELAY_SECONDS + 1} 127.0.0.1 >nul")
    lines.append("goto loop")
    lines.append(":done")
    for quoted in quoted_dirs:
        lines.append(f"if exist {quoted} rd {quoted}")
    lines.append('del /f /q "%~f0" >nul 2>&1')
    return "\r\n".join(lines) + "\r\n"


def spawn_self_destruct(files, dirs, max_attempts: int = MAX_DELETE_ATTEMPTS) -> Path | None:
    """Write and launch a detached self-destruction batch script."""
    files = [Path(p) for p in files if p]
    dirs = [Path(p) for p in dirs if p]
    if not files and not dirs:
        return None
    script = build_self_destruct_script(files, dirs, max_attempts)
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".cmd", mode="w", encoding="utf-8", newline=""
        ) as fh:
            script_path = Path(fh.name)
            fh.write(script)
    except Exception:
        return None
    try:
        subprocess.Popen(
            ["cmd", "/c", str(script_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        try:
            script_path.unlink()
        except Exception:
            pass
        return None
    return script_path
