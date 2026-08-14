from __future__ import annotations

import json
import os
import time
from pathlib import Path

from core.classifier import project_hint
from core.content_profile import content_profile
from core.operation_executor import execute_batch
from core.operation_journal import OperationJournal, ReversibleOperation
from core.placement_learning import MATURE_CONFIRMATIONS, SETTINGS_KEY as LEARNING_KEY, record_signature
from core.version_manager import detect_version
from core.windows_paths import downloads_path

POWER_SETTINGS_KEY = "power_settings_v1"
GENERIC_PROJECT_FILENAMES = {
    "main.py", "bot.py", "config.json", "settings.json", "requirements.txt", "pyproject.toml",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "dockerfile",
    "compose.yml", "docker-compose.yml", "server.properties", "project.godot",
}

DEFAULT_POWER_SETTINGS = {
    "background_enabled": True,
    "background_interval_minutes": 5,
    "start_with_windows": True,
    "close_to_background": True,
    "auto_sort_downloads": True,
    "download_min_age_seconds": 120,
    "separate_chatgpt": True,
    "chatgpt_target": "",
    "project_routes": {},
    "routes": {
        "Изображения": "",
        "Видео": "",
        "Аудио": "",
        "Документы": "",
        "Архивы": "",
        "Код": "",
        "Чертежи": "",
        "Программы": "",
        "Другое": "",
    },
    "keep_latest_versions": 5,
    "auto_quarantine_old_versions": False,
    "auto_correct_own_moves": True,
    "strictness": "strict",
}


def normalized_power_settings(value) -> dict:
    result = json.loads(json.dumps(DEFAULT_POWER_SETTINGS, ensure_ascii=False))
    if isinstance(value, dict):
        for key, raw in value.items():
            if key in {"routes", "project_routes"} and isinstance(raw, dict):
                result[key].update({str(k): str(v or "") for k, v in raw.items()})
            elif key in result:
                result[key] = raw
    try:
        result["background_interval_minutes"] = max(1, min(240, int(result["background_interval_minutes"])))
    except (TypeError, ValueError):
        result["background_interval_minutes"] = 5
    try:
        result["download_min_age_seconds"] = max(30, min(3600, int(result["download_min_age_seconds"])))
    except (TypeError, ValueError):
        result["download_min_age_seconds"] = 120
    try:
        result["keep_latest_versions"] = max(1, min(50, int(result["keep_latest_versions"])))
    except (TypeError, ValueError):
        result["keep_latest_versions"] = 5
    if result.get("strictness") not in {"strict", "balanced"}:
        result["strictness"] = "strict"
    for key in (
        "background_enabled", "start_with_windows", "close_to_background",
        "auto_sort_downloads", "separate_chatgpt", "auto_quarantine_old_versions",
        "auto_correct_own_moves",
    ):
        result[key] = bool(result.get(key))
    return result


def _existing_target(value: str) -> Path | None:
    if not str(value or "").strip():
        return None
    path = Path(str(value)).expanduser()
    return path if path.is_dir() else None


def _mature_learning_target(record: dict, rules: list[dict]) -> tuple[Path | None, str]:
    signature = record_signature(record)
    candidates: list[tuple[int, Path]] = []
    for rule in rules if isinstance(rules, list) else []:
        if not isinstance(rule, dict) or str(rule.get("signature") or "") != signature:
            continue
        try:
            confirmations = int(rule.get("confirmations", 0))
        except (TypeError, ValueError):
            continue
        if confirmations < MATURE_CONFIRMATIONS:
            continue
        target = _existing_target(str(rule.get("target_dir") or ""))
        if target is not None:
            candidates.append((confirmations, target))
    if not candidates:
        return None, ""
    best = max(count for count, _path in candidates)
    winners = sorted({str(path) for count, path in candidates if count == best}, key=str.casefold)
    if len(winners) != 1:
        return None, "ambiguous-learned-route"
    return Path(winners[0]), f"learned-after-{best}-confirmations"


def _record_for_path(source: Path, projects: list[dict]) -> tuple[dict, dict]:
    profile = content_profile(source)
    hint = project_hint(Path(source.name), projects)
    record = {
        "path": str(source),
        "parent": str(source.parent),
        "name": source.name,
        "extension": profile["extension"],
        "category": profile["category"],
        "project_hint": hint,
    }
    return profile, record


def infer_project_routes(folders: list[dict], projects: list[dict]) -> dict[str, str]:
    """Infer only unique top-level-looking existing project folders.

    The folder's own name must uniquely identify the project. Nested folders do
    not inherit evidence merely because an ancestor contains the project name.
    An unversioned canonical folder wins over version folders. Multiple equally
    plausible folders remain ambiguous and produce no background route.
    """
    result: dict[str, str] = {}
    for project in projects:
        project_name = str(project.get("name") or "").strip()
        if not project_name:
            continue
        candidates: list[tuple[bool, int, str]] = []
        for folder in folders:
            path = str(folder.get("path") or "").strip()
            name = str(folder.get("name") or Path(path).name).strip()
            if not path or not name:
                continue
            if project_hint(Path(name), projects) != project_name:
                continue
            try:
                depth = int(folder.get("depth", 0) or 0)
            except (TypeError, ValueError):
                depth = 0
            candidates.append((detect_version(name) is None, depth, path))
        if not candidates:
            continue
        unversioned = [item for item in candidates if item[0]]
        pool = unversioned or candidates
        min_depth = min(item[1] for item in pool)
        winners = sorted({item[2] for item in pool if item[1] == min_depth}, key=str.casefold)
        if len(winners) == 1 and Path(winners[0]).is_dir():
            result[project_name] = winners[0]
    return result


def choose_configured_target(
    source: Path,
    settings: dict,
    learning_rules: list[dict],
    projects: list[dict],
    *,
    allow_learning: bool = True,
) -> dict | None:
    """Choose one strict destination from project/origin/category/local memory."""
    profile, record = _record_for_path(source, projects)
    if profile["is_partial_download"]:
        return None

    target: Path | None = None
    reason = ""
    project_name = str(record.get("project_hint") or "")
    project_routes = settings.get("project_routes") if isinstance(settings.get("project_routes"), dict) else {}
    if project_name:
        target = _existing_target(str(project_routes.get(project_name, "") or ""))
        if target is not None:
            reason = f"explicit-project-route:{project_name}"
        if target is None:
            inferred = settings.get("_inferred_project_routes") if isinstance(settings.get("_inferred_project_routes"), dict) else {}
            target = _existing_target(str(inferred.get(project_name, "") or ""))
            if target is not None:
                reason = f"existing-project-folder:{project_name}"

    # Generic project filenames are too ambiguous for background category or
    # learned routing when the project itself was not identified.
    if target is None and not project_name and source.name.casefold() in GENERIC_PROJECT_FILENAMES:
        return None

    if target is None and settings.get("separate_chatgpt") and profile["is_ai_named"]:
        target = _existing_target(str(settings.get("chatgpt_target") or ""))
        if target is not None:
            reason = "explicit-chatgpt-route"

    if target is None:
        routes = settings.get("routes") if isinstance(settings.get("routes"), dict) else {}
        target = _existing_target(str(routes.get(profile["category"], "") or ""))
        if target is not None:
            reason = f"explicit-category-route:{profile['category']}"

    if target is None and allow_learning:
        target, learned_reason = _mature_learning_target(record, learning_rules)
        reason = learned_reason

    if target is None:
        return None
    if os.path.normcase(os.path.normpath(str(target))) == os.path.normcase(os.path.normpath(str(source.parent))):
        return None
    destination = target / source.name
    if destination.exists():
        return None
    return {
        "source": str(source),
        "target_dir": str(target),
        "target_path": str(destination),
        "profile": profile,
        "record": record,
        "reason": reason,
    }


def choose_download_target(
    source: Path,
    settings: dict,
    learning_rules: list[dict],
    projects: list[dict],
) -> dict | None:
    return choose_configured_target(source, settings, learning_rules, projects, allow_learning=True)


def collect_download_moves(database, projects: list[dict], now: float | None = None) -> list[dict]:
    settings = normalized_power_settings(database.get_setting(POWER_SETTINGS_KEY, {}))
    if not settings["background_enabled"] or not settings["auto_sort_downloads"]:
        return []
    root = downloads_path()
    if not root.is_dir():
        return []
    settings["_inferred_project_routes"] = infer_project_routes(database.snapshot_folders(), projects)
    learning = database.get_setting(LEARNING_KEY, []) or []
    timestamp = float(now if now is not None else time.time())
    result: list[dict] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file():
            continue
        try:
            age = timestamp - path.stat().st_mtime
        except OSError:
            continue
        if age < settings["download_min_age_seconds"]:
            continue
        decision = choose_download_target(path, settings, learning, projects)
        if decision:
            result.append(decision)
    return result


def apply_download_moves(database, projects: list[dict]) -> dict:
    decisions = collect_download_moves(database, projects)
    if not decisions:
        return {"moved": 0, "batch_id": None, "decisions": []}
    operations = [
        ReversibleOperation("move", item["source"], item["target_path"], f"background download: {item['reason']}")
        for item in decisions
    ]
    journal = OperationJournal(database)
    batch_id = journal.plan_batch(operations, label="background-download-routing")
    result = execute_batch(journal, batch_id)
    database.log_action(
        "background-download-routing",
        batch_id,
        "ok",
        f"moved={result['applied']}; routes=" + ",".join(item["reason"] for item in decisions),
    )
    return {"moved": result["applied"], "batch_id": batch_id, "decisions": decisions}


def collect_corrections(database, projects: list[dict], limit: int = 1000) -> list[dict]:
    """Correct only Smart Organizer's own still-applied moves.

    A correction requires a newer explicit project/origin/category route. It
    never sweeps arbitrary user files and never relies on historical learning
    or inferred folder names alone.
    """
    settings = normalized_power_settings(database.get_setting(POWER_SETTINGS_KEY, {}))
    if not settings.get("auto_correct_own_moves"):
        return []
    learning = database.get_setting(LEARNING_KEY, []) or []
    seen: set[str] = set()
    result: list[dict] = []
    for row in database.operation_entries(limit=limit):
        if row.get("status") != "applied" or row.get("op_type") not in {"move", "rename"}:
            continue
        current = Path(str(row.get("target") or ""))
        if not current.is_file():
            continue
        key = os.path.normcase(os.path.normpath(str(current)))
        if key in seen:
            continue
        seen.add(key)
        decision = choose_configured_target(current, settings, learning, projects, allow_learning=False)
        if not decision or not str(decision.get("reason") or "").startswith("explicit-"):
            continue
        decision["previous_batch_id"] = row.get("batch_id")
        decision["original_source"] = row.get("source")
        result.append(decision)
    return result


def apply_corrections(database, projects: list[dict]) -> dict:
    decisions = collect_corrections(database, projects)
    if not decisions:
        return {"corrected": 0, "batch_id": None, "decisions": []}
    journal = OperationJournal(database)
    operations = [
        ReversibleOperation("move", item["source"], item["target_path"], f"self-correction: {item['reason']}")
        for item in decisions
    ]
    batch_id = journal.plan_batch(operations, label="self-correction")
    execution = execute_batch(journal, batch_id)
    database.log_action(
        "self-correction",
        batch_id,
        "ok",
        f"corrected={execution['applied']}; only_own_previous_moves=1",
    )
    return {"corrected": execution["applied"], "batch_id": batch_id, "decisions": decisions}
