from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

VERSION_RE = re.compile(
    r"(?i)(?<![a-z0-9])(?:v|version[\s_-]*)?"
    r"(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?"
    r"(?:[\s._-]*(alpha|beta|rc|preview|pre|test|dev)[\s._-]*(\d+)?)?"
)
COPY_SUFFIX_RE = re.compile(
    r"(?i)(?:\s*[\(\[]\d+[\)\]]|\s*-\s*(?:copy|копия)(?:\s*\(\d+\))?|\s+(?:copy|копия))$"
)
CHANNEL_RANK = {"dev": 0, "test": 0, "alpha": 1, "pre": 2, "preview": 2, "beta": 2, "rc": 3, "release": 4}


@dataclass(frozen=True)
class VersionInfo:
    raw: str
    parts: tuple[int, ...]
    channel: str = "release"
    qualifier_number: int = 0

    @property
    def normalized(self) -> str:
        base = "v" + ".".join(str(p) for p in self.parts)
        if self.channel != "release":
            suffix = self.channel + (str(self.qualifier_number) if self.qualifier_number else "")
            return f"{base}-{suffix}"
        return base

    @property
    def sort_key(self) -> tuple:
        padded = self.parts + (0,) * (4 - len(self.parts))
        return padded[:4] + (CHANNEL_RANK.get(self.channel, 0), self.qualifier_number)


def detect_version(value: str) -> VersionInfo | None:
    stem = Path(value).stem
    matches = list(VERSION_RE.finditer(stem))
    if not matches:
        return None
    match = max(
        matches,
        key=lambda m: (
            int(bool(re.search(r"(?i)(?:^|[^a-z0-9])(?:v|version)", m.group(0)))),
            int("." in m.group(0)),
            len(m.group(0)),
        ),
    )
    groups = match.groups()
    numeric = [groups[i] for i in range(4)]
    parts = tuple(int(x) for x in numeric if x is not None)
    if not parts:
        return None
    channel = (groups[4] or "release").lower()
    if channel == "preview":
        channel = "pre"
    qualifier = int(groups[5] or 0)
    return VersionInfo(match.group(0).strip(" _-"), parts, channel, qualifier)


def artifact_key(name: str) -> str:
    stem = Path(name).stem
    stem = COPY_SUFFIX_RE.sub("", stem)
    match = VERSION_RE.search(stem)
    if match:
        stem = stem[: match.start()] + " " + stem[match.end() :]
    stem = re.sub(r"(?i)\b(?:final|latest|release|build)\b", " ", stem)
    stem = re.sub(r"[\W_]+", " ", stem, flags=re.UNICODE).strip().lower()
    return stem or Path(name).stem.lower()


def version_groups(records: Iterable[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for record in records:
        info = detect_version(record.get("name", ""))
        if not info:
            continue
        key = (record.get("project_hint") or "Не определён", artifact_key(record.get("name", "")))
        item = dict(record)
        item["_version"] = info
        grouped.setdefault(key, []).append(item)

    results: list[dict] = []
    for (project, artifact), items in grouped.items():
        versions = {item["_version"].normalized for item in items}
        if len(versions) < 2:
            continue
        ordered = sorted(items, key=lambda x: x["_version"].sort_key, reverse=True)
        newest = ordered[0]
        results.append(
            {
                "project": project,
                "artifact": artifact,
                "newest": newest["_version"].normalized,
                "newest_path": newest.get("path"),
                "older": [
                    {"version": item["_version"].normalized, "path": item.get("path"), "name": item.get("name")}
                    for item in ordered[1:]
                ],
            }
        )
    return sorted(results, key=lambda x: (x["project"].lower(), x["artifact"]))


class VersionManager:
    def detect(self, name):
        info = detect_version(name)
        return [info.raw] if info else []

    def classify(self, version):
        info = detect_version(str(version))
        if not info:
            return "unknown"
        return "test" if info.channel in {"test", "dev", "alpha", "beta", "rc", "pre"} else "release"
