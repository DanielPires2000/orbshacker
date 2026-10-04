"""Tests for steam.py – pure functions only (no network calls)."""

import pytest

from orbshacker.errors import FileConflictError
from orbshacker.faker import GameFaker
from orbshacker.steam import (
    _acf_escape,
    _pick_windows_exe,
    _resolve_executable,
    create_steam_fake,
    generate_appmanifest,
    is_our_manifest,
)


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

    def test_none_config_does_not_crash(self):
        launch = {"0": {"executable": "game.exe", "config": None}}
        assert _pick_windows_exe(launch) == "game.exe"


class TestAcfEscape:
    def test_doubles_backslashes(self):
        assert _acf_escape("C:\\Steam\\x") == "C:\\\\Steam\\\\x"

    def test_strips_quotes(self):
        assert _acf_escape('We"ird') == "Weird"


class TestGenerateAppmanifest:
    def test_writes_expected_content(self, tmp_path):
        acf = generate_appmanifest(
            1234, "My Game", "MyGame", tmp_path, depot_id="5678", owner="76561198000000000"
        )
        assert acf is not None and acf.exists()
        text = acf.read_text(encoding="utf-8")
        assert '"appid"\t\t"1234"' in text
        assert '"name"\t\t"My Game"' in text
        assert '"installdir"\t\t"MyGame"' in text
        assert '"StateFlags"\t\t"1026"' in text
        assert '"LastOwner"\t\t"76561198000000000"' in text
        assert '"5678"' in text
        assert is_our_manifest(acf)

    def test_escapes_launcher_path(self, tmp_path):
        acf = generate_appmanifest(1, "N", "N", tmp_path, owner="0")
        text = acf.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "LauncherPath" in line:
                assert "\\\\" in line

    def test_omits_staged_section_without_depot(self, tmp_path):
        acf = generate_appmanifest(9, "N", "N", tmp_path, owner="0")
        text = acf.read_text(encoding="utf-8")
        assert '"StagedDepots"' in text
        assert '"dlcappid"' not in text

    def test_refuses_to_overwrite_foreign_manifest(self, tmp_path):
        steamapps = tmp_path / "steamapps"
        steamapps.mkdir()
        real = steamapps / "appmanifest_123.acf"
        real.write_text('"AppState"\n{\n"appid"\t\t"1234"\n"StateFlags"\t\t"4"\n}\n', encoding="utf-8")

        assert generate_appmanifest(123, "My Game", "MyGame", tmp_path, owner="0") is None
        assert '"StateFlags"\t\t"4"' in real.read_text(encoding="utf-8")

    def test_overwrites_our_own_manifest(self, tmp_path):
        first = generate_appmanifest(55, "A", "A", tmp_path, owner="0")
        second = generate_appmanifest(55, "B", "B", tmp_path, owner="0")
        assert first == second
        assert '"name"\t\t"B"' in second.read_text(encoding="utf-8")

    def test_foreign_manifest_is_not_ours(self, tmp_path):
        p = tmp_path / "appmanifest_1.acf"
        p.write_text('"StateFlags"\t\t"4"', encoding="utf-8")
        assert not is_our_manifest(p)


class TestCreateSteamFake:
    def _fake_faker(self, tmp_path):
        faker = GameFaker()
        faker._source_exe = tmp_path / "pythonw.exe"
        faker._source_exe.touch()
        faker._frozen = True
        return faker

    def test_creates_manifest_and_exe(self, tmp_path):
        from orbshacker.steam import SteamAppInfo

        faker = self._fake_faker(tmp_path)
        info: SteamAppInfo = {"name": "G", "installdir": "G", "executable": "g.exe", "depot_id": None}
        exe_path = create_steam_fake(faker, 42, info, tmp_path)

        assert exe_path is not None and exe_path.exists()
        assert (tmp_path / "steamapps" / "appmanifest_42.acf").exists()

    def test_rolls_back_manifest_when_exe_copy_fails(self, tmp_path):
        from unittest.mock import patch

        from orbshacker.steam import SteamAppInfo

        faker = self._fake_faker(tmp_path)
        info: SteamAppInfo = {"name": "G", "installdir": "G", "executable": "g.exe", "depot_id": None}

        with patch.object(GameFaker, "copy_exe_to", side_effect=OSError("disk full")):
            result = create_steam_fake(faker, 43, info, tmp_path)

        assert result is None
        assert not (tmp_path / "steamapps" / "appmanifest_43.acf").exists()

    def test_refuses_when_real_game_exe_present(self, tmp_path):
        faker = self._fake_faker(tmp_path)
        real_exe = tmp_path / "steamapps" / "common" / "G" / "g.exe"
        real_exe.parent.mkdir(parents=True)
        real_exe.write_bytes(b"MZ real")

        with pytest.raises(FileConflictError):
            faker.copy_exe_to(real_exe)

        assert real_exe.read_bytes() == b"MZ real"
