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
    # A missing build marker means the installation cannot be proven to match
    # the published runtime. Treat it as stale instead of silently accepting it.
    return bool(target and target != local_build)


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

    The bundle never contains data/ or logs/. Every replaceable runtime item is
    moved into one backup before any new file is copied. If any copy or startup
    preparation step fails, the complete previous runtime is restored so an
    installation can never be left half old and half new.
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
        "$runtimeItems = @('SmartOrganizer.exe','updater.exe','_runtime','main.py','app','core','modules','config','version.json','runtime-manifest.json','runtime-build.txt')",
        "try { Wait-Process -Id $waitPid -ErrorAction SilentlyContinue } catch {}",
        "Start-Sleep -Milliseconds 300",
        "Remove-Item -LiteralPath $unpack -Recurse -Force -ErrorAction SilentlyContinue",
        "Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue",
        "New-Item -ItemType Directory -Force -Path $unpack | Out-Null",
        "Expand-Archive -LiteralPath $bundle -DestinationPath $unpack -Force",
        "if (-not (Test-Path -LiteralPath (Join-Path $unpack 'SmartOrganizer.exe'))) { throw 'SmartOrganizer.exe missing from runtime package' }",
        "if (-not (Test-Path -LiteralPath (Join-Path $unpack '_runtime'))) { throw '_runtime missing from runtime package' }",
        "if (-not (Test-Path -LiteralPath (Join-Path $unpack 'main.py'))) { throw 'main.py missing from runtime package' }",
        "New-Item -ItemType Directory -Force -Path $backup | Out-Null",
        "foreach ($name in $runtimeItems) {",
        "  $old = Join-Path $root $name",
        "  if (Test-Path -LiteralPath $old) { Move-Item -LiteralPath $old -Destination (Join-Path $backup $name) -Force }",
        "}",
        "try {",
        "  Get-ChildItem -LiteralPath $unpack -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $root -Recurse -Force }",
        "  if (-not (Test-Path -LiteralPath (Join-Path $root 'SmartOrganizer.exe'))) { throw 'SmartOrganizer.exe missing after runtime update' }",
        "  if (-not (Test-Path -LiteralPath (Join-Path $root '_runtime'))) { throw '_runtime missing after runtime update' }",
        "  if (-not (Test-Path -LiteralPath (Join-Path $root 'main.py'))) { throw 'main.py missing after runtime update' }",
        "  $env:PYINSTALLER_RESET_ENVIRONMENT = '1'",
        "  Remove-Item Env:_PYI_APPLICATION_HOME_DIR -ErrorAction SilentlyContinue",
        "  Start-Process -FilePath (Join-Path $root 'SmartOrganizer.exe') -WorkingDirectory $root",
        "  Start-Sleep -Seconds 2",
        "  Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue",
        "  Remove-Item -LiteralPath $unpack -Recurse -Force -ErrorAction SilentlyContinue",
        "  Remove-Item -LiteralPath $bundle -Force -ErrorAction SilentlyContinue",
        "} catch {",
        "  foreach ($name in $runtimeItems) {",
        "    $current = Join-Path $root $name",
        "    if (Test-Path -LiteralPath $current) { Remove-Item -LiteralPath $current -Recurse -Force -ErrorAction SilentlyContinue }",
        "  }",
        "  foreach ($name in $runtimeItems) {",
        "    $saved = Join-Path $backup $name",
        "    if (Test-Path -LiteralPath $saved) { Move-Item -LiteralPath $saved -Destination (Join-Path $root $name) -Force }",
        "  }",
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
