from __future__ import annotations

from collections import Counter
from tkinter import messagebox, ttk

from core.operation_journal import OperationJournal
from core.plan_bridge import operations_from_sort_plan
from core.sort_planner import build_sort_plan


def _walk_widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk_widgets(child)


def install_ui_runtime(main_window) -> None:
    """Small UI upgrades kept separate from the original window implementation."""

    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_ui_runtime_installed", False):
        return
    cls._ui_runtime_installed = True

    original_show_home = cls.show_home
    original_show_files = cls.show_files
    original_show_settings = cls.show_settings
    original_apply_monitor_sample = cls._apply_monitor_sample

    def show_home(self) -> None:
        original_show_home(self)
        for widget in _walk_widgets(self.content):
            try:
                if isinstance(widget, ttk.LabelFrame) and str(widget.cget("text")).startswith("Что нового в v"):
                    widget.configure(text=f"Что нового в v{main_window.APP_VERSION}")
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Label):
                            child.configure(
                                text=(
                                    "• Стабильный Windows onedir-runtime без временной _MEI-папки\n"
                                    "• Атомарное обновление полного runtime-пакета с SHA-256\n"
                                    "• Реальный Рабочий стол Windows, включая перенаправление на другой диск\n"
                                    "• Безопасный план порядка: существующие папки имеют приоритет\n"
                                    "• Точные дубликаты SHA-256, версии и ZIP/RAR/7Z без распаковки\n"
                                    "• Локальный журнал обратимых операций; data/ и logs/ не заменяются"
                                )
                            )
                            break
                    break
            except Exception:
                continue

    def _files_toolbar(self):
        for widget in self.content.winfo_children():
            if not isinstance(widget, ttk.Frame):
                continue
            buttons = [child for child in widget.winfo_children() if isinstance(child, ttk.Button)]
            if any(str(button.cget("text")).startswith("🔍") for button in buttons):
                return widget
        return None

    def show_files(self) -> None:
        original_show_files(self)
        toolbar = _files_toolbar(self)
        if toolbar is not None:
            ttk.Button(toolbar, text="🧭 План порядка", command=self.preview_sort_plan).pack(side="left", padx=6)
            ttk.Button(toolbar, text="📝 В журнал", command=self.record_sort_plan).pack(side="left", padx=6)

    def _build_current_sort_plan(self) -> dict:
        return build_sort_plan(
            self.db.snapshot_files(),
            self.db.snapshot_folders(),
            self.knowledge.get("projects", []),
            self.db.get_setting("last_scan_root"),
        )

    def preview_sort_plan(self) -> None:
        files = self.db.snapshot_files()
        if not files:
            messagebox.showinfo("План порядка", "Сначала проанализируйте нужную папку или Рабочий стол.")
            return
        plan = _build_current_sort_plan(self)
        self._last_sort_plan = plan
        if not hasattr(self, "file_results"):
            self.show_files()
        box = self.file_results
        box.delete("1.0", "end")
        summary = plan["summary"]
        box.insert(
            "end",
            "БЕЗОПАСНЫЙ ПРЕДВАРИТЕЛЬНЫЙ ПЛАН — файловая система не изменена.\n\n"
            f"Файлов рассмотрено: {summary['files_considered']}\n"
            f"Уже на подходящем месте: {summary['already_placed']}\n"
            f"Предложено перемещений: {summary['moves_suggested']}\n"
            f"В существующие папки: {summary['existing_folder_targets']}\n"
            f"Требуют создания/подтверждения: {summary['new_folder_targets']}\n"
            f"Фактических изменений: {summary['filesystem_changes_performed']}\n\n",
        )
        items = plan.get("items", [])
        limit = 200
        for item in items[:limit]:
            marker = "СУЩЕСТВУЕТ" if item.get("mode") == "existing" else "НУЖНО ПОДТВЕРЖДЕНИЕ"
            box.insert(
                "end",
                f"[{marker} | {item.get('confidence', 'low')}]\n"
                f"  {item.get('source', '')}\n"
                f"  → {item.get('target_path', '')}\n"
                f"  Причина: {item.get('reason', '')}\n\n",
            )
        if len(items) > limit:
            box.insert("end", f"Показаны первые {limit} из {len(items)} предложений.\n")
        self.status_var.set(
            f"План готов: {summary['moves_suggested']} предложений, изменений файловой системы: 0."
        )

    def record_sort_plan(self) -> None:
        files = self.db.snapshot_files()
        if not files:
            messagebox.showinfo("Журнал", "Сначала проанализируйте нужную папку или Рабочий стол.")
            return
        plan = getattr(self, "_last_sort_plan", None) or _build_current_sort_plan(self)
        self._last_sort_plan = plan
        try:
            operations = operations_from_sort_plan(plan, existing_only=True)
        except ValueError as exc:
            messagebox.showwarning(
                "План требует проверки",
                "Безопасная запись остановлена из-за конфликта путей. Файлы не изменены.\n\n" + str(exc),
            )
            self.status_var.set("План не записан: найден конфликт целевых путей. Файлы не изменены.")
            return
        if not operations:
            messagebox.showinfo(
                "Журнал",
                "Нет безопасных перемещений в уже существующие папки. Новые папки автоматически не создаются.",
            )
            return
        journal = OperationJournal(self.db)
        batch_id = journal.plan_batch(operations, label="safe-sort-preview")
        self.db.log_action("sort-plan-journal", batch_id, "ok", f"planned={len(operations)}; filesystem_changes=0")
        self.status_var.set(
            f"В журнал записано {len(operations)} безопасных операций. Файлы не перемещались."
        )
        if hasattr(self, "file_results"):
            self.file_results.insert(
                "end",
                f"\nПакет журнала: {batch_id}\nЗаписано операций: {len(operations)}\nФайловая система не изменена.\n",
            )

    def show_settings(self) -> None:
        original_show_settings(self)
        for widget in _walk_widgets(self.content):
            if not isinstance(widget, ttk.Label):
                continue
            try:
                text = str(widget.cget("text"))
            except Exception:
                continue
            if "Эти ограничения специально сохраняются на этапе v0.2.0." in text:
                widget.configure(
                    text=text.replace(
                        "Эти ограничения специально сохраняются на этапе v0.2.0.",
                        f"Эти ограничения сохраняются в безопасном режиме v{main_window.APP_VERSION}.",
                    )
                )

        entries = self.db.operation_entries(limit=500)
        statuses = Counter(item["status"] for item in entries)
        journal = ttk.LabelFrame(self.content, text="Журнал безопасности и Undo", padding=12)
        journal.pack(fill="x", pady=(18, 0))
        ttk.Label(
            journal,
            text=(
                f"Записей операций: {len(entries)}   "
                f"запланировано: {statuses.get('planned', 0)}   "
                f"применено: {statuses.get('applied', 0)}   "
                f"отменено: {statuses.get('undone', 0)}   "
                f"ошибок: {statuses.get('failed', 0)}\n"
                "Планирование не меняет файлы. Кнопка «В журнал» в разделе «Файлы» записывает только "
                "перемещения в уже существующие папки; предложения новых папок остаются только предпросмотром."
            ),
            wraplength=760,
            justify="left",
        ).pack(anchor="w")

    def _apply_monitor_sample(self, sample: dict) -> None:
        original_apply_monitor_sample(self, sample)
        # The counters show current traffic, not an ISP speed-test result. The
        # explicit wording prevents an idle 0 bit/s value from looking like a
        # broken internet connection.
        self.monitor_vars["net"].set(
            f"Трафик сейчас ↓ {sample['download_text']}   ↑ {sample['upload_text']}"
        )

    cls.show_home = show_home
    cls.show_files = show_files
    cls.preview_sort_plan = preview_sort_plan
    cls.record_sort_plan = record_sort_plan
    cls._apply_monitor_sample = _apply_monitor_sample
    cls.show_settings = show_settings
