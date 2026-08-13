from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .classifier import category_for, project_hint

ALWAYS_EXCLUDED = {".git", "node_modules", "__pycache__"}
SYSTEM_ROOT_EXCLUDED = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
}


@dataclass
class ScanResult:
    root: str
    folders: list[dict] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    bytes_total: int = 0

    @property
    def summary(self) -> dict:
        return {
            "folders": len(self.folders),
            "files": len(self.files),
            "errors": len(self.errors),
            "bytes": self.bytes_total,
        }


def _is_volume_root(path: Path) -> bool:
    anchor = path.anchor
    return bool(anchor) and path == Path(anchor)


def _filter_dirs(current_path: Path, root: Path, names: list[str]) -> list[str]:
    excluded = set(ALWAYS_EXCLUDED)
    # OS directories are dangerous/noisy only when the user deliberately scans
    # an entire volume. A normal project is allowed to contain a legitimate
    # folder called "Windows" or "ProgramData" and it must not disappear from
    # Smart Organizer's snapshot.
    if current_path == root and _is_volume_root(root):
        excluded.update(SYSTEM_ROOT_EXCLUDED)
    return [
        name
        for name in names
        if name.lower() not in excluded and not Path(current_path, name).is_symlink()
    ]


def scan_tree(
    root: Path,
    projects: list[dict],
    progress: Callable[[int, int], None] | None = None,
    max_files: int = 250_000,
) -> ScanResult:
    """Read-only recursive scan.

    No file or folder mutation is performed here. Existing folder structure is
    recorded exactly as found so later organizers can prefer it over templates.
    """
    root = root.resolve()
    result = ScanResult(str(root))
    seen_files = 0

    def onerror(exc: OSError):
        result.errors.append(str(exc))

    for current, dirs, files in os.walk(root, topdown=True, onerror=onerror, followlinks=False):
        current_path = Path(current)
        dirs[:] = _filter_dirs(current_path, root, dirs)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            depth = 0
        result.folders.append({
            "path": str(current_path),
            "parent": str(current_path.parent) if current_path != root else "",
            "name": current_path.name or str(current_path),
            "depth": depth,
        })

        for name in files:
            if seen_files >= max_files:
                result.errors.append(f"Достигнут безопасный лимит {max_files} файлов")
                return result
            p = current_path / name
            try:
                if p.is_symlink():
                    continue
                stat = p.stat()
            except OSError as exc:
                result.errors.append(f"{p}: {exc}")
                continue
            item = {
                "path": str(p),
                "parent": str(current_path),
                "name": name,
                "extension": p.suffix.lower(),
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "category": category_for(p),
                "project_hint": project_hint(p, projects),
            }
            result.files.append(item)
            result.bytes_total += stat.st_size
            seen_files += 1
            if progress and seen_files % 250 == 0:
                progress(seen_files, len(result.folders))
    return result


class Scanner:
    """Compatibility API kept from the initial repository scaffold."""

    def __init__(self, projects: list[dict] | None = None):
        self.projects = projects or []

    def status(self):
        return "Scanner ready: analysis mode"

    def scan(self, path):
        return scan_tree(Path(path), self.projects)
