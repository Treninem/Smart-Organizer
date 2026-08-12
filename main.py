from __future__ import annotations

import json
import sys

from core.paths import app_root


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


def _install_real_windows_folder_resolver(main_window) -> None:
    """Make UI shortcuts use actual Windows Known Folder locations."""
    from core.windows_paths import desktop_path

    def scan_desktop(self) -> None:
        desktop = desktop_path()
        self.status_var.set(f"Рабочий стол Windows: {desktop}")
        self.start_scan(desktop)

    main_window.SmartOrganizerApp.scan_desktop = scan_desktop


def main() -> None:
    # Startup must never wait for the internet. The window is created first;
    # periodic update checks start in the background from the UI runtime.
    current_version = _local_version()
    _install_tkinter_compat()

    import app.main_window as main_window
    from core.auto_update_runtime import install_auto_update_runtime

    main_window.APP_VERSION = current_version
    _install_real_windows_folder_resolver(main_window)
    install_auto_update_runtime(main_window)

    app = main_window.SmartOrganizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
