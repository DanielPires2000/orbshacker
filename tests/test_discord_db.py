"""Tests for discord_db.py – pure functions only (no network calls)."""

from orbshacker.discord_db import DiscordGamesDB


def _make_db_with_games(games: list) -> DiscordGamesDB:
    """Create a DiscordGamesDB without hitting the network."""
    db = object.__new__(DiscordGamesDB)  # skip __init__
    db.games = games
    db.source = "test"
    return db


SAMPLE_GAMES = [
    {
        "id": "1",
        "name": "Minecraft",
        "aliases": ["MC"],
        "executables": [
            {"os": "win32", "name": "javaw.exe"},
            {"os": "win32", "name": ">Minecraft.Windows.exe"},
        ],
    },
    {
        "id": "2",
        "name": "Minecraft Dungeons",
        "aliases": [],
        "executables": [
            {"os": "win32", "name": "Dungeons.exe"},
            {"os": "linux", "name": "dungeons"},
        ],
    },
    {
        "id": "3",
        "name": "Fortnite",
        "aliases": ["FN", "Fort"],
        "executables": [
            {"os": "win32", "name": "FortniteClient-Win64-Shipping.exe"},
            {"os": "win32", "name": "FortniteClient-Win64-Shipping_BE.exe"},
            {"os": "win32", "name": "FortniteLauncher.exe"},
        ],
    },
]


class TestSearchGames:
    def test_exact_match_by_name(self):
        db = _make_db_with_games(SAMPLE_GAMES)
        results = db.search_games("Minecraft")
        assert results[0]["id"] == "1"

    def test_exact_match_by_alias(self):
        db = _make_db_with_games(SAMPLE_GAMES)
        results = db.search_games("MC")
        assert results[0]["id"] == "1"

    def test_partial_match(self):
        db = _make_db_with_games(SAMPLE_GAMES)
        results = db.search_games("mine")
        assert len(results) == 2  # Minecraft + Minecraft Dungeons

    def test_no_results(self):
        db = _make_db_with_games(SAMPLE_GAMES)
        results = db.search_games("nonexistent_game_xyz")
        assert results == []

    def test_case_insensitive(self):
        db = _make_db_with_games(SAMPLE_GAMES)
        results = db.search_games("fortnite")
        assert results[0]["id"] == "3"


class TestFilterWin32Exes:
    def test_returns_win32_only(self):
        db = _make_db_with_games(SAMPLE_GAMES)
        exes = db.get_all_executables(SAMPLE_GAMES[1])  # Minecraft Dungeons
        assert "Dungeons.exe" in exes
        assert "dungeons" not in exes  # linux exe excluded

    def test_skips_anti_cheat_with_patterns(self):
        db = _make_db_with_games(SAMPLE_GAMES)
        exe = db.get_win32_executable(SAMPLE_GAMES[2])  # Fortnite
        assert exe == "FortniteClient-Win64-Shipping.exe"
        # _BE and Launcher should be skipped
        all_exes = db.get_all_executables(SAMPLE_GAMES[2])
        assert "FortniteClient-Win64-Shipping_BE.exe" in all_exes  # all includes them

    def test_strips_leading_gt(self):
        db = _make_db_with_games(SAMPLE_GAMES)
        all_exes = db.get_all_executables(SAMPLE_GAMES[0])
        assert "Minecraft.Windows.exe" in all_exes
        assert ">Minecraft.Windows.exe" not in all_exes
