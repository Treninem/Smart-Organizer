from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _format_network_speed(bytes_per_second: float) -> str:
    bits = max(0.0, float(bytes_per_second)) * 8.0
    if bits >= 1_000_000_000:
        return f"{bits / 1_000_000_000:.2f} Gbit/s"
    if bits >= 1_000_000:
        return f"{bits / 1_000_000:.1f} Mbit/s"
    if bits >= 1_000:
        return f"{bits / 1_000:.1f} Kbit/s"
    return f"{bits:.0f} bit/s"


def _format_bytes(value: int | float | None) -> str:
    if value is None:
        return "—"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _filetime_to_int(value) -> int:
    return (int(value.dwHighDateTime) << 32) + int(value.dwLowDateTime)


class SystemMonitor:
    """Lightweight Windows monitor using only built-in OS/Python facilities."""

    def __init__(self, disk_path: str = "D:\\"):
        if Path(disk_path).exists():
            self.disk_path = disk_path
        else:
            self.disk_path = str(Path.home().anchor or "C:\\")
        self._last_cpu: tuple[int, int, int] | None = None
        self._last_net: tuple[float, int, int] | None = None

    def _cpu_percent(self) -> float | None:
        if os.name != "nt":
            return None
        idle = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        ok = ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        )
        if not ok:
            return None
        current = (_filetime_to_int(idle), _filetime_to_int(kernel), _filetime_to_int(user))
        if self._last_cpu is None:
            self._last_cpu = current
            return None
        old_idle, old_kernel, old_user = self._last_cpu
        self._last_cpu = current
        idle_delta = current[0] - old_idle
        total_delta = (current[1] - old_kernel) + (current[2] - old_user)
        if total_delta <= 0:
            return None
        busy = 100.0 * (1.0 - idle_delta / total_delta)
        return min(100.0, max(0.0, busy))

    def _memory(self) -> tuple[float | None, int | None, int | None]:
        if os.name != "nt":
            return None, None, None
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None, None, None
        used = int(status.ullTotalPhys - status.ullAvailPhys)
        return float(status.dwMemoryLoad), used, int(status.ullTotalPhys)

    def _disk(self) -> tuple[float | None, int | None]:
        try:
            usage = shutil.disk_usage(self.disk_path)
        except OSError:
            return None, None
        used_percent = 100.0 * (usage.total - usage.free) / usage.total if usage.total else 0.0
        return used_percent, usage.free

    @staticmethod
    def _net_totals() -> tuple[int, int] | None:
        if os.name != "nt":
            return None
        try:
            proc = subprocess.run(
                ["netstat", "-e"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=3,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        # `netstat -e` is localized, so parse the first statistics row with
        # exactly two integer counters instead of depending on the word "Bytes".
        for line in proc.stdout.splitlines():
            numbers = re.findall(r"\d+", line.replace(",", ""))
            if len(numbers) == 2:
                try:
                    return int(numbers[0]), int(numbers[1])
                except ValueError:
                    continue
        return None

    def _network_rates(self) -> tuple[float | None, float | None]:
        totals = self._net_totals()
        now = time.monotonic()
        if totals is None:
            return None, None
        if self._last_net is None:
            self._last_net = (now, totals[0], totals[1])
            return None, None
        old_time, old_recv, old_sent = self._last_net
        self._last_net = (now, totals[0], totals[1])
        elapsed = now - old_time
        if elapsed <= 0:
            return None, None
        return (
            max(0, totals[0] - old_recv) / elapsed,
            max(0, totals[1] - old_sent) / elapsed,
        )

    def sample(self) -> dict:
        cpu = self._cpu_percent()
        memory_percent, memory_used, memory_total = self._memory()
        disk_percent, disk_free = self._disk()
        down, up = self._network_rates()
        return {
            "cpu_percent": cpu,
            "memory_percent": memory_percent,
            "memory_used": memory_used,
            "memory_total": memory_total,
            "disk_percent": disk_percent,
            "disk_free": disk_free,
            "download_bps": down,
            "upload_bps": up,
            "download_text": "—" if down is None else _format_network_speed(down),
            "upload_text": "—" if up is None else _format_network_speed(up),
            "disk_free_text": _format_bytes(disk_free),
        }
