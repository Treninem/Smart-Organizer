"""Stable Windows launcher for Smart Organizer.

The executable runs external runtime modules next to SmartOrganizer.exe so
features can update without replacing the launcher every stage.
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


def _root() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def _self_test() -> int:
    import ctypes as _ctypes_test  # noqa: F401
    import tkinter.scrolledtext as _scrolledtext_test  # noqa: F401
    import urllib.request as _urllib_test  # noqa: F401
    print("SmartOrganizer frozen runtime self-test: OK")
    return 0


def main() -> None:
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())

    root = _root()
    sys.path.insert(0, str(root))
    runtime_entry = root / "main.py"
    if not runtime_entry.exists():
        raise FileNotFoundError(f"Не найден файл программы: {runtime_entry}")
    runpy.run_path(str(runtime_entry), run_name="__main__")


if __name__ == "__main__":
    main()
