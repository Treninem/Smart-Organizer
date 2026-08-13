from __future__ import annotations

import re
from collections import Counter


def _search_text(value: str) -> str:
    normalized = re.sub(r"[\W_]+", " ", str(value).casefold(), flags=re.UNICODE)
    return " " + " ".join(normalized.split()) + " "


def detect_template(record: dict, templates: list[dict]) -> str | None:
    text = _search_text(f"{record.get('path', '')} {record.get('name', '')}")
    best: tuple[int, str] | None = None
    for template in templates:
        score = 0
        for keyword in template.get("keywords", []):
            needle = _search_text(keyword).strip()
            if needle and f" {needle} " in text:
                score += 2
        for marker in template.get("markers", []):
            needle = _search_text(marker).strip()
            if needle and f" {needle} " in text:
                score += 3
        if score:
            candidate = (score, str(template.get("name", "Неизвестный шаблон")))
            if best is None or candidate > best:
                best = candidate
    return best[1] if best else None


def summarize_template_matches(records: list[dict], templates: list[dict]) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for record in records:
        match = detect_template(record, templates)
        if match:
            counts[match] += 1
    return counts.most_common()
