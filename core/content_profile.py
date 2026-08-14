from __future__ import annotations

import re
from pathlib import Path

from core.classifier import category_for

AI_NAME_PATTERNS = (
    re.compile(r"(?i)(?:^|[\s._-])chatgpt(?:[\s._-]|$)"),
    re.compile(r"(?i)(?:^|[\s._-])openai(?:[\s._-]|$)"),
    re.compile(r"(?i)(?:^|[\s._-])dall[\s._-]*e(?:[\s._-]|$)"),
    re.compile(r"(?i)(?:^|[\s._-])gpt[\s._-]*image(?:[\s._-]|$)"),
    re.compile(r"(?i)(?:^|[\s._-])sora(?:[\s._-]|$)"),
)

PARTIAL_DOWNLOAD_EXTENSIONS = {".crdownload", ".part", ".partial", ".download", ".tmp"}
CODE_ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".tgz"}


def origin_hint(path: Path | str) -> str:
    """Return a conservative origin hint from the actual filename only.

    Parent directories are intentionally excluded: a folder named ``ChatGPT``
    must not make every unrelated file inside it look AI-generated, while a
    downloaded filename such as ``ChatGPT Image ...png`` must still match even
    when its full Windows path contains backslashes.
    """
    value = Path(str(path)).name
    for pattern in AI_NAME_PATTERNS:
        if pattern.search(value):
            return "chatgpt-openai"
    return "unknown"


def content_profile(path: Path | str) -> dict:
    file_path = Path(path)
    category = category_for(file_path)
    extension = file_path.suffix.casefold()
    origin = origin_hint(file_path)
    media_kind = {
        "Изображения": "image",
        "Видео": "video",
        "Аудио": "audio",
        "Документы": "document",
        "Код": "code",
        "Архивы": "archive",
        "Чертежи": "cad",
        "Программы": "program",
    }.get(category, "other")
    return {
        "path": str(file_path),
        "name": file_path.name,
        "extension": extension,
        "category": category,
        "media_kind": media_kind,
        "origin": origin,
        "is_ai_named": origin == "chatgpt-openai",
        "is_partial_download": extension in PARTIAL_DOWNLOAD_EXTENSIONS,
        "is_archive": extension in CODE_ARCHIVE_EXTENSIONS,
    }
