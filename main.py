from __future__ import annotations

import json
import sys
from pathlib import Path

from core.paths import app_root
from core.updater import apply_source_update, fetch_manifest, update_available


def _local_version() -> str:
    path = app_root() / "version.json"
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("version", "0.0.0"))
    except Exception:
        return "0.0.0"


def _install_tkinter_compat() -> None:
    """Keep older frozen launchers compatible with newer UI modules."""
    try:
        import tkinter.scrolledtext  # noqa: F401
        return
    except ModuleNotFoundError:
        import tkinter as tk

        module = type(sys)("tkinter.scrolledtext")
        module.ScrolledText = tk.Text
        sys.modules["tkinter.scrolledtext"] = module


def _prelaunch_update() -> str:
    """Update program sources before importing the GUI.

    Local data/ and logs/ are protected by core.updater.
    Network/update errors never prevent the program from starting.
    """
    current = _local_version()
    try:
        manifest = fetch_manifest(timeout=6)
        if update_available(current, manifest):
            apply_source_update(app_root(), manifest)
            current = str(manifest.get("version", current))
    except Exception:
        pass
    return current


def main() -> None:
    current_version = _prelaunch_update()
    _install_tkinter_compat()

    import app.main_window as main_window

    main_window.APP_VERSION = current_version
    app = main_window.SmartOrganizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
