from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

from .classifier import project_hint
from .version_manager import detect_version

ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}


def _find_7zip() -> str | None:
    candidates = [
        shutil.which("7z"),
        shutil.which("7z.exe"),
        shutil.which("7zz"),
        shutil.which("7zz.exe"),
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files\7-Zip\7zz.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def _list_zip(path: Path) -> tuple[list[str], int, str]:
    try:
        import zipfile
    except Exception as exc:
        raise RuntimeError("ZIP analyzer is unavailable in this installed launcher.") from exc
    with zipfile.ZipFile(path) as zf:
        infos = [x for x in zf.infolist() if not x.is_dir()]
        return [x.filename for x in infos], sum(x.file_size for x in infos), "python-zipfile"


def _parse_7zip_slt(output: str) -> tuple[list[str], int]:
    """Parse ``7z l -slt`` output and keep files only.

    Older code counted directory records as archive entries. That made entry
    counts and extension statistics wrong for RAR/7Z archives with nested
    folders. 7-Zip exposes ``Folder = +`` and/or directory attributes, so the
    parser now filters those records explicitly.
    """

    records: list[dict[str, str]] = []
    current: dict[str, str] = {}

    def flush() -> None:
        nonlocal current
        if current.get("Path"):
            records.append(current)
        current = {}

    for raw_line in output.splitlines():
        line = raw_line.strip("\r\n")
        if not line.strip():
            flush()
            continue
        if " = " not in line:
            continue
        key, value = line.split(" = ", 1)
        if key == "Path" and current.get("Path"):
            flush()
        current[key] = value.strip()
    flush()

    names: list[str] = []
    total = 0
    for record in records:
        attributes = record.get("Attributes", "").upper()
        is_folder = record.get("Folder", "").strip() == "+" or attributes.startswith("D")
        if is_folder:
            continue
        name = record.get("Path")
        if not name:
            continue
        names.append(name)
        try:
            total += max(0, int(record.get("Size", "0")))
        except ValueError:
            pass
    return names, total


def _list_7zip(path: Path) -> tuple[list[str], int, str]:
    try:
        import subprocess
    except Exception as exc:
        raise RuntimeError("7-Zip analyzer is unavailable in this installed launcher.") from exc

    exe = _find_7zip()
    if not exe:
        raise RuntimeError("Для анализа RAR/7Z нужен бесплатный 7-Zip. ZIP анализируется без него.")
    proc = subprocess.run(
        [exe, "l", "-slt", "-ba", str(path)],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=45,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "7-Zip error").strip())
    names, total = _parse_7zip_slt(proc.stdout)
    return names, total, "7-Zip"


def analyze_archive(path: Path, projects: list[dict]) -> dict:
    path = path.resolve()
    ext = path.suffix.lower()
    if ext not in ARCHIVE_EXTENSIONS:
        raise ValueError("Поддерживаются ZIP, RAR и 7Z.")
    if not path.is_file():
        raise FileNotFoundError(f"Архив не найден: {path}")
    if ext == ".zip":
        names, total, engine = _list_zip(path)
    else:
        names, total, engine = _list_7zip(path)

    sample_text = " ".join([path.name, *names[:500]])
    hint = project_hint(Path(sample_text), projects)
    version = detect_version(path.name)
    extensions = Counter(Path(name).suffix.lower() or "[без расширения]" for name in names)
    return {
        "path": str(path),
        "format": ext.lstrip(".").upper(),
        "engine": engine,
        "entries": len(names),
        "uncompressed_bytes": total,
        "project_hint": hint,
        "version": version.normalized if version else None,
        "top_extensions": extensions.most_common(12),
        "sample": names[:50],
        "read_only": True,
    }
