from __future__ import annotations

import os
import re
from pathlib import Path

from .classifier import project_hint
from .paths import app_root


TYPE_CONTAINER_ALIASES = {
    "Telegram/VK bot + Mini App": {"боты", "bots", "telegram", "телеграм"},
    "older bot project": {"боты", "bots", "telegram", "телеграм"},
    "production Telegram bot + Mini App": {"боты", "bots", "производство", "production"},
    "Minecraft server": {"minecraft", "майнкрафт", "серверы", "servers"},
    "Windows desktop utility": {"программы", "programs", "apps", "applications"},
}


def _norm(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


def _token_text(value: str) -> str:
    return " ".join(re.sub(r"[\W_]+", " ", str(value).casefold(), flags=re.UNICODE).split())


def _is_same_or_inside(path: str | Path, protected: str | Path) -> bool:
    left = _norm(path)
    right = _norm(protected)
    return left == right or left.startswith(right + os.sep) or right.startswith(left + os.sep)


def _top_level_folders(folders: list[dict], scan_root: str | None) -> list[dict]:
    if not scan_root:
        return []
    root_key = _norm(scan_root)
    result = []
    for folder in folders:
        try:
            depth = int(folder.get("depth", -1))
        except (TypeError, ValueError):
            continue
        if depth != 1:
            continue
        if _norm(folder.get("parent") or "") != root_key:
            continue
        result.append(dict(folder))
    return result


def _project_record(project_name: str | None, projects: list[dict]) -> dict | None:
    if not project_name:
        return None
    return next((item for item in projects if item.get("name") == project_name), None)


def _folder_project(folder: dict, projects: list[dict]) -> str | None:
    # Use only the folder's own name so project keywords in an ancestor cannot
    # accidentally classify every sibling folder as the same project.
    return project_hint(Path(str(folder.get("name") or "")), projects)


def _container_candidates(project: dict, top_folders: list[dict]) -> list[dict]:
    aliases = TYPE_CONTAINER_ALIASES.get(str(project.get("type") or ""), set())
    if not aliases:
        return []
    candidates = []
    for folder in top_folders:
        name = _token_text(str(folder.get("name") or ""))
        if name in aliases:
            candidates.append(folder)
    return candidates


def _exact_project_folder(project: dict, candidates: list[dict]) -> dict | None:
    names = {
        _token_text(str(project.get("name") or "")),
        *(_token_text(str(value)) for value in project.get("aliases", [])),
    }
    exact = [folder for folder in candidates if _token_text(str(folder.get("name") or "")) in names]
    return exact[0] if len(exact) == 1 else None


def build_workspace_compaction_plan(
    files: list[dict],
    folders: list[dict],
    projects: list[dict],
    scan_root: str | None,
) -> dict:
    """Plan safe top-level workspace compaction without touching the filesystem.

    Two kinds of high-confidence moves are allowed:
    1. a recognized top-level project folder into an already existing user
       container such as "Боты", "Minecraft" or "Программы";
    2. a loose root-level file belonging to a recognized project into exactly
       one matching existing project folder.

    Ambiguous destinations are deliberately omitted. No new folder is proposed
    here, project internals are never changed, and the running Smart Organizer
    installation is protected from self-movement.
    """
    if not scan_root:
        return {"items": [], "summary": {"folder_moves": 0, "project_file_moves": 0, "ambiguous": 0}}

    root_key = _norm(scan_root)
    top = _top_level_folders(folders, scan_root)
    existing_paths = {_norm(folder.get("path") or "") for folder in folders}
    protected_runtime = app_root()
    items: list[dict] = []
    ambiguous = 0

    project_folders: dict[str, list[dict]] = {}
    for folder in top:
        project_name = _folder_project(folder, projects)
        if project_name:
            project_folders.setdefault(project_name, []).append(folder)

    # Compact whole project/version folders into an existing user container.
    for project_name, candidates in sorted(project_folders.items()):
        project = _project_record(project_name, projects)
        if not project:
            continue
        containers = _container_candidates(project, top)
        if len(containers) != 1:
            if len(containers) > 1:
                ambiguous += len(candidates)
            continue
        container = containers[0]
        container_path = str(container.get("path") or "")
        for folder in candidates:
            source = str(folder.get("path") or "")
            if not source or _is_same_or_inside(source, protected_runtime):
                continue
            if _norm(source) == _norm(container_path):
                continue
            target = str(Path(container_path) / str(folder.get("name") or Path(source).name))
            if _norm(target) in existing_paths:
                continue
            items.append(
                {
                    "kind": "folder",
                    "source": source,
                    "target_dir": container_path,
                    "target_path": target,
                    "mode": "existing",
                    "score": 180,
                    "confidence": "high",
                    "requires_confirmation": False,
                    "reason": "existing_project_container",
                    "evidence": [
                        f"папка распознана как проект {project_name}",
                        f"контейнер «{container.get('name')}» уже создан пользователем",
                        "внутреннее содержимое проекта не перестраивается",
                    ],
                    "category": "Папка проекта",
                    "project_hint": project_name,
                    "extension": "",
                }
            )

    # Route loose root-level project files only when one project folder is
    # unambiguous. If several version folders exist, an exact unversioned project
    # folder may act as the canonical destination; otherwise the file stays put.
    for record in files:
        if _norm(record.get("parent") or "") != root_key:
            continue
        project_name = str(record.get("project_hint") or "").strip()
        project = _project_record(project_name, projects)
        if not project:
            continue
        candidates = project_folders.get(project_name, [])
        chosen = candidates[0] if len(candidates) == 1 else _exact_project_folder(project, candidates)
        if chosen is None:
            if len(candidates) > 1:
                ambiguous += 1
            continue
        target_dir = str(chosen.get("path") or "")
        source = str(record.get("path") or "")
        target = str(Path(target_dir) / str(record.get("name") or Path(source).name))
        if not source or _norm(target) in existing_paths:
            continue
        # File targets are not present in folder_snapshot, so also compare the
        # actual scan records to prevent planning an overwrite.
        if any(_norm(item.get("path") or "") == _norm(target) for item in files):
            continue
        items.append(
            {
                "kind": "file",
                "source": source,
                "target_dir": target_dir,
                "target_path": target,
                "mode": "existing",
                "score": 170,
                "confidence": "high",
                "requires_confirmation": False,
                "reason": "single_existing_project_folder",
                "evidence": [
                    f"файл относится к проекту {project_name}",
                    f"найдена однозначная существующая папка проекта «{chosen.get('name')}»",
                ],
                "category": record.get("category"),
                "project_hint": project_name,
                "extension": record.get("extension"),
            }
        )

    # Stable ordering makes previews and regression tests deterministic.
    items.sort(key=lambda item: (0 if item.get("kind") == "file" else 1, str(item.get("source")).casefold()))
    return {
        "items": items,
        "summary": {
            "folder_moves": sum(1 for item in items if item.get("kind") == "folder"),
            "project_file_moves": sum(1 for item in items if item.get("kind") == "file"),
            "ambiguous": ambiguous,
        },
    }
