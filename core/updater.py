from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

REPO_RAW = "https://raw.githubusercontent.com/Treninem/Smart-Organizer/main"
MANIFEST_URL = f"{REPO_RAW}/update-manifest.json"


def parse_version(value: str) -> tuple[int, ...]:
    value = value.strip().lower().lstrip("v")
    parts = []
    for token in value.split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def fetch_manifest(timeout: int = 8) -> dict:
    req = urllib.request.Request(MANIFEST_URL, headers={"User-Agent": "Smart-Organizer-Updater"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def update_available(current_version: str, manifest: dict) -> bool:
    return parse_version(manifest.get("version", "0")) > parse_version(current_version)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def apply_source_update(app_root: Path, manifest: dict) -> list[str]:
    """Update only declared program files. The local data/ directory is never touched."""
    staging = app_root / ".update-staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    try:
        for item in manifest.get("files", []):
            rel = item["path"].replace("\\", "/").lstrip("/")
            if rel == "data" or rel.startswith("data/") or rel.startswith("logs/"):
                continue
            target_stage = staging / rel
            target_stage.parent.mkdir(parents=True, exist_ok=True)
            url = f"{REPO_RAW}/{rel}"
            req = urllib.request.Request(url, headers={"User-Agent": "Smart-Organizer-Updater"})
            with urllib.request.urlopen(req, timeout=20) as response, target_stage.open("wb") as out:
                shutil.copyfileobj(response, out)
            expected = item.get("sha256")
            if expected and sha256_file(target_stage).lower() != expected.lower():
                raise RuntimeError(f"Контрольная сумма не совпала: {rel}")
        for item in manifest.get("files", []):
            rel = item["path"].replace("\\", "/").lstrip("/")
            if rel == "data" or rel.startswith("data/") or rel.startswith("logs/"):
                continue
            src = staging / rel
            if not src.exists():
                continue
            dst = app_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            changed.append(rel)
        return changed
    finally:
        shutil.rmtree(staging, ignore_errors=True)
