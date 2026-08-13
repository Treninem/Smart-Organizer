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
import uuid  # noqa: F401
from ctypes import wintypes  # noqa: F401
from dataclasses import dataclass, field  # noqa: F401
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk  # noqa: F401
from typing import Callable, Iterable  # noqa: F401


def _root() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def _self_test(root: Path) -> int:
    """Verify both bundled stdlib pieces and staged external runtime imports."""
    import ctypes as _ctypes_test  # noqa: F401
    import tkinter.scrolledtext as _scrolledtext_test  # noqa: F401
    import urllib.request as _urllib_test  # noqa: F401
    import uuid as _uuid_test  # noqa: F401

    if (root / "core").is_dir():
        from core import diagnostics as _diagnostics_test  # noqa: F401
        from core import diagnostics_ui_runtime as _diagnostics_ui_test  # noqa: F401
        from core import duplicate_insights as _duplicate_insights_test  # noqa: F401
        from core import folder_tree as _folder_tree_test  # noqa: F401
        from core import full_features_runtime as _full_features_test  # noqa: F401
        from core import layout_memory as _layout_memory_test  # noqa: F401
        from core import local_ai as _local_ai_test  # noqa: F401
        from core import modern_ui_runtime as _modern_ui_test  # noqa: F401
        from core import operation_executor as _operation_executor_test  # noqa: F401
        from core import operation_journal as _operation_journal_test  # noqa: F401
        from core import safe_layout_runtime as _safe_layout_test  # noqa: F401
        from core import stable_workflow_runtime as _stable_workflow_test  # noqa: F401
        from core import ui_runtime as _ui_runtime_test  # noqa: F401

    return 0


def main() -> None:
    root = _root()
    sys.path.insert(0, str(root))

    if "--self-test" in sys.argv:
        raise SystemExit(_self_test(root))

    runtime_entry = root / "main.py"
    if not runtime_entry.exists():
        raise FileNotFoundError(f"Не найден файл программы: {runtime_entry}")
    runpy.run_path(str(runtime_entry), run_name="__main__")


if __name__ == "__main__":
    main()
