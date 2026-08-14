from __future__ import annotations

import re
from pathlib import Path

CATEGORY_EXTENSIONS = {
    "Изображения": {
        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg", ".ico", ".psd", ".xcf",
        ".avif", ".heic", ".heif", ".jxl", ".raw", ".dng", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2",
    },
    "Документы": {
        ".pdf", ".doc", ".docx", ".odt", ".txt", ".rtf", ".md", ".xlsx", ".xls", ".csv", ".ppt", ".pptx",
        ".epub", ".mobi", ".fb2", ".log", ".ods", ".odp", ".djvu", ".tex",
    },
    "Код": {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".java", ".kt", ".cs", ".cpp", ".c", ".h",
        ".go", ".rs", ".php", ".sql", ".json", ".yaml", ".yml", ".toml", ".ini", ".xml", ".vue", ".svelte", ".dart",
        ".gradle", ".sh", ".bash", ".zsh", ".fish", ".rb", ".swift", ".lua", ".r", ".ipynb", ".proto", ".graphql",
        ".properties", ".env.example", ".mcfunction",
    },
    "Архивы": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".cbz", ".cbr", ".tgz", ".zst", ".cab", ".iso",
    },
    "Видео": {
        ".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".m4v", ".flv", ".mpeg", ".mpg", ".m2ts", ".mts", ".ts",
        ".vob", ".ogv", ".3gp", ".3g2", ".mxf",
    },
    "Аудио": {
        ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma", ".aiff", ".aif", ".alac", ".ape", ".amr",
    },
    "Чертежи": {
        ".dwg", ".dxf", ".step", ".stp", ".iges", ".igs", ".stl", ".3mf", ".obj", ".blend", ".fbx", ".gltf", ".glb",
        ".sldprt", ".sldasm", ".ipt", ".iam", ".fcstd", ".skp",
    },
    "Программы": {
        ".exe", ".msi", ".msix", ".appx", ".bat", ".cmd", ".ps1", ".apk", ".appxbundle", ".msixbundle", ".deb", ".rpm",
    },
}


def category_for(path: Path) -> str:
    name = path.name.casefold()
    if name.endswith(".env.example"):
        return "Код"
    ext = path.suffix.lower()
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if ext in extensions:
            return category
    return "Другое"


def _search_text(value: str) -> str:
    normalized = re.sub(r"[\W_]+", " ", value.casefold(), flags=re.UNICODE)
    return " " + " ".join(normalized.split()) + " "


def _contains_term(search_text: str, term: str) -> bool:
    needle = _search_text(str(term)).strip()
    return bool(needle) and f" {needle} " in search_text


def project_scores(path: Path, projects: list[dict]) -> list[tuple[int, str]]:
    """Return deterministic project evidence scores without forcing a winner."""
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
    return sorted(scored, key=lambda item: (-item[0], item[1].casefold()))


def project_hint(path: Path, projects: list[dict]) -> str | None:
    """Return a project only when the strongest evidence is unique."""
    scored = project_scores(path, projects)
    if not scored:
        return None
    best_score = scored[0][0]
    winners = [name for score, name in scored if score == best_score]
    return winners[0] if len(winners) == 1 else None
