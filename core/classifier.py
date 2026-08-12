from __future__ import annotations

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


def project_hint(path: Path, projects: list[dict]) -> str | None:
    text = str(path).lower().replace("_", " ").replace("-", " ")
    scored: list[tuple[int, str]] = []
    for project in projects:
        score = 0
        for keyword in project.get("keywords", []):
            kw = keyword.lower()
            if kw and kw in text:
                score += 3 if kw == project.get("name", "").lower() else 1
        for alias in project.get("aliases", []):
            if alias.lower() in text:
                score += 2
        if score:
            scored.append((score, project["name"]))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][1]
