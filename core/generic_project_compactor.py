from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

from core.layout_memory import PROJECT_MARKERS
from core.paths import app_root


FAMILY_MARKERS = {
    "minecraft": {"server.properties"},
    "game": {"project.godot"},
    "java": {"pom.xml", "build.gradle", "build.gradle.kts"},
    "rust": {"cargo.toml"},
    "go": {"go.mod"},
    "javascript": {"package.json"},
    "python": {"main.py", "bot.py", "pyproject.toml", "requirements.txt"},
}


def _norm(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


def _folder_depth(folder: dict) -> int:
    try:
        return int(folder.get("depth", -1))
    except (TypeError, ValueError):
        return -1


def _direct_markers(files: list[dict]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    marker_names = {name.casefold() for name in PROJECT_MARKERS} | {
        marker.casefold() for markers in FAMILY_MARKERS.values() for marker in markers
    }
    for record in files:
        name = str(record.get("name") or "").casefold()
        if name not in marker_names:
            continue
        parent = str(record.get("parent") or "")
        if not parent:
            continue
        result.setdefault(_norm(parent), set()).add(name)
    return result


def _project_family(markers: set[str]) -> str:
    scores = Counter()
    for family, family_markers in FAMILY_MARKERS.items():
        for marker in family_markers:
            if marker.casefold() in markers:
                scores[family] += 1
    if not scores:
        return "generic"
    top = scores.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        # Python + JS or other mixed stacks are common; call them generic rather
        # than forcing one ecosystem and risking a wrong container.
        return "generic"
    return top[0][0]


def build_generic_project_compaction_plan(
    files: list[dict],
    folders: list[dict],
    scan_root: str | None,
    minimum_examples: int = 2,
) -> dict:
    """Group whole project folders by learning container use from the scan.

    No folder-name dictionary is required. A top-level folder becomes a learned
    project container only after the user already placed at least two immediate
    child project roots inside it. A loose top-level project is moved only when
    exactly one such container has matching project-family evidence.
    """
    empty = {"items": [], "summary": {"containers": 0, "folder_moves": 0, "ambiguous": 0}}
    if not scan_root:
        return empty

    root_key = _norm(scan_root)
    direct = _direct_markers(files)
    if not direct:
        return empty

    by_path = {_norm(folder.get("path") or ""): dict(folder) for folder in folders if folder.get("path")}
    top_level = [
        dict(folder)
        for folder in folders
        if _folder_depth(folder) == 1 and _norm(folder.get("parent") or "") == root_key
    ]
    second_level = [dict(folder) for folder in folders if _folder_depth(folder) == 2]

    # Learn container roles only from real project children already present.
    containers: dict[str, dict] = {}
    for top in top_level:
        top_path = str(top.get("path") or "")
        top_key = _norm(top_path)
        family_counts: Counter[str] = Counter()
        project_children = 0
        for child in second_level:
            if _norm(child.get("parent") or "") != top_key:
                continue
            child_key = _norm(child.get("path") or "")
            markers = direct.get(child_key)
            if not markers:
                continue
            project_children += 1
            family_counts[_project_family(markers)] += 1
        if project_children < minimum_examples:
            continue
        containers[top_key] = {
            "path": top_path,
            "name": str(top.get("name") or Path(top_path).name),
            "project_children": project_children,
            "families": dict(family_counts),
        }

    if not containers:
        return empty

    runtime = _norm(app_root())
    existing_paths = set(by_path)
    items: list[dict] = []
    ambiguous = 0

    for folder in top_level:
        source = str(folder.get("path") or "")
        source_key = _norm(source)
        if not source or source_key in containers:
            continue
        if source_key == runtime or source_key.startswith(runtime + os.sep) or runtime.startswith(source_key + os.sep):
            continue
        markers = direct.get(source_key)
        if not markers:
            continue
        family = _project_family(markers)

        candidates: list[dict] = []
        for container in containers.values():
            families = container["families"]
            same_family = int(families.get(family, 0))
            if family == "generic":
                # Generic/mixed projects require generic examples specifically;
                # do not infer that every project container accepts everything.
                if same_family < minimum_examples:
                    continue
            elif same_family < 1:
                continue
            candidates.append(container)

        if len(candidates) != 1:
            if len(candidates) > 1:
                ambiguous += 1
            continue

        container = candidates[0]
        target_dir = str(container["path"])
        target = str(Path(target_dir) / str(folder.get("name") or Path(source).name))
        if _norm(target) in existing_paths:
            continue

        same_family_examples = int(container["families"].get(family, 0))
        items.append(
            {
                "kind": "folder",
                "source": source,
                "target_dir": target_dir,
                "target_path": target,
                "mode": "existing",
                "score": 190 + min(30, same_family_examples * 5),
                "confidence": "high",
                "requires_confirmation": False,
                "reason": "learned_project_container",
                "evidence": [
                    f"в контейнере «{container['name']}» уже {container['project_children']} проектных папок",
                    f"из них совместимого типа «{family}»: {same_family_examples}",
                    "проект перемещается целой папкой; внутренняя структура не меняется",
                ],
                "category": "Папка проекта",
                "project_hint": None,
                "extension": "",
                "learned_container": True,
            }
        )

    items.sort(key=lambda item: str(item.get("source") or "").casefold())
    return {
        "items": items,
        "summary": {
            "containers": len(containers),
            "folder_moves": len(items),
            "ambiguous": ambiguous,
        },
    }
