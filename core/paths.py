from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Smart-Organizer"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def data_root() -> Path:
    override = os.environ.get("SMART_ORGANIZER_DATA")
    if override:
        return Path(override).expanduser().resolve()
    return app_root() / "data"


def ensure_runtime_dirs() -> dict[str, Path]:
    root = app_root()
    paths = {
        "root": root,
        "data": data_root(),
        "logs": root / "logs",
        "staging": root / ".update-staging",
    }
    for key in ("data", "logs"):
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths
