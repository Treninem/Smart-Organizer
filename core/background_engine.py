from __future__ import annotations

import json
import time
from pathlib import Path

from core.classifier import project_hint
from core.content_profile import content_profile
from core.operation_executor import execute_batch
from core.operation_journal import OperationJournal, ReversibleOperation
from core.placement_learning import MATURE_CONFIRMATIONS, SETTINGS_KEY as LEARNING_KEY, record_signature
from core.windows_paths import downloads_path

POWER_SETTINGS_KEY = "power_settings_v1"

DEFAULT_POWER_SETTINGS = {
    "background_enabled": True,
    "background_interval_minutes": 5,
    "start_with_windows": True,
    "close_to_background": True,
    "auto_sort_downloads": True,
    "download_min_age_seconds": 120,
    "separate_chatgpt": True,
    "chatgpt_target": "",
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
    "strictness": "strict",
}


def normalized_power_settings(value) -> dict:
    result = json.loads(json.dumps(DEFAULT_POWER_SETTINGS, ensure_ascii=False))
    if isinstance(value, dict):
        for key, raw in value.items():
            if key == "routes" and isinstance(raw, dict):
                result["routes"].update({str(k): str(v or "") for k, v in raw.items()})
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
    for key in ("background_enabled", "start_with_windows", "close_to_background", "auto_sort_downloads", "separate_chatgpt", "auto_quarantine_old_versions"):
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


def choose_download_target(
    source: Path,
    settings: dict,
    learning_rules: list[dict],
    projects: list[dict],
) -> dict | None:
    """Choose a destination for one finished top-level downloaded file.

    Explicit user routes outrank learning. ChatGPT/OpenAI filename markers can
    be separated when that option has a real existing target folder. Learned
    routes require repeated confirmations and a unique winner.
    """
    profile = content_profile(source)
    if profile["is_partial_download"]:
        return None

    record = {
        "path": str(source),
        "parent": str(source.parent),
        "name": source.name,
        "extension": profile["extension"],
        "category": profile["category"],
        "project_hint": project_hint(source, projects),
    }

    target: Path | None = None
    reason = ""
    if settings.get("separate_chatgpt") and profile["is_ai_named"]:
        target = _existing_target(str(settings.get("chatgpt_target") or ""))
        if target is not None:
            reason = "explicit-chatgpt-route"

    if target is None:
        routes = settings.get("routes") if isinstance(settings.get("routes"), dict) else {}
        target = _existing_target(str(routes.get(profile["category"], "") or ""))
        if target is not None:
            reason = f"explicit-category-route:{profile['category']}"

    if target is None:
        target, learned_reason = _mature_learning_target(record, learning_rules)
        reason = learned_reason

    if target is None:
        return None
    if target.resolve() == source.parent.resolve():
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


def collect_download_moves(database, projects: list[dict], now: float | None = None) -> list[dict]:
    settings = normalized_power_settings(database.get_setting(POWER_SETTINGS_KEY, {}))
    if not settings["background_enabled"] or not settings["auto_sort_downloads"]:
        return []
    root = downloads_path()
    if not root.is_dir():
        return []
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
    """Apply only explicitly configured or mature learned background routes."""
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
