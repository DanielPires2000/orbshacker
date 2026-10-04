"""Tests for path_utils.py – sanitization of Windows filenames and paths."""

from orbshacker.path_utils import (
    sanitize_filename,
    sanitize_relative_path,
)


class TestSanitizeFilename:
    def test_removes_trademark_and_registered_symbols(self):
        assert sanitize_filename("STAR WARS™") == "STAR WARS"
        assert sanitize_filename("Mortal Kombat® 11") == "Mortal Kombat 11"
        assert sanitize_filename("Pokemon©") == "Pokemon"
        assert sanitize_filename("Service℠ Mark") == "Service Mark"

    def test_removes_illegal_windows_characters(self):
        assert sanitize_filename("Game: Subtitle") == "Game Subtitle"
        assert sanitize_filename('Game "Special" Edition') == "Game Special Edition"
        assert sanitize_filename("What <is> | this ? *") == "What is  this"
        assert sanitize_filename("slash/backslash\\test") == "slashbackslashtest"

    def test_strips_trailing_dots_and_spaces(self):
        assert sanitize_filename("game.exe.") == "game.exe"
        assert sanitize_filename("game.exe. .") == "game.exe"
        assert sanitize_filename("  my_game  ") == "my_game"

    def test_handles_reserved_names(self):
        assert sanitize_filename("CON") == "_CON"
        assert sanitize_filename("con.exe") == "_con.exe"
        assert sanitize_filename("aux.txt") == "_aux.txt"
        assert sanitize_filename("NUL") == "_NUL"
        assert sanitize_filename("COM1") == "_COM1"
        assert sanitize_filename("lpt3.bin") == "_lpt3.bin"

    def test_fallback_for_empty_string(self):
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename("???") == "unnamed"
        assert sanitize_filename(":::***") == "unnamed"


class TestSanitizeRelativePath:
    def test_multi_segment_with_illegal_chars(self):
        result = sanitize_relative_path("NieR:Automata™/bin:x64/Game®.exe")
        assert result == "NieRAutomata/binx64/Game.exe"

    def test_normalizes_backslashes(self):
        result = sanitize_relative_path(r"Game Folder™\Bin\Game®.exe")
        assert result == "Game Folder/Bin/Game.exe"

    def test_strips_drive_letters(self):
        result = sanitize_relative_path(r"C:\Steam\NieR:Automata™\Game.exe")
        assert result == "Steam/NieRAutomata/Game.exe"

    def test_avoids_parent_directory_traversal(self):
        result = sanitize_relative_path(r"../../Games/My™ Game.exe")
        assert result == "Games/My Game.exe"

    def test_empty_returns_unnamed(self):
        assert sanitize_relative_path("") == "unnamed"
