from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import urllib.request
from pathlib import Path

from core.paths import app_root

RELEASE_API = "https://api.github.com/repos/Treninem/Smart-Organizer/releases/tags/auto-latest"
LAUNCHER_ASSET = "SmartOrganizer.exe"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch_launcher_asset(timeout: int = 8) -> dict | None:
    req = urllib.request.Request(RELEASE_API, headers={"User-Agent": "Smart-Organizer-Launcher"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        release = json.loads(response.read().decode("utf-8"))
    for asset in release.get("assets", []):
        if asset.get("name") == LAUNCHER_ASSET:
            return asset
    return None


def _download_launcher(asset: dict) -> Path | None:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return None
    current_exe = Path(sys.executable).resolve()
    digest = str(asset.get("digest") or "")
    if digest.startswith("sha256:"):
        expected = digest.split(":", 1)[1].lower()
        try:
            if _sha256(current_exe).lower() == expected:
                return None
        except OSError:
            pass
    else:
        expected = ""

    url = asset.get("browser_download_url")
    if not url:
        return None

    new_exe = app_root() / "SmartOrganizer.new.exe"
    req = urllib.request.Request(url, headers={"User-Agent": "Smart-Organizer-Launcher"})
    with urllib.request.urlopen(req, timeout=45) as response, new_exe.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

    if expected and _sha256(new_exe).lower() != expected:
        new_exe.unlink(missing_ok=True)
        raise RuntimeError("Launcher SHA-256 verification failed")
    return new_exe


def start_launcher_update_check(app) -> None:
    """Check the frozen launcher in background, never on the startup path."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    if getattr(app, "_launcher_update_thread", None):
        thread = app._launcher_update_thread
        if thread and thread.is_alive():
            return

    def worker() -> None:
        try:
            asset = _fetch_launcher_asset()
            if not asset:
                return
            new_exe = _download_launcher(asset)
            if new_exe is None:
                return

            def ready() -> None:
                try:
                    app.db.log_action("launcher-update", str(new_exe), "ok", "verified launcher ready")
                except Exception:
                    pass
                app._restart_pending = True
                app.status_var.set("Обновление ядра программы готово. Автоматический перезапуск после завершения работы…")
                app.after(300, app._restart_when_idle)

            app.after(0, ready)
        except Exception as exc:
            try:
                app.db.log_action("launcher-update", None, "error", str(exc))
            except Exception:
                pass

    app._launcher_update_thread = threading.Thread(target=worker, daemon=True)
    app._launcher_update_thread.start()
