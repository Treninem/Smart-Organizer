from __future__ import annotations

from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from core.diagnostics import collect_diagnostics


def install_diagnostics_ui_runtime(main_window) -> None:
    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_diagnostics_ui_runtime_installed", False):
        return
    cls._diagnostics_ui_runtime_installed = True
    original_show_home = cls.show_home
    original_show_settings = cls.show_settings

    def show_diagnostics(self) -> None:
        self.clear_content()
        ttk.Label(self.content, text="Диагностика", style="Title.TLabel").pack(anchor="w", pady=(4, 8))
        report = collect_diagnostics()
        summary = report["summary"]
        ttk.Label(
            self.content,
            text=f"OK: {summary['ok']}   Предупреждения: {summary['warnings']}   Ошибки: {summary['errors']}",
            style="SubTitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        box = ScrolledText(self.content, wrap="word", font=("Consolas", 10), height=25)
        box.pack(fill="both", expand=True)
        for item in report["checks"]:
            marker = {"ok": "OK", "warning": "WARN", "error": "ERROR"}.get(item["level"], "INFO")
            box.insert("end", f"[{marker}] {item['name']}\n  {item['detail']}\n\n")
        box.configure(state="disabled")
        self.status_var.set(f"Диагностика: ошибок {summary['errors']}, предупреждений {summary['warnings']}.")

    def show_home(self) -> None:
        original_show_home(self)
        for widget in self.content.winfo_children():
            if isinstance(widget, ttk.LabelFrame) and str(widget.cget("text")) == "Быстрые действия":
                ttk.Button(widget, text="🩺 Диагностика", command=self.show_diagnostics).pack(side="left", padx=8)
                break

    def show_settings(self) -> None:
        original_show_settings(self)
        frame = ttk.LabelFrame(self.content, text="Диагностика установки", padding=12)
        frame.pack(fill="x", pady=(18, 0))
        ttk.Button(frame, text="🩺 Открыть диагностику", command=self.show_diagnostics).pack(anchor="w")

    cls.show_diagnostics = show_diagnostics
    cls.show_home = show_home
    cls.show_settings = show_settings
