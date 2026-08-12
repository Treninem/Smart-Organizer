from __future__ import annotations

import os
from pathlib import Path

from .project_manager import suggest_destination


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def build_sort_plan(
    files: list[dict],
    folders: list[dict],
    projects: list[dict],
    scan_root: str | None = None,
) -> dict:
    """Build a read-only organization plan.

    The planner never mutates the filesystem. Existing user folders always have
    priority. Suggestions that require creating a new folder are explicitly
    marked as confirmation-required so a future executor cannot silently grow
    a parallel folder tree.
    """
    items: list[dict] = []
    already_placed = 0
    existing_targets = 0
    proposed_targets = 0

    for record in files:
        suggestion = suggest_destination(record, folders, projects, scan_root)
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
        else:
            proposed_targets += 1

        score = int(suggestion.get("score") or 0)
        confidence = "high" if mode == "existing" and score >= 20 else "medium" if mode == "existing" else "low"
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
            "filesystem_changes_performed": 0,
        },
        "safe_mode": True,
    }
