from __future__ import annotations

import os
from pathlib import Path

from core.generic_project_compactor import build_generic_project_compaction_plan


def _norm(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


def extend_with_generic_project_compaction(plan: dict, app) -> dict:
    if plan.get("generic_project_compaction_applied"):
        return plan

    generic = build_generic_project_compaction_plan(
        app.db.snapshot_files(),
        app.db.snapshot_folders(),
        app.db.get_setting("last_scan_root"),
    )
    result = {**plan, "summary": dict(plan.get("summary") or {})}
    items = [dict(item) for item in plan.get("items", [])]
    seen_sources = {_norm(item.get("source") or "") for item in items if item.get("source")}

    added = 0
    for item in generic.get("items", []):
        source_key = _norm(item.get("source") or "")
        if not source_key or source_key in seen_sources:
            continue
        items.append(dict(item))
        seen_sources.add(source_key)
        added += 1

    items.sort(
        key=lambda item: (
            item.get("mode") != "existing",
            1 if item.get("kind") == "folder" else 0,
            -int(item.get("score") or 0),
            str(item.get("source") or "").casefold(),
        )
    )
    result["items"] = items
    result["generic_project_compaction_applied"] = True
    result["summary"]["learned_project_containers"] = int(generic.get("summary", {}).get("containers", 0))
    result["summary"]["generic_project_folder_moves"] = added
    result["summary"]["generic_project_ambiguous"] = int(generic.get("summary", {}).get("ambiguous", 0))
    result["summary"]["moves_suggested"] = len(items)
    return result


def install_generic_compaction_runtime(main_window) -> None:
    """Add generic project grouping learned from the user's current hierarchy."""
    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_generic_compaction_runtime_installed", False):
        return
    cls._generic_compaction_runtime_installed = True

    original_current = cls._current_safe_plan
    original_render = cls._render_plan

    def _current_safe_plan(self) -> dict:
        return extend_with_generic_project_compaction(original_current(self), self)

    def _render_plan(self, plan: dict) -> None:
        extended = extend_with_generic_project_compaction(plan, self)
        original_render(self, extended)
        if not hasattr(self, "file_results") or not self.file_results.winfo_exists():
            return
        summary = extended.get("summary", {})
        self.file_results.insert(
            "end",
            "\n\nОБУЧЕНИЕ ПО СТРУКТУРЕ ПРОЕКТОВ\n"
            f"Контейнеров проектов распознано по вашей реальной раскладке: {summary.get('learned_project_containers', 0)}\n"
            f"Целых проектных папок можно сгруппировать: {summary.get('generic_project_folder_moves', 0)}\n"
            f"Неоднозначных контейнеров остановлено: {summary.get('generic_project_ambiguous', 0)}\n"
            "Контейнер считается изученным только если вы уже храните в нём минимум два проекта совместимого типа. "
            "Проект перемещается целиком, его внутренние файлы не смешиваются.\n",
        )

    cls._current_safe_plan = _current_safe_plan
    cls._render_plan = _render_plan
