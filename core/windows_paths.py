from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

# Windows Known Folder IDs. Using the Shell API means redirected folders
# (for example Desktop moved from C: to D:) resolve to their real location.
_FOLDER_IDS = {
    "desktop": (0xB4BFCC3A, 0xDB2C, 0x424C, (0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41)),
    "downloads": (0x374DE290, 0x123F, 0x4565, (0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B)),
    "documents": (0xFDD39AD0, 0x238F, 0x46AF, (0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7)),
}


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(parts: tuple[int, int, int, tuple[int, ...]]) -> _GUID:
    d1, d2, d3, d4 = parts
    return _GUID(d1, d2, d3, (ctypes.c_ubyte * 8)(*d4))


def _known_folder_from_shell(name: str) -> Path | None:
    if os.name != "nt":
        return None
    parts = _FOLDER_IDS.get(name.lower())
    if parts is None:
        raise KeyError(f"Unknown Windows folder: {name}")

    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(_GUID),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long

    value = ctypes.c_wchar_p()
    folder_id = _guid(parts)
    result = shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(value))
    if result != 0 or not value.value:
        return None

    try:
        return Path(value.value)
    finally:
        ole32.CoTaskMemFree(value)


def known_folder(name: str) -> Path:
    """Return the real Windows location of a known user folder.

    Redirected locations are respected. On non-Windows systems or if the Shell
    API is unavailable, a conservative user-profile fallback is used.
    """
    key = name.lower()
    try:
        resolved = _known_folder_from_shell(key)
        if resolved is not None:
            return resolved
    except Exception:
        pass

    home = Path(os.environ.get("USERPROFILE") or Path.home())
    fallback_names = {
        "desktop": "Desktop",
        "downloads": "Downloads",
        "documents": "Documents",
    }
    return home / fallback_names.get(key, name)


def desktop_path() -> Path:
    return known_folder("desktop")


def downloads_path() -> Path:
    return known_folder("downloads")


def documents_path() -> Path:
    return known_folder("documents")
