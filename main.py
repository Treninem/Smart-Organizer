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
    try:
        import tkinter.scrolledtext  # noqa: F401
        return
    except ModuleNotFoundError:
        import tkinter as tk

        module = type(sys)("tkinter.scrolledtext")
        module.ScrolledText = tk.Text
        sys.modules["tkinter.scrolledtext"] = module


def _install_real_windows_folder_resolver(main_window) -> None:
    from core.windows_paths import desktop_path

    def scan_desktop(self) -> None:
        desktop = desktop_path()
        self.status_var.set(f"Рабочий стол Windows: {desktop}")
        self.start_scan(desktop)

    main_window.SmartOrganizerApp.scan_desktop = scan_desktop


def _install_settings_and_close_fixes(main_window) -> None:
    """Make X, Alt+F4, Ctrl+Q and explicit Exit terminate the desktop app.

    Preserve the comprehensive settings provided by core.background_runtime:
    replacing them with a stub hid the real "Полностью выйти" option.
    """
    from tkinter import ttk

    cls = main_window.SmartOrganizerApp
    previous_init = cls.__init__

    def _force_exit_app(self) -> None:
        if getattr(self, "_closing", False):
            return
        self._closing = True
        self._force_real_exit = True
        self._restart_pending = False
        # Stop periodic callbacks before the database/UI are destroyed.
        try:
            self.monitor_stop.set()
        except Exception:
            pass
        for attribute in (
            "_background_after_id",
            "_auto_update_after_id",
            "_update_after_id",
            "_game_poll_after_id",
        ):
            callback = getattr(self, attribute, None)
            if callback:
                try:
                    self.after_cancel(callback)
                except Exception:
                    pass
                try:
                    setattr(self, attribute, None)
                except Exception:
                    pass
        try:
            self.db.close()
        except Exception:
            pass
        try:
            self.quit()
        except Exception:
            pass
        finally:
            try:
                self.destroy()
            except Exception:
                pass

    def on_close(self) -> None:
        self._force_exit_app()

    def __init__(self, *args, **kwargs):
        previous_init(self, *args, **kwargs)
        # Rebind after *all* runtime UI layers have been initialized.
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_all("<Control-q>", lambda _event: self._force_exit_app())

        nav = getattr(self, "_stable_nav_buttons", {})
        if nav:
            sidebar = next(iter(nav.values())).master
            # Visible on every page, including when settings cannot be opened.
            exit_button = ttk.Button(
                sidebar, text="⏻ Полностью выйти",
                style="Nav.TButton", command=self._force_exit_app,
            )
            exit_button.pack(side="bottom", fill="x", pady=(12, 8))
            self._shutdown_exit_button = exit_button

    cls.__init__ = __init__
    cls.on_close = on_close
    cls._force_exit_app = _force_exit_app


def _run_app_self_test(app) -> None:
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
    if hasattr(app, "show_pc_care"):
        screens.append(app.show_pc_care)
    for screen in screens:
        screen()
        app.update_idletasks()
    force_exit = getattr(app, "_force_exit_app", None)
    if callable(force_exit):
        force_exit()
    else:
        app.on_close()


def main() -> None:
    current_version = _local_version()
    _install_tkinter_compat()

    import app.main_window as main_window

    main_window.APP_VERSION = current_version
    _install_real_windows_folder_resolver(main_window)
    startup_warnings: list[str] = []

    installers = [
        ("core.auto_update_runtime", "install_auto_update_runtime", "автообновление runtime"),
        ("core.modern_ui_runtime", "install_modern_ui_runtime", "современный интерфейс"),
        ("core.ui_runtime", "install_ui_runtime", "расширения интерфейса"),
        ("core.diagnostics_ui_runtime", "install_diagnostics_ui_runtime", "диагностика"),
        ("core.full_features_runtime", "install_full_features_runtime", "дополнительный анализ"),
        ("core.stable_workflow_runtime", "install_stable_workflow_runtime", "стабильный сценарий"),
        ("core.safe_layout_runtime", "install_safe_layout_runtime", "защита пользовательской компоновки"),
        ("core.maximum_safety_runtime", "install_maximum_safety_runtime", "усиленная компоновка"),
        ("core.generic_compaction_runtime", "install_generic_compaction_runtime", "обучение контейнерам проектов"),
        ("core.final_safety_runtime", "install_final_safety_runtime", "финальный контроль плана"),
        ("core.adaptive_feedback_runtime", "install_adaptive_feedback_runtime", "локальное обучение и Undo"),
        ("core.background_runtime", "install_background_runtime", "фон, автозапуск и умная сортировка загрузок"),
    ]
    for module_name, function_name, label in installers:
        try:
            module = __import__(module_name, fromlist=[function_name])
            getattr(module, function_name)(main_window)
        except Exception as exc:
            startup_warnings.append(f"{label}: {exc}")

    # Apply the final UI/shutdown patch after all runtime installers so that
    # later modules cannot overwrite the fixed handlers.
    _install_settings_and_close_fixes(main_window)

    # PC-care wraps the final exit handler and adds a screen to the real sidebar.
    try:
        from core.pc_care_runtime import install_pc_care_runtime
        install_pc_care_runtime(main_window)
    except Exception as exc:
        startup_warnings.append(f"оптимизация ПК: {exc}")

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
