"""Tests for config.py and faker.py settings loading and cleanup behavior."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orbshacker import config
from orbshacker.bake import bake_config
from orbshacker.config import _coerce_bool, _coerce_int, _load_settings, ensure_user_settings
from orbshacker.errors import FileConflictError
from orbshacker.faker import GameFaker, build_timer_script, timer_script_for

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_entrypoint_module():
    spec = importlib.util.spec_from_file_location(
        "orbshacker_script", PROJECT_ROOT / "orbshacker.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSettingsValidation:
    def test_load_settings_json_in_dev(self, tmp_path):
        json_path = tmp_path / "settings.json"
        json_path.write_text('{"CHOSEN_FOLDER": "CustomDir"}', encoding="utf-8")

        fake_config_file = tmp_path / "orbshacker" / "config.py"
        with patch("orbshacker.config.__file__", str(fake_config_file)):
            settings = _load_settings()
            assert isinstance(settings, dict)
            assert settings.get("CHOSEN_FOLDER") == "CustomDir"

    def test_corrupt_settings_json_falls_back(self, tmp_path):
        json_path = tmp_path / "settings.json"
        json_path.write_text("{not json", encoding="utf-8")

        fake_config_file = tmp_path / "orbshacker" / "config.py"
        with patch("orbshacker.config.__file__", str(fake_config_file)):
            settings = _load_settings()
        assert settings is None or isinstance(settings, dict) or hasattr(settings, "TIMER_MINUTES")

    def test_ensure_user_settings_creates_json(self, tmp_path):
        exe_path = tmp_path / "orbshacker.exe"
        exe_path.touch()

        with patch("sys.frozen", True, create=True), patch("sys.executable", str(exe_path)):
            ensure_user_settings()

        json_file = tmp_path / "settings.json"
        assert json_file.exists()
        expected_desktop = str(Path.home() / "Desktop").replace("\\", "/")
        assert expected_desktop in json_file.read_text(encoding="utf-8")

        payload = json.loads(json_file.read_text(encoding="utf-8"))
        assert payload["TIMER_MINUTES"] == 15
        assert payload["AUTO_DELETE_ON_TIMER_END"] is True
        assert payload["AUTO_DELETE_ON_EXIT"] is False

    def test_ensure_user_settings_skips_faked_games(self, tmp_path):
        exe_path = tmp_path / "TslGame.exe"
        exe_path.write_bytes(b"MZ")
        bake_config(exe_path, {"TIMER_MINUTES": 15})

        with patch("sys.frozen", True, create=True), patch("sys.executable", str(exe_path)):
            ensure_user_settings()

        assert not (tmp_path / "settings.json").exists()

    def test_ensure_user_settings_keeps_existing_json(self, tmp_path):
        exe_path = tmp_path / "orbshacker.exe"
        exe_path.touch()
        json_file = tmp_path / "settings.json"
        json_file.write_text('{"TIMER_MINUTES": 5}', encoding="utf-8")

        with patch("sys.frozen", True, create=True), patch("sys.executable", str(exe_path)):
            ensure_user_settings()

        assert json_file.read_text(encoding="utf-8") == '{"TIMER_MINUTES": 5}'

    def test_coerce_bool_accepts_common_forms(self):
        assert _coerce_bool(True, False, "x") is True
        assert _coerce_bool("true", False, "x") is True
        assert _coerce_bool("no", True, "x") is False
        assert _coerce_bool(1, False, "x") is True

    def test_coerce_bool_rejects_garbage(self):
        with pytest.warns(UserWarning):
            assert _coerce_bool("banana", True, "x") is True

    def test_coerce_int_accepts_numeric_strings(self):
        assert _coerce_int("25", 15, "x") == 25
        assert _coerce_int(30.0, 15, "x") == 30

    def test_coerce_int_rejects_garbage_and_minimums(self):
        with pytest.warns(UserWarning):
            assert _coerce_int("fifteen", 15, "x") == 15
        with pytest.warns(UserWarning):
            assert _coerce_int(-5, 15, "x", minimum=1) == 15

    def test_coerce_int_rejects_fractional_floats(self):
        with pytest.warns(UserWarning):
            assert _coerce_int(15.7, 15, "x") == 15
        assert _coerce_int(15.0, 9, "x") == 15

    def test_invalid_user_settings_fall_back_to_defaults(self):
        with patch.object(config, "_user", {"TIMER_MINUTES": "soon", "AUTO_DELETE_ON_TIMER_END": "maybe"}):
            timer = config._get_validated("TIMER_MINUTES")
            flag = config._get_validated("AUTO_DELETE_ON_TIMER_END")
        assert timer == config.DEFAULTS["TIMER_MINUTES"]
        assert flag == config.DEFAULTS["AUTO_DELETE_ON_TIMER_END"]

    def test_legacy_auto_delete_key_maps_to_timer_end(self):
        with patch.object(config, "_user", {"AUTO_DELETE": True}):
            assert config._get_validated("AUTO_DELETE_ON_TIMER_END") is True
        with patch.object(config, "_user", {"AUTO_DELETE": False}):
            assert config._get_validated("AUTO_DELETE_ON_TIMER_END") is False

    def test_frozen_existing_json(self, tmp_path):
        exe_path = tmp_path / "orbshacker.exe"
        exe_path.touch()
        json_file = tmp_path / "settings.json"
        json_file.write_text('{"CHOSEN_FOLDER": "FrozenDir"}', encoding="utf-8")

        with patch("sys.frozen", True, create=True), patch("sys.executable", str(exe_path)):
            settings = _load_settings()
            assert isinstance(settings, dict)
            assert settings.get("CHOSEN_FOLDER") == "FrozenDir"


class TestBakedSettings:
    def test_load_settings_baked_frozen(self, tmp_path):
        exe_path = tmp_path / "TslGame.exe"
        config_data = {"CHOSEN_FOLDER": "BakedDir", "AUTO_DELETE_ON_TIMER_END": True, "TIMER_MINUTES": 45}
        exe_path.write_bytes(b"MZ_DUMMY_EXE_BYTES...")
        bake_config(exe_path, config_data)

        with patch("sys.frozen", True, create=True), patch("sys.executable", str(exe_path)):
            settings = _load_settings()
            assert isinstance(settings, dict)
            assert settings.get("CHOSEN_FOLDER") == "BakedDir"
            assert settings.get("AUTO_DELETE_ON_TIMER_END") is True
            assert settings.get("TIMER_MINUTES") == 45


class TestTimerScriptGeneration:
    def test_bakes_config_and_is_standalone(self):
        script = build_timer_script({"TIMER_MINUTES": 25, "AUTO_DELETE_ON_TIMER_END": False})
        assert "TIMER_MINUTES': 25" in script
        assert "AUTO_DELETE_ON_TIMER_END': False" in script
        compile(script, "<test>", "exec")
        assert "class TimerApp" in script
        assert "import orbshacker" not in script
        assert "from orbshacker" not in script

    def test_per_game_script_names(self, tmp_path):
        a = timer_script_for(tmp_path / "TslGame.exe")
        b = timer_script_for(tmp_path / "RocketLeague.exe")
        assert a != b
        assert a.name == "_TslGame_orbshacker_timer.pyw"
        assert a.parent == tmp_path


class TestFaker:
    def test_faker_cleanup_deletes_files_and_processes(self, tmp_path):
        with patch("orbshacker.config.AUTO_DELETE_ON_EXIT", True):
            faker = GameFaker()

            mock_proc = MagicMock()
            faker._processes.append(mock_proc)

            dummy_file = tmp_path / "faked_game.exe"
            dummy_file.touch()
            faker.register_created_file(dummy_file)

            dummy_dir = tmp_path / "Win64"
            dummy_dir.mkdir()
            faker._created_dirs.append(dummy_dir)

            faker.cleanup()

            mock_proc.terminate.assert_called_once()
            mock_proc.kill.assert_called_once()
            assert not dummy_file.exists()
            assert not dummy_dir.exists()

    def test_faker_cleanup_skipped_when_disabled(self, tmp_path):
        with patch("orbshacker.config.AUTO_DELETE_ON_EXIT", False):
            faker = GameFaker()
            mock_proc = MagicMock()
            faker._processes.append(mock_proc)
            dummy_file = tmp_path / "faked_game.exe"
            dummy_file.touch()
            faker.register_created_file(dummy_file)

            faker.cleanup()

            mock_proc.terminate.assert_not_called()
            assert dummy_file.exists()

    def test_faker_custom_timer_minutes(self, tmp_path):
        with patch("orbshacker.config.TIMER_MINUTES", 25), \
             patch("orbshacker.config.AUTO_DELETE_ON_TIMER_END", False), \
             patch("orbshacker.config.AUTO_DELETE_ON_EXIT", False):

            faker = GameFaker()
            dummy_src = tmp_path / "pythonw.exe"
            dummy_src.touch()
            faker._source_exe = dummy_src
            faker._frozen = False

            target_exe = tmp_path / "Win64" / "Game.exe"
            faker.copy_exe_to(target_exe)

            timer_script = timer_script_for(target_exe)
            assert timer_script.exists()
            script_code = timer_script.read_text(encoding="utf-8")
            assert "TIMER_MINUTES': 25" in script_code
            assert "AUTO_DELETE_ON_TIMER_END': False" in script_code

        with patch("orbshacker.config.TIMER_MINUTES", 35):
            faker = GameFaker()
            faker._frozen = True

            with patch("subprocess.Popen") as mock_popen:
                faker.launch_executable(Path("C:/Dummy/Game.exe"))

                mock_popen.assert_called_once()
                called_args = mock_popen.call_args[1].get("args", mock_popen.call_args[0][0])
                assert called_args == [str(Path("C:/Dummy/Game.exe"))]

    def test_multi_game_scripts_are_independent(self, tmp_path):
        with patch("orbshacker.config.TIMER_MINUTES", 11), \
             patch("orbshacker.config.CHOSEN_FOLDER", tmp_path):
            faker = GameFaker()
            dummy_src = tmp_path / "pythonw.exe"
            dummy_src.write_bytes(b"MZ pythonw source")
            faker._source_exe = dummy_src
            faker._frozen = False

            first = tmp_path / "Win64" / "TslGame.exe"
            faker.copy_exe_to(first)

            with patch("orbshacker.config.TIMER_MINUTES", 22):
                second = tmp_path / "Win64" / "RocketLeague.exe"
                faker.copy_exe_to(second)

            first_script = timer_script_for(first).read_text(encoding="utf-8")
            second_script = timer_script_for(second).read_text(encoding="utf-8")
            assert "TIMER_MINUTES': 11" in first_script
            assert "TIMER_MINUTES': 22" in second_script
            assert first_script != second_script

    def test_source_mode_exe_stays_byte_identical(self, tmp_path):
        with patch("orbshacker.config.TIMER_MINUTES", 15), \
             patch("orbshacker.config.CHOSEN_FOLDER", tmp_path):
            faker = GameFaker()
            dummy_src = tmp_path / "pythonw.exe"
            payload = b"MZ signed pythonw payload"
            dummy_src.write_bytes(payload)
            faker._source_exe = dummy_src
            faker._frozen = False

            target = tmp_path / "Win64" / "TslGame.exe"
            faker.copy_exe_to(target)

            assert target.read_bytes() == payload
            script = timer_script_for(target).read_text(encoding="utf-8")
            assert "TARGET_EXE" in script
            assert "SHARED_FILES" in script

    def test_frozen_mode_bakes_config_into_exe(self, tmp_path):
        faker = GameFaker()
        faker._source_exe = tmp_path / "orbshacker.exe"
        faker._source_exe.write_bytes(b"MZ tool")
        faker._frozen = True

        target = tmp_path / "Win64" / "TslGame.exe"
        faker.copy_exe_to(target)

        from orbshacker.bake import load_baked_config
        baked = load_baked_config(target)
        assert baked is not None
        assert baked["TIMER_MINUTES"] == config.TIMER_MINUTES

    def test_refuses_to_overwrite_foreign_file(self, tmp_path):
        faker = GameFaker()
        faker._source_exe = tmp_path / "pythonw.exe"
        faker._source_exe.touch()
        faker._frozen = True

        real_game = tmp_path / "steamapps" / "common" / "Game" / "Game.exe"
        real_game.parent.mkdir(parents=True)
        real_game.write_bytes(b"MZ real game")

        with pytest.raises(FileConflictError):
            faker.copy_exe_to(real_game, manifest_path=None)

        assert real_game.read_bytes() == b"MZ real game"

    def test_overwrites_our_own_fakes(self, tmp_path):
        faker = GameFaker()
        faker._source_exe = tmp_path / "pythonw.exe"
        faker._source_exe.touch()
        faker._frozen = True

        target = tmp_path / "Win64" / "TslGame.exe"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"MZ")
        bake_config(target, {"TIMER_MINUTES": 5})

        faker.copy_exe_to(target, manifest_path=None)
        assert target.exists()

    def test_register_parent_dirs_is_case_insensitive_for_steamapps(self, tmp_path):
        faker = GameFaker()
        fake_root = tmp_path / "SteamLibrary" / "SteamApps" / "Common" / "MyGame" / "Bin"
        fake_root.mkdir(parents=True)
        target = fake_root / "Game.exe"
        target.touch()

        limit = faker._limit_dir_for(target)
        assert limit.name.lower() == "common"

        added = faker.register_parent_dirs(target, limit)
        names = {p.name for p in added}
        assert "Bin" in names
        assert "MyGame" in names
        assert not any(p.name.lower() == "steamapps" for p in added)


def test_is_faked_game(tmp_path):
    orb_module = _load_entrypoint_module()

    faked = tmp_path / "TslGame.exe"
    faked.write_bytes(b"MZ")
    bake_config(faked, {"TIMER_MINUTES": 15})

    plain = tmp_path / "orbshacker.exe"
    plain.write_bytes(b"MZ")

    renamed_plain = tmp_path / "TotallyLegitGame.exe"
    renamed_plain.write_bytes(b"MZ")

    with patch("orbshacker.bake.current_target", return_value=faked):
        assert orb_module.is_faked_game()

    with patch("orbshacker.bake.current_target", return_value=plain):
        assert not orb_module.is_faked_game()

    with patch("orbshacker.bake.current_target", return_value=renamed_plain):
        assert not orb_module.is_faked_game()


def test_timer_self_destruction(tmp_path):
    from orbshacker.timer import TimerApp

    root = MagicMock()
    with patch.object(TimerApp, "_tick"):
        app = TimerApp(root, minutes=15, auto_delete=True,
                       cleanup_files=[tmp_path / "TslGame.exe"],
                       cleanup_dirs=[tmp_path])

    with patch("orbshacker.timer.spawn_self_destruct") as mock_spawn, \
         patch("sys.exit") as mock_exit:

        app.trigger_self_destruction()

        mock_spawn.assert_called_once()
        files, dirs = mock_spawn.call_args[0][0], mock_spawn.call_args[0][1]
        assert tmp_path / "TslGame.exe" in [Path(f) for f in files]
        assert tmp_path in [Path(d) for d in dirs]

        root.destroy.assert_called_once()
        mock_exit.assert_called_once_with(0)
