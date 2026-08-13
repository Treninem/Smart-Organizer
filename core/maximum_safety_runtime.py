from __future__ import annotations

import os
from pathlib import Path

from core.layout_memory import destination_allowed_by_layout, layout_affinity
from core.workspace_compactor import build_workspace_compaction_plan

MIN_LAYOUT_SCORE = 24
MIN_LAYOUT_MARGIN = 16


def _norm(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


def _layout_rankings(record: dict, folders: list[dict], files: list[dict], scan_root: str | None) -> list[tuple[int, str]]:
    current = _norm(record.get("parent") or "")
    ranked: list[tuple[int, str]] = []
    for folder in folders:
        path = str(folder.get("path") or "")
        if not path or _norm(path) == current:
            continue
        if not destination_allowed_by_layout(record, path, files, scan_root):
            continue
        score, _reasons = layout_affinity(record, path, files)
        if score >= MIN_LAYOUT_SCORE:
            ranked.append((score, path))
    ranked.sort(key=lambda item: (item[0], item[1].casefold()), reverse=True)
    return ranked


def _harden_layout_item(item: dict, record: dict, folders: list[dict], files: list[dict], scan_root: str | None) -> dict:
    result = dict(item)
    if result.get("mode") != "existing":
        return result
    if not str(result.get("reason") or "").startswith("user_layout:"):
        return result

    ranked = _layout_rankings(record, folders, files, scan_root)
    target = _norm(result.get("target_dir") or "")
    if not ranked:
        result.update(mode="review", requires_confirmation=True, confidence="ambiguous")
        result["reason"] = "layout_evidence_disappeared"
        return result

    best_score, best_path = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else 0
    margin = best_score - runner_up
    if _norm(best_path) != target or (len(ranked) > 1 and margin < MIN_LAYOUT_MARGIN):
        result.update(mode="review", requires_confirmation=True, confidence="ambiguous")
        result["reason"] = "ambiguous_user_layout"
        evidence = list(result.get("evidence") or [])
        evidence.append(
            f"решение остановлено: лучший балл {best_score}, второй {runner_up}, запас {margin}; нужен запас не меньше {MIN_LAYOUT_MARGIN}"
        )
        result["evidence"] = evidence
    else:
        result["layout_margin"] = margin
    return result


def harden_and_extend_plan(plan: dict, files: list[dict], folders: list[dict], projects: list[dict], scan_root: str | None) -> dict:
    """Make the file plan ambiguity-safe and add conservative whole-folder moves."""
    hardened = {**plan, "summary": dict(plan.get("summary") or {})}
    by_path = {str(record.get("path") or ""): record for record in files}
    items: list[dict] = []
    seen_sources: set[str] = set()

    for item in plan.get("items", []):
        source = str(item.get("source") or "")
        record = by_path.get(source)
        candidate = _harden_layout_item(item, record, folders, files, scan_root) if record else dict(item)
        items.append(candidate)
        if source:
            seen_sources.add(_norm(source))

    workspace = build_workspace_compaction_plan(files, folders, projects, scan_root)
    added = 0
    for item in workspace.get("items", []):
        source_key = _norm(item.get("source") or "")
        if not source_key or source_key in seen_sources:
            continue
        items.append(dict(item))
        seen_sources.add(source_key)
        added += 1

    items.sort(
        key=lambda item: (
            item.get("mode") != "existing",
            0 if item.get("kind") == "folder" else 1,
            -int(item.get("score") or 0),
            str(item.get("source") or "").casefold(),
        )
    )
    hardened["items"] = items
    hardened["workspace_compaction_applied"] = True
    hardened["summary"]["workspace_folder_moves"] = int(workspace.get("summary", {}).get("folder_moves", 0))
    hardened["summary"]["workspace_project_file_moves"] = int(workspace.get("summary", {}).get("project_file_moves", 0))
    hardened["summary"]["workspace_ambiguous"] = int(workspace.get("summary", {}).get("ambiguous", 0))
    hardened["summary"]["ambiguous_layout_blocked"] = sum(
        1 for item in items if item.get("confidence") == "ambiguous"
    )
    hardened["summary"]["moves_suggested"] = len(items)
    return hardened


def install_maximum_safety_runtime(main_window) -> None:
    """Final organization layer: clear winner or no automatic movement."""
    cls = main_window.SmartOrganizerApp
    if getattr(cls, "_maximum_safety_runtime_installed", False):
        return
    cls._maximum_safety_runtime_installed = True

    original_current = cls._current_safe_plan
    original_render = cls._render_plan

    def _current_safe_plan(self) -> dict:
        base = original_current(self)
        if base.get("workspace_compaction_applied"):
            return base
        files = self.db.snapshot_files()
        folders = self.db.snapshot_folders()
        projects = self.knowledge.get("projects", [])
        root = self.db.get_setting("last_scan_root")
        return harden_and_extend_plan(base, files, folders, projects, root)

    def _render_plan(self, plan: dict) -> None:
        if not plan.get("workspace_compaction_applied"):
            plan = harden_and_extend_plan(
                plan,
                self.db.snapshot_files(),
                self.db.snapshot_folders(),
                self.knowledge.get("projects", []),
                self.db.get_setting("last_scan_root"),
            )
        original_render(self, plan)
        if not hasattr(self, "file_results") or not self.file_results.winfo_exists():
            return
        summary = plan.get("summary", {})
        folder_moves = int(summary.get("workspace_folder_moves", 0))
        project_files = int(summary.get("workspace_project_file_moves", 0))
        blocked = int(summary.get("ambiguous_layout_blocked", 0)) + int(summary.get("workspace_ambiguous", 0))
        self.file_results.insert(
            "end",
            "\n\nУСИЛЕННАЯ КОМПОНОВКА\n"
            f"Целых папок проектов можно безопасно сгруппировать: {folder_moves}\n"
            f"Файлов проекта с однозначной папкой: {project_files}\n"
            f"Неоднозначных решений остановлено: {blocked}\n"
            "Если две папки подходят почти одинаково, Smart Organizer ничего не переносит.\n",
        )

    cls._current_safe_plan = _current_safe_plan
    cls._render_plan = _render_plan
