from __future__ import annotations

import json
import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from core.archive_analyzer import analyze_archive
from core.database import Database
from core.duplicates import exact_duplicate_groups
from core.knowledge import knowledge_items, load_initial_knowledge
from core.paths import app_root, ensure_runtime_dirs
from core.project_manager import suggest_destination, summarize_projects
from core.scanner import scan_tree
from core.system_monitor import SystemMonitor
from core.updater import apply_source_update, fetch_manifest, update_available
from core.version_manager import version_groups

APP_VERSION = "0.2.0"


def _human_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _percent(value) -> str:
    return "—" if value is None else f"{value:.0f}%"


class SmartOrganizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Smart Organizer v{APP_VERSION}")
        self.geometry("1160x740")
        self.minsize(960, 640)
        self.paths = ensure_runtime_dirs()
        self.db = Database(self.paths["data"] / "knowledge.db")
        self.knowledge = load_initial_knowledge(app_root() / "config" / "initial_knowledge.json")
        self.db.seed_knowledge(knowledge_items(self.knowledge))
        self.worker: threading.Thread | None = None
        self.status_var = tk.StringVar(value="Готов. Безопасный режим: только анализ.")
        self.monitor_vars = {
            "net": tk.StringVar(value="Сеть ↓ —  ↑ —"),
            "cpu": tk.StringVar(value="CPU —"),
            "ram": tk.StringVar(value="RAM —"),
            "disk": tk.StringVar(value="Диск D: —"),
        }
        self.monitor = SystemMonitor("D:\\")
        self.monitor_stop = threading.Event()
        self._setup_style()
        self._build_ui()
        self.refresh_dashboard()
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        self.after(900, self.check_updates_silent)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_style(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("SubTitle.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Big.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Monitor.TLabel", font=("Segoe UI", 9))
        style.configure("Nav.TButton", font=("Segoe UI", 10), padding=(12, 9))

    def _build_ui(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        sidebar = ttk.Frame(outer, width=210)
        sidebar.pack(side="left", fill="y", padx=(0, 12))
        sidebar.pack_propagate(False)
        ttk.Label(sidebar, text="Smart Organizer", style="Title.TLabel").pack(anchor="w", pady=(4, 4))
        ttk.Label(sidebar, text=f"v{APP_VERSION}").pack(anchor="w", pady=(0, 14))
        for text in ["🏠 Главная", "📂 Файлы", "🤖 Проекты", "🧠 Память ИИ", "🐙 GitHub", "📦 Архивы", "⚙ Настройки"]:
            ttk.Button(sidebar, text=text, style="Nav.TButton", command=lambda t=text: self.show_section(t)).pack(fill="x", pady=3)
        ttk.Separator(sidebar).pack(fill="x", pady=14)
        ttk.Label(sidebar, text="Безопасность:", style="SubTitle.TLabel").pack(anchor="w")
        ttk.Label(sidebar, text="ТОЛЬКО АНАЛИЗ", foreground="#b36b00").pack(anchor="w", pady=(2, 0))
        ttk.Label(sidebar, text="Не удаляет, не переносит\nи не перестраивает папки.", justify="left").pack(anchor="w", pady=(5, 0))

        right = ttk.Frame(outer)
        right.pack(side="left", fill="both", expand=True)
        self.content = ttk.Frame(right)
        self.content.pack(fill="both", expand=True)
        ttk.Separator(right).pack(fill="x", pady=(6, 5))
        ttk.Label(right, textvariable=self.status_var).pack(anchor="w")
        self.show_home()

    def clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def show_section(self, title: str):
        mapping = {
            "🏠 Главная": self.show_home,
            "📂 Файлы": self.show_files,
            "🤖 Проекты": self.show_projects,
            "🧠 Память ИИ": self.show_memory,
            "🐙 GitHub": self.show_github,
            "📦 Архивы": self.show_archives,
            "⚙ Настройки": self.show_settings,
        }
        mapping.get(title, self.show_home)()

    def _monitor_card(self, parent):
        frame = ttk.LabelFrame(parent, text="ПК и интернет сейчас", padding=8)
        frame.pack(side="right", anchor="ne")
        ttk.Label(frame, textvariable=self.monitor_vars["net"], style="Monitor.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=self.monitor_vars["cpu"], style="Monitor.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=self.monitor_vars["ram"], style="Monitor.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=self.monitor_vars["disk"], style="Monitor.TLabel").pack(anchor="w")

    def show_home(self):
        self.clear_content()
        header = ttk.Frame(self.content)
        header.pack(fill="x", pady=(4, 8))
        left = ttk.Frame(header)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="Главная", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="Smart Organizer изучает существующую структуру и предлагает порядок, не ломая ваши папки.").pack(anchor="w", pady=(4, 0))
        self._monitor_card(header)

        cards = ttk.Frame(self.content)
        cards.pack(fill="x", pady=(8, 0))
        self.stats_labels = {}
        items = [("files", "Файлов изучено"), ("folders", "Папок изучено"), ("knowledge", "Знаний в базе"), ("decisions", "Решений запомнено")]
        for idx, (key, title) in enumerate(items):
            frame = ttk.LabelFrame(cards, text=title, padding=14)
            frame.grid(row=0, column=idx, sticky="nsew", padx=4)
            label = ttk.Label(frame, text="0", style="Big.TLabel")
            label.pack()
            self.stats_labels[key] = label
            cards.columnconfigure(idx, weight=1)

        actions = ttk.LabelFrame(self.content, text="Быстрые действия", padding=14)
        actions.pack(fill="x", pady=16)
        ttk.Button(actions, text="🔍 Анализ папки", command=self.pick_and_scan).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="💻 Рабочий стол", command=self.scan_desktop).pack(side="left", padx=8)
        ttk.Button(actions, text="♻ Точные дубликаты", command=self.find_duplicates).pack(side="left", padx=8)
        ttk.Button(actions, text="🔄 Обновления", command=self.check_updates_manual).pack(side="left", padx=8)

        note = ttk.LabelFrame(self.content, text="Что нового в v0.2.0", padding=12)
        note.pack(fill="x")
        ttk.Label(
            note,
            text="• Живые CPU, RAM, диск D: и реальная текущая скорость сети ↓/↑\n"
                 "• Распознавание проектов и существующих папок\n"
                 "• Сравнение версий и кандидаты старых версий\n"
                 "• Точные дубликаты: размер + SHA-256\n"
                 "• Анализ ZIP, RAR и 7Z без распаковки\n"
                 "• Потокобезопасная локальная SQLite-база",
            justify="left",
        ).pack(anchor="w")
        self.refresh_dashboard()

    def _result_box(self) -> ScrolledText:
        box = ScrolledText(self.content, wrap="word", font=("Consolas", 10), height=24)
        box.pack(fill="both", expand=True, pady=(12, 0))
        return box

    def show_files(self):
        self.clear_content()
        ttk.Label(self.content, text="Файлы", style="Title.TLabel").pack(anchor="w", pady=(4, 8))
        ttk.Label(self.content, text="Все действия этого раздела сейчас только анализируют данные.").pack(anchor="w", pady=(0, 10))
        bar = ttk.Frame(self.content)
        bar.pack(fill="x")
        ttk.Button(bar, text="🔍 Выбрать папку", command=self.pick_and_scan).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="♻ Найти точные дубликаты", command=self.find_duplicates).pack(side="left", padx=6)
        ttk.Button(bar, text="📦 Найти старые версии", command=self.find_old_versions).pack(side="left", padx=6)
        ttk.Button(bar, text="📁 Куда положить файл", command=self.preview_destination).pack(side="left", padx=6)
        self.file_results = self._result_box()
        self.file_results.insert("end", "Сначала выполните анализ нужной папки.\n")

    def show_projects(self):
        self.clear_content()
        ttk.Label(self.content, text="Проекты", style="Title.TLabel").pack(anchor="w", pady=(4, 8))
        ttk.Label(self.content, text="Показывает проекты, найденные в последнем снимке. Существующие папки имеют приоритет.").pack(anchor="w", pady=(0, 10))
        ttk.Button(self.content, text="🤖 Проанализировать проекты", command=self.analyze_projects_ui).pack(anchor="w")
        self.project_results = self._result_box()

    def show_archives(self):
        self.clear_content()
        ttk.Label(self.content, text="Архивы", style="Title.TLabel").pack(anchor="w", pady=(4, 8))
        ttk.Label(self.content, text="ZIP анализируется встроенно. Для RAR/7Z используется бесплатный 7-Zip, если он установлен.").pack(anchor="w", pady=(0, 10))
        ttk.Button(self.content, text="📦 Выбрать ZIP / RAR / 7Z", command=self.pick_archive).pack(anchor="w")
        self.archive_results = self._result_box()

    def show_memory(self):
        self.clear_content()
        ttk.Label(self.content, text="Память ИИ", style="Title.TLabel").pack(anchor="w", pady=(4, 8))
        counts = self.db.counts()
        ttk.Label(
            self.content,
            text=f"Локальная база: {self.db.path}\nЗаписей знаний: {counts['knowledge']}\n\n"
                 "База хранится только на вашем ПК. GitHub не содержит вашу накопленную knowledge.db.",
            justify="left",
            wraplength=780,
        ).pack(anchor="w")
        box = self._result_box()
        for project in self.knowledge.get("projects", []):
            box.insert("end", f"{project['name']} | {project.get('type', '')} | {project.get('status', '')}\n  {project.get('notes', '')}\n\n")

    def show_github(self):
        self.clear_content()
        ttk.Label(self.content, text="GitHub", style="Title.TLabel").pack(anchor="w", pady=(4, 8))
        ttk.Label(self.content, text="Репозиторий обновлений: Treninem/Smart-Organizer\nЛокальная data/ при обновлениях не заменяется.").pack(anchor="w", pady=(0, 12))
        ttk.Button(self.content, text="🔄 Проверить и установить обновление", command=self.check_updates_manual).pack(anchor="w")

    def show_settings(self):
        self.clear_content()
        ttk.Label(self.content, text="Настройки", style="Title.TLabel").pack(anchor="w", pady=(4, 8))
        ttk.Label(
            self.content,
            text="Безопасный режим: ВКЛЮЧЁН\nПриоритет существующей структуры: ВКЛЮЧЁН\n"
                 "Автоудаление: ВЫКЛЮЧЕНО\nАвтоперемещение: ВЫКЛЮЧЕНО\n"
                 "Монитор ПК/сети: ВКЛЮЧЁН\n\nЭти ограничения специально сохраняются на этапе v0.2.0.",
            justify="left",
        ).pack(anchor="w")

    def refresh_dashboard(self):
        counts = self.db.counts()
        if hasattr(self, "stats_labels"):
            for key, label in self.stats_labels.items():
                label.configure(text=f"{counts.get(key, 0):,}".replace(",", " "))

    def _monitor_loop(self):
        while not self.monitor_stop.is_set():
            try:
                sample = self.monitor.sample()
                self.after(0, lambda s=sample: self._apply_monitor_sample(s))
            except Exception:
                pass
            self.monitor_stop.wait(1.5)

    def _apply_monitor_sample(self, sample: dict):
        self.monitor_vars["net"].set(f"Сеть ↓ {sample['download_text']}   ↑ {sample['upload_text']}")
        self.monitor_vars["cpu"].set(f"CPU {_percent(sample['cpu_percent'])}")
        ram_used = _human_size(sample["memory_used"]) if sample.get("memory_used") is not None else "—"
        ram_total = _human_size(sample["memory_total"]) if sample.get("memory_total") is not None else "—"
        self.monitor_vars["ram"].set(f"RAM {_percent(sample['memory_percent'])}  {ram_used} / {ram_total}")
        disk_name = Path(self.monitor.disk_path).drive or self.monitor.disk_path
        self.monitor_vars["disk"].set(f"Диск {disk_name} {_percent(sample['disk_percent'])}  свободно {sample['disk_free_text']}")

    def _start_worker(self, label: str, fn, done):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Smart Organizer", "Другой анализ уже выполняется.")
            return
        self.status_var.set(label)

        def run():
            try:
                result = fn()
                self.after(0, lambda: done(result))
            except Exception as exc:
                self.db.log_action("worker", label, "error", str(exc))
                self.after(0, lambda: self._worker_failed(str(exc)))

        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()

    def _worker_failed(self, error: str):
        self.status_var.set("Операция завершилась с ошибкой.")
        messagebox.showerror("Smart Organizer", error)

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
        def work():
            result = scan_tree(root, self.knowledge.get("projects", []))
            self.db.replace_scan(result.folders, result.files)
            self.db.set_setting("last_scan_root", str(root))
            self.db.log_action("scan", str(root), "ok", json.dumps(result.summary, ensure_ascii=False))
            return result.summary

        def done(summary):
            text = (
                f"Готово: {summary['files']} файлов, {summary['folders']} папок, "
                f"{_human_size(summary['bytes'])}, ошибок доступа: {summary['errors']}. "
                "Ничего не перемещено и не удалено."
            )
            self.status_var.set(text)
            if hasattr(self, "file_results"):
                self.file_results.delete("1.0", "end")
                self.file_results.insert("end", text + "\n")
            self.refresh_dashboard()

        self._start_worker(f"Анализ: {root}", work, done)

    def find_duplicates(self):
        records = self.db.snapshot_files()
        if not records:
            messagebox.showinfo("Дубликаты", "Сначала проанализируйте папку.")
            return

        def done(groups):
            self.status_var.set(f"Точных групп дубликатов: {len(groups)}")
            if not hasattr(self, "file_results"):
                self.show_files()
            self.file_results.delete("1.0", "end")
            if not groups:
                self.file_results.insert("end", "Точных дубликатов по SHA-256 не найдено.\n")
                return
            total_reclaim = 0
            for group in groups:
                reclaim = group["size"] * len(group["duplicates"])
                total_reclaim += reclaim
                self.file_results.insert(
                    "end",
                    f"SHA-256: {group['sha256']}\nРазмер: {_human_size(group['size'])}\n"
                    f"Предлагаемый оригинал: {group['canonical']}\nТочные копии:\n  - "
                    + "\n  - ".join(group["duplicates"]) + "\n\n",
                )
            self.file_results.insert("end", f"Потенциально освобождаемо после подтверждения: {_human_size(total_reclaim)}\n")
            self.db.log_action("duplicates", None, "ok", f"groups={len(groups)}")

        self._start_worker("Считаю SHA-256 только для файлов одинакового размера…", lambda: exact_duplicate_groups(records), done)

    def find_old_versions(self):
        groups = version_groups(self.db.snapshot_files())
        if not hasattr(self, "file_results"):
            self.show_files()
        self.file_results.delete("1.0", "end")
        if not groups:
            self.file_results.insert("end", "Групп с несколькими распознанными версиями не найдено.\n")
            return
        for group in groups:
            self.file_results.insert(
                "end",
                f"{group['project']} / {group['artifact']}\n  Новейшая по имени: {group['newest']}\n"
                f"  {group['newest_path']}\n  Более старые кандидаты:\n",
            )
            for old in group["older"]:
                self.file_results.insert("end", f"    {old['version']} -> {old['path']}\n")
            self.file_results.insert("end", "\n")
        self.status_var.set(f"Найдено групп версий: {len(groups)}. Удаление не выполнялось.")

    def preview_destination(self):
        path = filedialog.askopenfilename(title="Выберите файл для предварительного решения")
        if not path:
            return
        files = self.db.snapshot_files()
        folders = self.db.snapshot_folders()
        record = next((x for x in files if os.path.normcase(x["path"]) == os.path.normcase(path)), None)
        if record is None:
            p = Path(path)
            st = p.stat()
            from core.classifier import category_for, project_hint
            record = {
                "path": str(p),
                "parent": str(p.parent),
                "name": p.name,
                "extension": p.suffix.lower(),
                "size": st.st_size,
                "modified": st.st_mtime,
                "category": category_for(p),
                "project_hint": project_hint(p, self.knowledge.get("projects", [])),
            }
        suggestion = suggest_destination(record, folders, self.knowledge.get("projects", []), self.db.get_setting("last_scan_root"))
        if not hasattr(self, "file_results"):
            self.show_files()
        self.file_results.delete("1.0", "end")
        if suggestion["mode"] == "existing":
            self.file_results.insert(
                "end",
                f"НАЙДЕНА СУЩЕСТВУЮЩАЯ ПАПКА — программа предпочитает её:\n\n{suggestion['path']}\n\nФайл НЕ перемещён.",
            )
        else:
            self.file_results.insert(
                "end",
                f"Совпадения в существующем дереве не найдено.\nВ будущем программа сможет предложить создать:\n\n"
                f"{suggestion['path']}\n\nСейчас папка НЕ создана и файл НЕ перемещён.",
            )

    def analyze_projects_ui(self):
        summaries = summarize_projects(self.db.snapshot_files(), self.db.snapshot_folders(), self.knowledge.get("projects", []))
        self.project_results.delete("1.0", "end")
        if not summaries:
            self.project_results.insert("end", "Проекты пока не распознаны. Сначала выполните анализ папки или диска.\n")
            return
        for item in summaries:
            self.project_results.insert(
                "end",
                f"{item['name']} [{item['status']}]\nТип: {item['type']}\nGitHub: {item['repository'] or 'не задан'}\n"
                f"Файлов: {item['file_count']}\nВерсии: {', '.join(item['versions']) if item['versions'] else 'не распознаны'}\n"
                "Существующие папки:\n",
            )
            for folder in item["folders"] or ["не найдены по имени"]:
                self.project_results.insert("end", f"  - {folder}\n")
            self.project_results.insert("end", "\n")
        self.status_var.set(f"Распознано проектов: {len(summaries)}")

    def pick_archive(self):
        path = filedialog.askopenfilename(
            title="Выберите архив",
            filetypes=[("Архивы", "*.zip *.rar *.7z"), ("Все файлы", "*.*")],
        )
        if not path:
            return

        def done(result):
            self.archive_results.delete("1.0", "end")
            self.archive_results.insert(
                "end",
                f"Архив: {result['path']}\nФормат: {result['format']} ({result['engine']})\n"
                f"Файлов внутри: {result['entries']}\nРазмер распакованного содержимого: {_human_size(result['uncompressed_bytes'])}\n"
                f"Проект: {result['project_hint'] or 'не определён'}\nВерсия: {result['version'] or 'не определена'}\n\nРасширения:\n",
            )
            for ext, count in result["top_extensions"]:
                self.archive_results.insert("end", f"  {ext}: {count}\n")
            self.archive_results.insert("end", "\nПервые элементы:\n")
            for name in result["sample"]:
                self.archive_results.insert("end", f"  {name}\n")
            self.archive_results.insert("end", "\nАрхив не распаковывался и не изменялся.\n")
            self.status_var.set("Архив проанализирован без распаковки.")
            self.db.log_action("archive-analysis", path, "ok", json.dumps(result, ensure_ascii=False))

        self._start_worker(f"Анализ архива: {path}", lambda: analyze_archive(Path(path), self.knowledge.get("projects", [])), done)

    def check_updates_silent(self):
        def worker():
            try:
                manifest = fetch_manifest()
                if update_available(APP_VERSION, manifest):
                    changed = apply_source_update(app_root(), manifest)
                    version = manifest.get("version")
                    self.db.log_action("update", str(version), "ok", f"updated={len(changed)}")
                    self.after(0, lambda: self.status_var.set(f"Обновление {version} установлено. Полностью включится при следующем запуске."))
            except Exception as exc:
                self.db.log_action("update", None, "error", str(exc))
        threading.Thread(target=worker, daemon=True).start()

    def check_updates_manual(self):
        def work():
            manifest = fetch_manifest()
            if update_available(APP_VERSION, manifest):
                changed = apply_source_update(app_root(), manifest)
                return (
                    f"Версия {manifest.get('version')} установлена ({len(changed)} файлов). "
                    "Полностью включится при следующем запуске. Локальная data/ сохранена."
                )
            return "Установлена актуальная версия."

        def done(msg):
            self.status_var.set(msg)
            messagebox.showinfo("Обновления", msg)

        self._start_worker("Проверяю GitHub…", work, done)

    def on_close(self):
        self.monitor_stop.set()
        self.db.close()
        self.destroy()
