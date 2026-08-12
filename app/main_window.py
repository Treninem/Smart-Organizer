from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.database import Database
from core.knowledge import knowledge_items, load_initial_knowledge
from core.paths import app_root, ensure_runtime_dirs
from core.scanner import scan_tree
from core.updater import apply_source_update, fetch_manifest, update_available

APP_VERSION = "0.1.0"


class SmartOrganizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Smart Organizer v{APP_VERSION}")
        self.geometry("1050x680")
        self.minsize(900, 580)
        self.paths = ensure_runtime_dirs()
        self.db = Database(self.paths["data"] / "knowledge.db")
        self.knowledge = load_initial_knowledge(app_root() / "config" / "initial_knowledge.json")
        self.db.seed_knowledge(knowledge_items(self.knowledge))
        self.scan_thread: threading.Thread | None = None
        self._setup_style()
        self._build_ui()
        self.refresh_dashboard()
        self.after(800, self.check_updates_silent)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_style(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("CardTitle.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Big.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Nav.TButton", font=("Segoe UI", 10), padding=(12, 9))

    def _build_ui(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        sidebar = ttk.Frame(outer, width=205)
        sidebar.pack(side="left", fill="y", padx=(0, 12))
        sidebar.pack_propagate(False)
        ttk.Label(sidebar, text="Smart Organizer", style="Title.TLabel").pack(anchor="w", pady=(4, 18))
        for text in ["🏠 Главная", "📂 Файлы", "🤖 Проекты", "🧠 Память ИИ", "🐙 GitHub", "📦 Архивы", "⚙ Настройки"]:
            ttk.Button(sidebar, text=text, style="Nav.TButton", command=lambda t=text: self.show_section(t)).pack(fill="x", pady=3)
        ttk.Separator(sidebar).pack(fill="x", pady=14)
        ttk.Label(sidebar, text="Режим безопасности:").pack(anchor="w")
        ttk.Label(sidebar, text="ТОЛЬКО АНАЛИЗ", foreground="#b36b00").pack(anchor="w", pady=(2, 0))

        self.content = ttk.Frame(outer)
        self.content.pack(side="left", fill="both", expand=True)
        self.show_home()

    def clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def show_section(self, title: str):
        if title == "🏠 Главная":
            self.show_home()
            return
        if title == "📂 Файлы":
            self.show_files()
            return
        self.clear_content()
        ttk.Label(self.content, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.content, text="Раздел подключён к архитектуре и будет расширен в следующих этапах.").pack(anchor="w", pady=16)
        ttk.Label(self.content, text="v0.1.0 ничего не удаляет и не перемещает автоматически.").pack(anchor="w")

    def show_home(self):
        self.clear_content()
        ttk.Label(self.content, text="Главная", style="Title.TLabel").pack(anchor="w", pady=(4, 12))
        ttk.Label(self.content, text="Локальный помощник. Сначала понимает вашу структуру, затем предлагает действия.").pack(anchor="w", pady=(0, 16))
        cards = ttk.Frame(self.content)
        cards.pack(fill="x")
        self.stats_labels = {}
        for idx, (key, title) in enumerate([("files", "Файлов изучено"), ("folders", "Папок изучено"), ("knowledge", "Знаний в базе"), ("decisions", "Решений запомнено")]):
            frame = ttk.LabelFrame(cards, text=title, padding=14)
            frame.grid(row=0, column=idx, sticky="nsew", padx=4)
            label = ttk.Label(frame, text="0", style="Big.TLabel")
            label.pack()
            self.stats_labels[key] = label
            cards.columnconfigure(idx, weight=1)
        actions = ttk.LabelFrame(self.content, text="Быстрые действия", padding=14)
        actions.pack(fill="x", pady=16)
        ttk.Button(actions, text="🔍 Проанализировать папку", command=self.pick_and_scan).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="💻 Проанализировать рабочий стол", command=self.scan_desktop).pack(side="left", padx=8)
        ttk.Button(actions, text="🔄 Проверить обновления", command=self.check_updates_manual).pack(side="left", padx=8)
        self.status_var = tk.StringVar(value="Готов к анализу. Изменения файлов отключены.")
        ttk.Label(self.content, textvariable=self.status_var).pack(anchor="w", pady=8)
        self.progress = ttk.Progressbar(self.content, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 8))
        self.refresh_dashboard()

    def show_files(self):
        self.clear_content()
        ttk.Label(self.content, text="Файлы", style="Title.TLabel").pack(anchor="w", pady=(4, 12))
        ttk.Label(self.content, text="На этом этапе доступен безопасный анализ без перемещения и удаления.").pack(anchor="w", pady=(0, 14))
        ttk.Button(self.content, text="🔍 Выбрать папку для анализа", command=self.pick_and_scan).pack(anchor="w", pady=4)
        ttk.Button(self.content, text="💻 Анализ рабочего стола", command=self.scan_desktop).pack(anchor="w", pady=4)
        self.file_status = tk.StringVar(value="Выберите папку.")
        ttk.Label(self.content, textvariable=self.file_status, wraplength=740).pack(anchor="w", pady=16)

    def refresh_dashboard(self):
        counts = self.db.counts()
        if hasattr(self, "stats_labels"):
            for key, label in self.stats_labels.items():
                label.configure(text=f"{counts.get(key, 0):,}".replace(",", " "))

    def pick_and_scan(self):
        path = filedialog.askdirectory(title="Выберите папку для безопасного анализа")
        if path:
            self.start_scan(Path(path))

    def scan_desktop(self):
        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
        if not desktop.exists():
            desktop = Path.home() / "Desktop"
        self.start_scan(desktop)

    def start_scan(self, root: Path):
        if self.scan_thread and self.scan_thread.is_alive():
            messagebox.showinfo("Smart Organizer", "Анализ уже выполняется.")
            return
        if hasattr(self, "status_var"):
            self.status_var.set(f"Анализ: {root}")
        if hasattr(self, "file_status"):
            self.file_status.set(f"Анализ: {root}")
        if hasattr(self, "progress"):
            self.progress.start(10)

        def worker():
            try:
                result = scan_tree(root, self.knowledge.get("projects", []))
                self.db.replace_scan(result.folders, result.files)
                self.db.set_setting("last_scan_root", str(root))
                self.db.log_action("scan", str(root), "ok", json.dumps(result.summary, ensure_ascii=False))
                self.after(0, lambda: self.scan_done(result.summary))
            except Exception as exc:
                self.db.log_action("scan", str(root), "error", str(exc))
                self.after(0, lambda: self.scan_failed(str(exc)))

        self.scan_thread = threading.Thread(target=worker, daemon=True)
        self.scan_thread.start()

    def scan_done(self, summary: dict):
        if hasattr(self, "progress"):
            self.progress.stop()
        text = f"Готово: {summary['files']} файлов, {summary['folders']} папок, ошибок доступа: {summary['errors']}. Ничего не перемещено и не удалено."
        if hasattr(self, "status_var"):
            self.status_var.set(text)
        if hasattr(self, "file_status"):
            self.file_status.set(text)
        self.refresh_dashboard()

    def scan_failed(self, error: str):
        if hasattr(self, "progress"):
            self.progress.stop()
        messagebox.showerror("Ошибка анализа", error)

    def check_updates_silent(self):
        def worker():
            try:
                manifest = fetch_manifest()
                if update_available(APP_VERSION, manifest):
                    changed = apply_source_update(app_root(), manifest)
                    version = manifest.get("version")
                    self.db.log_action("update", str(version), "ok", f"updated={len(changed)}")
                    self.after(0, lambda: self.status_var.set(f"Обновление {version} установлено. Оно полностью включится при следующем запуске."))
            except Exception as exc:
                self.db.log_action("update", None, "error", str(exc))
        threading.Thread(target=worker, daemon=True).start()

    def check_updates_manual(self):
        self.status_var.set("Проверяю GitHub…")
        def worker():
            try:
                manifest = fetch_manifest()
                if update_available(APP_VERSION, manifest):
                    changed = apply_source_update(app_root(), manifest)
                    msg = f"Версия {manifest.get('version')} скачана и установлена ({len(changed)} файлов). Полностью включится при следующем запуске. Локальная data/ сохранена."
                else:
                    msg = "Установлена актуальная версия."
                self.after(0, lambda: messagebox.showinfo("Обновления", msg))
                self.after(0, lambda: self.status_var.set(msg))
            except Exception as exc:
                self.after(0, lambda: messagebox.showwarning("Обновления", f"Не удалось проверить GitHub:\n{exc}"))
                self.after(0, lambda: self.status_var.set("Не удалось проверить обновления."))
        threading.Thread(target=worker, daemon=True).start()

    def on_close(self):
        self.db.close()
        self.destroy()
