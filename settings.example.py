from pathlib import Path

# ╔═══════════════════════════════════════════════════════════╗
# ║             ORBSHACKER – USER SETTINGS                   ║
# ║  Copy this file to settings.py and edit the values.      ║
# ║  Frozen builds use settings.json instead (auto-created). ║
# ╚═══════════════════════════════════════════════════════════╝

# ── Destination folder for faked executables (defaults to Desktop) ──
CHOSEN_FOLDER = Path.home() / "Desktop"

# ── Subfolder (inside CHOSEN_FOLDER) where faked executables are created ──
FAKE_EXE_DIR = "Win64"

# ── Delete faked files automatically when the countdown timer finishes ──
AUTO_DELETE_ON_TIMER_END = True

# ── Kill faked processes and delete their files when the launcher exits ──
#    Leave False to keep quests running after closing orbshacker.
AUTO_DELETE_ON_EXIT = False

# ── Timer duration (in minutes) – Discord quests normally require 15 minutes ──
TIMER_MINUTES = 15
