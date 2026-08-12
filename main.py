from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

from core.paths import app_root
from core.updater import apply_source_update, fetch_manifest, update_available

RELEASE_API = "https://api.github.com/repos/Treninem/Smart-Organizer/releases/tags/auto-latest"
LAUNCHER_ASSET = "SmartOrganizer.exe"


def _local_version() -> str:
    path = app_root() / "version.json"
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("version", "0.0.0"))
    except Exception:
        return "0.0.0"


def _install_tkinter_compat() -> None:
    """Keep older frozen launchers compatible with newer UI modules."""
    try:
        import tkinter.scrolledtext  # noqa: F401
        return
    except ModuleNotFoundError:
        import tkinter as tk

        module = type(sys)("tkinter.scrolledtext")
        module.ScrolledText = tk.Text
        sys.modules["tkinter.scrolledtext"] = module


def _prelaunch_update() -> str:
    """Update program sources before importing the GUI."""
    current = _local_version()
    try:
        manifest = fetch_manifest(timeout=6)
        if update_available(current, manifest):
            apply_source_update(app_root(), manifest)
            current = str(manifest.get("version", current))
    except Exception:
        pass
    return current


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch_release_asset() -> dict | None:
    try:
        req = urllib.request.Request(RELEASE_API, headers={"User-Agent": "Smart-Organizer-Launcher"})
        with urllib.request.urlopen(req, timeout=8) as response:
            release = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    for asset in release.get("assets", []):
        if asset.get("name") == LAUNCHER_ASSET:
            return asset
    return None


def _launcher_state_path() -> Path:
    path = app_root() / "data" / "launcher_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _launcher_is_current(asset: dict) -> bool:
    try:
        state = json.loads(_launcher_state_path().read_text(encoding="utf-8"))
    except Exception:
        return False
    digest = asset.get("digest")
    if digest:
        return state.get("digest") == digest
    return state.get("asset_id") == asset.get("id")


def _schedule_launcher_update(asset: dict) -> bool:
    """Download a new EXE and let cmd replace the running launcher after exit."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    if _launcher_is_current(asset):
        return False

    root = app_root()
    new_exe = root / "SmartOrganizer.new.exe"
    current_exe = root / "SmartOrganizer.exe"
    script = root / ".apply-launcher-update.cmd"
    url = asset.get("browser_download_url")
    if not url:
        return False

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Smart-Organizer-Launcher"})
        with urllib.request.urlopen(req, timeout=45) as response, new_exe.open("wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)

        digest = str(asset.get("digest") or "")
        if digest.startswith("sha256:"):
            expected = digest.split(":", 1)[1].lower()
            if _sha256(new_exe).lower() != expected:
                new_exe.unlink(missing_ok=True)
                return False

        state = {
            "digest": asset.get("digest"),
            "asset_id": asset.get("id"),
            "updated_from": "auto-latest",
        }
        state_json = json.dumps(state, ensure_ascii=True, separators=(",", ":"))
        lines = [
            "@echo off",
            "setlocal",
            ":retry",
            "timeout /t 1 /nobreak >nul",
            f'move /y "{new_exe}" "{current_exe}" >nul 2>&1',
            "if errorlevel 1 goto retry",
            f'echo {state_json}>"{_launcher_state_path()}"',
            f'start "" "{current_exe}"',
            'del "%~f0"',
        ]
        script.write_text("\r\n".join(lines) + "\r\n", encoding="ascii")
        os.startfile(str(script))
        return True
    except Exception:
        try:
            new_exe.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def main() -> None:
    current_version = _prelaunch_update()

    asset = _fetch_release_asset()
    if asset and _schedule_launcher_update(asset):
        return

    _install_tkinter_compat()

    import app.main_window as main_window

    main_window.APP_VERSION = current_version
    app = main_window.SmartOrganizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
