from __future__ import annotations

import os
from pathlib import Path

from .classifier import project_hint
from .project_manager import INBOX_ROOT_NAMES, suggest_destination

PROJECT_ROOT_MARKERS = {
    "main.py", "bot.py", "requirements.txt", "pyproject.toml", "package.json",
    "server.properties", "project.godot", "cargo.toml", "go.mod", "pom.xml",
    "dockerfile", "compose.yml", "docker-compose.yml",
}


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _effective_scan_root(folders: list[dict], scan_root: str | None) -> str | None:
    """Prefer the exact canonical root recorded by the scanner."""
    for folder in folders:
        try:
            if int(folder.get("depth", -1)) == 0 and folder.get("path"):
                return str(folder["path"])
        except (TypeError, ValueError):
            continue
    return scan_root


def _scan_root_looks_like_project(files: list[dict], projects: list[dict], scan_root: str | None) -> bool:
    if not scan_root:
        return False
    root = Path(scan_root)
    if root.anchor and root == Path(root.anchor):
        return False
    if root.name.strip().casefold() in INBOX_ROOT_NAMES:
        return False
    if project_hint(root, projects):
        return True
    for record in files:
        parent = str(record.get("parent") or "")
        name = str(record.get("name") or "").casefold()
        if _norm(parent) == _norm(str(root)) and name in PROJECT_ROOT_MARKERS:
            return True
    return False


def build_sort_plan(
    files: list[dict],
    folders: list[dict],
    projects: list[dict],
    scan_root: str | None = None,
) -> dict:
    """Build a conservative read-only organization plan.

    The user's existing placement is primary evidence. Existing project trees
    are frozen. Loose files are moved only toward a confidently matching
    existing folder or to an explicitly confirmed new-folder proposal.
    """
    effective_root = _effective_scan_root(folders, scan_root)
    items: list[dict] = []
    already_placed = 0
    existing_targets = 0
    proposed_targets = 0
    layout_learned_targets = 0
    protected_project_root = _scan_root_looks_like_project(files, projects, effective_root)

    for record in files:
        if protected_project_root:
            already_placed += 1
            continue

        suggestion = suggest_destination(
            record,
            folders,
            projects,
            effective_root,
            all_files=files,
        )
        source = str(record.get("path") or "")
        target_dir = str(suggestion.get("path") or "")
        current_parent = str(record.get("parent") or Path(source).parent)

        if target_dir and _norm(current_parent) == _norm(target_dir):
            already_placed += 1
            continue

        mode = str(suggestion.get("mode") or "proposed")
        requires_confirmation = mode != "existing"
        if mode == "existing":
            existing_targets += 1
            if str(suggestion.get("reason") or "").startswith("user_layout:"):
                layout_learned_targets += 1
        else:
            proposed_targets += 1

        score = int(suggestion.get("score") or 0)
        if str(suggestion.get("reason") or "").startswith("user_layout:"):
            confidence = "high"
        elif mode == "existing" and score >= 40:
            confidence = "high"
        elif mode == "existing":
            confidence = "medium"
        else:
            confidence = "low"

        items.append(
            {
                "source": source,
                "target_dir": target_dir,
                "target_path": str(Path(target_dir) / record.get("name", Path(source).name)) if target_dir else "",
                "mode": mode,
                "score": score,
                "confidence": confidence,
                "requires_confirmation": requires_confirmation,
                "reason": suggestion.get("reason", ""),
                "evidence": list(suggestion.get("evidence") or []),
                "category": record.get("category"),
                "project_hint": record.get("project_hint"),
            }
        )

    items.sort(key=lambda item: (item["requires_confirmation"], -item["score"], item["source"].lower()))
    return {
        "items": items,
        "summary": {
            "files_considered": len(files),
            "moves_suggested": len(items),
            "already_placed": already_placed,
            "existing_folder_targets": existing_targets,
            "new_folder_targets": proposed_targets,
            "learned_user_layout_targets": layout_learned_targets,
            "protected_project_root": 1 if protected_project_root else 0,
            "filesystem_changes_performed": 0,
        },
        "safe_mode": True,
        "scan_root": effective_root,
    }
