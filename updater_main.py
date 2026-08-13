from __future__ import annotations

import argparse
import os
from pathlib import Path

from core.paths import app_root
from core.runtime_update import (
    create_apply_script,
    download_runtime_bundle,
    ensure_runtime_release_ready,
    fetch_runtime_manifest,
    fetch_runtime_release,
    find_runtime_asset,
    launch_apply_script,
)


def _looks_like_install(root: Path) -> bool:
    return (root / "SmartOrganizer.exe").exists() or (root / "data").is_dir()


def _resolve_install_root(explicit: str | None) -> Path:
    if explicit:
        return Path(os.path.expandvars(explicit)).expanduser().resolve()

    own_dir = app_root()
    candidates = [
        own_dir,
        Path(r"D:\Smart-Organizer"),
        Path.home() / "Documents" / "Smart-Organizer",
    ]
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if _looks_like_install(candidate):
            return candidate.resolve()

    raise RuntimeError(
        "Smart Organizer installation was not found. "
        "Place updater.exe in the Smart-Organizer folder or use --install-dir."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smart Organizer recovery updater")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check full runtime package availability without changing files",
    )
    parser.add_argument(
        "--install-dir",
        help="Existing Smart Organizer installation directory",
    )
    # Keep --apply for compatibility with older instructions. Applying is now
    # also the default so updater.exe can be used by double-click as a repair tool.
    parser.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    manifest = fetch_runtime_manifest()
    release = fetch_runtime_release()
    ensure_runtime_release_ready(manifest, release)
    asset = find_runtime_asset(release)
    if not asset:
        raise RuntimeError("SmartOrganizer-runtime.zip is not published")

    version = str(manifest.get("version", "?"))
    if args.check:
        print(f"Available version: {version}")
        print(f"Runtime: {asset.get('name', '?')}")
        return 0

    root = _resolve_install_root(args.install_dir)
    root.mkdir(parents=True, exist_ok=True)
    bundle = download_runtime_bundle(root, asset)
    script = create_apply_script(root, bundle, os.getpid())
    launch_apply_script(script)
    print(f"Smart Organizer {version}: verified full runtime downloaded.")
    print(f"Install directory: {root}")
    print("Update will be applied automatically after updater.exe exits.")
    print("data/ and logs/ are preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
