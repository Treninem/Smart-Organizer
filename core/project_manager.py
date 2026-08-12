from __future__ import annotations

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


def rank_existing_folders(record: dict, folders: list[dict], projects: list[dict], limit: int = 5) -> list[dict]:
    project_name = record.get("project_hint") or project_hint(Path(record.get("path", "")), projects)
    project = next((p for p in projects if p.get("name") == project_name), None)
    category = record.get("category") or ""
    version = detect_version(record.get("name", ""))
    parent = record.get("parent", "")
    ranked: list[tuple[int, int, dict]] = []

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
        for word in CATEGORY_FOLDER_WORDS.get(category, ()):
            if word in lower_name:
                score += 6
        if version and version.normalized.lower() in lower_path.replace("_", "-"):
            score += 8
        # Being the current parent is not evidence that it is the best destination.
        # Otherwise every scanned file scores its own folder highest and the
        # organizer can never discover a better existing user folder. A small
        # tie-break bonus is safe only after semantic/project evidence exists.
        if path == parent and score:
            score += 3
        if score:
            depth = int(folder.get("depth", 0))
            ranked.append((score, -depth, folder))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [{"path": item[2]["path"], "score": item[0], "reason": "existing_user_structure"} for item in ranked[:limit]]


def suggest_destination(record: dict, folders: list[dict], projects: list[dict], scan_root: str | None = None) -> dict:
    ranked = rank_existing_folders(record, folders, projects, limit=1)
    if ranked:
        return {"mode": "existing", **ranked[0]}

    project_name = record.get("project_hint") or project_hint(Path(record.get("path", "")), projects)
    project = next((p for p in projects if p.get("name") == project_name), None)
    base = Path(scan_root or record.get("parent") or ".")
    if project:
        root_hint = TYPE_ROOT_HINTS.get(project.get("type", ""), "Projects")
        proposed = base / root_hint / project["name"]
    else:
        proposed = base / "Smart-Organizer_Unsorted"
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
