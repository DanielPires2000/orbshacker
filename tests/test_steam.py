"""Tests for steam.py – pure functions only (no network calls)."""

from orbshacker.steam import _pick_windows_exe, _resolve_executable


class TestPickWindowsExe:
    def test_finds_first_windows_exe(self):
        launch = {
            "0": {
                "executable": "game.exe",
                "config": {"oslist": "windows"},
            },
            "1": {
                "executable": "game_server.exe",
                "config": {"oslist": "windows"},
            },
        }
        assert _pick_windows_exe(launch) == "game.exe"

    def test_skips_non_windows(self):
        launch = {
            "0": {
                "executable": "game.app",
                "config": {"oslist": "macos"},
            },
            "1": {
                "executable": "game.exe",
                "config": {"oslist": "windows"},
            },
        }
        assert _pick_windows_exe(launch) == "game.exe"

    def test_skips_non_exe(self):
        launch = {
            "0": {
                "executable": "game.sh",
                "config": {"oslist": "windows"},
            },
        }
        assert _pick_windows_exe(launch) is None

    def test_empty_launch(self):
        assert _pick_windows_exe({}) is None

    def test_normalises_backslashes(self):
        launch = {
            "0": {
                "executable": "Bin\\Win64\\game.exe",
                "config": {"oslist": "windows"},
            },
        }
        assert _pick_windows_exe(launch) == "Bin/Win64/game.exe"

    def test_empty_oslist_counts_as_windows(self):
        launch = {
            "0": {
                "executable": "game.exe",
                "config": {"oslist": ""},
            },
        }
        assert _pick_windows_exe(launch) == "game.exe"

    def test_handles_special_symbols_in_launch(self):
        launch = {
            "0": {
                "executable": "Bin\\Win64™\\Game®:Quest.exe",
                "config": {"oslist": "windows"},
            },
        }
        from orbshacker.path_utils import sanitize_relative_path
        raw_exe = _pick_windows_exe(launch)
        assert sanitize_relative_path(raw_exe) == "Bin/Win64/GameQuest.exe"


class TestResolveExecutable:
    def test_fc27_uses_known_executable_without_launch_metadata(self):
        # EA's launch URI doesn't give Steam a normal Windows executable to detect.
        assert _resolve_executable(4080220, "EA SPORTS FC 27", {}) == "fc27.exe"

    def test_other_games_keep_normal_detection(self):
        launch = {
            "0": {
                "executable": "Bin\\game.exe",
                "config": {"oslist": "windows"},
            },
        }
        assert _resolve_executable(1234, "Example Game", launch) == "Bin/game.exe"
