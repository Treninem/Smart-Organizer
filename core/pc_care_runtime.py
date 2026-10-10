"""Windows PC-care screen integrated into the existing Smart Organizer UI."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from core.game_priority import GameModeController, parse_names
from core.defender_report import defender_report, report_text
from core.desktop_shortcuts import parse_shortcut_rules, plan_shortcut_sort
from core.operation_journal import OperationJournal
from core.operation_executor import execute_batch, undo_batch
from core.windows_paths import desktop_path
from core.pc_health import (
    installed_applications, open_installed_apps, open_windows_security,
    running_processes, start_defender_quick_scan, startup_entries,
)


def install_pc_care_runtime(main_window) -> None:
    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_pc_care_runtime_installed", False):
        return
    cls._pc_care_runtime_installed = True
    original_init = cls.__init__
    original_exit = cls._force_exit_app

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._game_controller = GameModeController()
        self._game_poll_busy = False
        self._game_last_state = None
        nav = getattr(self, "_stable_nav_buttons", {})
        if nav:
            sidebar = next(iter(nav.values())).master
            button = ttk.Button(
                sidebar, text="Оптимизация ПК", style="Nav.TButton",
                command=lambda: (self._set_stable_nav("Оптимизация ПК"), self.show_pc_care()),
            )
            button.pack(fill="x", pady=4)
            nav["Оптимизация ПК"] = button
        self.after(15000, self._game_poll)

    def _game_poll(self):
        if getattr(self, "_closing", False):
            return
        settings = self.db.get_setting("game_priority_mode", {}) or {}
        enabled = bool(settings.get("enabled"))
        # Dedicated worker: do not block file-sorting operations or Tk's main thread.
        if enabled and not self._game_poll_busy:
            self._game_poll_busy = True

            def finish(processes, error):
                self._game_poll_busy = False
                if getattr(self, "_closing", False):
                    return
                if error is not None:
                    self.status_var.set(f"Игровой режим: нельзя прочитать процессы ({error}).")
                    return
                current = self.db.get_setting("game_priority_mode", {}) or {}
                result = self._game_controller.tick(
                    processes, current.get("games", []), current.get("background", []),
                    enabled=bool(current.get("enabled")),
                )
                if result != self._game_last_state:
                    self._game_last_state = result
                    self.status_var.set(
                        "Игровой режим: " +
                        ("игра обнаружена" if result["game_active"] else "ожидание игры") +
                        f"; ограничено {result['limited_now']}, восстановлено {result['restored']}."
                    )

            def work():
                try:
                    processes, error = running_processes(), None
                except Exception as exc:
                    processes, error = [], str(exc)
                try:
                    self.after(0, lambda: finish(processes, error))
                except RuntimeError:
                    pass

            threading.Thread(target=work, daemon=True).start()
        elif not enabled and self._game_controller._lowered:
            self._game_controller.restore_all()
            self._game_last_state = None
        self.after(15000, self._game_poll)

    def _save_game_priority(self):
        games = parse_names(self._pc_games.get())
        background = parse_names(self._pc_background.get())
        enabled = bool(self._pc_enabled.get())
        if enabled and not games:
            messagebox.showwarning("Игровой режим", "Укажите название процесса игры, например game.exe.")
            return
        if set(games) & set(background):
            messagebox.showwarning("Игровой режим", "Игра не может быть одновременно в списке фона.")
            return
        self.db.set_setting("game_priority_mode", {
            "enabled": enabled, "games": games, "background": background,
        })
        if not enabled:
            self._game_controller.restore_all()
        self.status_var.set("Игровой режим сохранён. Все изменения при выходе из игры восстанавливаются.")
        messagebox.showinfo(
            "Игровой режим",
            "Настройки сохранены.\n"
            "Понижается только приоритет явно выбранных фоновых программ, "
            "а не драйверов, защитных служб или всех процессов подряд."
        )

    def _render_pc_inventory(self, kind):
        output = getattr(self, "_pc_inventory", None)
        if output is None or not output.winfo_exists():
            self.show_pc_care()
            output = self._pc_inventory

        def work():
            if kind == "apps":
                return installed_applications()
            if kind == "startup":
                return startup_entries()
            return running_processes()

        def done(items):
            if not output.winfo_exists():
                return
            output.configure(state="normal")
            output.delete("1.0", "end")
            if kind == "apps":
                output.insert("end", f"Установленные приложения: {len(items)}\n")
                output.insert("end", "Нет издателя ≠ вирус. Это только повод проверить приложение.\n\n")
                for item in items[:500]:
                    output.insert(
                        "end",
                        f"{item['name']}  {item['version']}\n"
                        f"  Издатель: {item['publisher'] or 'не указан'} | {item['scope']}\n"
                        f"  Дата: {item['installed'] or '—'}\n\n",
                    )
            elif kind == "startup":
                output.insert("end", f"Записи автозагрузки: {len(items)}\n")
                output.insert("end", "Отключение записей выполняется через настройки Windows.\n\n")
                for item in items[:500]:
                    output.insert(
                        "end", f"{item['name']}\n  {item['source']}\n  {item['command']}\n\n"
                    )
            else:
                output.insert("end", f"Запущено процессов: {len(items)} (сортировка по памяти)\n\n")
                for item in items[:100]:
                    output.insert(
                        "end", f"{item['name']} | PID {item['pid']} | RAM {item['memory']}\n"
                    )
            if len(items) > (100 if kind == "processes" else 500):
                output.insert("end", "\nЧасть списка скрыта для быстрого отображения.\n")
            output.configure(state="disabled")
            self.status_var.set(f"Анализ ПК завершён: {len(items)} записей. Изменений: 0.")

        self._start_worker("Собираю сведения о ПК без удаления…", work, done)

    def _pc_launch(self, fn):
        try:
            fn()
        except Exception as exc:
            messagebox.showerror("Smart Organizer", str(exc))

    def _pc_defender_scan(self):
        if not messagebox.askyesno(
            "Проверка защиты",
            "Запустить быструю проверку Microsoft Defender?\n\n"
            "Проверка может временно нагружать компьютер. Удаление угроз здесь не производится. "
            "Посмотреть обнаружения и карантин можно в «Безопасность Windows».",
        ):
            return
        try:
            start_defender_quick_scan()
        except Exception as exc:
            messagebox.showerror("Защита Windows", str(exc))
            return
        self.status_var.set("Запрос быстрой проверки Defender отправлен (не означает завершение).")
        messagebox.showinfo(
            "Microsoft Defender",
            "Команда проверки отправлена. Откройте «Безопасность Windows», "
            "чтобы посмотреть ход проверки и результат.",
        )

    def _pc_show_defender_report(self):
        output = getattr(self, "_pc_inventory", None)
        if output is None or not output.winfo_exists():
            self.show_pc_care()
            output = self._pc_inventory

        def done(report):
            if not output.winfo_exists():
                return
            output.configure(state="normal")
            output.delete("1.0", "end")
            output.insert("end", report_text(report))
            output.configure(state="disabled")
            self.status_var.set("Данные Microsoft Defender получены; файлов не удалено.")

        self._start_worker("Получаю подлинный отчёт Microsoft Defender…", defender_report, done)

    def _pc_preview_desktop(self):
        output = getattr(self, "_pc_inventory", None)
        if output is None or not output.winfo_exists():
            return
        raw_rules = self._pc_shortcut_rules.get()
        try:
            plan = plan_shortcut_sort(desktop_path(), parse_shortcut_rules(raw_rules))
        except (OSError, ValueError) as exc:
            messagebox.showwarning("Группы ярлыков", str(exc))
            return
        self.db.set_setting("desktop_shortcut_rules", raw_rules)
        self._desktop_last_plan = plan
        output.configure(state="normal")
        output.delete("1.0", "end")
        output.insert("end", "ПРЕДПРОСМОТР ГРУППИРОВКИ ЯРЛЫКОВ\n\n")
        output.insert("end", f"Перемещений: {len(plan['matches'])}; неоднозначных/конфликтов: "
                      f"{len(plan['ambiguous'])}; без правила: {plan['untouched']}\n\n")
        for item in plan["matches"][:100]:
            output.insert("end", f"{item['name']}\n  → {item['category']}\n")
        if plan["ambiguous"]:
            output.insert("end", "\nПропущены (неоднозначность либо уже существует цель):\n")
            for name in plan["ambiguous"][:30]:
                output.insert("end", "  " + name + "\n")
        output.insert("end", "\nНикакие файлы не перемещены. Выполнение требует подтверждения.\n")
        output.configure(state="disabled")
        self.status_var.set("План ярлыков готов: изменений 0.")

    def _pc_apply_desktop(self):
        plan = getattr(self, "_desktop_last_plan", None)
        if not plan or not plan.get("matches"):
            messagebox.showinfo("Ярлыки", "Сначала сформируйте непустой план сортировки ярлыков.")
            return
        if not messagebox.askyesno(
            "Подтверждение группировки",
            f"Переместить {len(plan['matches'])} ярлыков в подпапки рабочего стола?\n\n"
            "Оригинальные программы и папки установки не затрагиваются. "
            "Перемещение можно отменить через журнал. Продолжить?",
        ):
            return
        # A fresh plan prevents moves based on stale preview or changed rules.
        try:
            current = plan_shortcut_sort(desktop_path(), parse_shortcut_rules(
                self._pc_shortcut_rules.get()
            ))
            if [(r["source"], r["target"]) for r in current["matches"]] != [
                (r["source"], r["target"]) for r in plan["matches"]
            ]:
                raise ValueError("Рабочий стол или правила изменились. Снова нажмите «Предпросмотр».")
            journal = OperationJournal(self.db)
            batch_id = journal.plan_batch(current["operations"], label="desktop-shortcuts")
        except (OSError, ValueError) as exc:
            messagebox.showwarning("Ярлыки", str(exc))
            return

        def work():
            return execute_batch(journal, batch_id)

        def done(result):
            self.db.set_setting("desktop_shortcut_last_batch", batch_id)
            self._desktop_last_plan = None
            self.db.log_action("desktop-shortcuts", batch_id, "ok",
                               f"applied={result['applied']}; files={len(plan['matches'])}")
            self.status_var.set(
                f"Сортировка ярлыков применена: {len(plan['matches'])}. Доступна отмена.")
            messagebox.showinfo("Готово", "Ярлыки разложены. Используйте «Отменить группировку» для отката.")

        self._start_worker("Группирую выбранные ярлыки с журналом Undo…", work, done)

    def _pc_undo_desktop(self):
        batch_id = self.db.get_setting("desktop_shortcut_last_batch")
        if not batch_id:
            messagebox.showinfo("Undo", "Нет последнего применённого пакета группировки.")
            return
        if not messagebox.askyesno(
            "Отмена группировки",
            "Вернуть ярлыки последнего пакета на прежние места? "
            "Занятые пути не будут перезаписаны.",
        ):
            return

        def work():
            return undo_batch(OperationJournal(self.db), batch_id)

        def done(result):
            self.db.set_setting("desktop_shortcut_last_batch", "")
            self.status_var.set(f"Undo группировки: {result['undone']} операций.")
            messagebox.showinfo("Undo", f"Отменено операций: {result['undone']}.")

        self._start_worker("Отменяю группировку ярлыков…", work, done)

    def show_pc_care(self):
        if hasattr(self, "_set_stable_nav"):
            self._set_stable_nav("Оптимизация ПК")
        self.clear_content()
        ttk.Label(self.content, text="Оптимизация и очистка ПК", style="Title.TLabel").pack(
            anchor="w", pady=(4, 8)
        )
        ttk.Label(
            self.content,
            text="Безопасный контроль игр, установленных приложений и автозапуска. "
                 "Без автоматического удаления программ или системных служб.",
            wraplength=820,
        ).pack(anchor="w", pady=(0, 12))

        notebook = ttk.Notebook(self.content)
        notebook.pack(fill="x", pady=(0, 12))
        games = ttk.Frame(notebook, padding=12)
        applications = ttk.Frame(notebook, padding=12)
        security = ttk.Frame(notebook, padding=12)
        shortcuts = ttk.Frame(notebook, padding=12)
        notebook.add(games, text="Игровой режим")
        notebook.add(applications, text="Программы и процессы")
        notebook.add(security, text="Безопасность")
        notebook.add(shortcuts, text="Ярлыки рабочего стола")

        settings = self.db.get_setting("game_priority_mode", {}) or {}
        self._pc_enabled = tk.BooleanVar(value=bool(settings.get("enabled")))
        self._pc_games = tk.StringVar(value=", ".join(settings.get("games", [])))
        self._pc_background = tk.StringVar(value=", ".join(settings.get("background", [])))

        ttk.Checkbutton(
            games, text="Включать ограничение фона при запуске указанной игры",
            variable=self._pc_enabled,
        ).pack(anchor="w", pady=4)
        ttk.Label(games, text="Процессы игр (.exe), через запятую:").pack(anchor="w")
        ttk.Entry(games, textvariable=self._pc_games, width=76).pack(fill="x", pady=3)
        ttk.Label(games, text="Разрешённые к снижению приоритета фоновые процессы (.exe):").pack(anchor="w")
        ttk.Entry(games, textvariable=self._pc_background, width=76).pack(fill="x", pady=3)
        ttk.Label(
            games, text="Пример: игра game.exe; фон browser.exe. "
                        "Меняется только NORMAL → BELOW_NORMAL. "
                        "ОС, антивирус и игра не затрагиваются. После выхода приоритет восстанавливается.",
            wraplength=820,
        ).pack(anchor="w", pady=4)
        ttk.Button(games, text="Сохранить игровой режим", command=self._save_game_priority).pack(
            anchor="w", pady=6
        )

        app_buttons = ttk.Frame(applications)
        app_buttons.pack(fill="x", pady=6)
        for label, kind in (
            ("Установленные программы", "apps"),
            ("Автозагрузка", "startup"),
            ("Что работает в фоне", "processes"),
        ):
            ttk.Button(
                app_buttons, text=label, command=lambda k=kind: self._render_pc_inventory(k)
            ).pack(side="left", padx=(0, 8))
        ttk.Button(
            applications, text="Открыть удаление программ Windows",
            command=lambda: self._pc_launch(open_installed_apps),
        ).pack(anchor="w", pady=5)
        ttk.Label(
            applications,
            text="Удаляйте выбранные приложения через их штатный деинсталлятор Windows. "
                 "Не удаляйте драйверы, Visual C++, .NET, античит и неизвестные системные компоненты.",
            wraplength=820,
        ).pack(anchor="w")

        ttk.Label(
            security,
            text="Рекламное ПО и PUA проверяет Microsoft Defender. "
                 "В «Защита на основе репутации» включите блокировку нежелательных приложений.",
            wraplength=820,
        ).pack(anchor="w", pady=5)
        ttk.Button(
            security, text="Запустить проверку Defender", command=self._pc_defender_scan
        ).pack(anchor="w", pady=4)
        ttk.Button(
            security, text="Последние обнаружения и защита Defender",
            command=self._pc_show_defender_report,
        ).pack(anchor="w", pady=4)
        ttk.Button(
            security, text="Открыть Безопасность Windows",
            command=lambda: self._pc_launch(open_windows_security),
        ).pack(anchor="w", pady=4)
        ttk.Button(
            security, text="Перейти к сортировке файлов и папок",
            command=self.show_files,
        ).pack(anchor="w", pady=4)

        ttk.Label(
            shortcuts, text="Правила «Название ярлыка=Группа», разделённые ;. "
                            "Группы: Игры, Программы, Работа, Документы.",
            wraplength=810,
        ).pack(anchor="w")
        self._pc_shortcut_rules = tk.StringVar(
            value=str(self.db.get_setting("desktop_shortcut_rules", "") or "")
        )
        ttk.Entry(shortcuts, textvariable=self._pc_shortcut_rules, width=78).pack(
            fill="x", pady=4
        )
        ttk.Label(
            shortcuts, text="Например: Steam=Игры; Minecraft=Игры; Chrome=Программы. "
                            "Обрабатываются только .lnk/.url непосредственно на рабочем столе. "
                            "Неизвестные или спорные ярлыки останутся на месте.",
            wraplength=830,
        ).pack(anchor="w", pady=3)
        shortcut_buttons = ttk.Frame(shortcuts)
        shortcut_buttons.pack(fill="x", pady=3)
        ttk.Button(shortcut_buttons, text="Предпросмотр", command=self._pc_preview_desktop).pack(
            side="left", padx=(0, 6))
        ttk.Button(shortcut_buttons, text="Группировать", command=self._pc_apply_desktop).pack(
            side="left", padx=6)
        ttk.Button(shortcut_buttons, text="Отменить группировку", command=self._pc_undo_desktop).pack(
            side="left", padx=6)

        self._pc_inventory = self._result_box()
        self._pc_inventory.insert(
            "end", "Выберите «Установленные программы», «Автозагрузка» "
                   "или «Что работает в фоне». Анализ не изменяет компьютер.\n"
        )

    def _force_exit_app(self):
        # User shutdown is never prevented by a failed priority restoration.
        try:
            controller = getattr(self, "_game_controller", None)
            if controller:
                controller.restore_all()
        except Exception as exc:
            try:
                self.db.log_action("game-priority-restore", None, "warning", str(exc))
            except Exception:
                pass
        finally:
            return original_exit(self)

    cls.__init__ = __init__
    cls._game_poll = _game_poll
    cls._save_game_priority = _save_game_priority
    cls._render_pc_inventory = _render_pc_inventory
    cls._pc_launch = _pc_launch
    cls._pc_defender_scan = _pc_defender_scan
    cls.show_pc_care = show_pc_care
    cls._pc_show_defender_report = _pc_show_defender_report
    cls._pc_preview_desktop = _pc_preview_desktop
    cls._pc_apply_desktop = _pc_apply_desktop
    cls._pc_undo_desktop = _pc_undo_desktop
    cls._force_exit_app = _force_exit_app
