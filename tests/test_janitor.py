"""Tests for janitor.py – self-destruct script generation and escaping."""

from pathlib import Path
from unittest.mock import patch

from orbshacker.janitor import (
    MAX_DELETE_ATTEMPTS,
    build_self_destruct_script,
    cmd_quote,
    spawn_self_destruct,
)


class TestCmdQuote:
    def test_wraps_in_quotes(self):
        assert cmd_quote("C:/x/y.exe") == '"C:/x/y.exe"'

    def test_escapes_percent(self):
        assert cmd_quote("C:/a%TEMP%b.exe") == '"C:/a%%TEMP%%b.exe"'

    def test_pathlike_accepted(self):
        quoted = cmd_quote(Path("game.exe"))
        assert quoted == '"game.exe"'


class TestBuildSelfDestructScript:
    def test_commands_are_independent_lines(self):
        script = build_self_destruct_script(["C:/a.exe", "C:/b.exe"], [])
        assert "&&" not in script
        assert 'del /f /q "C:/a.exe"' in script
        assert 'del /f /q "C:/b.exe"' in script

    def test_retries_are_bounded(self):
        script = build_self_destruct_script(["C:/a.exe"], [], max_attempts=7)
        assert "if %_n% geq 7 goto done" in script
        assert "goto loop" in script

    def test_default_max_attempts_used(self):
        script = build_self_destruct_script(["C:/a.exe"], [])
        assert f"if %_n% geq {MAX_DELETE_ATTEMPTS} goto done" in script

    def test_deletes_empty_dirs_deepest_first(self):
        script = build_self_destruct_script([], ["C:/outer", "C:/outer/inner"])
        assert script.index('rd "C:/outer/inner"') < script.index('rd "C:/outer"')

    def test_self_deletes_the_script(self):
        script = build_self_destruct_script(["C:/a.exe"], [])
        assert 'del /f /q "%~f0"' in script

    def test_escapes_percent_in_paths(self):
        script = build_self_destruct_script(["C:/we%ird.exe"], [])
        assert '"C:/we%%ird.exe"' in script
        assert '"C:/we%ird.exe"' not in script

    def test_dir_removal_is_conditional(self):
        script = build_self_destruct_script([], ["D:/Games"])
        assert 'if exist "D:/Games" rd "D:/Games"' in script


class TestSpawnSelfDestruct:
    def test_noop_when_nothing_to_delete(self):
        assert spawn_self_destruct([], []) is None

    def test_writes_script_and_spawns(self, tmp_path):
        with patch("orbshacker.janitor.subprocess.Popen") as mock_popen:
            script_path = spawn_self_destruct([tmp_path / "a.exe"], [tmp_path])
        assert script_path is not None
        assert script_path.exists()
        content = script_path.read_text(encoding="utf-8")
        assert "a.exe" in content
        mock_popen.assert_called_once()
        script_path.unlink()
