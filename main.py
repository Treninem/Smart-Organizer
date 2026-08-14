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
