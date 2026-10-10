"""Safe opt-in Windows Installer uninstall of explicitly selected MSI packages.

Never runs registry UninstallString (often arbitrary code). Only product GUIDs
with WindowsInstaller=1 are eligible, and Windows Installer displays its own UI.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

GUID = re.compile(
    r"^\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}$"
)
PROTECTED_NAMES = (
    "microsoft visual c++", "microsoft .net", ".net runtime", "windows desktop runtime",
    "microsoft windows", "windows sdk", "intel(r) management engine", "nvidia graphics driver",
    "realtek", "amd chipset", "intel chipset", "directx", "windows driver package",
)


def eligible_msi_items(apps: list[dict]) -> list[dict]:
    """Return only Win32 entries that explicitly advertise MSI with a GUID."""
    result = []
    seen: set[str] = set()
    for item in apps:
        code = str(item.get("registry_key") or "").strip()
        name = str(item.get("name") or "").strip()
        if (not name or not GUID.fullmatch(code)
                or not item.get("windows_installer", False)
                or name.casefold().startswith(PROTECTED_NAMES)):
            continue
        if code.casefold() in seen:
            continue
        seen.add(code.casefold())
        result.append({
            "name": name, "product_code": code.upper(),
            "publisher": str(item.get("publisher") or ""),
            "version": str(item.get("version") or ""),
        })
    return sorted(result, key=lambda x: x["name"].casefold())


def launch_msi_uninstall(product_code: str) -> int:
    """Launch official interactive msiexec /x; caller must confirm in UI first.

    A spawned process is not evidence that the app has been successfully removed.
    No /quiet, no /passive, no shell=True, no elevation bypass.
    """
    if os.name != "nt":
        raise RuntimeError("Удаление Windows Installer доступно только в Windows.")
    code = str(product_code).strip().upper()
    if not GUID.fullmatch(code):
        raise ValueError("Некорректный идентификатор MSI; отменено.")
    system_root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    exe = system_root / "System32" / "msiexec.exe"
    if not exe.is_file():
        raise RuntimeError("Не найден штатный установщик Windows Installer (msiexec.exe).")
    proc = subprocess.Popen([str(exe), "/x", code], shell=False)
    return int(proc.pid)
