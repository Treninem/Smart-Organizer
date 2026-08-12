"""Stable Windows launcher for Smart Organizer.

The executable produced from this file deliberately runs the external main.py
located next to SmartOrganizer.exe. Most future runtime modules can therefore
update from GitHub without replacing the launcher.
"""
from __future__ import annotations

import ctypes  # noqa: F401
import hashlib  # noqa: F401
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import runpy
import shutil  # noqa: F401
import sqlite3  # noqa: F401
import subprocess  # noqa: F401
import sys
import threading  # noqa: F401
import time  # noqa: F401
import tkinter  # noqa: F401
import urllib.request  # noqa: F401
from ctypes import wintypes  # noqa: F401
from dataclasses import dataclass, field  # noqa: F401
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk  # noqa: F401
from typing import Callable, Iterable  # noqa: F401


def main() -> None:
    root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    sys.path.insert(0, str(root))
    runtime_entry = root / "main.py"
    if not runtime_entry.exists():
        raise FileNotFoundError(f"Не найден файл программы: {runtime_entry}")
    runpy.run_path(str(runtime_entry), run_name="__main__")


if __name__ == "__main__":
    main()
