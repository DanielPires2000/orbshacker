#!/usr/bin/env python3
"""
Backward-compatible entry point.

Usage:
    python orbshacker.py         (main menu)
    python -m orbshacker         (package-style)

When launched with --timer-mode (by a renamed copy of itself),
it runs the 15-minute timer instead of the main menu.
"""

import sys
import os

# ── Safety: redirect stdio to devnull when running without a console ──────────
# PyInstaller --noconsole (or pythonw) sets sys.stdout/stderr/stdin to None.
# Redirect to devnull so print() / input() don't crash the whole app.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r")

if "--timer-mode" in sys.argv:
    from orbshacker.timer import run_timer
    run_timer()
else:
    from orbshacker.main import main
    from orbshacker.ui import print_color, Colors

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
