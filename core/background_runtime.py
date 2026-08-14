from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.background_engine import (
    DEFAULT_POWER_SETTINGS,
    POWER_SETTINGS_KEY,
    apply_download_moves,
    normalized_power_settings,
)
from core.operation_executor import execute_batch
from core.operation_journal import OperationJournal
from core.paths import data_root
from core.placement_learning import SETTINGS_KEY as LEARNING_KEY, learning_summary
from core.scanner import scan_tree
from core.version_retention import build_version_retention_plan, quarantine_operations
from core.windows_paths import downloads_path

RUN_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "SmartOrganizer"


def windows_autostart_command(executable: Path) -> str:
    return f'"{executable}" --background'


def set_windows_autostart(enabled: bool, executable: Path | None = None) -> tuple[bool, str]:
    """Enable per-user Windows autostart without administrator privileges."""
    if os.name != "nt":
        return False, "Автозапуск Windows доступен только в Windows."
    exe = Path(executable or sys.executable).resolve()
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        if enabled:
            proc = subprocess.run(
                [
                    "reg.exe", "add", RUN_KEY, "/v", RUN_VALUE, "/t", "REG_SZ",
                    "/d", windows_autostart_command(exe), "/f",
                ],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=5,
                creationflags=creationflags,
            )
        else:
            proc = subprocess.run(
                ["reg.exe", "delete", RUN_KEY, "/v", RUN_VALUE, "/f"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=5,
                creationflags=creationflags,
            )
            # Missing value while disabling already means the desired state.
            if proc.returncode != 0 and "unable to find" in (proc.stderr or proc.stdout).casefold():
                return True, "Автозапуск уже выключен."
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout or "reg.exe error").strip()
        return True, "Автозапуск Windows обновлён."
    except Exception as exc:
        return False, str(exc)


def _quarantine_root() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    return data_root() / "quarantine" / "old-versions" / stamp


def install_background_runtime(main_window) -> None:
    """Add a conservative always-on organizer and a clear power settings UI."""
    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_background_runtime_installed", False):
        return
    cls._background_runtime_installed = True

    original_init = cls.__init__
    original_on_close = cls.on_close
    original_show_home = cls.show_home

    def _power_settings(self) -> dict:
        return normalized_power_settings(self.db.get_setting(POWER_SETTINGS_KEY, {}))

    def _schedule_background(self, delay_seconds: int | None = None) -> None:
        after_id = getattr(self, "_background_after_id", None)
        if after_id:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
            self._background_after_id = None
        settings = self._power_settings()
        if not settings["background_enabled"]:
            return
        delay = int(delay_seconds if delay_seconds is not None else settings["background_interval_minutes"] * 60)
        self._background_after_id = self.after(max(10, delay) * 1000, self._background_tick)

    def _background_tick(self) -> None:
        settings = self._power_settings()
        if not settings["background_enabled"]:
            return
        if getattr(self, "worker", None) is not None and self.worker.is_alive():
            self._schedule_background(60)
            return
        running = getattr(self, "_background_thread", None)
        if running is not None and running.is_alive():
            self._schedule_background(60)
            return

        def work() -> None:
            moved = 0
            retained = 0
            errors: list[str] = []
            try:
                result = apply_download_moves(self.db, self.knowledge.get("projects", []))
                moved = int(result.get("moved", 0))
            except Exception as exc:
                errors.append(f"Downloads: {exc}")

            settings_now = self._power_settings()
            if settings_now.get("auto_quarantine_old_versions"):
                try:
                    retention = build_version_retention_plan(
                        self.db.snapshot_files(),
                        self.db.snapshot_folders(),
                        settings_now["keep_latest_versions"],
                    )
                    if retention.get("items"):
                        operations = quarantine_operations(retention, _quarantine_root())
                        journal = OperationJournal(self.db)
                        batch_id = journal.plan_batch(operations, label="automatic-version-retention")
                        execution = execute_batch(journal, batch_id)
                        retained = int(execution.get("applied", 0))
                        root_text = self.db.get_setting("last_scan_root")
                        if root_text and Path(str(root_text)).exists():
                            refreshed = scan_tree(Path(str(root_text)), self.knowledge.get("projects", []))
                            self.db.replace_scan(refreshed.folders, refreshed.files)
                        self.db.log_action(
                            "automatic-version-retention",
                            batch_id,
                            "ok",
                            f"operations={retained}; keep_latest={settings_now['keep_latest_versions']}; permanent_deletes=0",
                        )
                except Exception as exc:
                    errors.append(f"версии: {exc}")

            self.db.set_setting(
                "background_last_result",
                {
                    "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    "downloads_moved": moved,
                    "retention_operations": retained,
                    "errors": errors,
                },
            )
            try:
                self.after(0, lambda: self._finish_background_tick(moved, retained, errors))
            except Exception:
                pass

        self._background_thread = threading.Thread(target=work, daemon=True)
        self._background_thread.start()

    def _finish_background_tick(self, moved: int, retained: int, errors: list[str]) -> None:
        if errors:
            self.status_var.set("Фоновая проверка завершена с предупреждением: " + errors[0])
        elif moved or retained:
            self.status_var.set(
                f"Фоновая работа: перемещено загрузок {moved}; операций карантина старых версий {retained}. Undo доступен."
            )
        self._schedule_background()

    def _browse_power_folder(self, key: str) -> None:
        selected = filedialog.askdirectory(title="Выберите существующую папку назначения")
        if selected and key in self._power_path_vars:
            self._power_path_vars[key].set(selected)

    def _save_power_settings(self) -> None:
        current = self._power_settings()
        try:
            interval = int(self._power_vars["background_interval_minutes"].get())
            age = int(self._power_vars["download_min_age_seconds"].get())
            keep = int(self._power_vars["keep_latest_versions"].get())
        except ValueError:
            messagebox.showwarning("Умные настройки", "Интервал, возраст файла и число сохраняемых версий должны быть целыми числами.")
            return
        routes = {category: variable.get().strip() for category, variable in self._route_vars.items()}
        settings = {
            **current,
            "background_enabled": bool(self._power_vars["background_enabled"].get()),
            "background_interval_minutes": interval,
            "start_with_windows": bool(self._power_vars["start_with_windows"].get()),
            "close_to_background": bool(self._power_vars["close_to_background"].get()),
            "auto_sort_downloads": bool(self._power_vars["auto_sort_downloads"].get()),
            "download_min_age_seconds": age,
            "separate_chatgpt": bool(self._power_vars["separate_chatgpt"].get()),
            "chatgpt_target": self._power_path_vars["chatgpt_target"].get().strip(),
            "routes": routes,
            "keep_latest_versions": keep,
            "auto_quarantine_old_versions": bool(self._power_vars["auto_quarantine_old_versions"].get()),
            "strictness": self._power_vars["strictness"].get(),
        }
        settings = normalized_power_settings(settings)

        missing = []
        for label, path_text in [("ChatGPT/OpenAI", settings["chatgpt_target"]), *list(settings["routes"].items())]:
            if path_text and not Path(path_text).is_dir():
                missing.append(f"{label}: {path_text}")
        if missing:
            messagebox.showwarning(
                "Папки назначения",
                "Эти папки не существуют. Smart Organizer не создаёт их молча:\n\n" + "\n".join(missing[:12]),
            )
            return

        self.db.set_setting(POWER_SETTINGS_KEY, settings)
        auto_ok, auto_message = set_windows_autostart(settings["start_with_windows"])
        self._schedule_background(15)
        self.status_var.set("Умные настройки сохранены. " + auto_message)
        if not auto_ok and settings["start_with_windows"]:
            messagebox.showwarning("Автозапуск", "Настройки сохранены, но Windows автозапуск включить не удалось:\n" + auto_message)
        else:
            messagebox.showinfo(
                "Умные настройки",
                "Сохранено. Фоновый режим использует только существующие папки, не перезаписывает файлы и ведёт Undo-журнал.",
            )

    def _show_retention_plan(self) -> None:
        settings = self._power_settings()
        plan = build_version_retention_plan(
            self.db.snapshot_files(), self.db.snapshot_folders(), settings["keep_latest_versions"]
        )
        summary = plan["summary"]
        if not plan["items"]:
            messagebox.showinfo(
                "Версии 5+",
                f"Кандидатов нет. Для каждой явной версии сохраняются последние {summary['keep_latest']} версий.",
            )
            return
        preview = "\n".join(
            f"• {item['version']} | {item['source']}" for item in plan["items"][:12]
        )
        if len(plan["items"]) > 12:
            preview += f"\n… ещё {len(plan['items']) - 12}"
        messagebox.showinfo(
            "Старые версии — только план",
            f"Семейств: {summary['families']}\n"
            f"Старых архивов: {summary['archive_candidates']}\n"
            f"Старых папок проектов: {summary['folder_candidates']}\n"
            f"Постоянных удалений: {summary['permanent_deletes']}\n\n{preview}\n\n"
            "Распознаются только явные версии. Обычные нумерованные папки не затрагиваются.",
        )

    def quarantine_old_versions_now(self) -> None:
        settings = self._power_settings()
        plan = build_version_retention_plan(
            self.db.snapshot_files(), self.db.snapshot_folders(), settings["keep_latest_versions"]
        )
        if not plan["items"]:
            messagebox.showinfo("Версии 5+", "Старых подтверждённых версий для карантина нет.")
            return
        summary = plan["summary"]
        preview = "\n".join(f"• {item['source']}" for item in plan["items"][:10])
        if not messagebox.askyesno(
            "Поместить старые версии в карантин",
            f"Будут сохранены последние {summary['keep_latest']} явных версий каждого семейства.\n"
            f"В карантин: {summary['candidates']} элементов.\n"
            f"Архивов: {summary['archive_candidates']}; целых папок проектов: {summary['folder_candidates']}.\n\n"
            f"{preview}\n\nНичего не удаляется навсегда. Все элементы перемещаются целиком в локальный карантин и доступны для Undo. Продолжить?",
        ):
            return
        root = _quarantine_root()
        operations = quarantine_operations(plan, root)
        journal = OperationJournal(self.db)
        batch_id = journal.plan_batch(operations, label="confirmed-version-retention")
        root_text = self.db.get_setting("last_scan_root")

        def work():
            result = execute_batch(journal, batch_id)
            if root_text and Path(str(root_text)).exists():
                refreshed = scan_tree(Path(str(root_text)), self.knowledge.get("projects", []))
                self.db.replace_scan(refreshed.folders, refreshed.files)
            return result

        def done(result):
            self.db.log_action(
                "confirmed-version-retention", batch_id, "ok",
                f"applied={result['applied']}; keep_latest={summary['keep_latest']}; permanent_deletes=0",
            )
            self.status_var.set(
                f"Старые версии помещены в карантин: операций {result['applied']}. Последние {summary['keep_latest']} версий сохранены. Undo доступен."
            )

        self._start_worker("Перемещаю подтверждённые старые версии в обратимый карантин…", work, done)

    def _force_exit_app(self) -> None:
        self._force_real_exit = True
        original_on_close(self)

    def show_settings(self) -> None:
        self._set_stable_nav("Настройки") if hasattr(self, "_set_stable_nav") else None
        self.clear_content()
        ttk.Label(self.content, text="Настройки и подстройка", style="Title.TLabel").pack(anchor="w", pady=(4, 8))
        ttk.Label(
            self.content,
            text="Широкие настройки без скрытых действий: фон, автозапуск, Загрузки, ChatGPT/OpenAI, версии и безопасность.",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        settings = self._power_settings()
        self._power_vars = {
            "background_enabled": tk.BooleanVar(value=settings["background_enabled"]),
            "background_interval_minutes": tk.StringVar(value=str(settings["background_interval_minutes"])),
            "start_with_windows": tk.BooleanVar(value=settings["start_with_windows"]),
            "close_to_background": tk.BooleanVar(value=settings["close_to_background"]),
            "auto_sort_downloads": tk.BooleanVar(value=settings["auto_sort_downloads"]),
            "download_min_age_seconds": tk.StringVar(value=str(settings["download_min_age_seconds"])),
            "separate_chatgpt": tk.BooleanVar(value=settings["separate_chatgpt"]),
            "keep_latest_versions": tk.StringVar(value=str(settings["keep_latest_versions"])),
            "auto_quarantine_old_versions": tk.BooleanVar(value=settings["auto_quarantine_old_versions"]),
            "strictness": tk.StringVar(value=settings["strictness"]),
        }
        self._power_path_vars = {"chatgpt_target": tk.StringVar(value=settings["chatgpt_target"])}
        self._route_vars = {category: tk.StringVar(value=path) for category, path in settings["routes"].items()}

        notebook = ttk.Notebook(self.content)
        notebook.pack(fill="both", expand=True)

        background = ttk.Frame(notebook, padding=12)
        downloads = ttk.Frame(notebook, padding=12)
        versions = ttk.Frame(notebook, padding=12)
        safety = ttk.Frame(notebook, padding=12)
        notebook.add(background, text="Фон и Windows")
        notebook.add(downloads, text="Загрузки и типы")
        notebook.add(versions, text="Версии 5+")
        notebook.add(safety, text="Безопасность")

        ttk.Checkbutton(background, text="Работать в фоне", variable=self._power_vars["background_enabled"]).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(background, text="Запускать вместе с Windows", variable=self._power_vars["start_with_windows"]).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Checkbutton(background, text="Крестик сворачивает в фон, а не завершает программу", variable=self._power_vars["close_to_background"]).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(background, text="Фоновая проверка каждые").grid(row=3, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(background, textvariable=self._power_vars["background_interval_minutes"], width=7).grid(row=3, column=1, sticky="w", padx=6, pady=(12, 0))
        ttk.Label(background, text="минут").grid(row=3, column=2, sticky="w", pady=(12, 0))
        ttk.Label(
            background,
            text="Автозапуск записывается только для текущего пользователя Windows и не требует прав администратора. При старте с Windows окно открывается свёрнутым.",
            wraplength=780,
            justify="left",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(14, 0))

        ttk.Checkbutton(downloads, text="Автоматически разбирать завершённые файлы из Загрузок", variable=self._power_vars["auto_sort_downloads"]).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(downloads, text="Не трогать новый файл первые").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(downloads, textvariable=self._power_vars["download_min_age_seconds"], width=8).grid(row=1, column=1, sticky="w", padx=6, pady=(8, 0))
        ttk.Label(downloads, text="секунд — защита незавершённых загрузок").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(downloads, text="Отделять файлы с явными метками ChatGPT / OpenAI / DALL-E / Sora", variable=self._power_vars["separate_chatgpt"]).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(downloads, text="ChatGPT/OpenAI →").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(downloads, textvariable=self._power_path_vars["chatgpt_target"], width=62).grid(row=3, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(downloads, text="Выбрать", command=lambda: self._browse_power_folder("chatgpt_target")).grid(row=3, column=2, sticky="w", pady=4)
        row = 4
        for category, variable in self._route_vars.items():
            ttk.Label(downloads, text=f"{category} →").grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(downloads, textvariable=variable, width=62).grid(row=row, column=1, sticky="ew", padx=6, pady=3)
            key = f"route:{category}"
            self._power_path_vars[key] = variable
            ttk.Button(downloads, text="Выбрать", command=lambda k=key: self._browse_power_folder(k)).grid(row=row, column=2, sticky="w", pady=3)
            row += 1
        downloads.columnconfigure(1, weight=1)
        ttk.Label(
            downloads,
            text="Пустое поле = не задавать жёсткий маршрут. Тогда Smart Organizer использует только зрелое локальное обучение. Папки назначения должны уже существовать; перезапись запрещена.",
            wraplength=820,
            justify="left",
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Label(versions, text="Сохранять последних явных версий:").grid(row=0, column=0, sticky="w")
        ttk.Entry(versions, textvariable=self._power_vars["keep_latest_versions"], width=7).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Checkbutton(
            versions,
            text="Автоматически помещать более старые версии в обратимый карантин в фоне",
            variable=self._power_vars["auto_quarantine_old_versions"],
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Label(
            versions,
            text=(
                "Строгая защита: учитываются только явные версии (например v1.2.3). Для папок с кодом обязателен прямой маркер проекта — main.py, requirements.txt, package.json, project.godot и т.п. "
                "Обычные папки 2024, Фото 12 и разные проекты с одинаковыми main.py не считаются одной цепочкой. Постоянное удаление не выполняется — используется карантин + Undo."
            ),
            wraplength=820,
            justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(12, 10))
        ttk.Button(versions, text="Показать кандидатов 5+", command=self._show_retention_plan).grid(row=3, column=0, sticky="w")
        ttk.Button(versions, text="Поместить старые версии в карантин сейчас", command=self.quarantine_old_versions_now).grid(row=3, column=1, columnspan=2, sticky="w", padx=8)

        learned = learning_summary(self.db.get_setting(LEARNING_KEY, []) or [])
        ttk.Label(
            safety,
            text=(
                "Режим строгости: программа предпочитает ничего не сделать, чем ошибиться.\n\n"
                f"Локальных правил размещения: {learned['rules']}\n"
                f"Надёжных после повторных подтверждений: {learned['mature']}\n"
                f"Ещё обучаются: {learned['learning']}\n\n"
                "Всегда включено: защита проектных границ; запрет перезаписи; пакетный preflight; журнал; Undo; SHA-256 для точных дублей; data/ и logs/ не заменяются обновлением."
            ),
            wraplength=820,
            justify="left",
        ).pack(anchor="w")
        strict_row = ttk.Frame(safety)
        strict_row.pack(fill="x", pady=(14, 0))
        ttk.Label(strict_row, text="Строгость:").pack(side="left")
        ttk.Combobox(
            strict_row,
            textvariable=self._power_vars["strictness"],
            values=("strict", "balanced"),
            state="readonly",
            width=14,
        ).pack(side="left", padx=8)
        ttk.Label(strict_row, text="strict — максимум защиты; balanced — больше подсказок, но фон всё равно выполняет только надёжные маршруты.").pack(side="left", padx=4)

        bottom = ttk.Frame(self.content)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Button(bottom, text="Сохранить все настройки", command=self._save_power_settings).pack(side="left")
        if hasattr(self, "check_updates_manual"):
            ttk.Button(bottom, text="Проверить обновления", command=self.check_updates_manual).pack(side="left", padx=8)
        if hasattr(self, "show_diagnostics"):
            ttk.Button(bottom, text="Диагностика", command=self.show_diagnostics).pack(side="left", padx=8)
        if hasattr(self, "undo_last_stable"):
            ttk.Button(bottom, text="Undo", command=self.undo_last_stable).pack(side="left", padx=8)
        ttk.Button(bottom, text="Полностью выйти", command=self._force_exit_app).pack(side="right")

    def show_home(self) -> None:
        original_show_home(self)
        settings = self._power_settings()
        last = self.db.get_setting("background_last_result", {}) or {}
        frame = ttk.LabelFrame(self.content, text="Фоновый помощник", padding=12)
        frame.pack(fill="x", pady=(14, 0))
        ttk.Label(
            frame,
            text=(
                f"Фон: {'ВКЛ' if settings['background_enabled'] else 'ВЫКЛ'}   "
                f"Windows: {'автозапуск' if settings['start_with_windows'] else 'ручной запуск'}   "
                f"Загрузки: {'автосортировка' if settings['auto_sort_downloads'] else 'только вручную'}   "
                f"Сохранять версий: {settings['keep_latest_versions']}\n"
                f"Последняя фоновая проверка: {last.get('time', 'ещё не выполнялась')}"
            ),
            justify="left",
        ).pack(anchor="w")

    def on_close(self) -> None:
        settings = self._power_settings()
        if (
            settings.get("background_enabled")
            and settings.get("close_to_background")
            and not getattr(self, "_force_real_exit", False)
        ):
            self.iconify()
            self.status_var.set("Smart Organizer свёрнут и продолжает работать в фоне. Для полного выхода используйте Настройки → Полностью выйти.")
            return
        original_on_close(self)

    def __init__(self, *args, **kwargs):
        self._background_after_id = None
        self._background_thread = None
        self._force_real_exit = False
        original_init(self, *args, **kwargs)
        settings = self._power_settings()
        # The user requested Windows background/autostart behavior. Keep the
        # registry entry self-healing on real frozen launches, but never modify
        # the CI machine during application self-tests.
        if getattr(sys, "frozen", False) and "--app-self-test" not in sys.argv:
            set_windows_autostart(settings["start_with_windows"])
        if "--background" in sys.argv and settings["background_enabled"]:
            self.after(500, self.iconify)
        self._schedule_background(20)

    cls.__init__ = __init__
    cls._power_settings = _power_settings
    cls._schedule_background = _schedule_background
    cls._background_tick = _background_tick
    cls._finish_background_tick = _finish_background_tick
    cls._browse_power_folder = _browse_power_folder
    cls._save_power_settings = _save_power_settings
    cls._show_retention_plan = _show_retention_plan
    cls.quarantine_old_versions_now = quarantine_old_versions_now
    cls._force_exit_app = _force_exit_app
    cls.show_settings = show_settings
    cls.show_home = show_home
    cls.on_close = on_close
