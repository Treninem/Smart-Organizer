from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from core.operation_executor import execute_batch
from core.operation_journal import OperationJournal
from core.plan_bridge import operations_from_sort_plan
from core.scanner import scan_tree
from core.sort_planner import build_sort_plan


def safe_executable_items(plan: dict) -> list[dict]:
    """Return only moves to existing folders accepted by the conservative planner.

    Low-confidence new-folder proposals stay visible as suggestions but can not
    be executed by the main "Навести порядок" button. This prevents one broad
    confirmation from moving files into guessed folders.
    """
    result: list[dict] = []
    for item in plan.get("items", []):
        if item.get("mode") != "existing":
            continue
        if item.get("requires_confirmation"):
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
        review = [item for item in plan.get("items", []) if item not in executable]

        box.insert(
            "end",
            "ПЛАН ПОРЯДКА — ПО ВАШЕЙ КОМПОНОВКЕ\n\n"
            f"Файлов изучено: {summary.get('files_considered', 0)}\n"
            f"Оставить на месте: {summary.get('already_placed', 0)}\n"
            f"Надёжных перемещений в существующие папки: {len(executable)}\n"
            f"Определено по вашей текущей раскладке: {summary.get('learned_user_layout_targets', 0)}\n"
            f"Неуверенных предложений, которые НЕ будут выполнены: {len(review)}\n\n",
        )

        if summary.get("protected_project_root"):
            box.insert(
                "end",
                "ЗАЩИЩЕНО: выбранная папка похожа на проект. Внутренняя структура проекта не перестраивается.\n\n",
            )

        if executable:
            box.insert("end", "БУДЕТ МОЖНО ПРИМЕНИТЬ\n")
            for item in executable[:120]:
                box.insert(
                    "end",
                    f"\n• {item.get('source', '')}\n"
                    f"  → {item.get('target_path', '')}\n"
                    f"  Почему: {_reason_text(item)}\n",
                )
        else:
            box.insert("end", "Надёжных перемещений пока нет. Ничего не будет передвинуто.\n")

        if review:
            box.insert(
                "end",
                "\n\nТОЛЬКО ПОДСКАЗКИ — НЕ ВЫПОЛНЯЮТСЯ\n"
                "Для этих файлов программа не нашла достаточно надёжного совпадения с вашей существующей раскладкой:\n",
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
            "папки проектов не перестраиваются; существующие целевые файлы не перезаписываются; "
            "неуверенные новые папки основной кнопкой не создаются.\n",
        )

    def organize_current(self) -> None:
        records = self.db.snapshot_files()
        if not records:
            self.scan_and_prepare()
            return

        plan = _current_safe_plan(self)
        self._last_sort_plan = plan
        self._render_plan(plan)
        executable = safe_executable_items(plan)
        skipped = len(plan.get("items", [])) - len(executable)

        if not executable:
            if plan.get("summary", {}).get("protected_project_root"):
                messagebox.showinfo(
                    "Навести порядок",
                    "Это рабочий проект. Его внутренняя компоновка защищена, поэтому Smart Organizer ничего внутри него не перемещает.",
                )
            else:
                messagebox.showinfo(
                    "Навести порядок",
                    "Надёжных перемещений не найдено. Ничего не изменено.\n\n"
                    "Программа не будет угадывать папку и переносить файл не туда. После следующего анализа она снова изучит вашу текущую раскладку.",
                )
            self.status_var.set("Надёжных перемещений нет. Файлы оставлены на месте.")
            return

        safe_plan = {**plan, "items": executable}
        try:
            operations = operations_from_sort_plan(safe_plan, existing_only=True)
        except ValueError as exc:
            messagebox.showwarning(
                "План остановлен",
                "Обнаружен конфликт целевых путей. Ничего не перемещено.\n\n" + str(exc),
            )
            self.status_var.set("План остановлен из-за конфликта. Файлы не изменены.")
            return

        preview = "\n".join(
            f"• {item.get('source')}\n  → {item.get('target_path')}\n  {_reason_text(item)}"
            for item in executable[:8]
        )
        if len(executable) > 8:
            preview += f"\n… и ещё {len(executable) - 8}"

        note = ""
        if skipped:
            note = f"\n\nНеуверенных предложений оставлено на месте: {skipped}."
        confirmed = messagebox.askyesno(
            "Применить надёжные перемещения",
            f"Будет перемещено файлов: {len(executable)}.\n"
            "Новые папки этим действием НЕ создаются.\n\n"
            f"{preview}{note}\n\n"
            "Все перемещения относятся к существующей пользовательской структуре, проверяются пакетом и доступны для Undo. Применить?",
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
                f"applied={result['applied']}; skipped_uncertain={skipped}",
            )
            self.refresh_dashboard()
            self._render_stable_files_screen()
            if self.db.snapshot_files():
                self._render_plan(_current_safe_plan(self))
            self.status_var.set(
                f"Надёжные перемещения выполнены: {result['applied']}. Неуверенных оставлено на месте: {skipped}. Undo доступен."
            )

        self._start_worker("Применяю только надёжные перемещения по вашей компоновке…", work, done)

    cls._current_safe_plan = _current_safe_plan
    cls._render_plan = _render_plan
    cls.organize_current = organize_current
