from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from core.duplicates import COPY_MARKER_RE

_SPACE_RE = re.compile(r"[\s._-]+")


def normalized_duplicate_name(name: str) -> str:
    """Normalize obvious copy suffixes without claiming content equality."""
    path = Path(str(name))
    stem = COPY_MARKER_RE.sub("", path.stem)
    stem = _SPACE_RE.sub(" ", stem).strip().casefold()
    return f"{stem}{path.suffix.casefold()}"


def duplicate_candidate_groups(records: Iterable[dict], limit_per_kind: int = 200) -> dict:
    """Find cheap duplicate candidates by normalized name and size.

    These groups are informational only. Exact duplicate status still requires
    a full SHA-256 match through core.duplicates.exact_duplicate_groups().
    """
    rows = [dict(record) for record in records]
    by_name: dict[str, list[dict]] = defaultdict(list)
    by_size: dict[int, list[dict]] = defaultdict(list)

    for record in rows:
        name_key = normalized_duplicate_name(record.get("name", ""))
        if name_key:
            by_name[name_key].append(record)
        try:
            size = int(record.get("size", -1))
        except (TypeError, ValueError):
            size = -1
        if size >= 0:
            by_size[size].append(record)

    name_groups = []
    for key, matches in by_name.items():
        if len(matches) < 2:
            continue
        ordered = sorted(matches, key=lambda item: str(item.get("path", "")).casefold())
        name_groups.append(
            {
                "key": key,
                "count": len(ordered),
                "paths": [str(item.get("path", "")) for item in ordered],
                "sizes": sorted({int(item.get("size", 0)) for item in ordered}),
            }
        )

    size_groups = []
    for size, matches in by_size.items():
        if len(matches) < 2:
            continue
        ordered = sorted(matches, key=lambda item: str(item.get("path", "")).casefold())
        size_groups.append(
            {
                "size": size,
                "count": len(ordered),
                "paths": [str(item.get("path", "")) for item in ordered],
            }
        )

    name_groups.sort(key=lambda item: (-item["count"], item["key"]))
    size_groups.sort(key=lambda item: (-item["size"], -item["count"]))
    return {
        "summary": {
            "files": len(rows),
            "same_name_groups": len(name_groups),
            "same_size_groups": len(size_groups),
        },
        "name_groups": name_groups[:limit_per_kind],
        "size_groups": size_groups[:limit_per_kind],
        "truncated_name_groups": max(0, len(name_groups) - limit_per_kind),
        "truncated_size_groups": max(0, len(size_groups) - limit_per_kind),
    }
