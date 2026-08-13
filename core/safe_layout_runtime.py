from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from core.operation_executor import execute_batch
from core.operation_journal import OperationJournal
from core.plan_bridge import operations_from_confirmed_sort_plan
from core.scanner import scan_tree
from core.sort_planner import build_sort_plan


def safe_executable_items(plan: dict) -> list[dict]:
    """Return only high-confidence moves into already existing folders."""
    result: list[dict] = []
    for item in plan.get("items", []):
        if item.get("mode") != "existing":
            continue
        if item.get("confidence") != "high":
            continue
        if item.get("requires_confirmation"):
            continue
        if not str(item.get("target_dir") or "").strip():
            continue
        if not str(item.get("target_path") or "").strip():
            continue
        result.append(dict(item))
    return result


def confirmed_creation_items(plan: dict) -> list[dict]:
    """Return only explicit high-confidence grouping proposals.

    These are different from ordinary low-confidence new-folder guesses: the
    planner marks them executable only when a strong version-family rule was
    satisfied, and they still require the user's confirmation in the same main
    workflow before a directory can be created.
    """
    result: list[dict] = []
    for item in plan.get("items", []):
        if not item.get("allow_confirmed_creation"):
            continue
        if item.get("confidence") != "high":
            continue
        if not str(item.get("target_dir") or "").strip():
            continue
        if not str(item.get("target_path") or "").strip():
            continue
        result.append(dict(item))
    return result


def _reason_text(item: dict) -> str:
    evidence = [str(value) for value in item.get("evidence", []) if str(value).strip()]
    if evidence:
        return "; ".join(evidence)
    reason = str(item.get("reason") or "")
    if reason.startswith("user_layout:"):
        return reason.split(":", 1)[1].strip()
    return "совпадение с существующей пользовательской структурой"


def install_safe_layout_runtime(main_window) -> None:
    """Make the main organizer conservative enough for real user data."""
    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_safe_layout_runtime_installed", False):
        return
    cls._safe_layout_runtime_installed = True

    def _current_safe_plan(self) -> dict:
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
        summary = plan.get("summary", {})
        executable = safe_executable_items(plan)
        family_creation = confirmed_creation_items(plan)
        actionable_keys = {
            (str(item.get("source") or ""), str(item.get("target_path") or ""))
            for item in executable + family_creation
        }
        review = [
            item
            for item in plan.get("items", [])
            if (str(item.get("source") or ""), str(item.get("target_path") or "")) not in actionable_keys
        ]

        box.insert(
            "end",
            "ПЛАН ПОРЯДКА — ПО ВАШЕЙ КОМПОНОВКЕ\n\n"
            f"Файлов изучено: {summary.get('files_considered', 0)}\n"
            f"Оставить на месте: {summary.get('already_placed', 0)}\n"
            f"Надёжных перемещений в существующие папки: {len(executable)}\n"
            f"Подтверждаемых группировок папок-версий: {len(family_creation)}\n"
            f"Определено по вашей текущей раскладке: {summary.get('learned_user_layout_targets', 0)}\n"
            f"Неуверенных предложений, которые НЕ будут выполнены: {len(review)}\n\n",
        )

        if summary.get("protected_project_root"):
            box.insert(
                "end",
                "ЗАЩИЩЕНО: выбранная папка похожа на проект. Внутренняя структура проекта не перестраивается.\n\n",
            )

        actionable = executable + family_creation
        if actionable:
            box.insert("end", "МОЖНО ПРИМЕНИТЬ ПОСЛЕ ПОДТВЕРЖДЕНИЯ\n")
            for item in actionable[:120]:
                kind = "ПАПКА" if item.get("kind") == "folder" else "ФАЙЛ"
                box.insert(
                    "end",
                    f"\n• [{kind}] {item.get('source', '')}\n"
                    f"  → {item.get('target_path', '')}\n"
                    f"  Почему: {_reason_text(item)}\n",
                )
        else:
            box.insert("end", "Надёжных действий пока нет. Ничего не будет передвинуто.\n")

        if review:
            box.insert(
                "end",
                "\n\nТОЛЬКО ПОДСКАЗКИ — НЕ ВЫПОЛНЯЮТСЯ\n"
                "Для этих элементов программа не нашла достаточно надёжного решения:\n",
            )
            for item in review[:80]:
                box.insert(
                    "end",
                    f"\n• {item.get('source', '')}\n"
                    f"  предполагается: {item.get('target_path', '')}\n"
                    "  статус: оставить на месте до более уверенного решения\n",
                )

        box.insert(
            "end",
            "\n\nЗащита: одинаковые main.py/config.json в разных проектах не объединяются; "
            "внутренности проектов и версий не смешиваются; существующие цели не перезаписываются; "
            "неуверенные предложения не исполняются.\n",
        )

    def organize_current(self) -> None:
        if not self.db.snapshot_files() and not self.db.snapshot_folders():
            self.scan_and_prepare()
            return

        # Important: call the current class method, not the local base planner.
        # Later safety layers add ambiguity checks and whole-folder compaction.
        plan = self._current_safe_plan()
        self._last_sort_plan = plan
        self._render_plan(plan)
        existing = safe_executable_items(plan)
        family_creation = confirmed_creation_items(plan)
        actionable = existing + family_creation
        actionable_keys = {
            (str(item.get("source") or ""), str(item.get("target_path") or "")) for item in actionable
        }
        skipped = sum(
            1
            for item in plan.get("items", [])
            if (str(item.get("source") or ""), str(item.get("target_path") or "")) not in actionable_keys
        )

        if not actionable:
            if plan.get("summary", {}).get("protected_project_root"):
                messagebox.showinfo(
                    "Навести порядок",
                    "Это рабочий проект. Его внутренняя компоновка защищена, поэтому Smart Organizer ничего внутри него не перемещает.",
                )
            else:
                messagebox.showinfo(
                    "Навести порядок",
                    "Надёжных действий не найдено. Ничего не изменено.\n\n"
                    "Программа не будет угадывать место файла или папки.",
                )
            self.status_var.set("Надёжных действий нет. Файлы и папки оставлены на месте.")
            return

        safe_plan = {**plan, "items": actionable}
        try:
            operations = operations_from_confirmed_sort_plan(safe_plan)
        except ValueError as exc:
            messagebox.showwarning(
                "План остановлен",
                "Обнаружен конфликт целевых путей. Ничего не перемещено.\n\n" + str(exc),
            )
            self.status_var.set("План остановлен из-за конфликта. Файлы и папки не изменены.")
            return

        file_moves = sum(1 for item in actionable if item.get("kind", "file") != "folder")
        folder_moves = sum(1 for item in actionable if item.get("kind") == "folder")
        created_dirs = sum(1 for operation in operations if operation.op_type == "mkdir")
        preview_lines = []
        for item in actionable[:10]:
            kind = "ПАПКА" if item.get("kind") == "folder" else "ФАЙЛ"
            preview_lines.append(
                f"• [{kind}] {item.get('source')}\n  → {item.get('target_path')}\n  {_reason_text(item)}"
            )
        if len(actionable) > 10:
            preview_lines.append(f"… и ещё {len(actionable) - 10}")

        confirmed = messagebox.askyesno(
            "Применить проверенный порядок",
            f"Файлов к перемещению: {file_moves}.\n"
            f"Целых папок к группировке: {folder_moves}.\n"
            f"Новых групповых папок: {created_dirs}.\n"
            f"Неуверенных предложений останется на месте: {skipped}.\n\n"
            + "\n".join(preview_lines)
            + "\n\nПапки перемещаются целиком, внутренние main.py/config.json и другие файлы не смешиваются. "
              "Существующие цели не перезаписываются. Весь пакет проверяется заранее и доступен для Undo. Применить?",
        )
        if not confirmed:
            self.status_var.set("План показан, но не применён.")
            return

        journal = OperationJournal(self.db)
        batch_id = journal.plan_batch(operations, label="safe-user-layout-organize")
        root_text = self.db.get_setting("last_scan_root")

        def work():
            result = execute_batch(journal, batch_id)
            refreshed = None
            if root_text:
                refreshed = scan_tree(Path(root_text), self.knowledge.get("projects", []))
                self.db.replace_scan(refreshed.folders, refreshed.files)
            return result, refreshed

        def done(payload):
            result, _refreshed = payload
            self.db.log_action(
                "safe-layout-organize",
                batch_id,
                "ok",
                f"applied={result['applied']}; files={file_moves}; folders={folder_moves}; created_dirs={created_dirs}; skipped_uncertain={skipped}",
            )
            self.refresh_dashboard()
            self._render_stable_files_screen()
            if self.db.snapshot_files() or self.db.snapshot_folders():
                self._render_plan(self._current_safe_plan())
            self.status_var.set(
                f"Порядок применён: файлов {file_moves}, папок {folder_moves}. Неуверенных оставлено: {skipped}. Undo доступен."
            )

        self._start_worker("Применяю только проверенный план порядка…", work, done)

    cls._current_safe_plan = _current_safe_plan
    cls._render_plan = _render_plan
    cls.organize_current = organize_current
