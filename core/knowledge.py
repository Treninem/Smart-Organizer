from __future__ import annotations

import json
from pathlib import Path


def load_initial_knowledge(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def knowledge_items(payload: dict) -> list[dict]:
    items: list[dict] = []
    for project in payload.get("projects", []):
        items.append({"kind": "project", "name": project["name"], **project})
    for rule in payload.get("rules", []):
        items.append({"kind": "rule", "name": rule["id"], **rule})
    return items
