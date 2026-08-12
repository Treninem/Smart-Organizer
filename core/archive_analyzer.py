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
        r"C:\Program Files\7-Zip\7z.exe",
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
    names: list[str] = []
    total = 0
    current_path: str | None = None
    current_size = 0
    for line in proc.stdout.splitlines():
        if line.startswith("Path = "):
            if current_path is not None:
                names.append(current_path)
                total += current_size
            current_path = line[7:].strip()
            current_size = 0
        elif line.startswith("Size = "):
            try:
                current_size = int(line[7:].strip())
            except ValueError:
                current_size = 0
    if current_path is not None:
        names.append(current_path)
        total += current_size
    return names, total, "7-Zip"


def analyze_archive(path: Path, projects: list[dict]) -> dict:
    path = path.resolve()
    ext = path.suffix.lower()
    if ext not in ARCHIVE_EXTENSIONS:
        raise ValueError("Поддерживаются ZIP, RAR и 7Z.")
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
