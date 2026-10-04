"""Tests for timer.py – config resolution and cleanup target safety."""

from pathlib import Path
from unittest.mock import patch

from orbshacker.bake import bake_config
from orbshacker.timer import cleanup_targets, parse_timer_args, resolve_config


class TestParseTimerArgs:
    def test_absent(self):
        assert parse_timer_args(["prog.py"]) is None

    def test_with_minutes(self):
        assert parse_timer_args(["prog.py", "--timer-mode", "30"]) == 30

    def test_flag_without_value(self):
        assert parse_timer_args(["prog.py", "--timer-mode"]) is None

    def test_flag_with_garbage(self):
        assert parse_timer_args(["prog.py", "--timer-mode", "abc"]) is None


class TestResolveConfig:
    def test_baked_config_wins(self):
        with patch("orbshacker.timer.ORBSHACKER_BAKED_CONFIG",
                   {"TIMER_MINUTES": 45, "AUTO_DELETE_ON_TIMER_END": False}, create=True):
            cfg = resolve_config()
        assert cfg["TIMER_MINUTES"] == 45
        assert cfg["AUTO_DELETE_ON_TIMER_END"] is False

    def test_explicit_minutes_win_over_baked(self):
        with patch("orbshacker.timer.ORBSHACKER_BAKED_CONFIG",
                   {"TIMER_MINUTES": 45}, create=True):
            cfg = resolve_config(7)
        assert cfg["TIMER_MINUTES"] == 7

    def test_defaults_without_baked(self):
        cfg = resolve_config()
        assert cfg["TIMER_MINUTES"] == 15
        assert cfg["CLEANUP_DIRS"] == []


class TestCleanupTargets:
    def test_never_deletes_unmarked_files(self, tmp_path):
        exe = tmp_path / "python.exe"
        exe.write_bytes(b"MZ real interpreter")
        script = tmp_path / "orbshacker.py"
        script.write_text("print('tool')", encoding="utf-8")

        with patch("orbshacker.timer.sys.executable", str(exe)), \
             patch("orbshacker.timer.sys.argv", ["prog", str(script)]):
            files, dirs = cleanup_targets({"CLEANUP_DIRS": [], "EXTRA_FILES": []})

        assert exe not in files
        assert script not in files

    def test_deletes_target_exe_without_marker(self, tmp_path):
        exe = tmp_path / "TslGame.exe"
        exe.write_bytes(b"MZ identical pythonw copy")

        with patch("orbshacker.timer.sys.executable", str(exe)), \
             patch("orbshacker.timer.sys.argv", ["prog"]):
            files, dirs = cleanup_targets({
                "TARGET_EXE": str(exe),
                "CLEANUP_DIRS": [],
                "EXTRA_FILES": [],
            })

        assert exe in files

    def test_target_exe_must_match_running_process(self, tmp_path):
        other = tmp_path / "ImportantFile.exe"
        other.write_bytes(b"MZ")
        running = tmp_path / "python.exe"
        running.write_bytes(b"MZ")

        with patch("orbshacker.timer.sys.executable", str(running)), \
             patch("orbshacker.timer.sys.argv", ["prog"]):
            files, dirs = cleanup_targets({
                "TARGET_EXE": str(other),
                "CLEANUP_DIRS": [],
                "EXTRA_FILES": [],
            })

        assert other not in files

    def test_deletes_marked_faked_files(self, tmp_path):
        exe = tmp_path / "TslGame.exe"
        exe.write_bytes(b"MZ")
        bake_config(exe, {"TIMER_MINUTES": 5})
        script = tmp_path / "_TslGame_orbshacker_timer.pyw"
        script.write_text("# fake", encoding="utf-8")
        bake_config(script, {"TIMER_MINUTES": 5})

        with patch("orbshacker.timer.sys.executable", str(exe)), \
             patch("orbshacker.timer.sys.argv", [str(script)]):
            files, dirs = cleanup_targets({
                "STEAM_MANIFEST_PATH": "C:/Steam/appmanifest_1.acf",
                "CLEANUP_DIRS": ["C:/Games/G"],
                "EXTRA_FILES": ["C:/Games/G/python312.dll"],
            })

        names = [Path(f).name for f in files]
        assert "TslGame.exe" in names
        assert "_TslGame_orbshacker_timer.pyw" in names
        assert "appmanifest_1.acf" in names
        assert "python312.dll" in names
        assert [Path(d).name for d in dirs] == ["G"]

    def test_shared_files_kept_while_other_fakes_remain(self, tmp_path):
        own_exe = tmp_path / "TslGame.exe"
        own_exe.write_bytes(b"MZ")
        bake_config(own_exe, {"TIMER_MINUTES": 5})
        other_script = tmp_path / "_RocketLeague_orbshacker_timer.pyw"
        other_script.write_text("# other fake", encoding="utf-8")
        bake_config(other_script, {"TIMER_MINUTES": 5})
        dll = tmp_path / "python312.dll"
        dll.write_bytes(b"MZ dll")

        with patch("orbshacker.timer.sys.executable", str(own_exe)), \
             patch("orbshacker.timer.sys.argv", ["prog"]):
            files, dirs = cleanup_targets({
                "TARGET_EXE": str(own_exe),
                "SHARED_FILES": [str(dll)],
                "CLEANUP_DIRS": [],
                "EXTRA_FILES": [],
            })

        assert own_exe in files
        assert dll not in files

    def test_shared_files_deleted_when_last_fake(self, tmp_path):
        own_exe = tmp_path / "TslGame.exe"
        own_exe.write_bytes(b"MZ")
        bake_config(own_exe, {"TIMER_MINUTES": 5})
        dll = tmp_path / "python312.dll"
        dll.write_bytes(b"MZ dll")

        with patch("orbshacker.timer.sys.executable", str(own_exe)), \
             patch("orbshacker.timer.sys.argv", ["prog"]):
            files, dirs = cleanup_targets({
                "TARGET_EXE": str(own_exe),
                "SHARED_FILES": [str(dll)],
                "CLEANUP_DIRS": [],
                "EXTRA_FILES": [],
            })

        assert dll in files


class TestTkEnvironment:
    def test_sets_tcl_and_tk_libraries(self):
        import os

        from orbshacker.timer import _setup_tk_environment

        saved = {k: os.environ.pop(k, None) for k in ("TCL_LIBRARY", "TK_LIBRARY")}
        try:
            _setup_tk_environment(["C:/Python/tcl/tcl8.6", "C:/Python/tcl/tk8.6"])
            assert os.environ.get("TCL_LIBRARY") == "C:/Python/tcl/tcl8.6"
            assert os.environ.get("TK_LIBRARY") == "C:/Python/tcl/tk8.6"
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
