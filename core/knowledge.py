from __future__ import annotations

import json
from pathlib import Path


def _merge_named(base: list[dict], extra: list[dict], key: str) -> list[dict]:
    """Merge catalogs deterministically without creating duplicate identities."""
    order: list[str] = []
    merged: dict[str, dict] = {}
    for item in [*base, *extra]:
        if not isinstance(item, dict):
            continue
        name = str(item.get(key) or "").strip()
        if not name:
            continue
        if name not in merged:
            order.append(name)
            merged[name] = dict(item)
        else:
            combined = dict(merged[name])
            combined.update(item)
            merged[name] = combined
    return [merged[name] for name in order]


def load_initial_knowledge(config_path: Path) -> dict:
    """Load base knowledge plus optional expandable local starter catalogs.

    Keeping historical project identities in a separate JSON file makes it
    possible to grow recognition without turning the core safety rules into one
    enormous document. User-learned knowledge still lives only in knowledge.db.
    """
    with config_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    extra_path = config_path.with_name("project_catalog_history.json")
    if extra_path.is_file():
        with extra_path.open("r", encoding="utf-8") as fh:
            extra = json.load(fh)
        payload["projects"] = _merge_named(payload.get("projects", []), extra.get("projects", []), "name")
        payload["templates"] = _merge_named(payload.get("templates", []), extra.get("templates", []), "name")
        payload["rules"] = _merge_named(payload.get("rules", []), extra.get("rules", []), "id")
    return payload


def knowledge_items(payload: dict) -> list[dict]:
    items: list[dict] = []
    for project in payload.get("projects", []):
        items.append({"kind": "project", "name": project["name"], **project})
    for template in payload.get("templates", []):
        items.append({"kind": "template", "name": template["name"], **template})
    for rule in payload.get("rules", []):
        items.append({"kind": "rule", "name": rule["id"], **rule})
    return items
