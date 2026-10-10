"""Opt-in per-process game mode with reversible Windows priority changes.

No process is killed or suspended. The game itself is not altered. Only explicitly
named non-system background applications are lowered from NORMAL to BELOW_NORMAL.
"""
from __future__ import annotations

import os
import re

NORMAL_PRIORITY = 0x20
BELOW_NORMAL_PRIORITY = 0x4000

PROTECTED = frozenset({
    "system", "system idle process", "registry", "secure system",
    "csrss.exe", "smss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "svchost.exe", "explorer.exe",
    "dwm.exe", "conhost.exe", "taskhostw.exe", "audiodg.exe",
    "sihost.exe", "fontdrvhost.exe", "msmpeng.exe", "securityhealthservice.exe",
    "searchhost.exe", "startmenuexperiencehost.exe", "runtimebroker.exe",
    "smartorganizer.exe", "powershell.exe", "cmd.exe", "tasklist.exe",
})


def parse_names(raw: str | list[str]) -> list[str]:
    """Accept executable base names only, never commands, paths or wildcard patterns."""
    parts = re.split(r"[,;\n]+", raw) if isinstance(raw, str) else raw
    names = []
    for value in parts:
        name = str(value).strip().casefold()
        if not re.fullmatch(r"[\w ()+\-.]{1,80}\.exe", name, flags=re.UNICODE):
            continue
        if name not in names and name not in PROTECTED:
            names.append(name)
    return names


def get_priority(pid: int) -> int | None:
    if os.name != "nt":
        return None
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetPriorityClass.argtypes = [ctypes.c_void_p]
    kernel.GetPriorityClass.restype = ctypes.c_uint32
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, 0, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        return int(kernel.GetPriorityClass(handle)) or None
    finally:
        kernel.CloseHandle(handle)


def set_priority(pid: int, priority: int) -> bool:
    if os.name != "nt" or priority not in {NORMAL_PRIORITY, BELOW_NORMAL_PRIORITY}:
        return False
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.SetPriorityClass.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x0200 | 0x1000, 0, pid)
    if not handle:
        return False
    try:
        return bool(kernel.SetPriorityClass(handle, priority))
    finally:
        kernel.CloseHandle(handle)


class GameModeController:
    """Maintain changes only for user-selected processes, restoring on game exit."""

    def __init__(self) -> None:
        self._lowered: dict[int, tuple[str, int]] = {}

    def tick(
        self, processes: list[dict], games: list[str], background: list[str],
        *, enabled: bool = True, read_priority=get_priority, write_priority=set_priority,
    ) -> dict:
        own_pid = os.getpid()
        names = {str(p.get("name", "")).casefold() for p in processes}
        game_set = set(parse_names(games))
        candidate_set = set(parse_names(background)) - game_set
        active = enabled and bool(names & game_set)
        by_pid = {
            int(p["pid"]): str(p["name"]).casefold()
            for p in processes if isinstance(p.get("pid"), int) and int(p["pid"]) > 0
        }

        restored = 0
        # Restore if the game ended or the process is no longer a configured target.
        for pid, (name, original) in list(self._lowered.items()):
            current_name = by_pid.get(pid)
            if current_name != name:
                self._lowered.pop(pid, None)  # PID exited or was reused; never touch.
                continue
            if active and name in candidate_set:
                continue
            try:
                if read_priority(pid) == BELOW_NORMAL_PRIORITY and write_priority(pid, original):
                    restored += 1
                    self._lowered.pop(pid, None)
                elif read_priority(pid) != BELOW_NORMAL_PRIORITY:
                    self._lowered.pop(pid, None)  # Another program changed it.
            except (OSError, PermissionError):
                pass

        changed = 0
        if active:
            for pid, name in by_pid.items():
                if pid == own_pid or name not in candidate_set or pid in self._lowered:
                    continue
                try:
                    priority = read_priority(pid)
                    if priority == NORMAL_PRIORITY and write_priority(pid, BELOW_NORMAL_PRIORITY):
                        self._lowered[pid] = (name, priority)
                        changed += 1
                except (OSError, PermissionError):
                    continue
        return {"game_active": active, "newly_limited": changed,
                "restored": restored, "limited_now": len(self._lowered)}

    def restore_all(self, *, read_priority=get_priority, write_priority=set_priority) -> int:
        restored = 0
        for pid, (_name, original) in list(self._lowered.items()):
            try:
                if read_priority(pid) == BELOW_NORMAL_PRIORITY and write_priority(pid, original):
                    restored += 1
            except (OSError, PermissionError):
                pass
            self._lowered.pop(pid, None)
        return restored
