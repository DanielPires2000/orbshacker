"""
faker.py – GameFaker class, manual_mode, and executable launching.

In frozen (.exe) mode:   copies orbshacker.exe itself → GameName.exe (--timer-mode)
In source mode:           copies pythonw.exe → GameName.exe + _orbshacker_timer.pyw
"""

import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

from . import config
from .ui import (
    Colors, print_color, print_boxed_title,
    loading_animation, ask_confirm,
)

# Timer code embedded for source mode – written as a standalone .pyw file
# so that the renamed pythonw.exe can run it without any package dependency.
_TIMER_PYW_CODE = '''\
import tkinter as tk

class TimerApp:
    def __init__(self, root):
        root.title("Timer")
        root.geometry("400x250")
        root.resizable(False, False)
        root.configure(bg="#1a1a1a")
        self.remaining = 15 * 60
        self.label = tk.Label(root, text="15:00", font=("Consolas", 56, "bold"),
                              fg="#e0e0e0", bg="#1a1a1a")
        self.label.pack(expand=True)
        self.status = tk.Label(root, text="Running", font=("Segoe UI", 10),
                               fg="#666666", bg="#1a1a1a")
        self.status.pack(side="bottom", pady=20)
        self._tick()

    def _tick(self):
        m, s = divmod(self.remaining, 60)
        self.label.config(text=f"{m:02d}:{s:02d}")
        if self.remaining > 0:
            self.remaining -= 1
            self.label.after(1000, self._tick)
        else:
            self.label.config(text="00:00", fg="#ff6b6b")
            self.status.config(text="Complete", fg="#ff6b6b")

root = tk.Tk()
TimerApp(root)
root.mainloop()
'''


def _is_frozen() -> bool:
    return getattr(sys, 'frozen', False)


def _find_source_exe() -> Path:
    """Find the executable to copy for fake game processes."""
    if _is_frozen():
        return Path(sys.executable)  # copy ourselves

    # Source mode: prefer pythonw.exe (no console window)
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    if pythonw.exists():
        return pythonw
    return Path(sys.executable)  # fallback to python.exe


class GameFaker:
    def __init__(self):
        self._frozen = _is_frozen()
        self._source_exe = _find_source_exe()
        self.desktop_path = Path.home() / "Desktop"

    def copy_exe_to(self, target_path: Path) -> None:
        """Copy the faker executable to *target_path*.

        In source mode, also creates a ``_orbshacker_timer.pyw`` next to
        the target so the renamed Python interpreter can run it.
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._source_exe, target_path)

        if not self._frozen:
            timer_script = target_path.parent / "_orbshacker_timer.pyw"
            if not timer_script.exists():
                timer_script.write_text(_TIMER_PYW_CODE, encoding="utf-8")

    def create_fake_game(self, exe_name: str) -> Path | None:
        """Create fake game executable under Desktop/<FAKE_EXE_DIR>/."""
        if not exe_name.lower().endswith('.exe'):
            exe_name += '.exe'
        exe_name = exe_name.replace('\\', '/')
        target_path = self.desktop_path / config.FAKE_EXE_DIR / exe_name
        try:
            loading_animation(f"Creating {exe_name.split('/')[-1]}", 0.8)
            self.copy_exe_to(target_path)
            print_color(f"[OK] Created: {target_path}", Colors.GREEN, bold=True)
            return target_path
        except Exception as e:
            print_color(f"[ERROR] Failed to create executable: {e}", Colors.RED, bold=True)
            print_color("[!] Check file permissions or disk space", Colors.YELLOW)
            return None

    def launch_executable(self, exe_path: Path) -> bool:
        """Launch the fake game process in background."""
        try:
            loading_animation("Launching process", 0.8)

            if self._frozen:
                args = [str(exe_path), "--timer-mode"]
                env = None
            else:
                timer_script = exe_path.parent / "_orbshacker_timer.pyw"
                args = [str(exe_path), str(timer_script)]
                env = os.environ.copy()
                base_prefix = Path(sys.base_prefix)
                env["PYTHONHOME"] = str(base_prefix)

                path_parts = [str(base_prefix), env.get("PATH", "")]
                env["PATH"] = os.pathsep.join(part for part in path_parts if part)

            if sys.platform == 'win32':
                DETACHED_PROCESS = 0x00000008
                subprocess.Popen(
                    args,
                    env=env,
                    creationflags=DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    args,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )

            print_color("[OK] Process launched in background", Colors.GREEN, bold=True)
            print_color("[*] Discord should now detect the game (if Discord is running)", Colors.CYAN)
            print_color("[!] IMPORTANT: Discord MUST be running for the spoofing to work", Colors.YELLOW)
            print_color("[*] Wait a few seconds for Discord to scan processes", Colors.GRAY)
            print_color("[*] TIP: You can run this tool multiple times to emulate multiple games!", Colors.MAGENTA)
            return True
        except Exception as e:
            print_color(f"[!] Failed to auto-launch: {e}", Colors.YELLOW)
            print_color(f"[*] You can manually run: {exe_path}", Colors.CYAN)
            return False


def manual_mode(faker: GameFaker) -> None:
    """Manual mode – user types an exact process name to fake."""
    print_boxed_title("MANUAL MODE", width=50, color=Colors.CYAN)
    print_color("[*] Enter the exact process name Discord expects", Colors.CYAN)
    print_color("[*] Examples:", Colors.GRAY)
    print_color("    • TslGame.exe (PUBG)", Colors.GRAY)
    print_color("    • League of Legends.exe (LoL)", Colors.GRAY)
    print_color("    • Overwatch.exe", Colors.GRAY)
    print_color("[*] Make sure the name matches exactly (case-sensitive on some systems)", Colors.GRAY)
    print()

    exe_name = input(f"{Colors.BOLD}Executable name{Colors.RESET} (or 'back'): ").strip()
    if not exe_name or exe_name.lower() in ('back', 'b'):
        return

    print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  Executable: {Colors.CYAN}{exe_name}{Colors.RESET}")
    print(f"  Path: {Colors.GRAY}{faker.desktop_path / config.FAKE_EXE_DIR / exe_name}{Colors.RESET}")

    if not ask_confirm():
        print_color("\n[!] Operation cancelled", Colors.YELLOW)
        time.sleep(config.SLEEP_SHORT)
        return

    result = faker.create_fake_game(exe_name)
    if result:
        print()
        faker.launch_executable(result)
        print_color("\n[OK] Setup complete!", Colors.GREEN, bold=True)
        print_color("[!] IMPORTANT: Discord MUST be running for the spoofing to work", Colors.YELLOW)

    input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")
