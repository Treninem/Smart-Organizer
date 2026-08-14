from __future__ import annotations

from collections import Counter
from tkinter import messagebox, ttk

from core.operation_executor import OperationExecutionError, execute_batch, undo_batch
from core.operation_journal import OperationJournal
from core.placement_learning import (
    SETTINGS_KEY as PLACEMENT_LEARNING_KEY,
    forget_undone_moves,
    learning_summary,
)
from core.plan_bridge import operations_from_sort_plan
from core.sort_planner import build_sort_plan
from core.undo_feedback import remember_undone_moves


def _walk_widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk_widgets(child)


def install_ui_runtime(main_window) -> None:
    """Safe UI upgrades kept separate from the original window implementation."""

    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_ui_runtime_installed", False):
        return
    cls._ui_runtime_installed = True

    original_init = cls.__init__
    original_show_home = cls.show_home
    original_show_files = cls.show_files
    original_show_settings = cls.show_settings
    original_apply_monitor_sample = cls._apply_monitor_sample

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._last_sort_plan = None
        for widget in _walk_widgets(self):
            if not isinstance(widget, ttk.Label):
                continue
            try:
                text = str(widget.cget("text"))
            except Exception:
                continue
            if text == "ТОЛЬКО АНАЛИЗ":
                widget.configure(text="ТОЛЬКО ПО ПОДТВЕРЖДЕНИЮ")
            elif text == "Не удаляет, не переносит\nи не перестраивает папки.":
                widget.configure(text="Сам ничего не удаляет.\nПеремещения — только после проверки и подтверждения.")

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
                                    "• Единый безопасный движок для предпросмотра и реального выполнения\n"
                                    "• Локальное обучение на подтверждённых размещениях и обратной связи Undo\n"
                                    "• Существующая пользовательская структура всегда важнее старой памяти\n"
                                    "• Целые проекты и версии группируются без смешивания внутренностей\n"
                                    "• Точные дубликаты только в безопасном контексте и после полного SHA-256\n"
                                    "• Атомарное onedir-обновление с self-test до и после установки"
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
        # All toolbar actions must use the same final planner as the main
        # "Навести порядок" action. This prevents old preview/journal buttons
        # from bypassing newer safety and learning layers.
        current = getattr(self, "_current_safe_plan", None)
        if callable(current):
            return current()
        return build_sort_plan(
            self.db.snapshot_files(),
            self.db.snapshot_folders(),
            self.knowledge.get("projects", []),
            self.db.get_setting("last_scan_root"),
        )

    def preview_sort_plan(self) -> None:
        files = self.db.snapshot_files()
        folders = self.db.snapshot_folders()
        if not files and not folders:
            messagebox.showinfo("План порядка", "Сначала проанализируйте нужную папку или Рабочий стол.")
            return
        plan = _build_current_sort_plan(self)
        self._last_sort_plan = plan
        renderer = getattr(self, "_render_plan", None)
        if callable(renderer):
            renderer(plan)
            self.status_var.set("Показан тот же проверенный план, который использует реальная команда наведения порядка.")
            return

        if not hasattr(self, "file_results"):
            self.show_files()
        box = self.file_results
        box.delete("1.0", "end")
        summary = plan["summary"]
        box.insert(
            "end",
            "БЕЗОПАСНЫЙ ПРЕДВАРИТЕЛЬНЫЙ ПЛАН — файловая система не изменена.\n\n"
            f"Файлов рассмотрено: {summary.get('files_considered', 0)}\n"
            f"Уже на подходящем месте: {summary.get('already_placed', 0)}\n"
            f"Предложено действий: {summary.get('moves_suggested', 0)}\n"
            f"Фактических изменений: {summary.get('filesystem_changes_performed', 0)}\n\n",
        )
        self.status_var.set("Предварительный план готов. Изменений файловой системы: 0.")

    def record_sort_plan(self) -> None:
        files = self.db.snapshot_files()
        folders = self.db.snapshot_folders()
        if not files and not folders:
            messagebox.showinfo("Журнал", "Сначала проанализируйте нужную папку или Рабочий стол.")
            return
        plan = _build_current_sort_plan(self)
        self._last_sort_plan = plan

        # The journal shortcut remains stricter than the main organizer: only
        # already-existing high-confidence destinations enter it. New folders
        # are handled by the main reviewed workflow with an explicit preview.
        try:
            from core.safe_layout_runtime import safe_executable_items

            strict_items = safe_executable_items(plan)
        except Exception:
            strict_items = [
                dict(item)
                for item in plan.get("items", [])
                if item.get("mode") == "existing"
                and item.get("confidence") == "high"
                and not item.get("requires_confirmation")
            ]
        strict_plan = {**plan, "items": strict_items}
        try:
            operations = operations_from_sort_plan(strict_plan, existing_only=True)
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
                "Нет высоконадёжных перемещений в уже существующие папки. Неуверенные решения и новые папки в журнал этой кнопкой не попадают.",
            )
            return
        journal = OperationJournal(self.db)
        batch_id = journal.plan_batch(operations, label="safe-sort-preview")
        self.db.log_action("sort-plan-journal", batch_id, "ok", f"planned={len(operations)}; filesystem_changes=0")
        self.status_var.set(
            f"В журнал записано {len(operations)} высоконадёжных операций. Выполнение требует отдельного подтверждения."
        )
        if hasattr(self, "file_results"):
            self.file_results.insert(
                "end",
                f"\nПакет журнала: {batch_id}\nЗаписано операций: {len(operations)}\n"
                "Файлы пока не изменены. Выполнение требует отдельного подтверждения в Настройках.\n",
            )

    def _latest_batch(self, wanted_status: str):
        entries = self.db.operation_entries(limit=5000)
        for row in entries:
            if row.get("status") != wanted_status:
                continue
            batch_id = row.get("batch_id")
            if not batch_id:
                continue
            batch = self.db.operation_entries(batch_id=batch_id, limit=5000)
            matching = [item for item in batch if item.get("status") == wanted_status]
            if matching:
                return batch_id, matching
        return None, []

    def apply_latest_planned_batch(self) -> None:
        batch_id, entries = _latest_batch(self, "planned")
        if not batch_id:
            messagebox.showinfo("Журнал", "Нет запланированного пакета для выполнения.")
            return
        preview = "\n".join(
            f"• {item['source']}\n  → {item.get('target') or '—'}" for item in entries[:8]
        )
        if len(entries) > 8:
            preview += f"\n… и ещё {len(entries) - 8}"
        confirmed = messagebox.askyesno(
            "Подтвердить перемещения",
            f"Будет выполнено операций: {len(entries)}.\n\n{preview}\n\n"
            "Smart Organizer НЕ перезаписывает существующие файлы и заранее проверяет весь пакет. Применить этот пакет?",
        )
        if not confirmed:
            self.status_var.set("Выполнение пакета отменено пользователем. Файлы не изменены.")
            return

        def work():
            return execute_batch(OperationJournal(self.db), batch_id)

        def done(result):
            self.db.log_action("journal-apply", batch_id, "ok", f"applied={result['applied']}")
            self.status_var.set(
                f"Пакет применён: {result['applied']} операций. При необходимости используйте Undo в Настройках."
            )
            self.show_settings()

        self._start_worker(f"Выполняю подтверждённый пакет {batch_id[:8]}…", work, done)

    def undo_latest_applied_batch(self) -> None:
        batch_id, entries = _latest_batch(self, "applied")
        if not batch_id:
            messagebox.showinfo("Undo", "Нет применённого пакета, который можно отменить.")
            return
        if not messagebox.askyesno(
            "Undo",
            f"Отменить последний применённый пакет ({len(entries)} операций)?\n\n"
            "Undo никогда не перезаписывает существующий путь. Если исходное место уже занято, отмена остановится. "
            "Отменённое направление также запомнится локально и больше не будет автоматически предлагаться как надёжное.",
        ):
            return

        def work():
            return undo_batch(OperationJournal(self.db), batch_id)

        def done(result):
            rejected = remember_undone_moves(self.db, entries)
            forgotten = forget_undone_moves(self.db, entries)
            self.db.log_action(
                "journal-undo",
                batch_id,
                "ok",
                f"undone={result['undone']}; rejected_routes={rejected}; removed_positive_examples={forgotten}",
            )
            self.status_var.set(
                f"Undo выполнен: отменено операций {result['undone']}. "
                f"Запомнено нежелательных направлений: {rejected}; положительных примеров убрано: {forgotten}."
            )
            self.show_settings()

        self._start_worker(f"Undo пакета {batch_id[:8]}…", work, done)

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
                text = text.replace(
                    "Эти ограничения специально сохраняются на этапе v0.2.0.",
                    f"Автоперемещение остаётся выключенным. Ручное выполнение доступно только после проверки и подтверждения в v{main_window.APP_VERSION}.",
                )
                widget.configure(text=text)

        entries = self.db.operation_entries(limit=500)
        statuses = Counter(item["status"] for item in entries)
        learned = learning_summary(self.db.get_setting(PLACEMENT_LEARNING_KEY, []) or [])
        rejected_routes = len(self.db.get_setting("undo_rejected_destinations", []) or [])
        journal = ttk.LabelFrame(self.content, text="Журнал безопасности, обучение и Undo", padding=12)
        journal.pack(fill="x", pady=(18, 0))
        ttk.Label(
            journal,
            text=(
                f"Записей операций: {len(entries)}   "
                f"запланировано: {statuses.get('planned', 0)}   "
                f"применено: {statuses.get('applied', 0)}   "
                f"отменено: {statuses.get('undone', 0)}   "
                f"ошибок: {statuses.get('failed', 0)}\n"
                f"Локальное обучение: правил {learned['rules']}, надёжных {learned['mature']}, обучаются {learned['learning']}, "
                f"подтверждений {learned['confirmations']}; запрещённых Undo-направлений {rejected_routes}.\n"
                "Одного подтверждения недостаточно для автоматического правила. Реальная текущая компоновка всегда важнее истории. "
                "Undo удаляет положительный пример и запоминает отменённое точное направление. Данные обучения остаются только в knowledge.db."
            ),
            wraplength=820,
            justify="left",
        ).pack(anchor="w")
        buttons = ttk.Frame(journal)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="▶ Применить последний пакет", command=self.apply_latest_planned_batch).pack(side="left")
        ttk.Button(buttons, text="↶ Undo последнего пакета", command=self.undo_latest_applied_batch).pack(side="left", padx=(8, 0))

    def _apply_monitor_sample(self, sample: dict) -> None:
        original_apply_monitor_sample(self, sample)
        self.monitor_vars["net"].set(
            f"Трафик сейчас ↓ {sample['download_text']}   ↑ {sample['upload_text']}"
        )

    cls.__init__ = __init__
    cls.show_home = show_home
    cls.show_files = show_files
    cls.preview_sort_plan = preview_sort_plan
    cls.record_sort_plan = record_sort_plan
    cls.apply_latest_planned_batch = apply_latest_planned_batch
    cls.undo_latest_applied_batch = undo_latest_applied_batch
    cls._apply_monitor_sample = _apply_monitor_sample
    cls.show_settings = show_settings
