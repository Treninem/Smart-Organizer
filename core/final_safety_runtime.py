from __future__ import annotations

import os
from pathlib import Path


def _norm(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


def _is_ancestor(parent: str, child: str) -> bool:
    parent_key = _norm(parent)
    child_key = _norm(child)
    return bool(parent_key and child_key and child_key.startswith(parent_key + os.sep))


def finalize_executable_plan(plan: dict) -> dict:
    """Apply the last safety gate before the UI can turn a plan into moves.

    Automatic execution requires an existing destination and high confidence.
    Ambiguous or medium-confidence items stay visible but become review-only.
    Whole-folder moves are ordered after file moves and are rejected when they
    would move a folder into itself or overlap another folder move.
    """
    result = {**plan, "summary": dict(plan.get("summary") or {})}
    items = [dict(item) for item in plan.get("items", [])]

    for item in items:
        item.setdefault("kind", "file")
        if item.get("mode") == "existing" and item.get("confidence") != "high":
            item["mode"] = "review"
            item["requires_confirmation"] = True
            item["reason"] = "confidence_below_execution_threshold"
            evidence = list(item.get("evidence") or [])
            evidence.append("автоматическое перемещение разрешено только при высокой уверенности")
            item["evidence"] = evidence

        if item.get("kind") == "folder" and item.get("mode") == "existing":
            source = str(item.get("source") or "")
            target = str(item.get("target_path") or "")
            if _norm(source) == _norm(target) or _is_ancestor(source, target):
                item["mode"] = "review"
                item["requires_confirmation"] = True
                item["confidence"] = "blocked"
                item["reason"] = "folder_cycle_blocked"

    executable_folder_sources = [
        str(item.get("source") or "")
        for item in items
        if item.get("kind") == "folder" and item.get("mode") == "existing"
    ]
    for item in items:
        if item.get("kind") != "folder" or item.get("mode") != "existing":
            continue
        source = str(item.get("source") or "")
        for other in executable_folder_sources:
            if _norm(other) == _norm(source):
                continue
            if _is_ancestor(source, other) or _is_ancestor(other, source):
                item["mode"] = "review"
                item["requires_confirmation"] = True
                item["confidence"] = "blocked"
                item["reason"] = "overlapping_folder_moves_blocked"
                break

    # Files first: a loose project archive may need to enter a project folder
    # before that whole project folder is moved into an existing user container.
    items.sort(
        key=lambda item: (
            item.get("mode") != "existing",
            1 if item.get("kind") == "folder" else 0,
            -int(item.get("score") or 0),
            str(item.get("source") or "").casefold(),
        )
    )
    result["items"] = items
    result["final_safety_applied"] = True
    result["summary"]["final_execution_ready"] = sum(1 for item in items if item.get("mode") == "existing")
    result["summary"]["final_review_only"] = sum(1 for item in items if item.get("mode") != "existing")
    result["summary"]["folder_moves_ready"] = sum(
        1 for item in items if item.get("kind") == "folder" and item.get("mode") == "existing"
    )
    return result


def install_final_safety_runtime(main_window) -> None:
    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_final_safety_runtime_installed", False):
        return
    cls._final_safety_runtime_installed = True

    original_current = cls._current_safe_plan
    original_render = cls._render_plan

    def _current_safe_plan(self) -> dict:
        plan = original_current(self)
        return plan if plan.get("final_safety_applied") else finalize_executable_plan(plan)

    def _render_plan(self, plan: dict) -> None:
        safe = plan if plan.get("final_safety_applied") else finalize_executable_plan(plan)
        original_render(self, safe)
        if not hasattr(self, "file_results") or not self.file_results.winfo_exists():
            return
        summary = safe.get("summary", {})
        self.file_results.insert(
            "end",
            "\nФИНАЛЬНЫЙ КОНТРОЛЬ\n"
            f"Готово к выполнению: {summary.get('final_execution_ready', 0)}\n"
            f"Оставлено только на просмотр: {summary.get('final_review_only', 0)}\n"
            f"Целых папок можно сгруппировать: {summary.get('folder_moves_ready', 0)}\n",
        )

    cls._current_safe_plan = _current_safe_plan
    cls._render_plan = _render_plan
