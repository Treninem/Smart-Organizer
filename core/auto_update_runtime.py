from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from core.paths import app_root
from core.runtime_update import (
    create_apply_script,
    download_runtime_bundle,
    fetch_runtime_manifest,
    fetch_runtime_release,
    find_runtime_asset,
    launch_apply_script,
    runtime_update_needed,
)

DEFAULT_UPDATE_INTERVAL_MINUTES = 60
MIN_UPDATE_INTERVAL_MINUTES = 1


def normalize_interval_minutes(value, default: int = DEFAULT_UPDATE_INTERVAL_MINUTES) -> int:
    try:
        minutes = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(MIN_UPDATE_INTERVAL_MINUTES, minutes)


def _worker_active(app) -> bool:
    worker = getattr(app, "worker", None)
    return bool(worker and worker.is_alive())


def install_auto_update_runtime(main_window) -> None:
    """Install periodic full-runtime updates and automatic idle restart.

    v0.2.7+ updates the complete Windows runtime as one verified ZIP. This keeps
    SmartOrganizer.exe, its PyInstaller runtime and Python modules in sync and
    avoids one-file _MEI temporary-directory failures.
    """
    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_auto_update_runtime_installed", False):
        return
    cls._auto_update_runtime_installed = True

    original_init = cls.__init__
    original_show_settings = cls.show_settings

    def _schedule_next_update(self, delay_minutes: int | None = None) -> None:
        after_id = getattr(self, "_auto_update_after_id", None)
        if after_id:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
            self._auto_update_after_id = None
        if not getattr(self, "auto_update_enabled", True):
            return
        minutes = normalize_interval_minutes(
            delay_minutes if delay_minutes is not None
            else getattr(self, "auto_update_interval_minutes", DEFAULT_UPDATE_INTERVAL_MINUTES)
        )
        self._auto_update_after_id = self.after(minutes * 60_000, self.check_updates_silent)

    def _restart_application(self) -> None:
        if getattr(self, "_restart_started", False):
            return
        self._restart_started = True
        root = app_root()
        try:
            runtime_zip = getattr(self, "_pending_runtime_zip", None)
            if getattr(sys, "frozen", False) and runtime_zip:
                script = create_apply_script(root, runtime_zip, os.getpid())
                launch_apply_script(script)
            elif getattr(sys, "frozen", False):
                env = os.environ.copy()
                env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
                env.pop("_PYI_APPLICATION_HOME_DIR", None)
                subprocess.Popen([sys.executable], cwd=str(root), env=env)
            else:
                subprocess.Popen([sys.executable, str(root / "main.py")], cwd=str(root))
            try:
                self.db.log_action("restart-after-update", None, "ok", "automatic idle restart")
            except Exception:
                pass
        except Exception as exc:
            self._restart_started = False
            self.status_var.set(f"Обновление готово, но автоперезапуск не удался: {exc}")
            return

        try:
            self.monitor_stop.set()
        except Exception:
            pass
        try:
            self.db.close()
        except Exception:
            pass
        self.destroy()

    def _restart_when_idle(self) -> None:
        if not getattr(self, "_restart_pending", False):
            return
        if _worker_active(self):
            self.status_var.set(
                "Обновление скачано. Перезапуск будет выполнен автоматически после завершения текущей операции."
            )
            self.after(1000, self._restart_when_idle)
            return
        self.status_var.set("Обновление готово. Smart Organizer перезапускается автоматически…")
        self.after(250, self._restart_application)

    def _finish_update_check(self, result: dict, manual: bool) -> None:
        self._update_thread = None
        if result.get("updated"):
            version = str(result.get("version", "?"))
            self._pending_runtime_zip = result.get("runtime_zip")
            self.db.log_action("runtime-update", version, "ok", "verified runtime bundle ready; auto_restart=1")
            self._restart_pending = True
            self.status_var.set(f"Обновление {version} проверено и скачано. Подготовка автоматического перезапуска…")
            self.after(300, self._restart_when_idle)
            return

        if result.get("error"):
            self.db.log_action("runtime-update", None, "error", str(result["error"]))
            if manual:
                messagebox.showwarning("Обновления", f"Не удалось проверить GitHub:\n{result['error']}")
            self.status_var.set("Не удалось проверить обновления.")
        elif manual:
            self.status_var.set("Установлена актуальная версия.")
            messagebox.showinfo("Обновления", "Установлена актуальная версия.")
        self._schedule_next_update()

    def _start_update_check(self, manual: bool = False) -> None:
        update_thread = getattr(self, "_update_thread", None)
        if update_thread and update_thread.is_alive():
            if manual:
                self.status_var.set("Проверка обновлений уже выполняется.")
            return
        if not manual and _worker_active(self):
            self._schedule_next_update(1)
            return
        if manual:
            self.status_var.set("Проверяю обновление Smart Organizer…")

        def run() -> None:
            result = {"updated": False}
            try:
                root = app_root()
                manifest = fetch_runtime_manifest()
                release = fetch_runtime_release()
                if runtime_update_needed(root, main_window.APP_VERSION, manifest, release):
                    asset = find_runtime_asset(release)
                    if not asset:
                        raise RuntimeError("Готовый Windows runtime-пакет обновления ещё не опубликован")
                    runtime_zip = download_runtime_bundle(root, asset)
                    result.update(
                        updated=True,
                        version=str(manifest.get("version", "?")),
                        runtime_zip=runtime_zip,
                    )
            except Exception as exc:
                result["error"] = str(exc)
            try:
                self.after(0, lambda: self._finish_update_check(result, manual))
            except Exception:
                pass

        self._update_thread = threading.Thread(target=run, daemon=True)
        self._update_thread.start()

    def check_updates_silent(self) -> None:
        if not getattr(self, "auto_update_enabled", True):
            return
        self._start_update_check(False)

    def check_updates_manual(self) -> None:
        self._start_update_check(True)

    def _save_auto_update_settings(self) -> None:
        enabled = bool(self._auto_update_enabled_var.get())
        raw_interval = self._auto_update_interval_var.get()
        try:
            parsed = int(str(raw_interval).strip())
        except ValueError:
            messagebox.showwarning("Автообновления", "Интервал должен быть целым числом минут.")
            return
        if parsed < MIN_UPDATE_INTERVAL_MINUTES:
            messagebox.showwarning("Автообновления", "Минимальный интервал — 1 минута.")
            return

        self.auto_update_enabled = enabled
        self.auto_update_interval_minutes = parsed
        self.db.set_setting("auto_update_enabled", enabled)
        self.db.set_setting("auto_update_interval_minutes", parsed)
        self._schedule_next_update()
        state = "включена" if enabled else "выключена"
        self.status_var.set(f"Автопроверка обновлений {state}. Интервал: {parsed} мин.")

    def show_settings(self) -> None:
        original_show_settings(self)
        frame = ttk.LabelFrame(self.content, text="Автообновления", padding=12)
        frame.pack(fill="x", pady=(18, 0))

        self._auto_update_enabled_var = tk.BooleanVar(value=getattr(self, "auto_update_enabled", True))
        self._auto_update_interval_var = tk.StringVar(
            value=str(getattr(self, "auto_update_interval_minutes", DEFAULT_UPDATE_INTERVAL_MINUTES))
        )

        ttk.Checkbutton(
            frame,
            text="Автоматически проверять и устанавливать обновления",
            variable=self._auto_update_enabled_var,
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frame, text="Проверять каждые").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frame, textvariable=self._auto_update_interval_var, width=8).grid(
            row=1, column=1, sticky="w", padx=6, pady=(10, 0)
        )
        ttk.Label(frame, text="минут (например: 10, 30, 60, 120)").grid(
            row=1, column=2, sticky="w", pady=(10, 0)
        )
        ttk.Label(
            frame,
            text=(
                "Обновляется весь runtime-пакет целиком. После проверки SHA-256 программа сама ждёт окончания работы, "
                "заменяет runtime и перезапускается. Локальные data/ и logs/ не затрагиваются."
            ),
            wraplength=720,
            justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Button(
            frame,
            text="Сохранить настройки обновлений",
            command=self._save_auto_update_settings,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 0))

    def __init__(self, *args, **kwargs):
        self._auto_update_after_id = None
        self._update_thread = None
        self._restart_pending = False
        self._restart_started = False
        self._pending_runtime_zip = None
        original_init(self, *args, **kwargs)
        self.auto_update_enabled = bool(self.db.get_setting("auto_update_enabled", True))
        self.auto_update_interval_minutes = normalize_interval_minutes(
            self.db.get_setting("auto_update_interval_minutes", DEFAULT_UPDATE_INTERVAL_MINUTES)
        )

    cls.__init__ = __init__
    cls._schedule_next_update = _schedule_next_update
    cls._restart_application = _restart_application
    cls._restart_when_idle = _restart_when_idle
    cls._finish_update_check = _finish_update_check
    cls._start_update_check = _start_update_check
    cls._save_auto_update_settings = _save_auto_update_settings
    cls.check_updates_silent = check_updates_silent
    cls.check_updates_manual = check_updates_manual
    cls.show_settings = show_settings
