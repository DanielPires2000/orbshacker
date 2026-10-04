#!/usr/bin/env python3
"""
Backward-compatible entry point.

Usage:
    python orbshacker.py         (main menu)
    python -m orbshacker         (package-style)

A renamed copy of itself carrying a baked config (a faked game) runs the
countdown timer instead of the main menu, as does ``--timer-mode``.
"""

import os
import sys

# ── Safety: redirect stdio to devnull when running without a console ──────────
# PyInstaller --noconsole (or pythonw) sets sys.stdout/stderr/stdin to None.
# Redirect to devnull so print() / input() don't crash the whole app.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r")


def is_faked_game() -> bool:
    """A process is a faked game only if it carries an orbshacker baked config."""
    from orbshacker.bake import is_faked_game as _is_faked
    return _is_faked()


def show_console() -> None:
    """Allocate and show a Windows console window if running on Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            if not ctypes.windll.kernel32.GetConsoleWindow():
                if not ctypes.windll.kernel32.AttachConsole(-1):
                    ctypes.windll.kernel32.AllocConsole()

                sys.stdout = open("CONOUT$", "w", encoding="utf-8")
                sys.stderr = open("CONOUT$", "w", encoding="utf-8")
                sys.stdin = open("CONIN$", "r", encoding="utf-8")
        except Exception:
            pass


if __name__ == "__main__":
    if is_faked_game() or "--timer-mode" in sys.argv:
        from orbshacker.timer import parse_timer_args, run_timer
        run_timer(parse_timer_args(sys.argv))
    else:
        show_console()
        from orbshacker.main import main
        from orbshacker.ui import Colors, print_color

        try:
            main()
        except KeyboardInterrupt:
            print_color("\n\n[!] Interrupted", Colors.YELLOW)
            sys.exit(0)
        except Exception as e:
            print_color(f"\n[ERROR] Fatal error: {e}", Colors.RED, bold=True)
            import traceback
            traceback.print_exc()
            input("\nPress Enter to exit...")
            sys.exit(1)
