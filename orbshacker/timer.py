"""
timer.py – Fake game process: a standalone countdown timer with self-cleanup.

This module is both the runtime used by ``--timer-mode`` and the source that
``orbshacker.faker.build_timer_script`` inlines (together with bake.py and
janitor.py) into generated ``_*_orbshacker_timer_*.pyw`` files. Because of
that it stays stdlib-only and only imports package siblings behind a
try/except that fails harmlessly in the inlined form.
"""

import sys
import time

try:
    from .bake import has_baked_config, load_baked_config
    from .janitor import spawn_self_destruct
except ImportError:
    pass

WINDOW_TITLE = "Timer"
WINDOW_SIZE = "400x250"
BG_COLOR = "#1a1a1a"
TEXT_COLOR = "#e0e0e0"
SECONDARY_COLOR = "#666666"
DONE_COLOR = "#ff6b6b"
DEFAULT_MINUTES = 15
BAKED_CONFIG_KEYS = (
    "TARGET_EXE",
    "TIMER_MINUTES",
    "AUTO_DELETE_ON_TIMER_END",
    "STEAM_MANIFEST_PATH",
    "CLEANUP_DIRS",
    "EXTRA_FILES",
    "SHARED_FILES",
    "TK_SUPPORT_DIRS",
)


def resolve_config(minutes=None) -> dict:
    """Merge defaults, package settings, baked config and explicit overrides."""
    cfg = {
        "TARGET_EXE": None,
        "TIMER_MINUTES": DEFAULT_MINUTES,
        "AUTO_DELETE_ON_TIMER_END": True,
        "STEAM_MANIFEST_PATH": None,
        "CLEANUP_DIRS": [],
        "EXTRA_FILES": [],
        "SHARED_FILES": [],
        "TK_SUPPORT_DIRS": [],
    }
    if __package__:
        try:
            from . import config
            cfg["TIMER_MINUTES"] = config.TIMER_MINUTES
            cfg["AUTO_DELETE_ON_TIMER_END"] = config.AUTO_DELETE_ON_TIMER_END
            cfg["STEAM_MANIFEST_PATH"] = config.STEAM_MANIFEST_PATH
        except Exception:
            pass
    baked = globals().get("ORBSHACKER_BAKED_CONFIG")
    if baked is None and globals().get("load_baked_config") is not None:
        try:
            baked = load_baked_config(sys.executable)
        except Exception:
            baked = None
    if isinstance(baked, dict):
        for key in BAKED_CONFIG_KEYS:
            if baked.get(key) is not None:
                cfg[key] = baked[key]
    if minutes is not None:
        cfg["TIMER_MINUTES"] = minutes
    return cfg


def parse_timer_args(argv=None) -> int | None:
    """Return the minutes given as ``--timer-mode N``, or None when absent/unparseable."""
    argv = list(sys.argv if argv is None else argv)
    if "--timer-mode" not in argv:
        return None
    idx = argv.index("--timer-mode")
    if idx + 1 < len(argv):
        try:
            return int(argv[idx + 1])
        except ValueError:
            return None
    return None


def _other_fakes_in(folder, own) -> bool:
    """True when *folder* still holds faked files that are not in *own*."""
    import os
    from pathlib import Path

    folder = Path(folder)
    if not folder.is_dir():
        return False
    own_keys = {os.path.normcase(str(p)) for p in own}
    for entry in folder.iterdir():
        if entry.suffix.lower() not in (".exe", ".py", ".pyw"):
            continue
        if os.path.normcase(str(entry)) in own_keys:
            continue
        if has_baked_config(entry):
            return True
    return False


def cleanup_targets(cfg: dict) -> tuple[list, list]:
    """Return (files, dirs) a finished faked process should delete.

    Only files carrying an orbshacker baked config are deleted, plus the exe
    named by ``TARGET_EXE`` in our own baked config (source-mode pythonw copies
    stay byte-identical and carry no marker). Shared runtime files are deleted
    only when no other faked game is left in their folder.
    """
    import os
    from pathlib import Path

    files = []
    exe = Path(sys.executable)
    target = cfg.get("TARGET_EXE")
    target_matches = bool(target) and os.path.normcase(str(target)) == os.path.normcase(str(exe))
    if has_baked_config(exe) or target_matches:
        files.append(exe)
    if sys.argv and sys.argv[0]:
        script = Path(sys.argv[0])
        same_as_exe = os.path.normcase(str(script)) == os.path.normcase(str(exe))
        if not same_as_exe and script.suffix.lower() in (".py", ".pyw") and has_baked_config(script):
            files.append(script)
    manifest = cfg.get("STEAM_MANIFEST_PATH")
    if manifest:
        files.append(Path(manifest))
    files.extend(Path(p) for p in cfg.get("EXTRA_FILES", []) if p)
    shared = [Path(p) for p in cfg.get("SHARED_FILES", []) if p]
    for p in shared:
        if not _other_fakes_in(p.parent, list(files) + shared):
            files.append(p)
    dirs = [Path(p) for p in cfg.get("CLEANUP_DIRS", []) if p]
    return files, dirs


class TimerApp:
    def __init__(self, root, minutes=DEFAULT_MINUTES, auto_delete=True,
                 cleanup_files=None, cleanup_dirs=None):
        self.root = root
        self.auto_delete = bool(auto_delete)
        self.cleanup_files = list(cleanup_files or [])
        self.cleanup_dirs = list(cleanup_dirs or [])
        root.title(WINDOW_TITLE)
        root.geometry(WINDOW_SIZE)
        root.resizable(False, False)
        root.configure(bg=BG_COLOR)
        self.remaining = int(minutes) * 60
        self._deadline = time.monotonic() + self.remaining
        from tkinter import Label
        self.label = Label(root, text=f"{int(minutes):02d}:00", font=("Consolas", 56, "bold"),
                           fg=TEXT_COLOR, bg=BG_COLOR)
        self.label.pack(expand=True)
        self.status = Label(root, text="Running", font=("Segoe UI", 10),
                           fg=SECONDARY_COLOR, bg=BG_COLOR)
        self.status.pack(side="bottom", pady=20)
        self._tick()

    def _tick(self):
        remaining = int(round(self._deadline - time.monotonic()))
        if remaining < 0:
            remaining = 0
        m, s = divmod(remaining, 60)
        self.label.config(text=f"{m:02d}:{s:02d}")
        if remaining > 0:
            self.label.after(250, self._tick)
        else:
            self.label.config(text="00:00", fg=DONE_COLOR)
            self.status.config(text="Complete", fg=DONE_COLOR)
            self.root.update()
            if self.auto_delete:
                self.trigger_self_destruction()

    def trigger_self_destruction(self):
        spawn_self_destruct(self.cleanup_files, self.cleanup_dirs)
        self.root.destroy()
        sys.exit(0)


def _setup_tk_environment(tk_support_dirs) -> None:
    """Point TCL_LIBRARY/TK_LIBRARY at the real install so tkinter works from anywhere."""
    import os

    for entry in tk_support_dirs or []:
        name = entry.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].lower()
        if name.startswith("tcl"):
            os.environ.setdefault("TCL_LIBRARY", entry)
        elif name.startswith("tk"):
            os.environ.setdefault("TK_LIBRARY", entry)


def run_timer(minutes=None) -> None:
    """Entry point for a faked game process or ``--timer-mode``."""
    cfg = resolve_config(minutes)
    _setup_tk_environment(cfg.get("TK_SUPPORT_DIRS"))
    import tkinter as tk

    files, dirs = cleanup_targets(cfg)
    root = tk.Tk()
    TimerApp(
        root,
        minutes=cfg["TIMER_MINUTES"],
        auto_delete=cfg["AUTO_DELETE_ON_TIMER_END"],
        cleanup_files=files,
        cleanup_dirs=dirs,
    )
    root.mainloop()


if __name__ == "__main__":
    run_timer()
