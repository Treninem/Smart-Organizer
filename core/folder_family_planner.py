from __future__ import annotations

import os
import re
from pathlib import Path

from .paths import app_root
from .version_manager import artifact_key, detect_version

MIN_FAMILY_SIZE = 3


def _norm(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


def _safe_family_label(names: list[str]) -> str | None:
    candidates: list[str] = []
    for name in names:
        info = detect_version(name)
        if not info:
            continue
        pattern = re.compile(re.escape(info.raw), flags=re.IGNORECASE)
        cleaned = pattern.sub(" ", str(name), count=1)
        cleaned = re.sub(r"[\s._\-\[\]()]+", " ", cleaned).strip()
        cleaned = re.sub(r"(?i)\b(?:final|latest|release|build)\b", " ", cleaned)
        cleaned = " ".join(cleaned.split()).strip(" ._-")
        if len(cleaned) >= 3 and not cleaned.isdigit():
            candidates.append(cleaned)
    if not candidates:
        return None
    # Prefer the shortest stable base because long names usually still contain
    # build-specific suffixes. Preserve the user's original capitalization.
    return sorted(candidates, key=lambda value: (len(value), value.casefold()))[0]


def _top_level(folders: list[dict], scan_root: str) -> list[dict]:
    root = _norm(scan_root)
    result: list[dict] = []
    for folder in folders:
        try:
            depth = int(folder.get("depth", -1))
        except (TypeError, ValueError):
            continue
        if depth != 1 or _norm(folder.get("parent") or "") != root:
            continue
        result.append(dict(folder))
    return result


def build_folder_family_plan(
    folders: list[dict],
    scan_root: str | None,
    protected_project_root: bool = False,
) -> dict:
    """Group obvious sibling version folders without inspecting their internals.

    A family requires at least three top-level folders carrying explicit version
    markers and the same artifact key. Existing unversioned family folders are
    preferred. Otherwise one new family container may be created, but only by a
    separately confirmed journal batch. Running Smart Organizer files are never
    proposed for movement.
    """
    if not scan_root or protected_project_root:
        return {"items": [], "groups": [], "summary": {"families": 0, "folder_moves": 0, "new_containers": 0}}

    top = _top_level(folders, scan_root)
    runtime = app_root()
    by_key: dict[str, list[dict]] = {}
    unversioned: dict[str, list[dict]] = {}

    for folder in top:
        name = str(folder.get("name") or "")
        path = str(folder.get("path") or "")
        if not name or not path:
            continue
        path_key = _norm(path)
        runtime_key = _norm(runtime)
        if path_key == runtime_key or runtime_key.startswith(path_key + os.sep) or path_key.startswith(runtime_key + os.sep):
            continue
        key = artifact_key(name)
        if detect_version(name):
            by_key.setdefault(key, []).append(folder)
        else:
            unversioned.setdefault(key, []).append(folder)

    items: list[dict] = []
    groups: list[dict] = []
    existing_paths = {_norm(folder.get("path") or "") for folder in folders}

    for key, members in sorted(by_key.items()):
        if len(members) < MIN_FAMILY_SIZE:
            continue
        names = [str(member.get("name") or "") for member in members]
        label = _safe_family_label(names)
        if not label:
            continue

        existing = unversioned.get(key, [])
        existing_container = existing[0] if len(existing) == 1 else None
        if existing_container:
            target_dir = str(existing_container.get("path") or "")
            mode = "existing"
            create_container = False
        else:
            target_dir = str(Path(scan_root) / label)
            if _norm(target_dir) in existing_paths:
                continue
            mode = "family_proposed"
            create_container = True

        planned = 0
        for member in sorted(members, key=lambda row: str(row.get("name") or "").casefold()):
            source = str(member.get("path") or "")
            name = str(member.get("name") or Path(source).name)
            if _norm(source) == _norm(target_dir):
                continue
            target = str(Path(target_dir) / name)
            if _norm(target) in existing_paths:
                continue
            items.append(
                {
                    "kind": "folder",
                    "source": source,
                    "target_dir": target_dir,
                    "target_path": target,
                    "mode": mode,
                    "score": 220,
                    "confidence": "high",
                    "requires_confirmation": create_container,
                    "allow_confirmed_creation": True,
                    "reason": "version_folder_family",
                    "evidence": [
                        f"найдено {len(members)} соседних папок одной версии/семейства",
                        f"семейство: {label}",
                        "папки перемещаются целиком, их внутренние файлы не смешиваются",
                    ],
                    "category": "Семейство версий",
                    "project_hint": None,
                    "extension": "",
                }
            )
            planned += 1
        if planned:
            groups.append(
                {
                    "key": key,
                    "label": label,
                    "target_dir": target_dir,
                    "count": planned,
                    "create_container": create_container,
                }
            )

    return {
        "items": items,
        "groups": groups,
        "summary": {
            "families": len(groups),
            "folder_moves": len(items),
            "new_containers": sum(1 for group in groups if group["create_container"]),
        },
    }
