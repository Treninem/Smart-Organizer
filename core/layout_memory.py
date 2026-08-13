from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_MARKERS = {
    "main.py",
    "bot.py",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "server.properties",
    "project.godot",
    "cargo.toml",
    "go.mod",
    "pom.xml",
    "dockerfile",
    "compose.yml",
    "docker-compose.yml",
}


def _norm(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


def _relative_parts(path: str | Path, root: str | Path | None) -> tuple[str, ...]:
    if not root:
        return ()
    try:
        return Path(path).relative_to(Path(root)).parts
    except (ValueError, OSError):
        return ()


def protected_project_roots(files: list[dict], scan_root: str | None) -> set[str]:
    """Infer top-level project trees that must not receive unrelated loose files."""
    if not scan_root:
        return set()
    root = Path(scan_root)
    protected: set[str] = set()
    for record in files:
        name = str(record.get("name") or "").casefold()
        if name not in PROJECT_MARKERS:
            continue
        parent = Path(str(record.get("parent") or ""))
        parts = _relative_parts(parent, root)
        if not parts:
            continue
        protected.add(_norm(root / parts[0]))
    return protected


def folder_profiles(files: list[dict]) -> dict[str, dict]:
    """Describe how the user already uses every folder, based on direct files."""
    raw: dict[str, dict] = defaultdict(
        lambda: {
            "path": "",
            "count": 0,
            "categories": Counter(),
            "extensions": Counter(),
            "projects": Counter(),
        }
    )
    for record in files:
        parent = str(record.get("parent") or "")
        if not parent:
            continue
        key = _norm(parent)
        profile = raw[key]
        profile["path"] = parent
        profile["count"] += 1
        category = str(record.get("category") or "").strip()
        extension = str(record.get("extension") or Path(str(record.get("name") or "")).suffix).casefold()
        project = str(record.get("project_hint") or "").strip()
        if category:
            profile["categories"][category] += 1
        if extension:
            profile["extensions"][extension] += 1
        if project:
            profile["projects"][project] += 1
    return dict(raw)


def layout_affinity(record: dict, folder_path: str, files: list[dict]) -> tuple[int, list[str]]:
    """Score a destination from the user's actual existing placement pattern.

    Folder names alone are deliberately weak. Real files already stored by the
    user in that folder are the main evidence.
    """
    profile = folder_profiles(files).get(_norm(folder_path))
    if not profile:
        return 0, []

    category = str(record.get("category") or "").strip()
    extension = str(record.get("extension") or Path(str(record.get("name") or "")).suffix).casefold()
    project = str(record.get("project_hint") or "").strip()
    score = 0
    reasons: list[str] = []

    same_project = int(profile["projects"].get(project, 0)) if project else 0
    same_category = int(profile["categories"].get(category, 0)) if category else 0
    same_extension = int(profile["extensions"].get(extension, 0)) if extension else 0

    if same_project:
        score += 40 + min(40, same_project * 8)
        reasons.append(f"в этой папке уже {same_project} файл(ов) проекта {project}")
    if same_category:
        score += 10 + min(30, same_category * 5)
        reasons.append(f"здесь уже {same_category} файл(ов) категории {category}")
    if same_extension:
        score += 8 + min(24, same_extension * 4)
        reasons.append(f"здесь уже {same_extension} файл(ов) типа {extension or 'без расширения'}")

    # Archives often carry versions/backups/releases and therefore need extra
    # respect for the folder where the user already stores archives.
    if category == "Архивы" and same_category:
        score += 18
        reasons.append("папка уже используется пользователем для архивов")

    return score, reasons


def destination_allowed_by_layout(
    record: dict,
    folder_path: str,
    files: list[dict],
    scan_root: str | None,
) -> bool:
    """Block unrelated loose files from entering inferred project trees."""
    protected = protected_project_roots(files, scan_root)
    candidate = _norm(folder_path)
    for project_root in protected:
        if candidate == project_root or candidate.startswith(project_root + os.sep):
            project = str(record.get("project_hint") or "").strip().casefold()
            if not project:
                return False
            # A recognized project may enter its own tree only when the project
            # name is visibly present in that tree path. This is conservative by
            # design: false negatives are safer than damaging another project.
            return project in candidate.casefold()
    return True


def best_user_layout_folder(
    record: dict,
    folders: list[dict],
    files: list[dict],
    scan_root: str | None,
    minimum_score: int = 24,
) -> dict | None:
    """Return the strongest existing destination learned from user placement."""
    current_parent = _norm(record.get("parent") or "")
    ranked: list[tuple[int, int, str, list[str]]] = []
    for folder in folders:
        path = str(folder.get("path") or "")
        if not path or _norm(path) == current_parent:
            continue
        if not destination_allowed_by_layout(record, path, files, scan_root):
            continue
        score, reasons = layout_affinity(record, path, files)
        if score < minimum_score:
            continue
        depth = int(folder.get("depth", 0) or 0)
        ranked.append((score, -depth, path, reasons))

    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1], item[2].casefold()), reverse=True)
    score, _depth, path, reasons = ranked[0]
    return {
        "path": path,
        "score": score,
        "reason": "user_layout: " + "; ".join(reasons),
        "evidence": reasons,
    }
