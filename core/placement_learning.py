from __future__ import annotations

import os
from pathlib import Path

from core.layout_memory import destination_allowed_by_layout
from core.project_manager import INBOX_ROOT_NAMES

SETTINGS_KEY = "confirmed_placement_rules"
MAX_RULES = 500
MAX_EXAMPLES_PER_RULE = 12
MATURE_CONFIRMATIONS = 2


def _norm(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


def _signature_from_values(project: str, category: str, extension: str) -> str:
    return "|".join(
        [
            project.strip().casefold() or "*",
            category.strip().casefold() or "*",
            extension.strip().casefold() or "*",
        ]
    )


def record_signature(record: dict) -> str:
    return _signature_from_values(
        str(record.get("project_hint") or ""),
        str(record.get("category") or ""),
        str(record.get("extension") or Path(str(record.get("name") or "")).suffix),
    )


def item_signature(item: dict) -> str:
    return _signature_from_values(
        str(item.get("project_hint") or ""),
        str(item.get("category") or ""),
        str(item.get("extension") or Path(str(item.get("source") or "")).suffix),
    )


def _loose_source(record: dict, scan_root: str | None) -> bool:
    """Only learn routing for loose/inbox files, never project internals."""
    if not scan_root:
        return False
    parent = Path(str(record.get("parent") or ""))
    root = Path(scan_root)
    if _norm(parent) == _norm(root):
        return True
    try:
        relative_parent = parent.relative_to(root)
    except (ValueError, OSError):
        return False
    if len(relative_parent.parts) != 1:
        return False
    return relative_parent.parts[0].strip().casefold() in INBOX_ROOT_NAMES


def _rule_key(signature: str, target_dir: str) -> tuple[str, str]:
    return signature, _norm(target_dir)


def _clean_rules(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    result: list[dict] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        signature = str(raw.get("signature") or "").strip()
        target_dir = str(raw.get("target_dir") or "").strip()
        if not signature or not target_dir:
            continue
        item = dict(raw)
        item["signature"] = signature
        item["target_dir"] = target_dir
        try:
            item["confirmations"] = max(0, int(item.get("confirmations", 0)))
        except (TypeError, ValueError):
            item["confirmations"] = 0
        examples = item.get("examples")
        item["examples"] = [dict(example) for example in examples if isinstance(example, dict)] if isinstance(examples, list) else []
        result.append(item)
    return result


def remember_confirmed_items(database, items: list[dict]) -> int:
    """Learn from successfully applied, explicitly confirmed file placements.

    One confirmation is not enough for automatic influence. The same semantic
    signature must be confirmed repeatedly before it can become a mature rule.
    """
    rules = _clean_rules(database.get_setting(SETTINGS_KEY, []) or [])
    by_key = {_rule_key(rule["signature"], rule["target_dir"]): rule for rule in rules}
    changed = 0

    for item in items:
        if item.get("kind", "file") == "folder":
            continue
        source = str(item.get("source") or "").strip()
        target = str(item.get("target_path") or "").strip()
        target_dir = str(item.get("target_dir") or Path(target).parent).strip()
        if not source or not target or not target_dir:
            continue
        signature = item_signature(item)
        key = _rule_key(signature, target_dir)
        rule = by_key.get(key)
        if rule is None:
            rule = {
                "signature": signature,
                "target_dir": target_dir,
                "confirmations": 0,
                "examples": [],
            }
            rules.append(rule)
            by_key[key] = rule

        example_key = (_norm(source), _norm(target))
        examples = list(rule.get("examples") or [])
        if any((_norm(example.get("source") or ""), _norm(example.get("target") or "")) == example_key for example in examples):
            continue
        examples.append({"source": source, "target": target})
        rule["examples"] = examples[-MAX_EXAMPLES_PER_RULE:]
        rule["confirmations"] = int(rule.get("confirmations", 0)) + 1
        changed += 1

    if changed:
        rules.sort(key=lambda rule: (-int(rule.get("confirmations", 0)), rule["signature"], _norm(rule["target_dir"])))
        database.set_setting(SETTINGS_KEY, rules[:MAX_RULES])
    return changed


def forget_undone_moves(database, entries: list[dict]) -> int:
    """Remove positive evidence for exact moves that the user later undid."""
    rules = _clean_rules(database.get_setting(SETTINGS_KEY, []) or [])
    undone_pairs = {
        (_norm(row.get("source") or ""), _norm(row.get("target") or ""))
        for row in entries
        if row.get("op_type") in {"move", "rename"} and row.get("source") and row.get("target")
    }
    if not undone_pairs:
        return 0

    changed = 0
    kept_rules: list[dict] = []
    for rule in rules:
        examples = list(rule.get("examples") or [])
        kept_examples = [
            example
            for example in examples
            if (_norm(example.get("source") or ""), _norm(example.get("target") or "")) not in undone_pairs
        ]
        removed = len(examples) - len(kept_examples)
        if removed:
            changed += removed
            rule = dict(rule)
            rule["examples"] = kept_examples
            rule["confirmations"] = max(0, int(rule.get("confirmations", 0)) - removed)
        if int(rule.get("confirmations", 0)) > 0:
            kept_rules.append(rule)

    if changed:
        database.set_setting(SETTINGS_KEY, kept_rules[:MAX_RULES])
    return changed


def learning_summary(rules: list[dict] | None) -> dict:
    cleaned = _clean_rules(rules or [])
    mature = sum(1 for rule in cleaned if int(rule.get("confirmations", 0)) >= MATURE_CONFIRMATIONS)
    return {
        "rules": len(cleaned),
        "mature": mature,
        "learning": len(cleaned) - mature,
        "confirmations": sum(int(rule.get("confirmations", 0)) for rule in cleaned),
    }


def apply_confirmed_learning(
    plan: dict,
    files: list[dict],
    folders: list[dict],
    rules: list[dict] | None,
    scan_root: str | None,
) -> dict:
    """Use mature local placement rules without overriding current real layout.

    Rules affect only loose files. Current user-layout evidence always wins. A
    single confirmation remains informational. Competing mature destinations
    with the same confirmation count are treated as ambiguous and never execute.
    """
    cleaned = _clean_rules(rules or [])
    result = {**plan, "summary": dict(plan.get("summary") or {})}
    summary = learning_summary(cleaned)
    result["summary"].update(
        learned_rules=summary["rules"],
        mature_learned_rules=summary["mature"],
        pending_learned_rules=summary["learning"],
        learned_rule_confirmations=summary["confirmations"],
    )
    if not cleaned:
        result["learning_applied"] = True
        return result

    existing_folders = {_norm(folder.get("path") or ""): str(folder.get("path") or "") for folder in folders if folder.get("path")}
    records = {str(record.get("path") or ""): record for record in files}
    by_signature: dict[str, list[dict]] = {}
    for rule in cleaned:
        if _norm(rule["target_dir"]) not in existing_folders:
            continue
        by_signature.setdefault(rule["signature"], []).append(rule)

    items: list[dict] = []
    boosted = 0
    ambiguous = 0
    pending = 0

    for raw in plan.get("items", []):
        item = dict(raw)
        if item.get("kind", "file") == "folder":
            items.append(item)
            continue
        source = str(item.get("source") or "")
        record = records.get(source)
        if not record or not _loose_source(record, scan_root):
            items.append(item)
            continue

        candidates = by_signature.get(record_signature(record), [])
        if not candidates:
            items.append(item)
            continue
        candidates = sorted(
            candidates,
            key=lambda rule: (int(rule.get("confirmations", 0)), _norm(rule["target_dir"])),
            reverse=True,
        )
        best_count = int(candidates[0].get("confirmations", 0))
        best_rules = [rule for rule in candidates if int(rule.get("confirmations", 0)) == best_count]

        # Existing current-layout evidence is stronger than historical memory.
        current_reason = str(item.get("reason") or "")
        if current_reason.startswith("user_layout:"):
            current_target = _norm(item.get("target_dir") or "")
            matching = next((rule for rule in candidates if _norm(rule["target_dir"]) == current_target), None)
            if matching:
                evidence = list(item.get("evidence") or [])
                evidence.append(f"это направление уже подтверждалось {int(matching.get('confirmations', 0))} раз")
                item["evidence"] = evidence
            items.append(item)
            continue

        if best_count < MATURE_CONFIRMATIONS:
            pending += 1
            evidence = list(item.get("evidence") or [])
            evidence.append("локальная память видела похожее подтверждение один раз; этого недостаточно для автоматического решения")
            item["evidence"] = evidence
            items.append(item)
            continue

        if len(best_rules) != 1:
            ambiguous += 1
            item.update(mode="review", requires_confirmation=True, confidence="ambiguous")
            item["reason"] = "conflicting_confirmed_learning"
            evidence = list(item.get("evidence") or [])
            evidence.append("локальная память содержит несколько одинаково подтверждённых мест; решение остановлено")
            item["evidence"] = evidence
            items.append(item)
            continue

        chosen = best_rules[0]
        target_dir = existing_folders.get(_norm(chosen["target_dir"]))
        if not target_dir or not destination_allowed_by_layout(record, target_dir, files, scan_root):
            items.append(item)
            continue
        target_path = str(Path(target_dir) / str(record.get("name") or Path(source).name))
        if any(_norm(other.get("path") or "") == _norm(target_path) for other in files):
            items.append(item)
            continue

        item.update(
            target_dir=target_dir,
            target_path=target_path,
            mode="existing",
            score=max(int(item.get("score") or 0), 210 + min(best_count, 20)),
            confidence="high",
            requires_confirmation=False,
            reason="confirmed_local_learning",
        )
        evidence = list(item.get("evidence") or [])
        evidence.append(f"вы уже подтверждали похожее размещение сюда {best_count} раз")
        evidence.append("правило хранится только в локальной knowledge.db")
        item["evidence"] = evidence
        boosted += 1
        items.append(item)

    result["items"] = items
    result["learning_applied"] = True
    result["summary"]["learned_moves_boosted"] = boosted
    result["summary"]["learned_moves_ambiguous"] = ambiguous
    result["summary"]["learned_moves_pending"] = pending
    return result
