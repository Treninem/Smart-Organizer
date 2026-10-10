"""Read-only Windows PC inventory and explicit Microsoft Defender scan entry point.

No registry modifications, uninstall commands, or threat verdicts are issued here.
"""
from __future__ import annotations

import csv
import os
import re
import subprocess
from pathlib import Path

UNINSTALL_ROOT = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
STARTUP_ROOT = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"


def _registry_views():
    import winreg

    views = [0]
    if hasattr(winreg, "KEY_WOW64_64KEY"):
        views = [winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY]
    for hive, label in ((winreg.HKEY_CURRENT_USER, "Пользователь"),
                        (winreg.HKEY_LOCAL_MACHINE, "Компьютер")):
        for view in views:
            yield hive, label, view


def _get_value(key, name, default=""):
    import winreg

    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return default


def installed_applications() -> list[dict]:
    """Inventory registered uninstall entries, without judging malware by publisher/name."""
    if os.name != "nt":
        return []
    import winreg

    result: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for hive, scope, view in _registry_views():
        try:
            root = winreg.OpenKey(hive, UNINSTALL_ROOT, 0, winreg.KEY_READ | view)
        except OSError:
            continue
        with root:
            index = 0
            while True:
                try:
                    key_name = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                try:
                    key = winreg.OpenKey(root, key_name)
                except OSError:
                    continue
                with key:
                    name = str(_get_value(key, "DisplayName")).strip()
                    if not name or int(_get_value(key, "SystemComponent", 0) or 0) == 1:
                        continue
                    if _get_value(key, "ParentKeyName"):
                        continue
                    publisher = str(_get_value(key, "Publisher")).strip()
                    version = str(_get_value(key, "DisplayVersion")).strip()
                    signature = (scope, name.casefold(), version.casefold())
                    if signature in seen:
                        continue
                    seen.add(signature)
                    result.append({
                        "name": name,
                        "version": version,
                        "publisher": publisher,
                        "installed": str(_get_value(key, "InstallDate")).strip(),
                        "scope": scope,
                        "registry_key": key_name,
                        "windows_installer": _get_value(key, "WindowsInstaller", 0) == 1,
                        "review": not bool(publisher),
                    })
    return sorted(result, key=lambda item: item["name"].casefold())


def startup_entries() -> list[dict]:
    """Read Run registry keys and Startup shortcut locations; do not disable anything."""
    if os.name != "nt":
        return []
    import winreg

    items = []
    seen: set[tuple[str, str]] = set()
    for hive, scope, view in _registry_views():
        try:
            key = winreg.OpenKey(hive, STARTUP_ROOT, 0, winreg.KEY_READ | view)
        except OSError:
            continue
        with key:
            index = 0
            while True:
                try:
                    name, command, _kind = winreg.EnumValue(key, index)
                except OSError:
                    break
                index += 1
                token = (scope, name.casefold())
                if token in seen:
                    continue
                seen.add(token)
                items.append({"name": name, "source": "Реестр: " + scope,
                              "command": str(command)})
    for env, suffix, scope in (
        ("APPDATA", r"Microsoft\Windows\Start Menu\Programs\Startup", "Пользователь"),
        ("PROGRAMDATA", r"Microsoft\Windows\Start Menu\Programs\Startup", "Компьютер"),
    ):
        base = os.environ.get(env)
        if not base:
            continue
        folder = Path(base) / suffix
        try:
            entries = list(folder.iterdir())
        except OSError:
            continue
        for path in entries:
            if path.is_file():
                items.append({"name": path.name, "source": "Папка автозагрузки: " + scope,
                              "command": str(path)})
    return sorted(items, key=lambda item: item["name"].casefold())


def running_processes() -> list[dict]:
    """One-shot lightweight tasklist inventory. Nothing is terminated or suspended."""
    if os.name != "nt":
        return []
    result = subprocess.run(
        ["tasklist.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, errors="replace", timeout=8,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("tasklist.exe: " + (result.stderr or "не удалось получить процессы")[:300])
    processes = []
    for columns in csv.reader(result.stdout.splitlines()):
        if len(columns) < 2:
            continue
        try:
            pid = int(columns[1].replace(",", "").strip())
        except ValueError:
            continue
        memory = columns[4] if len(columns) > 4 else ""
        # tasklist formats memory using localized separators: digits are enough for sorting.
        memory_kib = int("".join(re.findall(r"\d+", memory)) or 0)
        processes.append({"name": columns[0].strip(), "pid": pid,
                          "memory": memory, "memory_kib": memory_kib})
    return sorted(processes, key=lambda item: item["memory_kib"], reverse=True)


def open_installed_apps() -> None:
    """Open Windows' own uninstall UI; never execute a registry UninstallString."""
    if os.name != "nt":
        raise RuntimeError("Управление установленными приложениями доступно только в Windows.")
    try:
        os.startfile("ms-settings:appsfeatures")
    except OSError:
        subprocess.Popen(["control.exe", "appwiz.cpl"])


def open_windows_security() -> None:
    if os.name != "nt":
        raise RuntimeError("Безопасность Windows доступна только в Windows.")
    os.startfile("windowsdefender:")


def start_defender_quick_scan() -> None:
    """Request an explicit on-demand QuickScan, leaving all removals to Windows Security."""
    if os.name != "nt":
        raise RuntimeError("Microsoft Defender доступен только в Windows.")
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
         "Start-MpScan -ScanType QuickScan"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
