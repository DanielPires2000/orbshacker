"""
faker.py – GameFaker class, manual_mode, and executable launching.

In frozen (.exe) mode:  copies orbshacker.exe itself -> GameName.exe (config baked in)
In source mode:         copies pythonw.exe -> GameName.exe + _<stem>_orbshacker_timer.pyw
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import config
from .bake import MARKER, bake_config, has_baked_config
from .errors import FileConflictError
from .path_utils import sanitize_relative_path
from .ui import (
    Colors,
    ask_confirm,
    loading_animation,
    pause,
    print_boxed_title,
    print_color,
)

_SOURCES_FOR_INLINE = ("bake.py", "janitor.py", "timer.py")


def timer_script_for(target_path: Path) -> Path:
    """Return the per-game timer script path for *target_path*."""
    return target_path.parent / f"_{target_path.stem}_orbshacker_timer.pyw"


def build_timer_script(config_dict: dict) -> str:
    """Assemble a standalone timer script with *config_dict* baked in."""
    parts = [f"ORBSHACKER_BAKED_CONFIG = {config_dict!r}\n\n"]
    for name in _SOURCES_FOR_INLINE:
        source_path = Path(__file__).with_name(name)
        if not source_path.exists():
            raise RuntimeError(f"cannot inline {name}: source file missing ({source_path})")
        parts.append(source_path.read_text(encoding="utf-8").rstrip("\n") + "\n\n")
    payload = json.dumps(config_dict, separators=(",", ":"))
    parts.append(f"#{MARKER.decode('utf-8')}{payload}{MARKER.decode('utf-8')}\n")
    script = "".join(parts)
    compile(script, "<orbshacker_timer>", "exec")
    return script


def _is_frozen() -> bool:
    return getattr(sys, 'frozen', False)


def _find_source_exe() -> Path:
    """Find the executable to copy for fake game processes."""
    if _is_frozen():
        return Path(sys.executable)

    base_dir = Path(sys.base_prefix)
    pythonw = base_dir / "pythonw.exe"
    if pythonw.exists():
        return pythonw
    python = base_dir / "python.exe"
    if python.exists():
        return python

    pythonw_fallback = Path(sys.executable).parent / "pythonw.exe"
    if pythonw_fallback.exists():
        return pythonw_fallback
    return Path(sys.executable)


class GameFaker:
    def __init__(self):
        self._frozen = _is_frozen()
        self._source_exe = _find_source_exe()
        self.chosen_path = config.CHOSEN_FOLDER
        self._created_files = []
        self._shared_files = []
        self._created_dirs = []
        self._processes = []

    def register_created_file(self, path: Path) -> None:
        """Register a file to be deleted on cleanup."""
        self._created_files.append(Path(path))

    def register_shared_file(self, path: Path) -> None:
        """Register a file shared by several fakes (deleted only on launcher cleanup)."""
        self._shared_files.append(Path(path))

    def unregister_created_file(self, path: Path) -> None:
        target = Path(path)
        self._created_files = [p for p in self._created_files if p != target]

    def register_parent_dirs(self, path: Path, limit_dir: Path) -> list:
        """Register parent directories of *path* up to *limit_dir*; return the new ones."""
        parent = path.parent
        limit_key = os.path.normcase(str(limit_dir.resolve()))
        added = []
        depth = 0
        while os.path.normcase(str(parent.resolve())) != limit_key and parent != parent.parent and depth < 16:
            if parent not in self._created_dirs:
                self._created_dirs.append(parent)
                added.append(parent)
            parent = parent.parent
            depth += 1
        return added

    def _limit_dir_for(self, target_path: Path) -> Path:
        parts = str(target_path).replace("\\", "/").split("/")
        for index in range(len(parts) - 1):
            if parts[index].lower() == "steamapps" and parts[index + 1].lower() == "common":
                prefix = "/".join(parts[: index + 2])
                return Path(prefix.replace("/", os.sep))
        return self.chosen_path

    def build_baked_config(self, target_exe=None, manifest_path=None, cleanup_dirs=(),
                           extra_files=(), shared_files=()) -> dict:
        return {
            "TARGET_EXE": str(target_exe).replace("\\", "/") if target_exe else None,
            "TIMER_MINUTES": config.TIMER_MINUTES,
            "AUTO_DELETE_ON_TIMER_END": config.AUTO_DELETE_ON_TIMER_END,
            "STEAM_MANIFEST_PATH": str(manifest_path).replace("\\", "/") if manifest_path else None,
            "CLEANUP_DIRS": [str(d).replace("\\", "/") for d in cleanup_dirs],
            "EXTRA_FILES": [str(f).replace("\\", "/") for f in extra_files],
            "SHARED_FILES": [str(f).replace("\\", "/") for f in shared_files],
            "TK_SUPPORT_DIRS": self._tk_support_dirs(),
        }

    @staticmethod
    def _tk_support_dirs() -> list:
        base = Path(sys.base_prefix) / "tcl"
        if not base.is_dir():
            return []
        return [str(p).replace("\\", "/") for p in sorted(base.iterdir()) if p.is_dir()]

    def copy_exe_to(self, target_path: Path, manifest_path: Path | None = None) -> None:
        """Copy the faker executable to *target_path* and bake the active config.

        Refuses to overwrite files that were not created by orbshacker so a real
        game executable is never destroyed.
        """
        target_path = Path(target_path)
        existing_script = timer_script_for(target_path)
        is_ours = has_baked_config(target_path) or existing_script.exists()
        if target_path.exists() and not is_ours:
            raise FileConflictError(
                f"{target_path} already exists and was not created by orbshacker "
                "(real game executable?); refusing to overwrite"
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._source_exe, target_path)
        self.register_created_file(target_path)

        limit_dir = self._limit_dir_for(target_path)
        cleanup_dirs = self.register_parent_dirs(target_path, limit_dir)
        shared_files = []
        if not self._frozen:
            shared_files = self._copy_python_runtime(target_path.parent)

        baked = self.build_baked_config(
            target_exe=target_path,
            manifest_path=manifest_path,
            cleanup_dirs=cleanup_dirs,
            shared_files=shared_files,
        )
        if self._frozen:
            bake_config(target_path, baked)
        else:
            # Keep the pythonw copy byte-identical (its Authenticode signature
            # must survive); the per-game script carries the baked config.
            script = timer_script_for(target_path)
            script.write_text(build_timer_script(baked), encoding="utf-8")
            self.register_created_file(script)

    def _copy_python_runtime(self, folder: Path) -> list:
        """Ensure pythonXY.dll and a ._pth exist beside the fake exe.

        Returns every shared file in place afterwards (created now or by an
        earlier fake), so any game's cleanup can remove them once it is the
        last fake in the folder.
        """
        version_tag = f"{sys.version_info.major}{sys.version_info.minor}"
        ensured = []

        target_dll = folder / f"python{version_tag}.dll"
        source_dll = Path(sys.base_prefix) / target_dll.name
        if not target_dll.exists() and source_dll.exists():
            try:
                shutil.copy2(source_dll, target_dll)
                self.register_shared_file(target_dll)
            except Exception:
                pass
        if target_dll.exists():
            ensured.append(target_dll)

        pth = folder / f"python{version_tag}._pth"
        if not pth.exists():
            try:
                base = Path(sys.base_prefix)
                lines = [
                    str(base / "Lib"),
                    str(base / "DLLs"),
                    str(folder),
                ]
                pth.write_text("\n".join(lines) + "\n", encoding="utf-8")
                self.register_shared_file(pth)
            except Exception:
                pass
        if pth.exists():
            ensured.append(pth)

        return ensured

    def create_fake_game(self, exe_name: str) -> Path | None:
        """Create fake game executable under Desktop/<FAKE_EXE_DIR>/."""
        exe_name = sanitize_relative_path(exe_name)
        if not exe_name.lower().endswith('.exe'):
            exe_name += '.exe'
        target_path = self.chosen_path / config.FAKE_EXE_DIR / exe_name
        try:
            loading_animation(f"Creating {exe_name.split('/')[-1]}", 0.5)
            self.copy_exe_to(target_path)
            print_color(f"[OK] Created: {target_path}", Colors.GREEN, bold=True)
            return target_path
        except FileConflictError as e:
            print_color(f"[ERROR] {e}", Colors.RED, bold=True)
            return None
        except Exception as e:
            print_color(f"[ERROR] Failed to create executable: {e}", Colors.RED, bold=True)
            print_color("[!] Check file permissions or disk space", Colors.YELLOW)
            return None

    def launch_executable(self, exe_path: Path) -> bool:
        """Launch the fake game process in background."""
        try:
            loading_animation("Launching process", 0.5)

            if self._frozen:
                args = [str(exe_path)]
                env = None
            else:
                timer_script = timer_script_for(exe_path)
                args = [str(exe_path), str(timer_script)]
                env = os.environ.copy()
                base_prefix = Path(sys.base_prefix)
                env["PYTHONHOME"] = str(base_prefix)

                path_parts = [str(base_prefix), env.get("PATH", "")]
                env["PATH"] = os.pathsep.join(part for part in path_parts if part)

            if sys.platform == 'win32':
                DETACHED_PROCESS = 0x00000008
                proc = subprocess.Popen(
                    args,
                    env=env,
                    creationflags=DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            else:
                proc = subprocess.Popen(
                    args,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
            self._processes.append(proc)

            print_color("[OK] Process launched in background", Colors.GREEN, bold=True)
            print_color("[*] Discord should now detect the game (if Discord is running)", Colors.CYAN)
            print_color("[!] IMPORTANT: Discord MUST be running for the spoofing to work", Colors.YELLOW)
            print_color("[*] Wait a few seconds for Discord to scan processes", Colors.GRAY)
            print_color("[*] TIP: Use the menu again to emulate multiple games at once!", Colors.MAGENTA)
            return True
        except Exception as e:
            print_color(f"[!] Failed to auto-launch: {e}", Colors.YELLOW)
            print_color(f"[*] You can manually run: {exe_path}", Colors.CYAN)
            return False

    def cleanup(self) -> None:
        """Terminate faked processes and delete created files (AUTO_DELETE_ON_EXIT only)."""
        if not config.AUTO_DELETE_ON_EXIT:
            return

        print_color("\n[*] AUTO_DELETE_ON_EXIT enabled. Cleaning up faked processes and files...", Colors.CYAN)

        for proc in self._processes:
            try:
                proc.terminate()
            except Exception:
                pass

        if self._processes:
            time.sleep(1.0)
            for proc in self._processes:
                try:
                    proc.kill()
                except Exception:
                    pass

        for file_path in list(self._created_files) + list(self._shared_files):
            deleted = False
            for _ in range(5):
                try:
                    if file_path.exists():
                        file_path.unlink()
                    deleted = True
                    break
                except Exception:
                    time.sleep(0.2)
            if not deleted and file_path.exists():
                print_color(f"[!] Failed to delete: {file_path} (file is locked)", Colors.YELLOW)

        sorted_dirs = sorted(self._created_dirs, key=lambda p: len(p.parts), reverse=True)
        for dir_path in sorted_dirs:
            try:
                if dir_path.exists() and not any(dir_path.iterdir()):
                    dir_path.rmdir()
            except Exception:
                pass

        print_color("[OK] Cleanup complete!", Colors.GREEN)


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
    print(f"  Path: {Colors.GRAY}{faker.chosen_path / config.FAKE_EXE_DIR / exe_name}{Colors.RESET}")

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

    pause()
