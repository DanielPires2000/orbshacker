"""
steam.py – Steam quest helpers: registry, API, appmanifest, and quest mode UI.
"""

import os
import sys
import time
from pathlib import Path
from typing import Any, TypedDict, cast

from . import config
from .errors import NetworkError
from .faker import GameFaker
from .net import fetch_json
from .path_utils import sanitize_filename, sanitize_path_segment, sanitize_relative_path
from .ui import (
    Colors,
    ask_confirm,
    loading_animation,
    pause,
    print_boxed_title,
    print_color,
)


class SteamAppInfo(TypedDict):
    name: str
    installdir: str
    executable: str
    depot_id: str | None


class SteamStoreItem(TypedDict):
    id: int
    name: str


class SteamLaunchEntry(TypedDict, total=False):
    executable: str
    config: dict[str, str]


SteamLaunchMap = dict[str, SteamLaunchEntry]
SteamDataMap = dict[str, Any]

# Windows registry – optional
try:
    import winreg as _winreg
except ImportError:
    _winreg = None


# ── Registry helpers ──────────────────────────────────────────────────────────

def get_steam_path() -> Path | None:
    """Read Steam installation path from Windows registry."""
    if sys.platform != 'win32' or _winreg is None:
        return None
    try:
        with _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = _winreg.QueryValueEx(key, "SteamPath")
        return Path(value)
    except Exception:
        fallback = Path("C:/Program Files (x86)/Steam")
        return fallback if fallback.exists() else None


def get_steam_user_id() -> str:
    """Read the currently logged-in Steam user ID from registry."""
    if sys.platform != 'win32' or _winreg is None:
        return "0"
    try:
        with _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess") as key:
            value, _ = _winreg.QueryValueEx(key, "ActiveUser")
        steam_id_64 = int(value) + 76561197960265728
        return str(steam_id_64)
    except Exception:
        return "0"


# ── API helpers ───────────────────────────────────────────────────────────────

def _pick_windows_exe(launch: SteamLaunchMap) -> str | None:
    """Return the first Windows .exe found in a SteamCMD launch dict."""
    for key in sorted(launch.keys()):
        entry = launch[key]
        entry_config = entry.get("config") or {}
        oslist = str(entry_config.get("oslist", "windows") or "")
        if "windows" in oslist or oslist == "":
            exe = entry.get("executable", "")
            if exe.endswith(".exe"):
                return exe.replace("\\", "/")
    return None


def _resolve_executable(appid: int, installdir: str, launch: SteamLaunchMap) -> str:
    """Resolve the executable path, including known games with nonstandard launch metadata."""
    # FC 27 launches through EA's URI, so Steam's launch data does not expose its game EXE.
    if appid == 4080220:
        return "fc27.exe"

    executable = _pick_windows_exe(launch)
    if not executable:
        executable = installdir.split("/")[-1] + ".exe"
    return sanitize_relative_path(executable)


def fetch_steam_app_info(appid: int) -> SteamAppInfo | None:
    """Fetch app info from SteamCMD API. Returns dict or None on failure."""
    url = f"{config.STEAMCMD_API_URL}/{appid}"
    try:
        loading_animation(f"Fetching Steam app info for {appid}", 0.5)
        data = cast(SteamDataMap, fetch_json(url))

        data_root = data.get("data")
        if not isinstance(data_root, dict):
            raise ValueError("unexpected SteamCMD payload shape")
        app_data = data_root.get(str(appid))
        if not isinstance(app_data, dict):
            raise ValueError("appid missing from SteamCMD payload")
        common_cfg = app_data.get("common") or {}
        app_cfg = app_data.get("config") or {}
        if not isinstance(common_cfg, dict) or not isinstance(app_cfg, dict):
            raise ValueError("unexpected SteamCMD app sections")

        raw_name = str(common_cfg.get("name") or f"App {appid}")
        name = sanitize_filename(raw_name)
        raw_installdir = str(app_cfg.get("installdir") or raw_name)
        installdir = sanitize_path_segment(raw_installdir) or name
        launch_map = cast(SteamLaunchMap, app_cfg.get("launch") or {})
        executable = _resolve_executable(appid, installdir, launch_map)

        depots = app_data.get("depots") or {}
        depot_id = None
        if isinstance(depots, dict):
            depot_id = next((key for key in depots.keys() if key.isdigit()), None)
        return {"name": name, "installdir": installdir, "executable": executable, "depot_id": depot_id}

    except (NetworkError, ValueError, AttributeError, TypeError) as e:
        print_color(f"[!] SteamCMD API error: {e}", Colors.YELLOW)
        return None


def search_steam_games(query: str) -> list[SteamStoreItem]:
    """Search Steam store. Returns list of {id, name} dicts."""
    try:
        loading_animation(f"Searching Steam for '{query}'", 0.5)
        data = cast(dict[str, Any], fetch_json(
            config.STEAM_STORE_SEARCH_URL,
            params={"term": query, "l": "english", "cc": "US"},
        ))
        items = data.get("items", [])
        if not isinstance(items, list):
            return []
        cleaned: list[SteamStoreItem] = []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("id"), int) and isinstance(item.get("name"), str):
                cleaned.append(cast(SteamStoreItem, {"id": item["id"], "name": item["name"]}))
        return cleaned
    except NetworkError as e:
        print_color(f"[!] Steam search error: {e}", Colors.YELLOW)
        return []


# ── Appmanifest generation ────────────────────────────────────────────────────

_ACF_TEMPLATE = '''"AppState"
{{
\t"appid"\t\t"{appid}"
\t"universe"\t\t"1"
\t"LauncherPath"\t\t"{launcher}"
\t"name"\t\t"{name}"
\t"StateFlags"\t\t"1026"
\t"installdir"\t\t"{installdir}"
\t"LastUpdated"\t\t"0"
\t"LastPlayed"\t\t"0"
\t"SizeOnDisk"\t\t"0"
\t"StagingSize"\t\t"1073741824"
\t"buildid"\t\t"0"
\t"LastOwner"\t\t"{owner}"
\t"DownloadType"\t\t"1"
\t"UpdateResult"\t\t"4"
\t"BytesToDownload"\t\t"1073741824"
\t"BytesDownloaded"\t\t"27262976"
\t"BytesToStage"\t\t"1073741824"
\t"BytesStaged"\t\t"27262976"
\t"TargetBuildID"\t\t"0"
\t"AutoUpdateBehavior"\t\t"0"
\t"AllowOtherDownloadsWhileRunning"\t\t"0"
\t"ScheduledAutoUpdate"\t\t"0"
\t"InstalledDepots"
\t{{
\t}}
\t"StagedDepots"
\t{{{staged}
\t}}
\t"UserConfig"
\t{{
\t}}
\t"MountedConfig"
\t{{
\t}}
}}
'''

_STAGED_DEPOT_TEMPLATE = '''
\t\t"{depot_id}"
\t\t{{
\t\t\t"manifest"\t\t"0"
\t\t\t"size"\t\t"1073741824"
\t\t\t"dlcappid"\t\t"0"
\t\t}}'''

_OUR_MANIFEST_FINGERPRINT = (
    '"StagingSize"\t\t"1073741824"',
    '"BytesDownloaded"\t\t"27262976"',
    '"TargetBuildID"\t\t"0"',
)


def _acf_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', "")


def is_our_manifest(path: Path) -> bool:
    """True when *path* holds an appmanifest previously generated by orbshacker."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return all(fingerprint in text for fingerprint in _OUR_MANIFEST_FINGERPRINT)


def generate_appmanifest(
    appid: int,
    name: str,
    installdir: str,
    steam_path: Path,
    depot_id: str | None = None,
    owner: str | None = None,
) -> Path | None:
    """Generate a realistic appmanifest_<appid>.acf (StateFlags 1026).

    Refuses to touch an existing manifest that was not generated by orbshacker,
    so an installed game is never destroyed.
    """
    acf_path = steam_path / "steamapps" / f"appmanifest_{appid}.acf"
    if acf_path.exists() and not is_our_manifest(acf_path):
        print_color(
            f"[ERROR] {acf_path} already exists and was not generated by orbshacker "
            "(game really installed?); refusing to overwrite",
            Colors.RED, bold=True,
        )
        return None

    acf_content = _ACF_TEMPLATE.format(
        appid=appid,
        launcher=_acf_escape(steam_path / "steam.exe"),
        name=_acf_escape(name),
        installdir=_acf_escape(installdir),
        owner=owner if owner is not None else get_steam_user_id(),
        staged=_STAGED_DEPOT_TEMPLATE.format(depot_id=depot_id) if depot_id else "",
    )
    try:
        acf_path.parent.mkdir(parents=True, exist_ok=True)
        with open(acf_path, "w", encoding="utf-8") as f:
            f.write(acf_content)
        print_color(f"[OK] Created appmanifest: {acf_path}", Colors.GREEN, bold=True)
        return acf_path
    except Exception as e:
        print_color(f"[ERROR] Failed to write appmanifest: {e}", Colors.RED, bold=True)
        return None


def create_steam_fake(
    faker: GameFaker,
    appid: int,
    info: SteamAppInfo,
    steam_path: Path,
) -> Path | None:
    """Create manifest + fake exe, rolling the manifest back if the exe fails."""
    acf = generate_appmanifest(
        appid, info["name"], info["installdir"], steam_path, depot_id=info.get("depot_id")
    )
    if not acf:
        return None

    exe_full_path = f"{info['installdir']}/{info['executable']}"
    fake_exe_path = steam_path / "steamapps" / "common" / exe_full_path.replace("/", os.sep)

    faker.register_created_file(acf)
    try:
        loading_animation(f"Creating {info['executable'].split('/')[-1]}", 0.5)
        faker.copy_exe_to(fake_exe_path, manifest_path=acf)
    except Exception as e:
        print_color(f"[ERROR] Failed to copy exe: {e}", Colors.RED, bold=True)
        try:
            if acf.exists():
                acf.unlink()
            faker.unregister_created_file(acf)
            print_color("[*] Rolled back the generated appmanifest", Colors.YELLOW)
        except Exception:
            pass
        time.sleep(config.SLEEP_SHORT)
        return None

    print_color(f"[OK] Created: {fake_exe_path}", Colors.GREEN, bold=True)
    return fake_exe_path


# ── Interactive UI for Steam Quest Mode ───────────────────────────────────────

def _resolve_steam_path() -> Path | None:
    """Auto-detect or prompt for Steam path."""
    steam_path = get_steam_path()
    if steam_path and steam_path.exists():
        return steam_path
    print_color("[!] Could not locate Steam automatically.", Colors.YELLOW)
    manual = input(
        f"{Colors.BOLD}Enter Steam path manually{Colors.RESET}"
        " (e.g. C:/Program Files (x86)/Steam): "
    ).strip()
    if not manual:
        print_color("[!] No Steam path provided. Aborting.", Colors.RED)
        return None
    candidate = Path(manual)
    if not candidate.is_dir():
        print_color(f"[ERROR] Not a directory: {candidate}", Colors.RED)
        time.sleep(config.SLEEP_SHORT)
        return None
    if not (candidate / "steamapps").is_dir():
        print_color(f"[ERROR] No steamapps folder inside {candidate} — wrong Steam path?", Colors.RED)
        time.sleep(config.SLEEP_SHORT)
        return None
    return candidate


def _pick_steam_game(query: str) -> SteamStoreItem | None:
    """Search Steam and let the user choose a game."""
    results = search_steam_games(query)
    if not results:
        print_color(f"\n[ERROR] No results found for '{query}'", Colors.RED)
        print_color("[!] Try a different search term", Colors.YELLOW)
        time.sleep(config.SLEEP_LONG)
        return None

    print(f"\n{Colors.BOLD}{Colors.GREEN}Found {len(results)} result(s):{Colors.RESET}\n")
    print(f"{Colors.GRAY}{'─' * 60}{Colors.RESET}")
    for idx, game in enumerate(results, 1):
        print(f"  {Colors.BOLD}{Colors.CYAN}{idx:2d}.{Colors.RESET} {Colors.WHITE}{game['name']}{Colors.RESET}  {Colors.GRAY}(AppID: {game['id']}){Colors.RESET}")
        if idx < len(results):
            print(f"{Colors.GRAY}{'─' * 60}{Colors.RESET}")
    print()

    raw = input(f"{Colors.BOLD}Select [1-{len(results)}]{Colors.RESET} (or 'back'): ").strip()
    if raw.lower() in ('back', 'b', ''):
        return None
    try:
        idx = int(raw)
        if not 1 <= idx <= len(results):
            raise ValueError
    except ValueError:
        print_color("[ERROR] Invalid selection.", Colors.RED)
        time.sleep(config.SLEEP_SHORT)
        return None
    return results[idx - 1]


def _prompt_app_info_manually(appid: int) -> SteamAppInfo:
    """Fallback: ask user to type Steam app info."""
    print_color("[!] Could not fetch app info automatically.", Colors.YELLOW)
    print_color("[*] Enter details manually:", Colors.CYAN)
    name_raw = input(f"  {Colors.BOLD}Game name{Colors.RESET}: ").strip() or f"App {appid}"
    install_raw = input(f"  {Colors.BOLD}Install dir{Colors.RESET} (folder in steamapps/common): ").strip() or f"App{appid}"
    exe_raw = input(f"  {Colors.BOLD}Executable{Colors.RESET} (e.g. Bin/Game.exe): ").strip() or "Game.exe"
    return {
        "name":       sanitize_filename(name_raw),
        "installdir": sanitize_path_segment(install_raw),
        "executable": sanitize_relative_path(exe_raw),
        "depot_id":   None,
    }


def steam_quest_mode(faker: GameFaker) -> None:
    """Steam Quest Mode – generates appmanifest + fake exe for any Steam appid."""
    print_boxed_title("STEAM QUEST MODE", width=55, color=Colors.CYAN)
    print_color("[*] This mode generates a fake Steam appmanifest + exe", Colors.CYAN)
    print_color("[*] Required for games that verify Steam ownership (Marathon, Toxic Commando…)", Colors.GRAY)
    print_color("[*] Search by name — demos and DLCs are separate, pick the right one!", Colors.YELLOW)
    print()

    steam_path = _resolve_steam_path()
    if not steam_path:
        return
    print_color(f"[OK] Steam found at: {steam_path}", Colors.GREEN)

    query = input(f"\n{Colors.BOLD}Search game{Colors.RESET} (or 'back'): ").strip()
    if query.lower() in ('back', 'b', ''):
        return

    game = _pick_steam_game(query)
    if not game:
        return

    appid = int(game["id"])
    print_color(f"\n[OK] Selected: {game['name']} (AppID: {appid})", Colors.GREEN, bold=True)
    info = fetch_steam_app_info(appid) or _prompt_app_info_manually(appid)

    print(f"\n{Colors.BOLD}Detected info:{Colors.RESET}")
    print(f"  Name:        {Colors.CYAN}{info['name']}{Colors.RESET}")
    print(f"  Install dir: {Colors.CYAN}{info['installdir']}{Colors.RESET}")
    print(f"  Executable:  {Colors.CYAN}{info['executable']}{Colors.RESET}")

    override = input(f"\n{Colors.BOLD}Override executable path?{Colors.RESET} [leave empty to keep]: ").strip()
    if override:
        info['executable'] = sanitize_relative_path(override)
    info['installdir'] = sanitize_path_segment(info['installdir'])

    exe_full_path = f"{info['installdir']}/{info['executable']}"
    fake_exe_path = steam_path / "steamapps" / "common" / exe_full_path.replace("/", os.sep)

    print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  AppManifest: {Colors.GRAY}{steam_path / 'steamapps' / f'appmanifest_{appid}.acf'}{Colors.RESET}")
    print(f"  Fake exe:    {Colors.GRAY}{fake_exe_path}{Colors.RESET}")

    if not ask_confirm():
        print_color("\n[!] Operation cancelled.", Colors.YELLOW)
        time.sleep(config.SLEEP_SHORT)
        return

    result = create_steam_fake(faker, appid, info, steam_path)
    if not result:
        return

    print()
    faker.launch_executable(result)
    print_color("\n[OK] Steam Quest setup complete!", Colors.GREEN, bold=True)
    print_color("[!] Discord MUST be running for detection to work.", Colors.YELLOW)
    print_color("[*] Keep the process running until the quest is done.", Colors.CYAN)
    pause()
