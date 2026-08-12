from __future__ import annotations

import argparse

from core.paths import app_root
from core.updater import apply_source_update, fetch_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Smart Organizer updater")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest = fetch_manifest()
    if not args.apply:
        print(f"Последняя версия: {manifest.get('version', '?')}")
        return 0
    changed = apply_source_update(app_root(), manifest)
    print(f"Обновлено файлов: {len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
