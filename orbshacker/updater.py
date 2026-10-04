"""
updater.py – Auto-update from GitHub Releases.

Only runs when the app is a compiled executable (sys.frozen).
Compares the current VERSION against the latest GitHub Release tag.
If a newer version exists, downloads the .exe asset, verifies its SHA-256
against the published SHA256SUMS asset, and replaces itself.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

import requests
from packaging.version import InvalidVersion, Version

from . import config, ui
from .janitor import spawn_self_destruct


class ReleaseAsset(TypedDict):
    name: str
    browser_download_url: str


class GitHubRelease(TypedDict, total=False):
    tag_name: str
    assets: list[ReleaseAsset]


class ChecksumError(Exception):
    """Downloaded asset failed SHA-256 verification."""


def _cleanup_old_exe(old_exe: Path) -> None:
    """Delete a leftover backup executable if it exists."""
    if old_exe.exists():
        try:
            old_exe.unlink()
        except Exception:
            pass


def _schedule_delete(path: Path) -> None:
    """Delete a file shortly after the updater restarts the app (bounded retries)."""
    if not path.exists():
        return
    spawn_self_destruct([path], [], max_attempts=15)


def is_frozen() -> bool:
    """Return True if running as a compiled executable (e.g. PyInstaller)."""
    return getattr(sys, 'frozen', False)


def _parse_version(tag: str) -> Version:
    """Parse a version tag like 'v2.1.0' or '2.1.0' into a Version object."""
    return Version(tag.lstrip('v'))


def _get_latest_release() -> GitHubRelease | None:
    """Fetch the latest release info from the GitHub API."""
    url = f"https://api.github.com/repos/{config.GITHUB_REPO_OWNER}/{config.GITHUB_REPO_NAME}/releases/latest"
    try:
        resp = requests.get(url, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _find_exe_asset(assets: list[ReleaseAsset]) -> ReleaseAsset | None:
    """Find the .exe download asset from a release."""
    for asset in assets:
        name = asset.get('name', '')
        if name.lower().endswith('.exe'):
            return asset
    return None


def _find_checksum_asset(assets: list[ReleaseAsset]) -> ReleaseAsset | None:
    """Find the SHA256SUMS asset from a release."""
    for asset in assets:
        if asset.get('name', '').upper() == 'SHA256SUMS':
            return asset
    return None


def parse_sha256sums(text: str) -> dict[str, str]:
    """Parse a SHA256SUMS file body into {filename: hex digest}."""
    sums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 64:
            sums[parts[-1].lstrip("*")] = parts[0].lower()
    return sums


def _download_file(url: str, dest: Path) -> None:
    """Download a file from url to dest path."""
    resp = requests.get(url, stream=True, timeout=config.REQUEST_TIMEOUT_LONG)
    resp.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in resp.iter_content(8192):
            if chunk:
                f.write(chunk)


def _download_text(url: str) -> str:
    resp = requests.get(url, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _verify_sha256(path: Path, asset_name: str, sums: dict[str, str]) -> None:
    expected = sums.get(asset_name)
    if not expected:
        raise ChecksumError(f"no checksum entry for {asset_name} in SHA256SUMS")
    actual = _sha256(path)
    if actual != expected:
        raise ChecksumError(f"SHA-256 mismatch for {asset_name}: expected {expected}, got {actual}")


def _replace_exe(new_exe: Path) -> None:
    """Replace the currently running .exe with the new one.

    On Windows we can't overwrite a running file, so we:
    1. Rename current exe to .old
    2. Move new exe into place
    3. Launch new exe
    4. Exit current process
    """
    current_exe = Path(sys.executable)
    old_exe = current_exe.with_suffix('.old')

    if old_exe.exists():
        try:
            os.remove(old_exe)
        except Exception:
            pass

    try:
        os.rename(current_exe, old_exe)
        new_exe.rename(current_exe)
        ui.print_color("[UPDATE] Updated to new version!", ui.Colors.GREEN, bold=True)
        ui.print_color("[UPDATE] Restarting...", ui.Colors.CYAN)

        os.startfile(str(current_exe))
        _schedule_delete(old_exe)
        sys.exit(0)
    except Exception as e:
        if old_exe.exists() and not current_exe.exists():
            os.rename(old_exe, current_exe)
        ui.print_color(f"[UPDATE] Failed to apply update: {e}", ui.Colors.RED)


def auto_update() -> None:
    """Check for updates and auto-update if a new release is available.

    Only runs when the app is a compiled executable.
    Skips silently when running from source.
    """
    if not is_frozen():
        return

    _cleanup_old_exe(Path(sys.executable).with_suffix('.old'))

    try:
        ui.loading_animation("Checking for updates", 0.5)
    except Exception:
        pass

    release = _get_latest_release()
    if not release:
        return

    tag = release.get('tag_name', '')
    try:
        remote_version = _parse_version(tag)
        local_version = _parse_version(config.VERSION)
    except InvalidVersion:
        return

    if remote_version <= local_version:
        ui.print_color(f"[UPDATE] You're up to date (v{config.VERSION})", ui.Colors.CYAN)
        return

    assets = release.get('assets', [])
    asset = _find_exe_asset(assets)
    if not asset:
        ui.print_color(f"[UPDATE] v{tag} available but no .exe found in release", ui.Colors.YELLOW)
        ui.print_color(f"[UPDATE] Download manually: {config.REPO_URL}/releases/latest", ui.Colors.GRAY)
        return

    sums_asset = _find_checksum_asset(assets)
    if not sums_asset:
        ui.print_color("[UPDATE] No SHA256SUMS in release — refusing unverified update", ui.Colors.YELLOW)
        ui.print_color(f"[UPDATE] Download manually: {config.REPO_URL}/releases/latest", ui.Colors.GRAY)
        return

    ui.print_color(f"[UPDATE] New version available: {config.VERSION} → {tag}", ui.Colors.GREEN, bold=True)
    try:
        ui.loading_animation(f"Downloading {asset['name']}", 0.5)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.exe') as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            sums = parse_sha256sums(_download_text(sums_asset['browser_download_url']))
            _download_file(asset['browser_download_url'], tmp_path)
            _verify_sha256(tmp_path, asset['name'], sums)
            _replace_exe(tmp_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
    except ChecksumError as e:
        ui.print_color(f"[UPDATE] Verification failed: {e}", ui.Colors.RED)
        ui.print_color("[UPDATE] Update aborted — download manually from GitHub", ui.Colors.YELLOW)
    except Exception as e:
        ui.print_color(f"[UPDATE] Download failed: {e}", ui.Colors.YELLOW)
        ui.print_color(f"[UPDATE] Download manually: {config.REPO_URL}/releases/latest", ui.Colors.GRAY)


def _sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()
