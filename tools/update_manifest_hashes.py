from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "update-manifest.json"
VERSION = ROOT / "version.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = json.loads(VERSION.read_text(encoding="utf-8"))
    manifest["version"] = str(version.get("version", manifest.get("version", "0.0.0")))

    for item in manifest.get("files", []):
        rel = str(item.get("path", "")).replace("\\", "/").lstrip("/")
        if not rel:
            continue
        path = ROOT / rel
        if not path.is_file():
            raise FileNotFoundError(f"Manifest file does not exist: {rel}")
        item["sha256"] = sha256(path)

    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
