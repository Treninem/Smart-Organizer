from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

from .classifier import project_hint
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


def _is_within(path: str | Path, root: str | Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False


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
) -> list[dict]:
    project_name = record.get("project_hint") or project_hint(Path(record.get("path", "")), projects)
    project = next((p for p in projects if p.get("name") == project_name), None)
    category = record.get("category") or ""
    version = detect_version(record.get("name", ""))
    parent = record.get("parent", "")
    source_scope = _structural_scope(record, scan_root)
    ranked: list[tuple[int, int, dict]] = []

    # Existing project internals are intentionally frozen. Smart Organizer is
    # meant to route loose/new files into the user's structure, not rewrite a
    # working project because another folder happens to be called src/app/docs.
    if source_scope is not None:
        return [{"path": parent, "score": 100, "reason": "preserve_existing_project_tree"}]

    aliases: set[str] = set()
    keywords: set[str] = set()
    if project:
        aliases = {project["name"].lower(), *(str(a).lower() for a in project.get("aliases", []))}
        keywords = {str(k).lower() for k in project.get("keywords", []) if len(str(k)) >= 3}

    for folder in folders:
        path = folder.get("path", "")
        name = folder.get("name", "")
        lower_path = path.lower()
        lower_name = name.lower()
        score = 0

        if project:
            for alias in aliases:
                if alias and alias in lower_path:
                    score += 14
            score += min(8, sum(2 for kw in keywords if kw in lower_path))
            # A generic src/app/docs folder in an unrelated project must never
            # win only because of its common folder name.
            if score == 0:
                continue

        for word in CATEGORY_FOLDER_WORDS.get(category, ()):
            if word in lower_name:
                score += 6
        if version and version.normalized.lower() in lower_path.replace("_", "-"):
            score += 8
        if _norm(path) == _norm(parent) and score:
            score += 3
        if score:
            depth = int(folder.get("depth", 0))
            ranked.append((score, -depth, folder))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [{"path": item[2]["path"], "score": item[0], "reason": "existing_user_structure"} for item in ranked[:limit]]


def suggest_destination(record: dict, folders: list[dict], projects: list[dict], scan_root: str | None = None) -> dict:
    ranked = rank_existing_folders(record, folders, projects, limit=1, scan_root=scan_root)
    if ranked:
        return {"mode": "existing", **ranked[0]}

    project_name = record.get("project_hint") or project_hint(Path(record.get("path", "")), projects)
    project = next((p for p in projects if p.get("name") == project_name), None)
    base = Path(scan_root or record.get("parent") or ".")
    category = str(record.get("category") or "Прочее")
    if project:
        root_hint = TYPE_ROOT_HINTS.get(project.get("type", ""), "Projects")
        proposed = base / root_hint / project["name"] / category
    else:
        proposed = base / "Smart-Organizer_Unsorted" / category
    return {"mode": "proposed", "path": str(proposed), "score": 0, "reason": "no_existing_match_create_only_after_confirmation"}


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
