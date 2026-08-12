from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

RUNTIME_MANIFEST_URL = "https://raw.githubusercontent.com/Treninem/Smart-Organizer/main/runtime-manifest.json"
RELEASE_API = "https://api.github.com/repos/Treninem/Smart-Organizer/releases/tags/auto-latest"
RUNTIME_ASSET = "SmartOrganizer-runtime.zip"
USER_AGENT = "Smart-Organizer-Runtime-Updater"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_runtime_manifest(timeout: int = 8) -> dict:
    req = urllib.request.Request(RUNTIME_MANIFEST_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_runtime_release(timeout: int = 8) -> dict:
    req = urllib.request.Request(RELEASE_API, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _version_tuple(value: str) -> tuple[int, ...]:
    pieces = []
    for token in str(value).strip().lower().lstrip("v").split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        pieces.append(int(digits or 0))
    return tuple(pieces)


def local_runtime_build(root: Path) -> str:
    path = root / "runtime-build.txt"
    try:
        return path.read_text(encoding="ascii").strip()
    except OSError:
        return ""


def runtime_update_needed(root: Path, current_version: str, manifest: dict, release: dict) -> bool:
    latest_version = str(manifest.get("version", "0"))
    if _version_tuple(latest_version) > _version_tuple(current_version):
        return True
    target = str(release.get("target_commitish") or "").strip()
    local_build = local_runtime_build(root)
    return bool(target and local_build and target != local_build)


def find_runtime_asset(release: dict) -> dict | None:
    for asset in release.get("assets", []):
        if asset.get("name") == RUNTIME_ASSET:
            return asset
    return None


def download_runtime_bundle(root: Path, asset: dict) -> Path:
    url = asset.get("browser_download_url")
    if not url:
        raise RuntimeError("Runtime asset has no download URL")

    staging = root / ".update-staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    destination = staging / RUNTIME_ASSET

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=90) as response, destination.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

    digest = str(asset.get("digest") or "")
    if digest.startswith("sha256:"):
        expected = digest.split(":", 1)[1].lower()
        actual = _sha256(destination).lower()
        if actual != expected:
            destination.unlink(missing_ok=True)
            raise RuntimeError("Runtime package SHA-256 verification failed")
    return destination


def create_apply_script(root: Path, bundle: Path, process_id: int) -> Path:
    """Create an ASCII PowerShell transaction that runs after the app exits.

    The bundle never contains data/ or logs/. The current runtime is backed up
    before replacement, so a failed copy can restore the previous executable
    runtime without touching the user's local knowledge database.
    """
    script = root / ".apply-smart-organizer-runtime.ps1"
    unpack = root / ".runtime-new"
    backup = root / ".runtime-backup"

    def ps_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$root = {ps_quote(str(root))}",
        f"$bundle = {ps_quote(str(bundle))}",
        f"$unpack = {ps_quote(str(unpack))}",
        f"$backup = {ps_quote(str(backup))}",
        f"$waitPid = {int(process_id)}",
        "try { Wait-Process -Id $waitPid -ErrorAction SilentlyContinue } catch {}",
        "Start-Sleep -Milliseconds 300",
        "Remove-Item -LiteralPath $unpack -Recurse -Force -ErrorAction SilentlyContinue",
        "Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue",
        "New-Item -ItemType Directory -Force -Path $unpack | Out-Null",
        "Expand-Archive -LiteralPath $bundle -DestinationPath $unpack -Force",
        "New-Item -ItemType Directory -Force -Path $backup | Out-Null",
        "$oldRuntime = Join-Path $root '_runtime'",
        "$oldExe = Join-Path $root 'SmartOrganizer.exe'",
        "if (Test-Path -LiteralPath $oldRuntime) { Move-Item -LiteralPath $oldRuntime -Destination (Join-Path $backup '_runtime') -Force }",
        "if (Test-Path -LiteralPath $oldExe) { Move-Item -LiteralPath $oldExe -Destination (Join-Path $backup 'SmartOrganizer.exe') -Force }",
        "try {",
        "  Get-ChildItem -LiteralPath $unpack -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $root -Recurse -Force }",
        "  if (-not (Test-Path -LiteralPath (Join-Path $root 'SmartOrganizer.exe'))) { throw 'SmartOrganizer.exe missing after runtime update' }",
        "  $env:PYINSTALLER_RESET_ENVIRONMENT = '1'",
        "  Remove-Item Env:_PYI_APPLICATION_HOME_DIR -ErrorAction SilentlyContinue",
        "  Start-Process -FilePath (Join-Path $root 'SmartOrganizer.exe') -WorkingDirectory $root",
        "  Start-Sleep -Seconds 2",
        "  Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue",
        "  Remove-Item -LiteralPath $unpack -Recurse -Force -ErrorAction SilentlyContinue",
        "  Remove-Item -LiteralPath $bundle -Force -ErrorAction SilentlyContinue",
        "} catch {",
        "  Remove-Item -LiteralPath (Join-Path $root '_runtime') -Recurse -Force -ErrorAction SilentlyContinue",
        "  Remove-Item -LiteralPath (Join-Path $root 'SmartOrganizer.exe') -Force -ErrorAction SilentlyContinue",
        "  if (Test-Path -LiteralPath (Join-Path $backup '_runtime')) { Move-Item -LiteralPath (Join-Path $backup '_runtime') -Destination (Join-Path $root '_runtime') -Force }",
        "  if (Test-Path -LiteralPath (Join-Path $backup 'SmartOrganizer.exe')) { Move-Item -LiteralPath (Join-Path $backup 'SmartOrganizer.exe') -Destination (Join-Path $root 'SmartOrganizer.exe') -Force }",
        "  throw",
        "}",
        "Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue",
    ]
    script.write_text("\r\n".join(lines) + "\r\n", encoding="ascii")
    return script


def launch_apply_script(script: Path) -> None:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        cwd=str(script.parent),
        creationflags=creationflags,
        close_fds=True,
    )
