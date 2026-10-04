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

    def test_sanitizes_symbols_and_illegal_chars(self):
        games = [{
            "id": "99",
            "name": "Special Game™",
            "executables": [
                {"os": "win32", "name": "Game™:Special®/Bin/Launch*.exe"}
            ]
        }]
        db = _make_db_with_games(games)
        exes = db.get_all_executables(games[0])
        assert exes == ["GameSpecial/Bin/Launch.exe"]


class TestSkipPatterns:
    def _game(self, *names):
        return {
            "id": "1",
            "name": "X",
            "executables": [{"os": "win32", "name": n} for n in names],
        }

    def test_skips_known_noise(self):
        db = _make_db_with_games([])
        game = self._game(
            "FortniteLauncher.exe",
            "Unins000.exe",
            "UnityCrashHandler64.exe",
            "BugReport.exe",
            "Setup.exe",
            "Game_BE.exe",
            "Game_EAC.exe",
            "GameUpdater.exe",
        )
        assert db.get_all_executables(game, skip_patterns=True) == []

    def test_keeps_real_game_names(self):
        db = _make_db_with_games([])
        game = self._game(
            "CrashBandicoot4.exe",
            "UpdateTheGame.exe",
            "RocketLeague.exe",
            "ReportOfTheWeek.exe",
            "InstallerSimulator.exe",
            "SetupQuest.exe",
        )
        kept = db.get_all_executables(game, skip_patterns=True)
        assert "CrashBandicoot4.exe" in kept
        assert "UpdateTheGame.exe" in kept
        assert "RocketLeague.exe" in kept
        assert "ReportOfTheWeek.exe" in kept

    def test_primary_exe_prefers_real_game_over_noise(self):
        db = _make_db_with_games([])
        game = self._game("GameLauncher.exe", "TslGame.exe")
        assert db.get_win32_executable(game) == "TslGame.exe"

    def test_skip_patterns_disabled_keeps_everything(self):
        db = _make_db_with_games([])
        game = self._game("GameLauncher.exe", "TslGame.exe")
        assert len(db.get_all_executables(game, skip_patterns=False)) == 2


class TestValidateGames:
    def test_rejects_non_list_payload(self):
        import pytest

        from orbshacker.discord_db import _validate_games
        from orbshacker.errors import DatabaseLoadError

        with pytest.raises(DatabaseLoadError):
            _validate_games({"unexpected": "shape"})

    def test_rejects_empty_payload(self):
        import pytest

        from orbshacker.discord_db import _validate_games
        from orbshacker.errors import DatabaseLoadError

        with pytest.raises(DatabaseLoadError):
            _validate_games([])

    def test_filters_entries_without_id_or_name(self):
        from orbshacker.discord_db import _validate_games

        games = _validate_games([
            {"id": "1", "name": "Good"},
            {"id": "", "name": "NoId"},
            {"id": "2"},
            "not-a-dict",
            {"id": "3", "name": "AlsoGood"},
        ])
        assert [g["id"] for g in games] == ["1", "3"]

