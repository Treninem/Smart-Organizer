from __future__ import annotations

import os
from pathlib import Path

SETTINGS_KEY = "undo_rejected_destinations"
MAX_ITEMS = 500


def _norm(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


def rejected_pair(source: str, target: str, rules: list[dict] | None) -> bool:
    source_key = _norm(source)
    target_key = _norm(target)
    for rule in rules or []:
        if _norm(rule.get("source") or "") == source_key and _norm(rule.get("target") or "") == target_key:
            return True
    return False


def remember_undone_moves(database, entries: list[dict]) -> int:
    """Remember exact source/destination pairs that the user deliberately undid."""
    rules = [dict(item) for item in (database.get_setting(SETTINGS_KEY, []) or []) if isinstance(item, dict)]
    existing = {(_norm(item.get("source") or ""), _norm(item.get("target") or "")) for item in rules}
    added = 0
    for row in entries:
        if row.get("op_type") not in {"move", "rename"}:
            continue
        source = str(row.get("source") or "")
        target = str(row.get("target") or "")
        if not source or not target:
            continue
        key = (_norm(source), _norm(target))
        if key in existing:
            continue
        existing.add(key)
        rules.append({"source": source, "target": target, "reason": "user_undo"})
        added += 1
    if added:
        database.set_setting(SETTINGS_KEY, rules[-MAX_ITEMS:])
    return added


def apply_undo_feedback(plan: dict, rules: list[dict] | None) -> dict:
    """Turn previously undone exact destinations into review-only suggestions."""
    if not rules:
        return plan
    result = {**plan, "summary": dict(plan.get("summary") or {})}
    items = []
    blocked = 0
    for raw in plan.get("items", []):
        item = dict(raw)
        if rejected_pair(str(item.get("source") or ""), str(item.get("target_path") or ""), rules):
            item["mode"] = "review"
            item["requires_confirmation"] = True
            item["confidence"] = "rejected"
            item["reason"] = "destination_rejected_by_previous_undo"
            evidence = list(item.get("evidence") or [])
            evidence.append("это точное направление уже было отменено через Undo")
            item["evidence"] = evidence
            item.pop("allow_confirmed_creation", None)
            blocked += 1
        items.append(item)
    result["items"] = items
    result["summary"]["blocked_by_undo_memory"] = blocked
    return result
