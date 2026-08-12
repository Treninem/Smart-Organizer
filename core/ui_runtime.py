from __future__ import annotations

from collections import Counter
from tkinter import ttk


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
                "Планирование не меняет файлы. Перед будущими изменениями каждая операция будет записана "
                "в SQLite и получит обратный план для Undo."
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
    cls.show_settings = show_settings
    cls._apply_monitor_sample = _apply_monitor_sample
