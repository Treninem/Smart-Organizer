from __future__ import annotations

import hashlib
from pathlib import Path

from core.operation_journal import ReversibleOperation
from core.version_manager import artifact_key, detect_version

ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".zst"}
PROJECT_MARKERS = {
    "main.py", "bot.py", "requirements.txt", "pyproject.toml", "package.json",
    "server.properties", "project.godot", "cargo.toml", "go.mod", "pom.xml",
    "dockerfile", "compose.yml", "docker-compose.yml", "docker-compose.yaml",
}
GENERIC_ARTIFACT_KEYS = {
    "release", "build", "version", "versions", "app", "application", "project",
    "backup", "archive", "source", "sources", "code", "latest", "final",
}


def _safe_family_key(name: str) -> str | None:
    key = artifact_key(name).strip().casefold()
    if not key or key in GENERIC_ARTIFACT_KEYS or len(key) < 3:
        return None
    return key


def _folder_has_project_marker(folder: str, files: list[dict]) -> bool:
    target = str(Path(folder)).casefold()
    for record in files:
        if str(record.get("parent") or "").casefold() != target:
            continue
        if str(record.get("name") or "").casefold() in PROJECT_MARKERS:
            return True
    return False


def build_version_retention_plan(
    files: list[dict],
    folders: list[dict],
    keep_latest: int = 5,
) -> dict:
    """Find explicit old version archives and whole code-project folders.

    Nothing is permanently deleted. A candidate requires more than
    ``keep_latest`` *distinct explicit versions* of one non-generic artifact in
    the same parent. Whole code folders additionally require a direct project
    marker, so ordinary numbered folders are never treated as old code.
    """
    keep_latest = max(1, min(50, int(keep_latest)))
    groups: dict[tuple[str, str, str], list[dict]] = {}
    rejected_generic = 0

    for record in files:
        name = str(record.get("name") or "")
        path = str(record.get("path") or "")
        parent = str(record.get("parent") or Path(path).parent)
        suffix = Path(name).suffix.casefold()
        info = detect_version(name)
        if not path or not info or suffix not in ARCHIVE_EXTENSIONS:
            continue
        family = _safe_family_key(name)
        if not family:
            rejected_generic += 1
            continue
        key = ("archive", parent.casefold(), family)
        groups.setdefault(key, []).append(
            {"kind": "file", "source": path, "name": name, "version": info.normalized, "sort_key": info.sort_key}
        )

    for folder in folders:
        path = str(folder.get("path") or "")
        name = str(folder.get("name") or Path(path).name)
        parent = str(folder.get("parent") or Path(path).parent)
        info = detect_version(name)
        if not path or not info or not _folder_has_project_marker(path, files):
            continue
        family = _safe_family_key(name)
        if not family:
            rejected_generic += 1
            continue
        key = ("folder", parent.casefold(), family)
        groups.setdefault(key, []).append(
            {"kind": "folder", "source": path, "name": name, "version": info.normalized, "sort_key": info.sort_key}
        )

    candidates: list[dict] = []
    families: list[dict] = []
    for (kind, parent_key, family), members in groups.items():
        by_version: dict[str, list[dict]] = {}
        for member in members:
            by_version.setdefault(member["version"], []).append(member)
        if len(by_version) <= keep_latest:
            continue

        ordered_versions = sorted(
            by_version.items(),
            key=lambda pair: max(item["sort_key"] for item in pair[1]),
            reverse=True,
        )
        kept_versions = [version for version, _items in ordered_versions[:keep_latest]]
        old_versions = ordered_versions[keep_latest:]
        family_candidates: list[dict] = []
        for version, version_items in old_versions:
            for member in version_items:
                candidate = {
                    "kind": member["kind"],
                    "source": member["source"],
                    "name": member["name"],
                    "version": version,
                    "family": family,
                    "reason": f"older_than_latest_{keep_latest}_explicit_versions",
                    "confidence": "high",
                    "destructive_action": "quarantine_only",
                }
                candidates.append(candidate)
                family_candidates.append(candidate)
        families.append(
            {
                "kind": kind,
                "parent": parent_key,
                "family": family,
                "versions": len(by_version),
                "kept_versions": kept_versions,
                "old_versions": [version for version, _items in old_versions],
                "candidates": len(family_candidates),
            }
        )

    candidates.sort(key=lambda item: (item["kind"], item["family"], item["version"], item["source"].casefold()))
    return {
        "items": candidates,
        "families": families,
        "summary": {
            "keep_latest": keep_latest,
            "families": len(families),
            "candidates": len(candidates),
            "archive_candidates": sum(1 for item in candidates if item["kind"] == "file"),
            "folder_candidates": sum(1 for item in candidates if item["kind"] == "folder"),
            "generic_families_rejected": rejected_generic,
            "permanent_deletes": 0,
        },
    }


def quarantine_operations(plan: dict, quarantine_root: Path) -> list[ReversibleOperation]:
    """Convert reviewed retention candidates into reversible quarantine moves."""
    items = list(plan.get("items") or [])
    if not items:
        return []

    operations: list[ReversibleOperation] = []
    root = Path(quarantine_root)
    missing: list[Path] = []
    cursor = root
    while not cursor.exists():
        missing.append(cursor)
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    for path in reversed(missing):
        operations.append(ReversibleOperation("mkdir", str(path), None, "version retention quarantine"))

    for index, item in enumerate(items, 1):
        source = Path(str(item["source"]))
        digest = hashlib.sha256(str(source).encode("utf-8", errors="replace")).hexdigest()[:8]
        target = root / f"{index:04d}_{digest}_{source.name}"
        operations.append(
            ReversibleOperation(
                "delete-to-quarantine",
                str(source),
                str(target),
                f"retention: keep latest {plan.get('summary', {}).get('keep_latest', 5)} versions",
            )
        )
    return operations
