from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

from .classifier import project_hint
from .layout_memory import best_user_layout_folder
from .version_manager import detect_version

CATEGORY_FOLDER_WORDS = {
    "Изображения": ("images", "image", "img", "фото", "картинки"),
    "Документы": ("docs", "documents", "документы", "documentation"),
    "Код": ("src", "source", "code", "код", "app", "core"),
    "Архивы": ("archives", "archive", "архив", "архивы", "releases", "backup"),
    "Видео": ("video", "videos", "видео"),
    "Аудио": ("audio", "аудио", "sound"),
    "Чертежи": ("drawings", "cad", "чертежи", "чертёж"),
    "Программы": ("bin", "build", "dist", "release", "releases"),
}

TYPE_ROOT_HINTS = {
    "Telegram/VK bot + Mini App": "Bots",
    "older bot project": "Bots",
    "production Telegram bot + Mini App": "Bots",
    "Minecraft server": "Minecraft",
    "Windows desktop utility": "Programs",
}

INBOX_ROOT_NAMES = {
    "desktop", "рабочий стол", "downloads", "download", "загрузки",
    "inbox", "входящие", "unsorted", "разобрать", "разное", "temp", "tmp",
}


def _norm(path: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _structural_scope(record: dict, scan_root: str | None) -> Path | None:
    """Return a conservative project-tree boundary for already nested files."""
    if not scan_root:
        return None
    source = Path(str(record.get("path") or ""))
    root = Path(scan_root)
    try:
        relative = source.relative_to(root)
    except (ValueError, OSError):
        return None
    if len(relative.parts) < 2:
        return None
    first = str(relative.parts[0]).strip().casefold()
    if first in INBOX_ROOT_NAMES:
        return None
    return root / relative.parts[0]


def rank_existing_folders(
    record: dict,
    folders: list[dict],
    projects: list[dict],
    limit: int = 5,
    scan_root: str | None = None,
    all_files: list[dict] | None = None,
) -> list[dict]:
    project_name = record.get("project_hint") or project_hint(Path(record.get("path", "")), projects)
    project = next((p for p in projects if p.get("name") == project_name), None)
    category = record.get("category") or ""
    version = detect_version(record.get("name", ""))
    parent = record.get("parent", "")
    source_scope = _structural_scope(record, scan_root)
    all_files = all_files or []

    # Existing project internals are frozen. Smart Organizer routes loose/new
    # files; it does not reorganize a working project from the inside.
    if source_scope is not None:
        return [{"path": parent, "score": 1000, "reason": "preserve_existing_project_tree"}]

    ranked: list[tuple[int, int, dict]] = []

    # First and strongest signal: how the user actually uses folders now.
    learned = best_user_layout_folder(record, folders, all_files, scan_root)
    if learned:
        learned_folder = next((folder for folder in folders if _norm(folder.get("path", "")) == _norm(learned["path"])), None)
        if learned_folder:
            ranked.append((int(learned["score"]) + 100, -int(learned_folder.get("depth", 0)), {
                "path": learned["path"],
                "score": int(learned["score"]) + 100,
                "reason": learned["reason"],
                "evidence": learned.get("evidence", []),
            }))

    aliases: set[str] = set()
    keywords: set[str] = set()
    if project:
        aliases = {project["name"].lower(), *(str(a).lower() for a in project.get("aliases", []))}
        keywords = {str(k).lower() for k in project.get("keywords", []) if len(str(k)) >= 3}

    for folder in folders:
        path = str(folder.get("path", ""))
        name = str(folder.get("name", ""))
        if not path or _norm(path) == _norm(parent):
            continue
        lower_path = path.lower()
        lower_name = name.lower()
        depth = int(folder.get("depth", 0))
        score = 0

        if project:
            # Recognized project files may go only into an explicitly matching
            # project tree. Generic words such as bot/app/src are not enough.
            alias_match = any(alias and alias in lower_path for alias in aliases)
            if not alias_match:
                continue
            score += 40
            score += min(10, sum(2 for kw in keywords if kw in lower_path))
        else:
            # Unknown loose files may use only shallow user folders. Nested
            # folders are often project internals and are never guessed into.
            if depth > 1:
                continue

        # Folder names are only a weak hint now. Actual user contents above are
        # deliberately much stronger so the program follows the user's layout.
        for word in CATEGORY_FOLDER_WORDS.get(category, ()):
            if word in lower_name:
                score += 4
        if version and version.normalized.lower() in lower_path.replace("_", "-"):
            score += 6

        # Never move merely because a generic folder name matched. Require a
        # meaningful project match or let the learned-layout scorer decide.
        minimum = 30 if project else 12
        if score >= minimum:
            ranked.append((score, -depth, {
                "path": path,
                "score": score,
                "reason": "existing_user_structure_name_hint",
                "evidence": ["совпадение с существующей структурой"] if score else [],
            }))

    ranked.sort(key=lambda item: (item[0], item[1], item[2]["path"].casefold()), reverse=True)
    seen: set[str] = set()
    result: list[dict] = []
    for _score, _depth, item in ranked:
        key = _norm(item["path"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def suggest_destination(
    record: dict,
    folders: list[dict],
    projects: list[dict],
    scan_root: str | None = None,
    all_files: list[dict] | None = None,
) -> dict:
    ranked = rank_existing_folders(
        record,
        folders,
        projects,
        limit=1,
        scan_root=scan_root,
        all_files=all_files,
    )
    if ranked:
        return {"mode": "existing", **ranked[0]}

    project_name = record.get("project_hint") or project_hint(Path(record.get("path", "")), projects)
    project = next((p for p in projects if p.get("name") == project_name), None)
    base = Path(scan_root or record.get("parent") or ".")
    category = str(record.get("category") or "Прочее")

    # If no existing placement pattern is convincing, do not pretend to know
    # where the file belongs. A new-folder suggestion is low confidence and can
    # only become executable after explicit confirmation.
    if project:
        root_hint = TYPE_ROOT_HINTS.get(project.get("type", ""), "Projects")
        proposed = base / root_hint / project["name"] / category
    else:
        proposed = base / "Smart-Organizer_Unsorted" / category
    return {
        "mode": "proposed",
        "path": str(proposed),
        "score": 0,
        "reason": "no_confident_user_layout_match_create_only_after_confirmation",
        "evidence": [],
    }


def summarize_projects(files: list[dict], folders: list[dict], projects: list[dict]) -> list[dict]:
    summaries = []
    for project in projects:
        name = project["name"]
        project_files = [f for f in files if f.get("project_hint") == name]
        folder_matches = []
        aliases = {name.lower(), *(str(a).lower() for a in project.get("aliases", []))}
        for folder in folders:
            lp = folder.get("path", "").lower()
            if any(alias and alias in lp for alias in aliases):
                folder_matches.append(folder["path"])
        versions = Counter()
        for file in project_files:
            info = detect_version(file.get("name", ""))
            if info:
                versions[info.normalized] += 1
        if project_files or folder_matches:
            summaries.append(
                {
                    "name": name,
                    "type": project.get("type", "unknown"),
                    "repository": project.get("repository"),
                    "status": project.get("status", "unknown"),
                    "file_count": len(project_files),
                    "folders": sorted(set(folder_matches))[:10],
                    "versions": [v for v, _ in versions.most_common()],
                }
            )
    return summaries
