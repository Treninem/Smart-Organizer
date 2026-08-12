from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

_USER_SHELL_FOLDERS = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
_REGISTRY_VALUES = {
    "desktop": "Desktop",
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "documents": "Personal",
}
_FALLBACK_NAMES = {
    "desktop": "Desktop",
    "downloads": "Downloads",
    "documents": "Documents",
}


def _from_registry(name: str) -> Path | None:
    """Resolve redirected Windows user folders without ctypes."""
    if os.name != "nt":
        return None
    value_name = _REGISTRY_VALUES.get(name.lower())
    if not value_name:
        return None
    try:
        proc = subprocess.run(
            ["reg.exe", "query", _USER_SHELL_FOLDERS, "/v", value_name],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        if value_name.lower() not in line.lower():
            continue
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=2)
        if len(parts) < 3:
            continue
        raw = parts[2].strip()
        if raw:
            return Path(os.path.expandvars(raw))
    return None


def _from_powershell(name: str) -> Path | None:
    if os.name != "nt":
        return None
    special = {"desktop": "DesktopDirectory", "documents": "MyDocuments"}.get(name.lower())
    if special is None:
        return None
    command = f"[Environment]::GetFolderPath('{special}')"
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None
    value = proc.stdout.strip()
    return Path(value) if proc.returncode == 0 and value else None


def known_folder(name: str) -> Path:
    """Return the actual Windows user-folder path, including redirections."""
    key = name.lower()
    for resolver in (_from_registry, _from_powershell):
        try:
            resolved = resolver(key)
        except Exception:
            resolved = None
        if resolved is not None:
            return resolved
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    return home / _FALLBACK_NAMES.get(key, name)


def desktop_path() -> Path:
    return known_folder("desktop")


def downloads_path() -> Path:
    return known_folder("downloads")


def documents_path() -> Path:
    return known_folder("documents")
