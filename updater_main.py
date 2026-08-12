from __future__ import annotations

import argparse
import os

from core.paths import app_root
from core.runtime_update import (
    create_apply_script,
    download_runtime_bundle,
    fetch_runtime_manifest,
    fetch_runtime_release,
    find_runtime_asset,
    launch_apply_script,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smart Organizer recovery updater")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check full runtime package availability without changing files",
    )
    # Keep --apply for compatibility with older instructions. Applying is now
    # also the default so updater.exe can be used by double-click as a repair tool.
    parser.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    manifest = fetch_runtime_manifest()
    release = fetch_runtime_release()
    asset = find_runtime_asset(release)
    if not asset:
        raise RuntimeError("SmartOrganizer-runtime.zip is not published")

    version = str(manifest.get("version", "?"))
    if args.check:
        print(f"Available version: {version}")
        print(f"Runtime: {asset.get('name', '?')}")
        return 0

    root = app_root()
    bundle = download_runtime_bundle(root, asset)
    script = create_apply_script(root, bundle, os.getpid())
    launch_apply_script(script)
    print(f"Smart Organizer {version}: verified full runtime downloaded.")
    print("Update will be applied automatically after updater.exe exits.")
    print("data/ and logs/ are preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
