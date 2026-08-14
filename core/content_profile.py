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
AI_METADATA_MARKERS = (b"openai", b"chatgpt", b"dall-e", b"dall_e", b"gpt-image", b"sora")
AI_METADATA_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".heic", ".heif"}
PARTIAL_DOWNLOAD_EXTENSIONS = {".crdownload", ".part", ".partial", ".download", ".tmp"}
CODE_ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".tgz"}
MAX_METADATA_PROBE_BYTES = 512 * 1024


def _filename_ai_hint(file_path: Path) -> bool:
    value = file_path.name
    return any(pattern.search(value) for pattern in AI_NAME_PATTERNS)


def _metadata_ai_hint(file_path: Path) -> bool:
    """Probe only a small header window for explicit textual provenance.

    This is deliberately conservative and local. Pixel data is never decoded,
    no network lookup is performed, and files are not modified. The probe is
    limited to common image containers where XMP/text metadata normally lives
    near the beginning of the file.
    """
    if file_path.suffix.casefold() not in AI_METADATA_EXTENSIONS or not file_path.is_file():
        return False
    try:
        with file_path.open("rb") as fh:
            sample = fh.read(MAX_METADATA_PROBE_BYTES).lower()
    except OSError:
        return False
    return any(marker in sample for marker in AI_METADATA_MARKERS)


def origin_hint(path: Path | str) -> str:
    """Return a conservative ChatGPT/OpenAI provenance hint when explicit.

    Filename evidence is preferred. For renamed images, a bounded local metadata
    probe can still recognize explicit OpenAI/ChatGPT/DALL-E/Sora markers. A file
    with no explicit evidence remains ``unknown``; Smart Organizer never guesses
    AI provenance from visual appearance.
    """
    file_path = Path(path)
    if _filename_ai_hint(file_path):
        return "chatgpt-openai"
    if _metadata_ai_hint(file_path):
        return "chatgpt-openai"
    return "unknown"


def content_profile(path: Path | str) -> dict:
    file_path = Path(path)
    category = category_for(file_path)
    extension = file_path.suffix.casefold()
    filename_ai = _filename_ai_hint(file_path)
    metadata_ai = False if filename_ai else _metadata_ai_hint(file_path)
    origin = "chatgpt-openai" if filename_ai or metadata_ai else "unknown"
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
        "origin_evidence": "filename" if filename_ai else ("metadata" if metadata_ai else "none"),
        # Compatibility key used by the existing background router. It now means
        # "explicit AI provenance" rather than filename-only evidence.
        "is_ai_named": origin == "chatgpt-openai",
        "is_ai_filename": filename_ai,
        "is_ai_origin": origin == "chatgpt-openai",
        "is_partial_download": extension in PARTIAL_DOWNLOAD_EXTENSIONS,
        "is_archive": extension in CODE_ARCHIVE_EXTENSIONS,
    }
