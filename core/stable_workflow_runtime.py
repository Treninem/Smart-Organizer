from __future__ import annotations

import json
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.duplicates import exact_duplicate_groups
from core.operation_executor import execute_batch, undo_batch
from core.operation_journal import OperationJournal
from core.plan_bridge import operations_from_confirmed_sort_plan
from core.scanner import scan_tree
from core.sort_planner import build_sort_plan


def _human_size(value: int) -> str:
    size = float(max(0, int(value)))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def install_stable_workflow_runtime(main_window) -> None:
    """Replace button-heavy experimental screens with one reliable workflow."""
    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_stable_workflow_runtime_installed", False):
        return
    cls._stable_workflow_runtime_installed = True

    def _current_plan(self) -> dict:
        return build_sort_plan(
            self.db.snapshot_files(),
            self.db.snapshot_folders(),
            self.knowledge.get("projects", []),
            self.db.get_setting("last_scan_root"),
        )

    def _render_plan(self, plan: dict) -> None:
        if not hasattr(self, "file_results") or not self.file_results.winfo_exists():
            return
        box = self.file_results
        box.configure(state="normal")
        box.delete("1.0", "end")
        summary = plan["summary"]
        protected = bool(summary.get("protected_project_root"))
        box.insert(
            "end",
            "ПЛАН ПОРЯДКА\n\n"
            f"Файлов изучено: {summary['files_considered']}\n"
            f"Оставить на месте: {summary['already_placed']}\n"
            f"Можно переместить: {summary['moves_suggested']}\n"
            f"В существующие папки: {summary['existing_folder_targets']}\n"
            f"Нужно создать папки: {summary['new_folder_targets']}\n",
        )
        if protected:
            box.insert(
                "end",
                "\nВыбранная папка похожа на корень проекта. Её внутренняя структура защищена и не будет перестраиваться.\n",
            )
        box.insert("end", "\n")

        for item in plan.get("items", [])[:120]:
            mode = "существующая папка" if item.get("mode") == "existing" else "новая папка после подтверждения"
            box.insert(
                "end",
                f"• {item.get('source', '')}\n"
                f"  → {item.get('target_path', '')}\n"
                f"  {mode}\n\n",
            )
        if len(plan.get("items", [])) > 120:
            box.insert("end", f"… ещё {len(plan['items']) - 120} предложений\n")
        box.insert(
            "end",
            "\nЗащита: существующие проектные деревья не перестраиваются; одинаковые main.py/config.json в разных проектах "
            "не объединяются; целевые файлы никогда не перезаписываются.\n",
        )

    def _rescan_snapshot(self, root_text: str | None):
        if not root_text:
            return None
        refreshed = scan_tree(Path(root_text), self.knowledge.get("projects", []))
        self.db.replace_scan(refreshed.folders, refreshed.files)
        return refreshed

    def scan_and_prepare(self) -> None:
        selected = filedialog.askdirectory(title="Выберите папку или диск, где нужно навести порядок")
        if not selected:
            return
        root = Path(selected)

        def work():
            result = scan_tree(root, self.knowledge.get("projects", []))
            self.db.replace_scan(result.folders, result.files)
            self.db.set_setting("last_scan_root", str(root))
            self.db.log_action("scan", str(root), "ok", json.dumps(result.summary, ensure_ascii=False))
            plan = build_sort_plan(result.files, result.folders, self.knowledge.get("projects", []), str(root))
            return result.summary, plan

        def done(payload):
            summary, plan = payload
            self._last_sort_plan = plan
            self.refresh_dashboard()
            self._render_stable_files_screen()
            self._render_plan(plan)
            self.status_var.set(
                f"Анализ завершён: {summary['files']} файлов, {summary['folders']} папок. План готов."
            )

        self._start_worker(f"Анализирую {root}…", work, done)

    def organize_current(self) -> None:
        records = self.db.snapshot_files()
        if not records:
            self.scan_and_prepare()
            return

        plan = _current_plan(self)
        self._last_sort_plan = plan
        self._render_plan(plan)
        if not plan.get("items"):
            if plan["summary"].get("protected_project_root"):
                messagebox.showinfo(
                    "Навести порядок",
                    "Эта папка распознана как проект. Smart Organizer не перестраивает рабочую структуру проекта.",
                )
            else:
                messagebox.showinfo("Навести порядок", "Перемещать нечего: файлы уже лежат подходяще.")
            return

        try:
            operations = operations_from_confirmed_sort_plan(plan)
        except ValueError as exc:
            messagebox.showwarning(
                "План остановлен",
                "Обнаружен конфликт целевых путей. Ничего не перемещено.\n\n" + str(exc),
            )
            self.status_var.set("План остановлен из-за конфликта. Файлы не изменены.")
            return

        mkdir_count = sum(1 for item in operations if item.op_type == "mkdir")
        move_count = sum(1 for item in operations if item.op_type == "move")
        preview = "\n".join(
            f"• {item.get('source')}\n  → {item.get('target_path')}"
            for item in plan.get("items", [])[:8]
        )
        if len(plan.get("items", [])) > 8:
            preview += f"\n… и ещё {len(plan['items']) - 8}"

        confirmed = messagebox.askyesno(
            "Применить порядок",
            f"Будет перемещено файлов: {move_count}.\n"
            f"Будет создано папок: {mkdir_count}.\n\n{preview}\n\n"
            "Существующая структура проектов защищена. Существующие файлы не перезаписываются. "
            "Все действия журналируются и доступны для Undo. Применить?",
        )
        if not confirmed:
            self.status_var.set("План показан, но не применён.")
            return

        journal = OperationJournal(self.db)
        batch_id = journal.plan_batch(operations, label="confirmed-organize")
        root_text = self.db.get_setting("last_scan_root")

        def work():
            result = execute_batch(journal, batch_id)
            refreshed = _rescan_snapshot(self, root_text)
            return result, refreshed

        def done(payload):
            result, _refreshed = payload
            self.db.log_action("organize-apply", batch_id, "ok", f"applied={result['applied']}")
            self.refresh_dashboard()
            self._render_stable_files_screen()
            if self.db.snapshot_files():
                self._render_plan(_current_plan(self))
            self.status_var.set(f"Порядок применён: выполнено операций {result['applied']}. Undo доступен.")

        self._start_worker("Применяю подтверждённый план…", work, done)

    def find_exact_duplicates_stable(self) -> None:
        records = self.db.snapshot_files()
        if not records:
            self.scan_and_prepare()
            return
        scan_root = self.db.get_setting("last_scan_root")

        def done(groups):
            self._render_stable_files_screen()
            box = self.file_results
            box.configure(state="normal")
            box.delete("1.0", "end")
            if not groups:
                box.insert(
                    "end",
                    "Точных безопасных дубликатов не найдено.\n\n"
                    "Одинаковые main.py, config.json, изображения и другие файлы в разных проектах специально считаются независимыми.",
                )
                self.status_var.set("Безопасных точных дубликатов не найдено.")
                return
            reclaim = 0
            for group in groups:
                reclaim += group["size"] * len(group["duplicates"])
                box.insert(
                    "end",
                    f"Оригинал: {group['canonical']}\n"
                    f"SHA-256: {group['sha256']}\n"
                    f"Точные копии внутри одного проектного контекста:\n  - "
                    + "\n  - ".join(group["duplicates"])
                    + "\n\n",
                )
            box.insert("end", f"Потенциально освобождаемо после отдельного подтверждения: {_human_size(reclaim)}\n")
            self.status_var.set(f"Найдено безопасных групп точных дубликатов: {len(groups)}.")

        self._start_worker(
            "Проверяю содержимое файлов и проектные границы…",
            lambda: exact_duplicate_groups(records, scan_root),
            done,
        )

    def undo_last_stable(self) -> None:
        entries = self.db.operation_entries(limit=5000)
        batch_id = None
        for row in entries:
            if row.get("status") == "applied" and row.get("batch_id"):
                batch_id = row["batch_id"]
                break
        if not batch_id:
            messagebox.showinfo("Undo", "Нет применённого пакета для отмены.")
            return
        if not messagebox.askyesno("Undo", "Отменить последний применённый пакет действий?"):
            return
        root_text = self.db.get_setting("last_scan_root")

        def work():
            result = undo_batch(OperationJournal(self.db), batch_id)
            refreshed = _rescan_snapshot(self, root_text)
            return result, refreshed

        def done(payload):
            result, _refreshed = payload
            self.refresh_dashboard()
            self._render_stable_files_screen()
            if self.db.snapshot_files():
                self._render_plan(_current_plan(self))
            self.status_var.set(f"Undo выполнен: отменено операций {result['undone']}.")

        self._start_worker("Отменяю последний пакет…", work, done)

    def _render_stable_files_screen(self) -> None:
        self.clear_content()
        ttk.Label(self.content, text="Навести порядок", style="Title.TLabel").pack(anchor="w", pady=(4, 6))
        root = self.db.get_setting("last_scan_root")
        counts = self.db.counts()
        ttk.Label(
            self.content,
            text=(
                f"Область: {root or 'не выбрана'}\n"
                f"Изучено: {counts.get('files', 0)} файлов, {counts.get('folders', 0)} папок.\n"
                "Рабочий процесс: анализ → план → подтверждение → выполнение → Undo."
            ),
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        actions = ttk.Frame(self.content)
        actions.pack(fill="x")
        ttk.Button(actions, text="1  Выбрать и анализировать", command=self.scan_and_prepare).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="2  Навести порядок", command=self.organize_current).pack(side="left", padx=8)
        ttk.Button(actions, text="Точные дубликаты", command=self.find_exact_duplicates_stable).pack(side="left", padx=8)
        ttk.Button(actions, text="Undo", command=self.undo_last_stable).pack(side="left", padx=8)

        self.file_results = self._result_box()
        if counts.get("files", 0):
            self.file_results.insert("end", "Нажмите «Навести порядок», чтобы увидеть и подтвердить реальный план перемещений.\n")
        else:
            self.file_results.insert("end", "Сначала нажмите «Выбрать и анализировать».\n")

    def show_files(self) -> None:
        self._render_stable_files_screen()

    def show_home(self) -> None:
        self.clear_content()
        ttk.Label(self.content, text="Smart Organizer", style="Title.TLabel").pack(anchor="w", pady=(4, 4))
        ttk.Label(
            self.content,
            text="Один рабочий сценарий вместо набора тестовых кнопок.",
            style="SubTitle.TLabel",
        ).pack(anchor="w", pady=(0, 14))

        counts = self.db.counts()
        root = self.db.get_setting("last_scan_root")
        card = ttk.LabelFrame(self.content, text="Текущее состояние", padding=14)
        card.pack(fill="x", pady=(0, 14))
        ttk.Label(
            card,
            text=(
                f"Область: {root or 'ещё не выбрана'}\n"
                f"Файлов: {counts.get('files', 0)}   Папок: {counts.get('folders', 0)}   "
                f"Знаний: {counts.get('knowledge', 0)}"
            ),
            justify="left",
        ).pack(anchor="w")

        actions = ttk.LabelFrame(self.content, text="Главное", padding=14)
        actions.pack(fill="x")
        ttk.Button(actions, text="Выбрать папку / диск", command=self.scan_and_prepare).pack(side="left", padx=(0, 10))
        ttk.Button(actions, text="Навести порядок", command=self.organize_current).pack(side="left", padx=10)
        ttk.Button(actions, text="Undo", command=self.undo_last_stable).pack(side="left", padx=10)

        info = self._result_box()
        info.insert(
            "end",
            "Как работает:\n"
            "1. Изучает существующую структуру.\n"
            "2. Не перестраивает рабочие папки проектов.\n"
            "3. Свободные файлы направляет в подходящие существующие папки.\n"
            "4. Если подходящей папки нет — предлагает создать новую и ждёт подтверждения.\n"
            "5. Перед первым перемещением проверяет весь пакет.\n"
            "6. Любой применённый пакет можно отменить через Undo.\n"
            "7. Дубликаты проверяются по SHA-256 и только внутри одного проектного контекста.\n",
        )

    def show_settings(self) -> None:
        self.clear_content()
        ttk.Label(self.content, text="Настройки", style="Title.TLabel").pack(anchor="w", pady=(4, 8))
        ttk.Label(
            self.content,
            text=(
                f"Версия: v{main_window.APP_VERSION}\n"
                "Защита проектных папок: ВКЛЮЧЕНА\n"
                "Перезапись существующих файлов: ЗАПРЕЩЕНА\n"
                "Автоматическое удаление: ВЫКЛЮЧЕНО\n"
                "Undo: ВКЛЮЧЕН\n"
                f"Автопроверка обновлений: {'ВКЛЮЧЕНА' if getattr(self, 'auto_update_enabled', True) else 'ВЫКЛЮЧЕНА'}"
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 14))

        actions = ttk.LabelFrame(self.content, text="Служебные действия", padding=12)
        actions.pack(fill="x")
        if hasattr(self, "check_updates_manual"):
            ttk.Button(actions, text="Проверить обновления", command=self.check_updates_manual).pack(side="left", padx=(0, 8))
        if hasattr(self, "show_diagnostics"):
            ttk.Button(actions, text="Диагностика", command=self.show_diagnostics).pack(side="left", padx=8)
        ttk.Button(actions, text="Undo последнего пакета", command=self.undo_last_stable).pack(side="left", padx=8)

        ttk.Label(
            self.content,
            text=(
                "Основной режим намеренно простой: программа не делает скрытых изменений. "
                "Организация выполняется одной командой «Навести порядок» после показа плана и подтверждения."
            ),
            wraplength=820,
            justify="left",
        ).pack(anchor="w", pady=(16, 0))

    cls._current_plan = _current_plan
    cls._render_plan = _render_plan
    cls._rescan_snapshot = _rescan_snapshot
    cls.scan_and_prepare = scan_and_prepare
    cls.organize_current = organize_current
    cls.find_exact_duplicates_stable = find_exact_duplicates_stable
    cls.undo_last_stable = undo_last_stable
    cls._render_stable_files_screen = _render_stable_files_screen
    cls.show_files = show_files
    cls.show_home = show_home
    cls.show_settings = show_settings
