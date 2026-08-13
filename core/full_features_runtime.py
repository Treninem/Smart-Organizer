from __future__ import annotations

from pathlib import Path
from tkinter import messagebox, ttk

from core.duplicate_insights import duplicate_candidate_groups
from core.duplicates import exact_duplicate_groups
from core.folder_tree import render_folder_tree
from core.local_ai import analyze_local_snapshot
from core.operation_journal import OperationJournal, ReversibleOperation
from core.project_templates import summarize_template_matches


def _human_size(value: int) -> str:
    size = float(max(0, int(value)))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _quarantine_name(digest: str, index: int, source: str) -> str:
    path = Path(source)
    suffix = path.suffix[:20]
    stem = path.stem[:150] or "file"
    return f"{digest[:12]}_{index:04d}_{stem}{suffix}"


def install_full_features_runtime(main_window) -> None:
    """Expose remaining safe TЗ analysis tools in the desktop UI."""
    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_full_features_runtime_installed", False):
        return
    cls._full_features_runtime_installed = True

    original_show_files = cls.show_files
    original_show_projects = cls.show_projects

    def _ensure_results(self):
        if not hasattr(self, "file_results") or not self.file_results.winfo_exists():
            original_show_files(self)
        return self.file_results

    def show_folder_tree(self) -> None:
        folders = self.db.snapshot_folders()
        if not folders:
            messagebox.showinfo("Дерево папок", "Сначала проанализируйте Рабочий стол, Загрузки, диск или папку.")
            return
        box = _ensure_results(self)
        box.configure(state="normal")
        box.delete("1.0", "end")
        root = self.db.get_setting("last_scan_root")
        box.insert("end", f"ДЕРЕВО ПОСЛЕДНЕГО СКАНИРОВАНИЯ\nКорень: {root or 'не указан'}\n\n")
        box.insert("end", render_folder_tree(folders, root))
        box.insert("end", "\n\nСтруктура только показана. Папки не создавались, не переносились и не удалялись.\n")
        self.status_var.set(f"Показано дерево папок: {len(folders)} элементов.")

    def show_duplicate_candidates(self) -> None:
        records = self.db.snapshot_files()
        if not records:
            messagebox.showinfo("Кандидаты дублей", "Сначала выполните анализ папки или диска.")
            return
        report = duplicate_candidate_groups(records)
        box = _ensure_results(self)
        box.configure(state="normal")
        box.delete("1.0", "end")
        summary = report["summary"]
        box.insert(
            "end",
            "КАНДИДАТЫ ДУБЛИКАТОВ — БЕЗ УДАЛЕНИЯ\n\n"
            f"Файлов: {summary['files']}\n"
            f"Групп по похожему имени: {summary['same_name_groups']}\n"
            f"Групп одинакового размера: {summary['same_size_groups']}\n\n"
            "Совпадение имени или размера НЕ означает, что файлы одинаковые. "
            "Удаление допустимо только после полного совпадения SHA-256 и отдельного подтверждения.\n\n",
        )
        if report["name_groups"]:
            box.insert("end", "ПОХОЖИЕ ИМЕНА\n")
            for group in report["name_groups"][:80]:
                box.insert("end", f"\n{group['key']} | файлов: {group['count']}\n")
                for path in group["paths"][:12]:
                    box.insert("end", f"  • {path}\n")
                if len(group["paths"]) > 12:
                    box.insert("end", f"  … ещё {len(group['paths']) - 12}\n")
        if report["size_groups"]:
            box.insert("end", "\nОДИНАКОВЫЙ РАЗМЕР — НУЖЕН SHA-256\n")
            for group in report["size_groups"][:60]:
                box.insert("end", f"\n{_human_size(group['size'])} | файлов: {group['count']}\n")
                for path in group["paths"][:8]:
                    box.insert("end", f"  • {path}\n")
                if len(group["paths"]) > 8:
                    box.insert("end", f"  … ещё {len(group['paths']) - 8}\n")
        self.status_var.set(
            f"Кандидаты дублей: по имени {summary['same_name_groups']}, по размеру {summary['same_size_groups']}. Файлы не изменены."
        )

    def queue_exact_duplicate_quarantine(self) -> None:
        records = self.db.snapshot_files()
        if not records:
            messagebox.showinfo("Карантин дублей", "Сначала выполните анализ папки или диска.")
            return

        def done(groups):
            if not groups:
                messagebox.showinfo("Карантин дублей", "Точных дубликатов по полному SHA-256 не найдено.")
                self.status_var.set("Точных дубликатов для карантина не найдено.")
                return

            duplicate_count = sum(len(group["duplicates"]) for group in groups)
            reclaim = sum(group["size"] * len(group["duplicates"]) for group in groups)
            preview_lines: list[str] = []
            for group in groups[:6]:
                preview_lines.append(f"Оставить: {group['canonical']}")
                for duplicate in group["duplicates"][:3]:
                    preview_lines.append(f"  в карантин: {duplicate}")
                if len(group["duplicates"]) > 3:
                    preview_lines.append(f"  … ещё {len(group['duplicates']) - 3}")
            if len(groups) > 6:
                preview_lines.append(f"… ещё групп: {len(groups) - 6}")

            if not messagebox.askyesno(
                "Записать точные дубликаты в журнал",
                f"Полным SHA-256 подтверждено копий: {duplicate_count}.\n"
                f"Размер копий: {_human_size(reclaim)}.\n\n"
                + "\n".join(preview_lines)
                + "\n\nСейчас файлы НЕ будут перемещены. Создать обратимый пакет карантина в журнале?",
            ):
                self.status_var.set("Карантин дублей отменён. Файлы не изменены.")
                return

            quarantine = Path(self.paths["data"]) / "quarantine"
            operations: list[ReversibleOperation] = []
            if not quarantine.exists():
                operations.append(
                    ReversibleOperation("mkdir", str(quarantine), None, "confirmed duplicate quarantine folder")
                )

            used_targets: set[str] = set()
            counter = 1
            for group in groups:
                digest = str(group["sha256"])
                for duplicate in group["duplicates"]:
                    while True:
                        target = quarantine / _quarantine_name(digest, counter, duplicate)
                        counter += 1
                        key = str(target).casefold()
                        if key not in used_targets and not target.exists():
                            used_targets.add(key)
                            break
                    operations.append(
                        ReversibleOperation(
                            "delete-to-quarantine",
                            str(duplicate),
                            str(target),
                            f"exact SHA-256 duplicate of {group['canonical']}",
                        )
                    )

            journal = OperationJournal(self.db)
            batch_id = journal.plan_batch(operations, label="exact-duplicate-quarantine")
            self.db.log_action(
                "duplicate-quarantine-plan",
                batch_id,
                "ok",
                f"exact_duplicates={duplicate_count}; bytes={reclaim}; filesystem_changes=0",
            )
            box = _ensure_results(self)
            box.configure(state="normal")
            box.insert(
                "end",
                f"\n\nПАКЕТ КАРАНТИНА СОЗДАН\nID: {batch_id}\n"
                f"Точных копий: {duplicate_count}\nРазмер: {_human_size(reclaim)}\n"
                "Файлы пока не изменены. Для выполнения откройте Настройки → Журнал безопасности и Undo → "
                "Применить последний пакет. После применения доступен Undo.\n",
            )
            self.status_var.set(
                f"Точные дубликаты записаны в журнал: {duplicate_count}. Выполнение требует отдельного подтверждения."
            )

        self._start_worker(
            "Полностью проверяю SHA-256 перед созданием карантина…",
            lambda: exact_duplicate_groups(records),
            done,
        )

    def show_smart_brain_overview(self) -> None:
        records = self.db.snapshot_files()
        if not records:
            messagebox.showinfo("Smart Brain", "Сначала выполните анализ папки или диска.")
            return
        report = analyze_local_snapshot(records, self.knowledge.get("templates", []))
        summary = report["summary"]
        box = _ensure_results(self)
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert(
            "end",
            "SMART BRAIN — ЛОКАЛЬНЫЙ УМНЫЙ ОБЗОР\n"
            "Работает на вашем ПК, без сетевого ИИ и платных API.\n\n"
            f"Файлов изучено: {summary['files']}\n"
            f"Оставить без вмешательства: {summary['keep']}\n"
            f"Новейших распознанных версий: {summary['newest_versions']}\n"
            f"Кандидатов старых версий: {summary['old_version_candidates']}\n"
            f"Кандидатов копий по имени: {summary['copy_name_candidates']}\n"
            f"Файлов с распознанным проектом: {summary['known_project_files']}\n"
            f"Без проекта: {summary['unknown_project_files']}\n"
            f"Удалить без SHA-256: {summary['delete_without_sha256']}\n\n",
        )
        box.insert("end", "КАТЕГОРИИ\n")
        for name, count in report["categories"]:
            box.insert("end", f"  • {name}: {count}\n")
        box.insert("end", "\nПРОЕКТЫ\n")
        for name, count in report["projects"]:
            box.insert("end", f"  • {name}: {count}\n")
        if report["template_matches"]:
            box.insert("end", "\nШАБЛОНЫ ТИПОВ ПРОЕКТОВ\n")
            for name, count in report["template_matches"]:
                box.insert("end", f"  • {name}: признаков в {count} файлах/путях\n")
        if report["version_groups"]:
            box.insert("end", "\nВЕРСИИ ДЛЯ ПРОВЕРКИ\n")
            for group in report["version_groups"][:60]:
                box.insert(
                    "end",
                    f"  • {group['project']} / {group['artifact']}: новейшая {group['newest']}, "
                    f"старых кандидатов {len(group['older'])}\n",
                )
        box.insert(
            "end",
            "\nSmart Brain ничего не удалил и не переместил. Кандидаты старых версий и копий — только подсказки; "
            "точные дубликаты подтверждаются полным SHA-256.\n",
        )
        self.status_var.set("Smart Brain построил локальный обзор. Изменений файловой системы: 0.")

    def show_project_templates(self) -> None:
        templates = self.knowledge.get("templates", [])
        if not hasattr(self, "project_results") or not self.project_results.winfo_exists():
            original_show_projects(self)
        box = self.project_results
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert(
            "end",
            "ШАБЛОНЫ РАСПОЗНАВАНИЯ ПРОЕКТОВ\n"
            "Шаблоны помогают определить тип неизвестного проекта, но никогда не перестраивают существующие папки.\n\n",
        )
        matches = dict(summarize_template_matches(self.db.snapshot_files(), templates))
        for template in templates:
            name = template.get("name", "Без имени")
            box.insert(
                "end",
                f"{name} [{template.get('type', '')}]\n"
                f"Совпадений в последнем снимке: {matches.get(name, 0)}\n"
                f"Ключевые слова: {', '.join(template.get('keywords', []))}\n"
                f"Маркеры: {', '.join(template.get('markers', []))}\n\n",
            )
        self.status_var.set(f"Доступно шаблонов проектов: {len(templates)}.")

    def show_files(self) -> None:
        original_show_files(self)
        extra = ttk.Frame(self.content)
        try:
            extra.pack(fill="x", pady=(8, 0), before=self.file_results)
        except Exception:
            extra.pack(fill="x", pady=(8, 0))
        ttk.Label(extra, text="Дополнительный анализ:", style="SubTitle.TLabel").pack(side="left", padx=(0, 8))
        ttk.Button(extra, text="🌳 Дерево папок", command=self.show_folder_tree).pack(side="left", padx=4)
        ttk.Button(extra, text="🔎 Кандидаты дублей", command=self.show_duplicate_candidates).pack(side="left", padx=4)
        ttk.Button(extra, text="🧠 Умный обзор", command=self.show_smart_brain_overview).pack(side="left", padx=4)
        ttk.Button(extra, text="🛡 Точные дубли → карантин", command=self.queue_exact_duplicate_quarantine).pack(side="left", padx=4)

    def show_projects(self) -> None:
        original_show_projects(self)
        controls = ttk.Frame(self.content)
        try:
            controls.pack(fill="x", pady=(8, 0), before=self.project_results)
        except Exception:
            controls.pack(fill="x", pady=(8, 0))
        ttk.Button(controls, text="🧩 Шаблоны типов проектов", command=self.show_project_templates).pack(side="left")

    cls.show_folder_tree = show_folder_tree
    cls.show_duplicate_candidates = show_duplicate_candidates
    cls.queue_exact_duplicate_quarantine = queue_exact_duplicate_quarantine
    cls.show_smart_brain_overview = show_smart_brain_overview
    cls.show_project_templates = show_project_templates
    cls.show_files = show_files
    cls.show_projects = show_projects
