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


def _run_app_self_test(app) -> None:
    """Construct every major screen without entering the interactive event loop."""
    screens = [
        app.show_home,
        app.show_files,
        app.show_projects,
        app.show_memory,
        app.show_github,
        app.show_archives,
        app.show_settings,
    ]
    if hasattr(app, "show_diagnostics"):
        screens.append(app.show_diagnostics)
    for screen in screens:
        screen()
        app.update_idletasks()
    app.on_close()


def main() -> None:
    # Startup must never wait for the internet and must remain repairable even
    # when an old frozen launcher is temporarily missing a newer stdlib module.
    current_version = _local_version()
    _install_tkinter_compat()

    import app.main_window as main_window

    main_window.APP_VERSION = current_version
    _install_real_windows_folder_resolver(main_window)
    startup_warnings: list[str] = []

    try:
        from core.auto_update_runtime import install_auto_update_runtime

        install_auto_update_runtime(main_window)
    except Exception as exc:
        # The legacy base window still contains the source updater. Keeping the
        # application open lets that recovery path repair a partial migration.
        startup_warnings.append(f"автообновление runtime: {exc}")

    try:
        from core.modern_ui_runtime import install_modern_ui_runtime

        install_modern_ui_runtime(main_window)
    except Exception as exc:
        startup_warnings.append(f"современный интерфейс: {exc}")

    try:
        from core.ui_runtime import install_ui_runtime

        install_ui_runtime(main_window)
    except Exception as exc:
        # UI extensions are deliberately optional during a legacy migration.
        # A missing bundled module must not brick the updater or the base app.
        startup_warnings.append(f"расширения интерфейса: {exc}")

    try:
        from core.diagnostics_ui_runtime import install_diagnostics_ui_runtime

        install_diagnostics_ui_runtime(main_window)
    except Exception as exc:
        startup_warnings.append(f"диагностика: {exc}")

    try:
        from core.full_features_runtime import install_full_features_runtime

        install_full_features_runtime(main_window)
    except Exception as exc:
        startup_warnings.append(f"дополнительный анализ: {exc}")

    app = main_window.SmartOrganizerApp()
    if startup_warnings:
        app.status_var.set(
            "Запущен режим совместимости. Smart Organizer продолжит восстановление runtime; "
            + " | ".join(startup_warnings[:2])
        )
        try:
            app.db.log_action("startup-compatibility", None, "warning", " | ".join(startup_warnings))
        except Exception:
            pass

    if "--app-self-test" in sys.argv:
        _run_app_self_test(app)
        return

    app.mainloop()


if __name__ == "__main__":
    main()
