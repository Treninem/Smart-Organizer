from __future__ import annotations

from tkinter import messagebox, ttk

from core.operation_executor import undo_batch
from core.operation_journal import OperationJournal
from core.placement_learning import (
    SETTINGS_KEY as PLACEMENT_LEARNING_KEY,
    forget_undone_moves,
    learning_summary,
)
from core.undo_feedback import SETTINGS_KEY as UNDO_FEEDBACK_KEY, remember_undone_moves


def install_adaptive_feedback_runtime(main_window) -> None:
    """Connect the simplified stable UI to the newest safety/learning engine."""
    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_adaptive_feedback_runtime_installed", False):
        return
    cls._adaptive_feedback_runtime_installed = True

    original_show_settings = cls.show_settings

    def _current_plan(self) -> dict:
        current = getattr(self, "_current_safe_plan", None)
        if callable(current):
            return current()
        # This fallback should only be reached during a partial legacy migration.
        previous = getattr(cls, "_current_plan_before_adaptive", None)
        if callable(previous):
            return previous(self)
        return {"items": [], "summary": {}}

    def undo_last_stable(self) -> None:
        all_entries = self.db.operation_entries(limit=5000)
        batch_id = None
        for row in all_entries:
            if row.get("status") == "applied" and row.get("batch_id"):
                batch_id = str(row["batch_id"])
                break
        if not batch_id:
            messagebox.showinfo("Undo", "Нет применённого пакета для отмены.")
            return

        batch_entries = self.db.operation_entries(batch_id=batch_id, limit=5000)
        applied_entries = [row for row in batch_entries if row.get("status") == "applied"]
        if not applied_entries:
            messagebox.showinfo("Undo", "В последнем пакете нет применённых операций.")
            return

        if not messagebox.askyesno(
            "Undo с обучением",
            f"Отменить последний применённый пакет ({len(applied_entries)} операций)?\n\n"
            "Smart Organizer вернёт файлы только если обратные пути свободны. "
            "Отменённые направления будут запомнены локально, а соответствующие положительные примеры обучения — убраны.",
        ):
            return

        root_text = self.db.get_setting("last_scan_root")

        def work():
            result = undo_batch(OperationJournal(self.db), batch_id)
            refreshed = None
            rescan = getattr(self, "_rescan_snapshot", None)
            if callable(rescan):
                refreshed = rescan(root_text)
            return result, refreshed

        def done(payload):
            result, _refreshed = payload
            rejected = remember_undone_moves(self.db, applied_entries)
            forgotten = forget_undone_moves(self.db, applied_entries)
            self.db.log_action(
                "adaptive-undo",
                batch_id,
                "ok",
                f"undone={result['undone']}; rejected_routes={rejected}; removed_positive_examples={forgotten}",
            )
            try:
                self.refresh_dashboard()
            except Exception:
                pass
            try:
                self._set_stable_nav("Навести порядок")
                self._render_stable_files_screen()
                if self.db.snapshot_files() or self.db.snapshot_folders():
                    self._render_plan(self._current_safe_plan())
            except Exception:
                pass
            self.status_var.set(
                f"Undo выполнен: {result['undone']} операций. "
                f"Запомнено нежелательных направлений: {rejected}; положительных примеров обучения убрано: {forgotten}."
            )

        self._start_worker("Отменяю пакет и обновляю локальную память…", work, done)

    def show_settings(self) -> None:
        original_show_settings(self)
        learned = learning_summary(self.db.get_setting(PLACEMENT_LEARNING_KEY, []) or [])
        rejected = self.db.get_setting(UNDO_FEEDBACK_KEY, []) or []
        frame = ttk.LabelFrame(self.content, text="Локальный интеллект размещения", padding=12)
        frame.pack(fill="x", pady=(16, 0))
        ttk.Label(
            frame,
            text=(
                f"Правил: {learned['rules']}   "
                f"надёжных: {learned['mature']}   "
                f"ещё обучаются: {learned['learning']}   "
                f"подтверждений: {learned['confirmations']}   "
                f"Undo-запретов: {len(rejected)}\n"
                "Одно подтверждение не превращается в автоматическое правило. "
                "Фактическая текущая раскладка сильнее исторической памяти. "
                "Если два места подтверждены одинаково, перемещение блокируется. "
                "Все эти данные хранятся только локально в knowledge.db."
            ),
            wraplength=860,
            justify="left",
        ).pack(anchor="w")

    cls._current_plan_before_adaptive = getattr(cls, "_current_plan", None)
    cls._current_plan = _current_plan
    cls.undo_last_stable = undo_last_stable
    cls.show_settings = show_settings
