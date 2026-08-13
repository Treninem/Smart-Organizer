from __future__ import annotations

import re
from pathlib import Path

CATEGORY_EXTENSIONS = {
    "Изображения": {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg", ".ico"},
    "Документы": {".pdf", ".doc", ".docx", ".odt", ".txt", ".rtf", ".md", ".xlsx", ".xls", ".csv", ".ppt", ".pptx"},
    "Код": {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".java", ".kt", ".cs", ".cpp", ".c", ".h", ".go", ".rs", ".php", ".sql", ".json", ".yaml", ".yml", ".toml", ".ini"},
    "Архивы": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "Видео": {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".m4v"},
    "Аудио": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"},
    "Чертежи": {".dwg", ".dxf", ".step", ".stp", ".iges", ".igs", ".stl", ".3mf", ".obj"},
    "Программы": {".exe", ".msi", ".msix", ".appx", ".bat", ".cmd", ".ps1"},
}


def category_for(path: Path) -> str:
    ext = path.suffix.lower()
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if ext in extensions:
            return category
    return "Другое"


def _search_text(value: str) -> str:
    """Normalize paths/phrases into boundary-safe searchable text."""
    normalized = re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE)
    return " " + " ".join(normalized.split()) + " "


def _contains_term(search_text: str, term: str) -> bool:
    needle = _search_text(str(term)).strip()
    return bool(needle) and f" {needle} " in search_text


def project_hint(path: Path, projects: list[dict]) -> str | None:
    text = _search_text(str(path))
    scored: list[tuple[int, str]] = []
    for project in projects:
        score = 0
        project_name = str(project.get("name", ""))
        normalized_name = _search_text(project_name).strip()
        for keyword in project.get("keywords", []):
            kw = str(keyword)
            if _contains_term(text, kw):
                score += 3 if _search_text(kw).strip() == normalized_name else 1
        for alias in project.get("aliases", []):
            if _contains_term(text, str(alias)):
                score += 2
        if _contains_term(text, project_name):
            score += 4
        if score:
            scored.append((score, project_name))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][1]
